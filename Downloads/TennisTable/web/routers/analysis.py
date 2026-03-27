from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.user import User
from web.routers.deps import get_current_user
from web.services import analysis_service

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
