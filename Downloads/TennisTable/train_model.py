"""
Entraînement du classifieur de coups de tennis de table.
- Charge les 600 fenêtres CSV (25 samples × 20ms = 500ms)
- Extrait 16 features par fenêtre
- Entraîne un Random Forest
- Exporte le modèle en C (model.h) pour Arduino Nano 33 BLE
"""
import os
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

# ── Config ────────────────────────────────────────────────────────────────────
DATASET_DIR = Path(r"C:\Users\HP\synthetic_table_tennis_dataset")
OUTPUT_H    = Path(r"C:\Users\HP\Downloads\TennisTable\TableTennisBat\model.h")

CLASSES = {
    "BHdrive": 0,
    "BHsmash": 1,
    "FHdrive": 2,
    "FHloop":  3,
    "FHsmash": 4,
    "zzz":     5,   # repos / pas de coup
}

# ── Chargement ────────────────────────────────────────────────────────────────
def load_dataset(dataset_dir):
    X, y = [], []
    for cls_name, cls_id in CLASSES.items():
        files = sorted(dataset_dir.glob(f"{cls_name}*.csv"))
        for f in files:
            df = pd.read_csv(f)
            # Colonnes attendues: Timestamp,accX,accY,accZ,gyrX,gyrY,gyrZ
            if df.shape[0] < 10:
                continue
            gx = df["gyrX"].values.astype(float)
            gy = df["gyrY"].values.astype(float)
            gz = df["gyrZ"].values.astype(float)
            ax = df["accX"].values.astype(float)
            ay = df["accY"].values.astype(float)
            az = df["accZ"].values.astype(float)

            features = extract_features(gx, gy, gz, ax, ay, az)
            X.append(features)
            y.append(cls_id)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ── Extraction de features (16 valeurs) ──────────────────────────────────────
FEATURE_NAMES = [
    "peak_gyro_mag",    # magnitude max du gyroscope
    "peak_gx",          # gx au moment du pic
    "peak_gy",          # gy au moment du pic
    "peak_gz",          # gz au moment du pic
    "mean_gx",          # moyenne gx sur la fenêtre
    "mean_gy",          # moyenne gy
    "mean_gz",          # moyenne gz
    "rms_gyro",         # RMS de la magnitude gyro
    "peak_accel_mag",   # magnitude max accéléromètre
    "peak_ax",          # ax au moment du pic accél
    "peak_ay",
    "peak_az",
    "energy_gyro",      # énergie gyro (somme mag²)
    "peak_timing",      # position normalisée du pic (0=début, 1=fin)
    "ratio_gx_gy",      # rapport gx/gy au pic (discrimine les axes)
    "sign_gz_at_peak",  # signe de gz au pic (FH vs BH)
]

def extract_features(gx, gy, gz, ax, ay, az):
    gyro_mag  = np.sqrt(gx**2 + gy**2 + gz**2)
    accel_mag = np.sqrt(ax**2 + ay**2 + az**2)

    peak_idx  = int(np.argmax(gyro_mag))
    peak_gm   = float(gyro_mag[peak_idx])

    rms_gyro     = float(np.sqrt(np.mean(gyro_mag**2)))
    energy_gyro  = float(np.sum(gyro_mag**2))
    peak_timing  = peak_idx / max(len(gx) - 1, 1)

    peak_gx_ = float(gx[peak_idx])
    peak_gy_ = float(gy[peak_idx])
    peak_gz_ = float(gz[peak_idx])
    denom_gy = peak_gy_ if abs(peak_gy_) > 1e-3 else 1e-3
    ratio_gx_gy = float(np.clip(peak_gx_ / denom_gy, -50, 50))

    accel_peak_idx = int(np.argmax(accel_mag))
    peak_am  = float(accel_mag[accel_peak_idx])
    peak_ax_ = float(ax[accel_peak_idx])
    peak_ay_ = float(ay[accel_peak_idx])
    peak_az_ = float(az[accel_peak_idx])

    return [
        peak_gm,
        peak_gx_,
        peak_gy_,
        peak_gz_,
        float(np.mean(gx)),
        float(np.mean(gy)),
        float(np.mean(gz)),
        rms_gyro,
        peak_am,
        peak_ax_,
        peak_ay_,
        peak_az_,
        energy_gyro,
        peak_timing,
        ratio_gx_gy,
        1.0 if peak_gz_ >= 0 else -1.0,
    ]


# ── Export C ──────────────────────────────────────────────────────────────────
def export_tree_to_c(tree, feature_names, class_names, indent=2):
    """Convertit un DecisionTreeClassifier en code C récursif."""
    t = tree.tree_
    sp = " " * indent

    def recurse(node, depth):
        pad = sp * depth
        if t.feature[node] == -2:  # feuille
            cls = int(np.argmax(t.value[node]))
            return f"{pad}return {cls};  // {class_names[cls]}\n"
        feat = feature_names[t.feature[node]]
        thresh = t.threshold[node]
        code  = f"{pad}if (f[{t.feature[node]}] <= {thresh:.6f}f) {{  // {feat}\n"
        code += recurse(t.children_left[node],  depth + 1)
        code += f"{pad}}} else {{\n"
        code += recurse(t.children_right[node], depth + 1)
        code += f"{pad}}}\n"
        return code

    return recurse(0, 0)


def export_model_header(forest, feature_names, class_names, output_path):
    """Exporte le Random Forest comme ensemble de Decision Trees en C."""
    lines = []
    lines.append("// ============================================================")
    lines.append("// model.h — Classifieur de coups TT (généré automatiquement)")
    lines.append("// RandomForest → vote majoritaire entre N arbres")
    lines.append("// Classes : BHdrive=0  BHsmash=1  FHdrive=2  FHloop=3")
    lines.append("//           FHsmash=4  zzz=5 (repos)")
    lines.append("// ============================================================")
    lines.append("#pragma once")
    lines.append(f"#define N_FEATURES {len(feature_names)}")
    lines.append(f"#define N_CLASSES  {len(class_names)}")
    lines.append(f"#define N_TREES    {len(forest.estimators_)}")
    lines.append("")

    # Exporte chaque arbre comme une fonction C
    for i, tree in enumerate(forest.estimators_):
        lines.append(f"static int tree_{i}(const float* f) {{")
        lines.append(export_tree_to_c(tree, feature_names, class_names).rstrip())
        lines.append("}")
        lines.append("")

    # Fonction de vote majoritaire
    lines.append("static int predict_stroke(const float* f) {")
    lines.append(f"  int votes[{len(class_names)}] = {{0}};")
    for i in range(len(forest.estimators_)):
        lines.append(f"  votes[tree_{i}(f)]++;")
    lines.append("  int best = 0;")
    lines.append(f"  for (int i = 1; i < {len(class_names)}; i++)")
    lines.append("    if (votes[i] > votes[best]) best = i;")
    lines.append("  return best;")
    lines.append("}")
    lines.append("")
    lines.append("// Noms des classes pour le debug série")
    names_str = ", ".join(f'"{n}"' for n in class_names)
    lines.append(f'static const char* CLASS_NAMES[{len(class_names)}] = {{{names_str}}};')

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[✓] model.h exporté → {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Chargement du dataset ===")
    X, y = load_dataset(DATASET_DIR)
    print(f"Samples : {X.shape[0]}  |  Features : {X.shape[1]}")
    for cls_name, cls_id in CLASSES.items():
        print(f"  {cls_name}: {(y == cls_id).sum()} samples")

    # Validation croisée 5-fold
    print("\n=== Validation croisée (5-fold) ===")
    clf = RandomForestClassifier(
        n_estimators=15,    # 15 arbres → bon compromis taille/précision
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    cv_scores = cross_val_score(clf, X, y, cv=StratifiedKFold(5), scoring="accuracy")
    print(f"Accuracy CV : {cv_scores.mean()*100:.1f}% ± {cv_scores.std()*100:.1f}%")

    # Entraînement final sur tout le dataset
    print("\n=== Entraînement final ===")
    clf.fit(X, y)
    y_pred = clf.predict(X)
    print(f"Accuracy train : {(y_pred == y).mean()*100:.1f}%")
    print("\nRapport par classe :")
    class_names = list(CLASSES.keys())
    print(classification_report(y, y_pred, target_names=class_names))
    print("Matrice de confusion :")
    print(confusion_matrix(y, y_pred))

    # Export C
    print("\n=== Export model.h ===")
    OUTPUT_H.parent.mkdir(parents=True, exist_ok=True)
    export_model_header(clf, FEATURE_NAMES, class_names, OUTPUT_H)
    print("Terminé !")
