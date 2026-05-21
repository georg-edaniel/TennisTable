# ============================================================
#  AQIMS — Makefile
#  Commandes pratiques pour le développement et la production
# ============================================================

.PHONY: help up down dev logs setup-influx reset ps shell-backend shell-influx test

# ── Valeurs par défaut lues depuis .env ──────────────────────
include .env
export

INFLUX_URL ?= http://localhost:8086

help:
	@echo ""
	@echo "  AQIMS — Commandes disponibles"
	@echo "  ════════════════════════════"
	@echo "  make up              Démarrer toute la stack Docker"
	@echo "  make down            Arrêter les services"
	@echo "  make dev             Démarrer seulement InfluxDB + Redis (dev local)"
	@echo "  make logs            Suivre les logs en temps réel"
	@echo "  make logs-backend    Logs du backend uniquement"
	@echo "  make setup-influx    Configurer InfluxDB (bucket + rétention + test)"
	@echo "  make ps              État de tous les conteneurs"
	@echo "  make shell-backend   Shell interactif dans le backend"
	@echo "  make shell-influx    Shell influx CLI"
	@echo "  make test            Lancer les tests backend"
	@echo "  make reset           ⚠️  Stopper + supprimer tous les volumes"
	@echo ""

# ── Stack complète ───────────────────────────────────────────
up:
	docker compose up -d --build
	@echo ""
	@echo "✅  Services démarrés :"
	@echo "   Backend    → http://localhost:$(APP_PORT)"
	@echo "   InfluxDB   → http://localhost:8086"
	@echo "   EMQX admin → http://localhost:18083"
	@echo ""
	@echo "   ⏳  Attente que les services soient prêts..."
	@sleep 5
	@$(MAKE) ps

down:
	docker compose down

# ── Mode développement local ─────────────────────────────────
# Lance uniquement InfluxDB et Redis, le backend tourne en local
dev:
	docker compose up -d influxdb redis
	@echo ""
	@echo "✅  Services de dev démarrés :"
	@echo "   InfluxDB → http://localhost:8086  (login: $(INFLUX_USER))"
	@echo "   Redis    → localhost:6379"
	@echo ""
	@echo "   Démarrer le backend en local :"
	@echo "   cd backend && USE_SQLITE=true uvicorn main:app --reload --port $(APP_PORT)"
	@echo ""
	@echo "   Puis configurer InfluxDB :"
	@echo "   make setup-influx"

# ── Configuration InfluxDB ────────────────────────────────────
setup-influx:
	@echo "Configuration InfluxDB..."
	@echo "⏳  Attente que InfluxDB soit prêt (10s)..."
	@sleep 10
	python scripts/setup_influxdb.py \
		--host $(INFLUX_URL) \
		--token $(INFLUX_TOKEN) \
		--org $(INFLUX_ORG) \
		--bucket $(INFLUX_BUCKET)

# ── Logs ─────────────────────────────────────────────────────
logs:
	docker compose logs -f --tail=100

logs-backend:
	docker compose logs -f --tail=100 backend

# ── État des services ─────────────────────────────────────────
ps:
	@docker compose ps

# ── Shells interactifs ────────────────────────────────────────
shell-backend:
	docker compose exec backend bash

shell-influx:
	docker compose exec influxdb influx \
		--host http://localhost:8086 \
		--token $(INFLUX_TOKEN) \
		--org $(INFLUX_ORG)

# ── Tests ────────────────────────────────────────────────────
test:
	cd backend && USE_SQLITE=true pytest tests/ -v --cov=. --cov-report=term-missing

# ── Reset complet ─────────────────────────────────────────────
reset:
	@echo "⚠️  Ceci va supprimer TOUTES les données (volumes Docker)."
	@read -p "Confirmer ? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker compose down -v
	@echo "✅  Reset complet effectué."
