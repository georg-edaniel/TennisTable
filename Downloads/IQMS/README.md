# AQIMS — Air Quality Index Monitoring System

Système de supervision de la qualité de l'air — IoT sécurisé de bout en bout.

## Démarrage rapide

### 1. Prérequis
- Docker Desktop
- Python 3.12+
- Arduino IDE (pour le firmware ESP32)

### 2. Configuration
```bash
cp .env.example .env
# Éditez .env avec vos valeurs
```

### 3. Générer les certificats TLS
```bash
pip install cryptography
python scripts/generate_certs.py
```

### 4. Lancer l'infrastructure
```bash
docker compose up -d
```

### 5. Accès
| Service | URL | Identifiants |
|---------|-----|--------------|
| API + Dashboard | http://localhost:8000 | — |
| Documentation API | http://localhost:8000/docs | — |
| EMQX Dashboard | http://localhost:18083 | admin / aqims_admin_2024! |
| InfluxDB | http://localhost:8086 | voir .env |

### 6. Flasher l'ESP32
1. Ouvrez `firmware/aqims_sensor/aqims_sensor.ino` dans Arduino IDE
2. Modifiez `config.h` (WiFi, MQTT)
3. Le fichier `certs.h` est généré automatiquement par `generate_certs.py`
4. Flashez sur votre ESP32

### 7. Tests
```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v --cov=. --cov-report=html
```

## Architecture

```
ESP32 → MQTT/TLS → EMQX → FastAPI → InfluxDB (time-series)
                                   → PostgreSQL (users/devices)
                                   → Redis (cache/WebSocket)
                         → Nginx → Dashboard Web
```

## Sécurité
- TLS 1.3 mutuel (CA + certificats client/serveur)
- MQTT : username/password + QoS=2 + ACL
- API : JWT + Argon2 + 2FA TOTP
- Web : HTTPS + HSTS + CSP + Rate limiting
- DB : SQLAlchemy ORM (protection injection SQL)
