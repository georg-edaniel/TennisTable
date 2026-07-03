"""Lightweight i18n: load JSON translation files and return a t() callable."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Callable

_I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
_SUPPORTED = {"fr", "en"}
_DEFAULT = "fr"


@lru_cache(maxsize=4)
def _load(lang: str) -> dict:
    path = _I18N_DIR / f"{lang}.json"
    if not path.exists():
        path = _I18N_DIR / f"{_DEFAULT}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_translator(lang: str = _DEFAULT) -> Callable[[str], str]:
    """Return a t(key) function for the given language.

    Falls back to the key itself if the key is missing, so templates
    never raise KeyError.
    """
    if lang not in _SUPPORTED:
        lang = _DEFAULT
    translations = _load(lang)

    def t(key: str, **kwargs: object) -> str:
        val = translations.get(key, key)
        if kwargs:
            val = val.format(**kwargs)
        return val

    return t


def resolve_lang(request_lang: str | None) -> str:
    """Normalise a raw Accept-Language / cookie value to a supported code."""
    if not request_lang:
        return _DEFAULT
    code = request_lang.split("-")[0].lower()
    return code if code in _SUPPORTED else _DEFAULT
