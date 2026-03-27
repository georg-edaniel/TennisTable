from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.user import User
from web.schemas.user import UserOut, UserUpdate, AdminUserUpdate
from web.schemas.session import SummaryOut
from web.routers.deps import get_current_user, require_admin
from web.models.summary import SessionSummary

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.put("/users/me", response_model=UserOut)
def update_me(
    update: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if update.display_name is not None:
        user.display_name = update.display_name
    if update.email is not None:
        user.email = update.email
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users/me/stats")
def my_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    summaries = (
        db.query(SessionSummary)
        .filter(SessionSummary.player_id == user.id)
        .all()
    )
    if not summaries:
        return {"sessions": 0, "total_strokes": 0, "avg_spm": 0}
    total_strokes = sum(s.total_strokes for s in summaries)
    avg_spm = sum(s.strokes_per_min for s in summaries) / len(summaries)
    return {
        "sessions": len(summaries),
        "total_strokes": total_strokes,
        "avg_spm": round(avg_spm, 2),
    }


@router.post("/users/me/onboarding-complete")
def complete_onboarding(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.onboarding_completed = True
    db.commit()
    return {"ok": True}


# ── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return [UserOut.model_validate(u) for u in db.query(User).all()]


@router.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    update: AdminUserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if update.role is not None:
        user.role = update.role
    if update.is_active is not None:
        user.is_active = update.is_active
    if update.must_change_password is not None:
        user.must_change_password = update.must_change_password
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    user.is_active = False  # soft delete
    db.commit()
    return {"ok": True}
