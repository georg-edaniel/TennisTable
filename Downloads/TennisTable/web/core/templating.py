"""Shared Jinja2Templates instance with global helpers."""
from pathlib import Path
from fastapi.templating import Jinja2Templates
from web.core.i18n import get_translator

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# CSS / JS version string — bump this to bust browser cache after any static file change
CSS_VERSION = "4"

# Default translator (FR) injected as global — routes that pass _ctx() override it
# with the per-request language via the `t` context variable.
templates.env.globals["css_v"] = CSS_VERSION
templates.env.globals["t"] = get_translator("fr")
templates.env.globals["lang"] = "fr"
