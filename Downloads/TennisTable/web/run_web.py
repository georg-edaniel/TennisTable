#!/usr/bin/env python3
"""
Point d'entrée unique.

Usage:
    python web/run_web.py
    python web/run_web.py --host 0.0.0.0 --port 8000 --reload
"""
import sys
import subprocess
from pathlib import Path

# Ensure TennisTable/ is on sys.path so 'web' package is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Auto-install web dependencies ─────────────────────────────────────────────
_WEB_DEPS = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "passlib[bcrypt]>=1.7.4",
    "python-jose[cryptography]>=3.3.0",
    "python-multipart>=0.0.9",
    "jinja2>=3.1.0",
    "aiofiles>=23.2.1",
]


def _ensure_deps():
    import importlib.util
    checks = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "sqlalchemy": "sqlalchemy",
        "passlib": "passlib",
        "jose": "python-jose[cryptography]",
        "multipart": "python-multipart",
        "jinja2": "jinja2",
        "aiofiles": "aiofiles",
    }
    missing = [pkg for mod, pkg in checks.items() if not importlib.util.find_spec(mod)]
    if missing:
        print(f"[run_web] Installing: {missing}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


if not getattr(sys, "frozen", False):
    _ensure_deps()

# ── Start uvicorn ─────────────────────────────────────────────────────────────
import argparse
import asyncio
import uvicorn

# Fix: Windows ProactorEventLoop (IocpProactor) conflicts with uvicorn's create_server
# Switch to SelectorEventLoop BEFORE uvicorn creates its event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TT Tracker Web Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    # Check port availability before starting (no SO_REUSEADDR → strict check)
    import socket as _socket
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as _s:
        try:
            _s.bind((args.host if args.host != "0.0.0.0" else "127.0.0.1", args.port))
        except OSError:
            print(f"\n[ERROR] Port {args.port} is already in use.")
            print(f"  Stop the existing process or use: python web/run_web.py --port 8081")
            sys.exit(1)

    print(f"\n{'='*52}")
    print(f"  TT Tracker — http://localhost:{args.port}")
    print(f"  Login : admin / admin123")
    print(f"{'='*52}\n")

    from web.main import app  # import after sys.path is set
    uvicorn.run(
        app if not args.reload else "web.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(ROOT)] if args.reload else None,
        log_level="info",
    )
