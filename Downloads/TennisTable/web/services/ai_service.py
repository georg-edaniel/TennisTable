"""AI features: LLM coach (Claude) + Markov shot prediction."""
import os
import logging
from sqlalchemy.orm import Session

from web.models.stroke import Stroke

logger = logging.getLogger("ai_service")

SHOT_NAMES = ["bh_drive", "bh_smash", "fh_drive", "fh_loop", "fh_smash"]

# Cache Markov en mémoire : player_id → (transitions, stroke_count_au_moment_du_build)
# Invalidé automatiquement quand de nouveaux coups sont ajoutés.
_markov_cache: dict[int, tuple[dict, int]] = {}
SHOT_LABELS = {
    "bh_drive": "BH Drive",
    "bh_smash": "BH Smash",
    "fh_drive": "FH Drive",
    "fh_loop": "FH Loop",
    "fh_smash": "FH Smash",
}


# ── LLM Coach ────────────────────────────────────────────────────────────────

def get_llm_coach_tip(
    session_id: int,
    player_id: int,
    db: Session,
    tips_context: list[str],
    stroke_summary: dict,
) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _rule_based_fallback(tips_context, stroke_summary)
    try:
        import anthropic  # local import — graceful if not installed
        client = anthropic.Anthropic(api_key=api_key)
        dominant = stroke_summary.get("dominant_shot", "inconnu")
        style = stroke_summary.get("style_profile", "inconnu")
        total = stroke_summary.get("total_strokes", 0)
        tips_text = "\n".join(f"- {t}" for t in tips_context) if tips_context else "Aucun"
        prompt = (
            f"Tu es un coach de tennis de table expert. "
            f"Voici le profil du joueur pour la session #{session_id} :\n"
            f"- Style : {style}\n"
            f"- Coup dominant : {dominant}\n"
            f"- Total coups : {total}\n"
            f"- Statistiques détaillées : {stroke_summary}\n"
            f"Conseils automatiques déjà générés :\n{tips_text}\n\n"
            f"Donne un conseil de coaching personnalisé, précis et actionnable en 2-3 phrases. "
            f"Réponds uniquement avec le conseil, sans introduction."
        )
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        logger.warning("LLM coach tip failed: %s", exc)
        return _rule_based_fallback(tips_context, stroke_summary)


def _rule_based_fallback(tips_context: list[str], stroke_summary: dict) -> str:
    if tips_context:
        return tips_context[0]
    dominant = stroke_summary.get("dominant_shot", "")
    if "smash" in dominant.lower():
        return "Votre jeu est axé sur la puissance. Travaillez la régularité pour réduire les fautes directes."
    if "loop" in dominant.lower():
        return "Excellent usage du topspin ! Variez les vitesses pour déséquilibrer l'adversaire."
    return "Restez concentré sur la mise en jeu et la constance de vos placements."


def cache_llm_tip(db: Session, session_id: int, tip: str):
    from web.models.session import GameSession
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if sess:
        sess.llm_coach_tip = tip
        db.commit()


# ── Markov shot prediction ────────────────────────────────────────────────────

def build_markov_transition(db: Session, player_id: int) -> dict:
    """Construit une matrice de transition Markov 5×5 depuis l'historique des coups.
    Le résultat est mis en cache tant qu'aucun nouveau coup n'est ajouté."""
    total_count = (
        db.query(Stroke)
        .filter(Stroke.player_id == player_id, Stroke.stroke_name.in_(SHOT_NAMES))
        .count()
    )

    cached = _markov_cache.get(player_id)
    if cached and cached[1] == total_count and total_count >= 10:
        return cached[0]

    rows = (
        db.query(Stroke.stroke_name)
        .filter(Stroke.player_id == player_id, Stroke.stroke_name.in_(SHOT_NAMES))
        .order_by(Stroke.id.asc())
        .limit(2000)
        .all()
    )
    names = [r[0] for r in rows if r[0] in SHOT_NAMES]

    if len(names) < 10:
        return _uniform_transitions()

    counts = {s: {t: 0 for t in SHOT_NAMES} for s in SHOT_NAMES}
    for i in range(len(names) - 1):
        counts[names[i]][names[i + 1]] += 1

    transitions = {}
    for src in SHOT_NAMES:
        total = sum(counts[src].values())
        transitions[src] = (
            {t: counts[src][t] / total for t in SHOT_NAMES}
            if total > 0
            else {t: 0.2 for t in SHOT_NAMES}
        )

    _markov_cache[player_id] = (transitions, total_count)
    return transitions


def _uniform_transitions() -> dict:
    return {s: {t: 0.2 for t in SHOT_NAMES} for s in SHOT_NAMES}


def predict_next_shot(last_shot: str, transitions: dict) -> str:
    """Return the most probable next shot given the last shot."""
    row = transitions.get(last_shot, {t: 0.2 for t in SHOT_NAMES})
    return max(row, key=row.get)
