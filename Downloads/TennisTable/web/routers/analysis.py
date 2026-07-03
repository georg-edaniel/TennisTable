from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.session import GameSession
from web.models.user import User
from web.routers.deps import get_current_user
from web.services import analysis_service
from web.services import ai_service
from web.services.h2h_service import get_h2h

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/profile/{player_id}")
def profile(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return analysis_service.get_profile(db, player_id)


@router.get("/evolution/{player_id}")
def evolution(
    player_id: int,
    limit: int = 15,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return analysis_service.get_evolution(db, player_id, limit)


@router.get("/recommendations/{player_id}")
def recommendations(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {"recommendations": analysis_service.get_recommendations(db, player_id)}


@router.get("/training-vs-match/{player_id}")
def training_vs_match(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return analysis_service.get_training_vs_match(db, player_id)


@router.get("/comparison/{p1_id}/{p2_id}")
def comparison(
    p1_id: int,
    p2_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {
        "player1": analysis_service.get_profile(db, p1_id),
        "player2": analysis_service.get_profile(db, p2_id),
    }


@router.get("/h2h/{p1_id}/{p2_id}")
def head_to_head(
    p1_id: int,
    p2_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data = get_h2h(db, p1_id, p2_id)
    if not data:
        raise HTTPException(404, "Joueurs introuvables")
    return data


@router.get("/export/pdf/{player_id}")
def export_pdf(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pdf_bytes = analysis_service.generate_pdf_report(db, player_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=rapport_{player_id}.pdf"},
    )


@router.get("/coach-tip/{session_id}")
async def coach_tip(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sess = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not sess:
        raise HTTPException(404, "Session introuvable")
    if sess.player1_id != user.id and sess.player2_id != user.id:
        raise HTTPException(403, "Accès refusé")

    # Return cached tip if available
    if sess.llm_coach_tip:
        return {"session_id": session_id, "tip": sess.llm_coach_tip, "source": "llm"}

    # Build context from rule-based tips + stroke summary
    tips_context = analysis_service.get_session_coaching_tips(db, session_id, user.id)
    stroke_summary: dict = {}
    from web.models.summary import SessionSummary
    summary = db.query(SessionSummary).filter(
        SessionSummary.session_id == session_id,
        SessionSummary.player_id == user.id,
    ).first()
    if summary:
        stroke_summary = {
            "dominant_shot": summary.dominant_shot,
            "style_profile": summary.style_profile,
            "total_strokes": summary.total_strokes,
            "fh_ratio": summary.fh_ratio,
            "strokes_per_min": summary.strokes_per_min,
        }

    tip = ai_service.get_llm_coach_tip(session_id, user.id, db, tips_context, stroke_summary)
    import os
    source = "llm" if os.getenv("ANTHROPIC_API_KEY") else "rule_based"

    # Cache if LLM was used
    if source == "llm":
        ai_service.cache_llm_tip(db, session_id, tip)

    return {"session_id": session_id, "tip": tip, "source": source}


@router.get("/shot-prediction/{player_id}")
def shot_prediction(
    player_id: int,
    last_shot: str = Query("fh_drive"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if last_shot not in ai_service.SHOT_NAMES:
        last_shot = "fh_drive"
    transitions = ai_service.build_markov_transition(db, player_id)
    predicted = ai_service.predict_next_shot(last_shot, transitions)
    probs = transitions.get(last_shot, {t: 0.2 for t in ai_service.SHOT_NAMES})
    return {
        "last_shot": last_shot,
        "predicted_next": predicted,
        "predicted_label": ai_service.SHOT_LABELS.get(predicted, predicted),
        "probabilities": {ai_service.SHOT_LABELS.get(k, k): round(v * 100, 1) for k, v in probs.items()},
    }


@router.get("/export/csv/{player_id}")
def export_csv(
    player_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    csv_str = analysis_service.generate_csv_evolution(db, player_id)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=evolution_{player_id}.csv"},
    )
