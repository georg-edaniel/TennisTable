from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.racket import Racket
from web.models.user import User
from web.schemas.racket import RacketCreate, RacketUpdate, RacketAssign, RacketOut
from web.routers.deps import get_current_user, require_admin

router = APIRouter(prefix="/rackets", tags=["rackets"])


@router.get("", response_model=list[RacketOut])
def list_rackets(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [RacketOut.model_validate(r) for r in db.query(Racket).all()]


@router.get("/available", response_model=list[RacketOut])
def available_rackets(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rackets = db.query(Racket).filter(Racket.assigned_to.is_(None)).all()
    return [RacketOut.model_validate(r) for r in rackets]


@router.post("", response_model=RacketOut, status_code=201)
def create_racket(
    body: RacketCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if db.query(Racket).filter(Racket.ble_device_name == body.ble_device_name).first():
        raise HTTPException(409, "Device déjà enregistré")
    r = Racket(**body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return RacketOut.model_validate(r)


@router.put("/{racket_id}", response_model=RacketOut)
def update_racket(
    racket_id: int,
    body: RacketUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    r = db.query(Racket).filter(Racket.id == racket_id).first()
    if not r:
        raise HTTPException(404)
    if body.label is not None:
        r.label = body.label
    if body.color_hex is not None:
        r.color_hex = body.color_hex
    db.commit()
    db.refresh(r)
    return RacketOut.model_validate(r)


@router.put("/{racket_id}/assign", response_model=RacketOut)
def assign_racket(
    racket_id: int,
    body: RacketAssign,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    r = db.query(Racket).filter(Racket.id == racket_id).first()
    if not r:
        raise HTTPException(404)
    if body.player_id is not None:
        user = db.query(User).filter(User.id == body.player_id).first()
        if not user:
            raise HTTPException(404, "Joueur introuvable")
    r.assigned_to = body.player_id
    db.commit()
    db.refresh(r)
    return RacketOut.model_validate(r)


@router.delete("/{racket_id}/assign", response_model=RacketOut)
def unassign_racket(
    racket_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    r = db.query(Racket).filter(Racket.id == racket_id).first()
    if not r:
        raise HTTPException(404)
    r.assigned_to = None
    db.commit()
    db.refresh(r)
    return RacketOut.model_validate(r)
