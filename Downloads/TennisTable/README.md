# 🏓 TableTennis Dashboard V2

Système de suivi en temps réel pour match de tennis de table, utilisant des raquettes connectées (Arduino Nano 33 BLE Rev 2), un bridge Python BLE→MQTT, et un dashboard Node-RED.

---

## Architecture

```
[Raquette BLE]──BLE──▶[Python Bridge]──MQTT──▶[Node-RED]──▶[Dashboard UI]
   Arduino Nano 33                                              Node-RED UI
   BMI270 + BLE                                             InfluxDB (historique)
```

---

## Matériel requis

| Composant | Quantité |
|---|---|
| Arduino Nano 33 BLE Rev 2 | 2 |
| PC avec Bluetooth | 1 |
| Broker MQTT (Mosquitto) | sur 127.0.0.1:1883 |
| Node-RED | sur réseau local |
| InfluxDB v2 | sur 172.18.191.73:8086 |

---

## Installation

### 1. Dépendances Python

```bash
pip install bleak paho-mqtt
```

### 2. Arduino

Ouvrir `TableTennisBat/TableTennisBat.ino` dans l'IDE Arduino.

- Pour la raquette 1 : `#define PLAYER_ID 1` et `#define DEVICE_NAME "TableTennisBat1"`
- Pour la raquette 2 : `#define PLAYER_ID 2` et `#define DEVICE_NAME "TableTennisBat2"`

Bibliothèques requises (Arduino Library Manager) :
- `ArduinoBLE`
- `Arduino_BMI270_BMM150`

### 3. Trouver les raquettes BLE

Si les raquettes n'ont pas de nom visible dans le scan :

```bash
python scan_ble.py         # liste tous les devices BLE
python identify_ble.py     # identifie les raquettes parmi les sans-nom
```

### 4. Démarrer le bridge Python

```bash
python Connexion_Ble_MQTT.py
```

Le script se connecte aux deux raquettes via BLE et publie les coups sur le topic MQTT `tabletennis/data`.

### 5. Déployer le flow Node-RED

```bash
python gen_flow.py         # génère flow_v2.json (intègre le dashboard HTML)
```

Puis importer dans Node-RED via **Menu → Import → Presse-papiers** (coller le contenu de `flow_v2.json`).

Ou déploiement automatique (adapter l'IP) :
```bash
curl -X POST http://192.168.10.126:1880/flows \
  -H "Content-Type: application/json" \
  -H "Node-RED-Deployment-Type: flows" \
  -d @flow_v2.json
```

---

## Fonctionnalités du dashboard

| Fonctionnalité | Description |
|---|---|
| Stats par joueur | BH Drive, BH Smash, FH Drive, FH Loop, FH Smash + total |
| Radar chart | Visualisation graphique des 5 types de coups |
| Score match | Points et sets en temps réel |
| Format configurable | BO3 (first to 2) ou BO5 (first to 3) |
| Timer | Chronomètre du match |
| Undo point | Annulation du dernier point (jusqu'à 15 niveaux) |
| Noms pré-enregistrés | Dropdown avec ajout/suppression persistants |
| Indicateur connexion | Vert < 30s · Orange < 2min · Gris = inactif |
| Annonces vocales | Smash, set gagné, victoire (Web Speech API, français) |
| Timeline | Graphique coups/minute |
| Export CSV | Téléchargement de l'historique des coups |
| Historique matchs | 10 derniers matchs sauvegardés (Node-RED + InfluxDB) |

---

## Types de coups détectés

| Code | Nom | Déclencheur Arduino |
|---|---|---|
| 0 | BH Drive | gz ≤ 0, gyroMag < 400 |
| 1 | BH Smash | gz ≤ 0, gyroMag ≥ 400 |
| 2 | FH Drive | gz > 0, gyroMag < 400 |
| 3 | FH Loop | gz > 0, gy > 80 °/s |
| 4 | FH Smash | gz > 0, gyroMag ≥ 400 |

Seuils modifiables dans `TableTennisBat.ino` :
```cpp
#define THRESHOLD_SMASH  400.0f   // °/s
#define THRESHOLD_DRIVE  150.0f   // °/s
#define COOLDOWN_MS      600      // ms entre deux coups
```

---

## Structure des fichiers

```
TennisTable/
├── TableTennisBat/
│   └── TableTennisBat.ino      # Sketch Arduino
├── Connexion_Ble_MQTT.py       # Bridge BLE → MQTT
├── scan_ble.py                  # Scanner BLE
├── identify_ble.py              # Identification des raquettes sans nom
├── dashboard_v2.html            # Interface dashboard (source HTML)
├── gen_flow.py                  # Générateur du flow Node-RED
├── flow_v2.json                 # Flow Node-RED (généré)
├── flow_backup_v1.json          # Sauvegarde du flow original
└── README.md
```

---

## Restaurer l'ancienne version

Le flow original est sauvegardé dans `flow_backup_v1.json`. Pour restaurer :
Node-RED → Menu → Import → coller le contenu du fichier.

---

## InfluxDB

- **Organisation** : `CCNB`
- **Bucket coups** : `Tennis` — mesure `tennis_table` (tags: `device`, `player`)
- **Bucket matchs** : `Tennis` — mesure `tennis_match` (tags: `winner`, `p1_name`, `p2_name`)
- **URL** : `http://172.18.191.73:8086`
