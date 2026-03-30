/**
 * TT Tracker — Alpine.js global store + WebSocket client + Modal + CountUp
 */

// ── CountUp utility ───────────────────────────────────────────────────────────
function countUp(el, target, duration = 1200) {
  const start = Date.now();
  const startVal = 0;
  const step = () => {
    const elapsed = Date.now() - start;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(startVal + (target - startVal) * eased);
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// Run countUp on elements with data-countup attribute when they enter viewport
document.addEventListener('DOMContentLoaded', () => {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting && !e.target.dataset.counted) {
        e.target.dataset.counted = '1';
        const target = parseInt(e.target.dataset.countup, 10);
        countUp(e.target, target);
      }
    });
  }, { threshold: 0.3 });

  document.querySelectorAll('[data-countup]').forEach(el => observer.observe(el));
});

// ── Modal system ─────────────────────────────────────────────────────────────
const Modal = (() => {
  let _resolve = null;

  function _create(title, body, actions) {
    // Remove existing
    document.getElementById('tt-modal')?.remove();

    const overlay = document.createElement('div');
    overlay.id = 'tt-modal';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <button class="modal-close" aria-label="Fermer" onclick="Modal.close(false)">✕</button>
        <div class="modal-title" id="modal-title">${title}</div>
        <div class="modal-body">${body}</div>
        <div class="modal-actions">${actions}</div>
      </div>`;

    overlay.addEventListener('click', e => { if (e.target === overlay) Modal.close(false); });
    document.addEventListener('keydown', _onKey);
    document.body.appendChild(overlay);
    // Focus first button
    setTimeout(() => overlay.querySelector('button:not(.modal-close)')?.focus(), 50);
  }

  function _onKey(e) {
    if (e.key === 'Escape') Modal.close(false);
  }

  function close(value) {
    document.getElementById('tt-modal')?.remove();
    document.removeEventListener('keydown', _onKey);
    if (_resolve) { _resolve(value); _resolve = null; }
  }

  function alert(title, body = '', btnText = 'OK') {
    return new Promise(resolve => {
      _resolve = resolve;
      _create(title, body,
        `<button class="btn btn-primary" onclick="Modal.close(true)">${btnText}</button>`);
    });
  }

  function confirm(title, body = '', okText = 'Confirmer', cancelText = 'Annuler') {
    return new Promise(resolve => {
      _resolve = resolve;
      _create(title, body, `
        <button class="btn btn-ghost" onclick="Modal.close(false)">${cancelText}</button>
        <button class="btn btn-danger" onclick="Modal.close(true)">${okText}</button>`);
    });
  }

  function success(title, body = '') {
    return alert(`✅ ${title}`, body, 'Fermer');
  }

  function error(title, body = '') {
    return alert(`❌ ${title}`, body, 'Fermer');
  }

  return { close, alert, confirm, success, error };
})();

// ── WebSocket client ──────────────────────────────────────────────────────────
class TennisWS {
  constructor(token) {
    this.token = token || '';
    this.ws = null;
    this.reconnectDelay = 1500;
    this.maxDelay = 30000;
    this.handlers = [];
    this.connected = false;
    this._connect();
  }

  _connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/live?token=${encodeURIComponent(this.token)}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.connected = true;
      this.reconnectDelay = 1500;
      Alpine.store('tennis').bleConnected = true;
    };

    this.ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        this.handlers.forEach(fn => fn(msg));
      } catch(e) {}
    };

    this.ws.onclose = () => {
      this.connected = false;
      Alpine.store('tennis').bleConnected = false;
      setTimeout(() => this._connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    };

    this.ws.onerror = () => { this.ws.close(); };
  }

  on(fn) { this.handlers.push(fn); }

  joinSession(sessionId) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'join_session', session_id: sessionId }));
    }
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

// ── Web Bluetooth ─────────────────────────────────────────────────────────────
const WebBLE = (() => {
  const SERVICE_UUID = '19b10000-e8f2-537e-4f6c-d104768a1214';
  const CHAR_UUID    = '19b10001-e8f2-537e-4f6c-d104768a1214';
  const STROKE_NAMES = ['BH Drive','BH Smash','FH Drive','FH Loop','FH Smash'];
  const STORAGE_KEY  = 'tt_ble_device_name';

  let _device = null, _char = null, _onStroke = null, _onDisconnect = null;

  async function _attachDevice(device, onStroke, onDisconnect) {
    _onStroke = onStroke;
    _onDisconnect = onDisconnect;
    _device = device;

    _device.addEventListener('gattserverdisconnected', () => {
      _char = null;
      if (_onDisconnect) _onDisconnect();
    });

    const server  = await _device.gatt.connect();
    const service = await server.getPrimaryService(SERVICE_UUID);
    _char         = await service.getCharacteristic(CHAR_UUID);

    await _char.startNotifications();
    _char.addEventListener('characteristicvaluechanged', (evt) => {
      const byte = evt.target.value.getUint8(0);
      if (byte < 5 && _onStroke) {
        _onStroke(byte, STROKE_NAMES[byte]);
      }
    });

    sessionStorage.setItem(STORAGE_KEY, _device.name || 'TableTennisBat');
    return _device.name || 'TableTennisBat';
  }

  async function connect(onStroke, onDisconnect) {
    if (!navigator.bluetooth) {
      throw new Error('Web Bluetooth non supporté — utilisez Chrome ou Edge sur PC/Android.');
    }

    _device = await navigator.bluetooth.requestDevice({
      filters: [
        { namePrefix: 'TableTennisBat' },
        { services: [SERVICE_UUID] }
      ],
      optionalServices: [SERVICE_UUID],
    });

    return _attachDevice(_device, onStroke, onDisconnect);
  }

  // Reconnexion automatique sans popup (après navigation de page)
  async function autoReconnect(onStroke, onDisconnect) {
    if (!navigator.bluetooth?.getDevices) return false;
    const savedName = sessionStorage.getItem(STORAGE_KEY);
    if (!savedName) return false;
    try {
      const devices = await navigator.bluetooth.getDevices();
      const device  = devices.find(d => d.name && d.name.startsWith('TableTennisBat'));
      if (!device) return false;
      await _attachDevice(device, onStroke, onDisconnect);
      return device.name || 'TableTennisBat';
    } catch(e) {
      return false;
    }
  }

  async function disconnect() {
    sessionStorage.removeItem(STORAGE_KEY);
    if (_char) {
      try { await _char.stopNotifications(); } catch(e) {}
      _char = null;
    }
    if (_device?.gatt?.connected) {
      _device.gatt.disconnect();
    }
    _device = null;
  }

  function isSupported() { return !!navigator.bluetooth; }

  function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  }

  return { connect, autoReconnect, disconnect, isSupported, isIOS };
})();


// ── Alpine store ──────────────────────────────────────────────────────────────
document.addEventListener('alpine:init', () => {
  Alpine.store('tennis', {
    bleConnected: false,
    webBleConnected: false,
    webBleDevice: null,
    currentSessionId: null,
    devices: {},
    session: null,
    score: { p1: 0, p2: 0, p1_sets: 0, p2_sets: 0, sets: [] },
    liveStrokes: { bh_drive: 0, bh_smash: 0, fh_drive: 0, fh_loop: 0, fh_smash: 0, total: 0 },
    _strokeTimes: [],
    strokesPerMin: 0,
    _timerStart: null,
    _timerInterval: null,
    elapsedSeconds: 0,
    notifications: [],

    initWS(token) {
      window._ws = new TennisWS(token);
      window._ws.on((msg) => this._handleMessage(msg));
      // Reconnexion BLE automatique si raquette déjà appairée
      this._tryAutoReconnect();
    },

    async _tryAutoReconnect() {
      const deviceName = await WebBLE.autoReconnect(
        (strokeId, strokeName) => {
          if (window._ws) {
            window._ws.send({
              type: 'ble_stroke',
              stroke_id: strokeId,
              session_id: this.currentSessionId,
              device: deviceName,
            });
          }
        },
        () => {
          this.webBleConnected = false;
          this.webBleDevice = null;
        }
      );
      if (deviceName) {
        this.webBleConnected = true;
        this.webBleDevice = deviceName;
      }
    },

    // ── Web Bluetooth ──────────────────────────────────────────────────────
    async connectBLE(sessionId = null) {
      if (!WebBLE.isSupported()) {
        if (WebBLE.isIOS()) {
          this._notify('❌ iOS/Safari ne supporte pas Web Bluetooth. Ouvrez cette page dans Chrome sur PC ou Android.', 'error');
        } else {
          this._notify('❌ Web Bluetooth non supporté. Utilisez Chrome ou Edge (pas Firefox, pas Safari).', 'error');
        }
        return;
      }
      // Allow caller to set a session upfront (training/match pages)
      if (sessionId) this.currentSessionId = sessionId;
      try {
        this._notify('🔵 Recherche de la raquette…', 'info');
        const deviceName = await WebBLE.connect(
          (strokeId, strokeName) => {
            // Forward stroke to server via WebSocket — use live currentSessionId
            if (window._ws) {
              window._ws.send({
                type: 'ble_stroke',
                stroke_id: strokeId,
                session_id: this.currentSessionId,
                device: deviceName,
              });
            }
            this._notify(`🏓 ${strokeName}`, 'info');
          },
          () => {
            this.webBleConnected = false;
            this.webBleDevice = null;
            this._notify('🔴 Raquette déconnectée', 'error');
          }
        );
        this.webBleConnected = true;
        this.webBleDevice = deviceName;
        this._notify(`✅ ${deviceName} connectée !`, 'success');
      } catch(e) {
        if (e.name !== 'NotFoundError') {  // user cancelled — don't show error
          this._notify(`❌ ${e.message}`, 'error');
        }
      }
    },

    async disconnectBLE() {
      await WebBLE.disconnect();
      this.webBleConnected = false;
      this.webBleDevice = null;
      this._notify('Raquette déconnectée', 'info');
    },

    _handleMessage(msg) {
      if (msg.type === 'stroke') {
        const d = msg.data;
        this.devices[d.device || 'unknown'] = d;

        if (d.total !== undefined) {
          // MQTT / full payload — mise à jour complète
          Object.assign(this.liveStrokes, {
            bh_drive: d.bh_drive, bh_smash: d.bh_smash,
            fh_drive: d.fh_drive, fh_loop: d.fh_loop,
            fh_smash: d.fh_smash, total: d.total,
          });
        } else {
          // Web Bluetooth (1 coup à la fois) — incrémenter le bon compteur
          const key = d.last_stroke?.key;
          if (key && key in this.liveStrokes) {
            this.liveStrokes[key]++;
          }
          this.liveStrokes.total++;
        }

        window.dispatchEvent(new CustomEvent('tt-stroke'));

        const now = Date.now();
        this._strokeTimes.push(now);
        this._strokeTimes = this._strokeTimes.filter(t => now - t < 60000);
        this.strokesPerMin = this._strokeTimes.length;

        if (d.last_stroke?.name) this._notify(`🏓 ${d.last_stroke.name}`, 'info');
      }
      if (msg.type === 'status') {
        this.bleConnected = msg.data.status === 'online';
      }
    },

    startTimer() {
      this._timerStart = Date.now();
      this._timerInterval = setInterval(() => {
        this.elapsedSeconds = Math.floor((Date.now() - this._timerStart) / 1000);
      }, 1000);
    },

    stopTimer() {
      if (this._timerInterval) { clearInterval(this._timerInterval); this._timerInterval = null; }
    },

    formatTime(s) {
      return `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`;
    },

    resetLive() {
      this.liveStrokes = { bh_drive:0, bh_smash:0, fh_drive:0, fh_loop:0, fh_smash:0, total:0 };
      this._strokeTimes = [];
      this.strokesPerMin = 0;
      this.elapsedSeconds = 0;
    },

    _notify(text, type = 'info') {
      const id = Date.now() + Math.random();
      this.notifications.push({ id, text, type });
      setTimeout(() => {
        this.notifications = this.notifications.filter(n => n.id !== id);
      }, 3500);
    },

    notify(text, type = 'info') { this._notify(text, type); },

    async apiPost(url, body) {
      const r = await fetch('/api' + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || 'Erreur serveur');
      }
      return r.json();
    },

    async apiGet(url) {
      const r = await fetch('/api' + url);
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    },
  });
});
