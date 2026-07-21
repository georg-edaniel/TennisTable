"""Demo mode — simulated data, no DB, no login required."""
import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from web.core.templating import templates
from web.core.i18n import get_translator, resolve_lang

router = APIRouter(tags=["demo"])

_DEMO_STATS = {
    "total_strokes": 127,
    "sessions": 3,
    "style": "Attaquant",
    "top_shot": "Topspin revers",
    "radar": {
        "categories": ["Topspin", "Slice", "Smash", "Bloc", "Service", "Lob"],
        "values": [82, 45, 71, 60, 78, 38],
    },
    "recent": [
        {"date": "2026-03-27", "strokes": 54, "style": "Attaquant"},
        {"date": "2026-03-25", "strokes": 41, "style": "Attaquant"},
        {"date": "2026-03-22", "strokes": 32, "style": "Équilibré"},
    ],
}


@router.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request):
    lang = resolve_lang(request.cookies.get("tt_lang"))
    return templates.TemplateResponse(
        request, "demo.html",
        {
            "stats": _DEMO_STATS,
            "stats_json": json.dumps(_DEMO_STATS["radar"]),
            "lang": lang,
            "t": get_translator(lang),
            "csp_nonce": getattr(request.state, "csp_nonce", ""),
        },
    )
