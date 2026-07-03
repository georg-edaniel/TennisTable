import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import EmailStr
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.models.user import User
from web.schemas.user import UserOut, UserUpdate, AdminUserUpdate
from web.schemas.session import SummaryOut
from web.routers.deps import get_current_user, require_admin
from web.models.summary import SessionSummary

router = APIRouter(tags=["users"])
logger = logging.getLogger("users")


@router.get("/users/list")
def list_users_public(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Active users list for opponent dropdown (requires auth)."""
    users = db.query(User).filter(User.is_active == True, User.id != user.id).all()
    return [{"id": u.id, "display_name": u.display_name or u.username} for u in users]


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
        dn = update.display_name.strip()
        if len(dn) > 64:
            raise HTTPException(400, "Nom affiché : 64 caractères max")
        user.display_name = dn
    if update.email is not None:
        # Validate email format via pydantic
        try:
            from pydantic import TypeAdapter
            TypeAdapter(EmailStr).validate_python(update.email)
        except Exception:
            raise HTTPException(400, "Format email invalide")
        existing = db.query(User).filter(User.email == update.email, User.id != user.id).first()
        if existing:
            raise HTTPException(409, "Email déjà utilisé")
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


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/admin/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [UserOut.model_validate(u) for u in db.query(User).all()]


@router.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    update: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    changes = []
    if update.role is not None:
        if update.role not in ("admin", "player"):
            raise HTTPException(400, "Rôle invalide")
        if update.role != user.role:
            changes.append(f"role: {user.role}→{update.role}")
        user.role = update.role
    if update.is_active is not None:
        if update.is_active != user.is_active:
            changes.append(f"is_active: {user.is_active}→{update.is_active}")
        user.is_active = update.is_active
    if update.must_change_password is not None:
        user.must_change_password = update.must_change_password
    if update.coach_id is not None:
        if update.coach_id == 0:
            user.coach_id = None
            changes.append("coach: removed")
        else:
            coach = db.query(User).filter(User.id == update.coach_id).first()
            if not coach:
                raise HTTPException(404, "Coach introuvable")
            user.coach_id = update.coach_id
            changes.append(f"coach: {update.coach_id}")

    if changes:
        logger.info("ADMIN AUDIT: %s (id=%d) modified user %s (id=%d): %s",
                    admin.username, admin.id, user.username, user.id, "; ".join(changes))

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/admin/users/{user_id}/unlock")
def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Manually unlock a locked account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    logger.info("ADMIN AUDIT: %s (id=%d) unlocked account of %s (id=%d)",
                admin.username, admin.id, user.username, user.id)
    return {"ok": True}


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    if user.id == admin.id:
        raise HTTPException(400, "Impossible de supprimer son propre compte")
    user.is_active = False  # soft delete
    db.commit()
    logger.info("ADMIN AUDIT: %s (id=%d) deactivated user %s (id=%d)",
                admin.username, admin.id, user.username, user.id)
    return {"ok": True}
