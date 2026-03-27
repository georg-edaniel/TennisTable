"""
TableTennis System v3.3 — Interface PyQt6
Lance asyncio dans un QThread séparé ; communique avec le thread Qt
via des signaux PyQt6 (connexion automatique QueuedConnection).
"""

from __future__ import annotations

import asyncio
import html
import importlib.util
import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import (
    QObject, QThread, Qt, QTimer, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QProgressBar, QPushButton, QSizePolicy,
    QSplitter, QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

# ======================================================
# DataBridge — pont thread-safe entre asyncio et Qt
# ======================================================

class DataBridge(QObject):
    """
    Signaux émis depuis le thread asyncio, consommés dans le thread Qt.
    Qt gère automatiquement le passage inter-thread (QueuedConnection).
    """
    stats_updated  = pyqtSignal(dict)    # payload complet device
    status_updated = pyqtSignal(str, bool)  # (device_name, online)
    mqtt_connected = pyqtSignal(bool)
    log_event      = pyqtSignal(str, str)   # (level, message)
    reset_done     = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._reset_fn = None

    def set_loop(self, loop: asyncio.AbstractEventLoop, reset_fn) -> None:
        """Appelé depuis le thread asyncio juste avant le démarrage."""
        self._loop = loop
        self._reset_fn = reset_fn

    def trigger_reset(self) -> None:
        """Appelé depuis le thread Qt (bouton Reset)."""
        if self._loop and self._reset_fn:
            self._loop.call_soon_threadsafe(self._reset_fn)


# ======================================================
# QtLogHandler — redirige logging vers le signal log_event
# ======================================================

class QtLogHandler:
    """Handler logging.Handler-compatible qui émet vers DataBridge."""

    def __init__(self, bridge: DataBridge) -> None:
        self._bridge = bridge

    def emit_record(self, level: str, message: str) -> None:
        self._bridge.log_event.emit(level, message)


# ======================================================
# AsyncioWorker — asyncio dans un QThread
# ======================================================

class AsyncioWorker(QThread):
    """
    Exécute TableTennisSystem dans une boucle asyncio dédiée.
    Expose DataBridge pour que MainWindow puisse y connecter ses slots.
    """

    def __init__(self, bridge: DataBridge, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self) -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_system())
        finally:
            self._loop.close()

    async def _run_system(self) -> None:
        # Import ici pour éviter une dépendance circulaire au module level
        from Connexion_Ble_MQTT import (
            ConfigLoader, LoggerFactory, EnvironmentChecker, TableTennisSystem,
        )
        cfg = ConfigLoader().load_safe()
        LoggerFactory.setup(cfg["logging"])
        # Rediriger les logs vers le bridge
        self._setup_log_redirect()
        EnvironmentChecker(cfg["mqtt"]).run()
        system = TableTennisSystem(bridge=self._bridge)
        await system.run()

    def _setup_log_redirect(self) -> None:
        """Accroche un handler Python logging qui émet vers DataBridge."""
        import logging

        bridge = self._bridge

        class _BridgeHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    msg = self.format(record)
                    bridge.log_event.emit(record.levelname, msg)
                except Exception:
                    pass

        root = logging.getLogger("tabletennis")
        h = _BridgeHandler()
        h.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s",
                                         datefmt="%H:%M:%S"))
        root.addHandler(h)

    def request_stop(self) -> None:
        """Demande l'arrêt propre de la boucle asyncio."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)


# ======================================================
# StrokeBar — une ligne coup + barre de progression
# ======================================================

STROKE_LABELS = {
    "bh_drive": "BH Drive",
    "bh_smash": "BH Smash",
    "fh_drive": "FH Drive",
    "fh_loop":  "FH Loop",
    "fh_smash": "FH Smash",
}

class StrokeBar(QWidget):
    """Affiche le nom d'un type de coup, sa valeur et une barre de progression."""

    def __init__(self, key: str, color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._key = key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        label = QLabel(STROKE_LABELS.get(key, key))
        label.setFixedWidth(70)
        label.setStyleSheet("font-size: 11px;")
        layout.addWidget(label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 1)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(14)
        self._bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid #555; border-radius: 3px; background: #2a2a2a; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}"
        )
        layout.addWidget(self._bar, stretch=1)

        self._count = QLabel("0")
        self._count.setFixedWidth(36)
        self._count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._count.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout.addWidget(self._count)

    def update_value(self, value: int, maximum: int) -> None:
        self._bar.setMaximum(max(1, maximum))
        self._bar.setValue(value)
        self._count.setText(str(value))


# ======================================================
# PlayerPanel — panneau complet d'un joueur
# ======================================================

_PLAYER_COLORS = ["#4dabf7", "#f03e3e"]  # bleu / rouge

class PlayerPanel(QGroupBox):
    """Panneau stats pour un joueur (device BLE)."""

    def __init__(self, device_name: str, player_name: str,
                 color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._device_name = device_name
        self._color = color

        self.setTitle(f"  {player_name}  ")
        self.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; font-size: 13px; color: {color};"
            f"  border: 2px solid {color}; border-radius: 6px; margin-top: 8px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Status BLE
        status_row = QHBoxLayout()
        self._ble_dot = QLabel("●")
        self._ble_dot.setStyleSheet("color: #888; font-size: 16px;")
        self._ble_label = QLabel("Déconnecté")
        self._ble_label.setStyleSheet("color: #888; font-size: 11px;")
        status_row.addWidget(self._ble_dot)
        status_row.addWidget(self._ble_label)
        status_row.addStretch()
        self._device_label = QLabel(device_name)
        self._device_label.setStyleSheet("color: #666; font-size: 10px;")
        status_row.addWidget(self._device_label)
        layout.addLayout(status_row)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        # Total
        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total"))
        self._total_label = QLabel("0")
        self._total_label.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {color};"
        )
        self._total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_row.addWidget(self._total_label, stretch=1)
        layout.addLayout(total_row)

        # Barres de coups
        self._bars: dict[str, StrokeBar] = {}
        for key in STROKE_LABELS:
            bar = StrokeBar(key, color)
            self._bars[key] = bar
            layout.addWidget(bar)

        # Dernier coup
        self._last_stroke = QLabel("Dernier coup : —")
        self._last_stroke.setStyleSheet("color: #aaa; font-size: 10px; font-style: italic;")
        layout.addWidget(self._last_stroke)

        layout.addStretch()

    @pyqtSlot(dict)
    def on_stats_updated(self, payload: dict) -> None:
        if payload.get("device") != self._device_name:
            return
        total = payload.get("total", 0)
        self._total_label.setText(str(total))
        for key in STROKE_LABELS:
            val = payload.get(key, 0)
            self._bars[key].update_value(val, max(1, total))
        ls = payload.get("last_stroke")
        if ls:
            name = ls.get("name", "?")
            t = ls.get("time", "")
            self._last_stroke.setText(f"Dernier coup : {name}  {t}")

    @pyqtSlot(str, bool)
    def on_status_updated(self, device_name: str, online: bool) -> None:
        if device_name != self._device_name:
            return
        if online:
            self._ble_dot.setStyleSheet(f"color: #51cf66; font-size: 16px;")
            self._ble_label.setText("Connecté")
            self._ble_label.setStyleSheet("color: #51cf66; font-size: 11px;")
        else:
            self._ble_dot.setStyleSheet("color: #888; font-size: 16px;")
            self._ble_label.setText("Déconnecté")
            self._ble_label.setStyleSheet("color: #888; font-size: 11px;")

    @pyqtSlot()
    def on_reset(self) -> None:
        self._total_label.setText("0")
        for bar in self._bars.values():
            bar.update_value(0, 1)
        self._last_stroke.setText("Dernier coup : —")


# ======================================================
# MainWindow
# ======================================================

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", sans-serif;
}
QGroupBox { background-color: #252526; }
QTextEdit {
    background-color: #1a1a1a;
    color: #c0c0c0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 10px;
    border: 1px solid #3a3a3a;
}
QPushButton {
    background-color: #3a3a3a;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton:hover { background-color: #505050; }
QPushButton:pressed { background-color: #2a2a2a; }
QPushButton#reset_btn {
    background-color: #c0392b;
    color: white;
    border-color: #e74c3c;
    font-weight: bold;
}
QPushButton#reset_btn:hover { background-color: #e74c3c; }
QStatusBar { background-color: #007acc; color: white; font-size: 11px; }
QLabel#mqtt_status { font-size: 11px; padding: 2px 8px; }
QSplitter::handle { background-color: #3a3a3a; }
"""

_LOG_COLORS = {
    "DEBUG":    "#808080",
    "INFO":     "#c0c0c0",
    "WARNING":  "#f0a500",
    "ERROR":    "#f04040",
    "CRITICAL": "#ff4040",
}
_MAX_LOG_LINES = 400


class MainWindow(QMainWindow):
    def __init__(self, bridge: DataBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self.setWindowTitle("TableTennis System v3.3")
        self.resize(920, 660)
        self.setStyleSheet(DARK_STYLESHEET)
        self._log_line_count = 0

        # ---- widget central ----
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ---- barre supérieure : MQTT + Reset ----
        top_bar = QHBoxLayout()
        self._mqtt_dot = QLabel("●")
        self._mqtt_dot.setStyleSheet("color: #888; font-size: 18px;")
        top_bar.addWidget(self._mqtt_dot)
        self._mqtt_lbl = QLabel("MQTT hors ligne")
        self._mqtt_lbl.setObjectName("mqtt_status")
        top_bar.addWidget(self._mqtt_lbl)
        top_bar.addStretch()
        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet("color: #888; font-size: 11px;")
        top_bar.addWidget(self._clock_lbl)
        reset_btn = QPushButton("Réinitialiser les stats")
        reset_btn.setObjectName("reset_btn")
        reset_btn.clicked.connect(self._on_reset_clicked)
        top_bar.addWidget(reset_btn)
        root.addLayout(top_bar)

        # ---- splitter vertical : joueurs | logs ----
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, stretch=1)

        # Panneau joueurs (horizontal)
        players_widget = QWidget()
        players_layout = QHBoxLayout(players_widget)
        players_layout.setSpacing(12)
        players_layout.setContentsMargins(0, 0, 0, 0)
        self._panels: dict[str, PlayerPanel] = {}
        splitter.addWidget(players_widget)

        # Panneau logs
        log_frame = QGroupBox("Journal")
        log_frame.setStyleSheet(
            "QGroupBox { font-size: 11px; color: #888; border: 1px solid #3a3a3a;"
            "  margin-top: 6px; } QGroupBox::title { left: 8px; }"
        )
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(4, 10, 4, 4)
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.document().setMaximumBlockCount(_MAX_LOG_LINES)
        log_layout.addWidget(self._log_view)
        splitter.addWidget(log_frame)
        splitter.setSizes([440, 180])

        # ---- status bar ----
        self.statusBar().showMessage("Démarrage en cours…")

        # ---- connect signals ----
        bridge.mqtt_connected.connect(self._on_mqtt_connected)
        bridge.log_event.connect(self._append_log)
        bridge.reset_done.connect(self._on_reset_done)

        # ---- horloge 1s ----
        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(1000)
        self._tick_clock()

        # Les panels sont créés dynamiquement quand les devices arrivent
        # (on lit la config pour les créer dès le départ)
        self._players_layout = players_layout
        self._init_panels()

    def _init_panels(self) -> None:
        """Crée les panels joueurs en lisant la config du système."""
        try:
            # Import léger — juste ConfigLoader
            from Connexion_Ble_MQTT import ConfigLoader
            cfg = ConfigLoader().load_safe()
            devices = cfg.get("devices", [])
        except Exception:
            devices = [
                {"device_name": "TableTennisBat1", "player_name": "Joueur 1"},
                {"device_name": "TableTennisBat2", "player_name": "Joueur 2"},
            ]
        for i, d in enumerate(devices):
            color = _PLAYER_COLORS[i % len(_PLAYER_COLORS)]
            panel = PlayerPanel(d["device_name"], d.get("player_name", d["device_name"]), color)
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._panels[d["device_name"]] = panel
            self._players_layout.addWidget(panel)

            # Connecter les signaux bridge → panel
            self._bridge.stats_updated.connect(panel.on_stats_updated)
            self._bridge.status_updated.connect(panel.on_status_updated)
            self._bridge.reset_done.connect(panel.on_reset)

    # ---- slots ----

    @pyqtSlot(bool)
    def _on_mqtt_connected(self, connected: bool) -> None:
        if connected:
            self._mqtt_dot.setStyleSheet("color: #51cf66; font-size: 18px;")
            self._mqtt_lbl.setText("MQTT connecté")
            self._mqtt_lbl.setStyleSheet("color: #51cf66; font-size: 11px; padding: 2px 8px;")
            self.statusBar().showMessage("MQTT connecté")
        else:
            self._mqtt_dot.setStyleSheet("color: #f04040; font-size: 18px;")
            self._mqtt_lbl.setText("MQTT hors ligne — reconnexion…")
            self._mqtt_lbl.setStyleSheet("color: #f04040; font-size: 11px; padding: 2px 8px;")
            self.statusBar().showMessage("MQTT hors ligne — reconnexion automatique…")

    @pyqtSlot(str, str)
    def _append_log(self, level: str, message: str) -> None:
        color = _LOG_COLORS.get(level, "#c0c0c0")
        safe_msg = html.escape(message).replace("\n", "<br>")
        self._log_view.append(
            f'<span style="color:{color};">{safe_msg}</span>'
        )
        # Auto-scroll vers le bas
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)

    @pyqtSlot()
    def _on_reset_done(self) -> None:
        self._append_log("INFO", "─── Stats réinitialisées ───")

    def _on_reset_clicked(self) -> None:
        self._bridge.trigger_reset()

    def _tick_clock(self) -> None:
        self._clock_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def closeEvent(self, event) -> None:
        """Arrêt propre : on demande à l'asyncio worker de s'arrêter."""
        self._bridge.trigger_reset()   # juste pour nettoyer si en cours
        # Note : le worker sera stoppé par run_gui() après exec()
        event.accept()


# ======================================================
# run_gui() — point d'entrée
# ======================================================

def run_gui() -> None:
    """Lance l'application PyQt6 avec asyncio en arrière-plan."""
    app = QApplication(sys.argv)
    app.setApplicationName("TableTennis System")
    app.setStyle("Fusion")

    bridge = DataBridge()
    worker = AsyncioWorker(bridge)
    window = MainWindow(bridge)

    worker.start()
    window.show()

    exit_code = app.exec()

    # Arrêt propre de asyncio
    worker.request_stop()
    worker.wait(5000)

    sys.exit(exit_code)


if __name__ == "__main__":
    run_gui()
