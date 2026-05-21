-- ============================================================
--  AQIMS — Initialisation PostgreSQL
-- ============================================================

-- Extension pour les UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Les tables sont créées par SQLAlchemy/Alembic au démarrage
-- Ce script initialise les extensions nécessaires
