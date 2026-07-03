FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps (web-only, lighter than full requirements.txt)
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# App code
COPY . .

# Migrations are handled by main.py lifespan on startup
CMD ["sh", "-c", "uvicorn web.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
