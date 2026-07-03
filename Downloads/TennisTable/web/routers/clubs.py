"""Club management — HTML pages + REST API."""
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.core.database import get_db
from web.core.security import decode_token
from web.core.templating import templates
from web.models.club import Club, ClubMember
from web.models.user import User
from web.routers.deps import get_current_user
from web.services.auth_service import get_user_by_id

router     = APIRouter(tags=["clubs"])
api_router = APIRouter(prefix="/clubs", tags=["clubs-api"])

ACCESS_COOKIE = "access_token"


def _get_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        data = decode_token(token)
        uid = data.get("sub", "")
        return get_user_by_id(db, int(uid)) if uid.isdigit() else None
    except Exception:
        return None


def _ctx(request, user, **extra):
    return {"user": user, "access_token": request.cookies.get(ACCESS_COOKIE, ""), **extra}


def _resp(request, tpl, ctx, status=200):
    return templates.TemplateResponse(request, tpl, ctx, status_code=status)


def _is_member(db, club_id, user_id) -> ClubMember | None:
    return db.query(ClubMember).filter(
        ClubMember.club_id == club_id, ClubMember.user_id == user_id,
    ).first()


# ── HTML pages ────────────────────────────────────────────────────────────────

@router.get("/clubs", response_class=HTMLResponse)
def clubs_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")

    # Clubs I own or belong to
    my_club_ids = {
        m.club_id for m in db.query(ClubMember).filter(ClubMember.user_id == user.id).all()
    }
    my_clubs = db.query(Club).filter(Club.id.in_(my_club_ids)).all() if my_club_ids else []
    all_clubs = db.query(Club).order_by(Club.created_at.desc()).all()

    return _resp(request, "clubs.html", _ctx(
        request, user,
        my_clubs=my_clubs,
        all_clubs=all_clubs,
        my_club_ids=my_club_ids,
    ))


@router.get("/clubs/{club_id}", response_class=HTMLResponse)
def club_detail(club_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login")
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(404)

    member_rows = db.query(ClubMember).filter(ClubMember.club_id == club_id).all()
    member_ids = [m.user_id for m in member_rows]
    member_users = {u.id: u for u in db.query(User).filter(User.id.in_(member_ids)).all()} if member_ids else {}

    members = sorted([
        {
            "user": member_users[m.user_id],
            "role": m.role,
            "joined": m.joined_at.strftime("%d/%m/%Y"),
        }
        for m in member_rows if m.user_id in member_users
    ], key=lambda x: (x["role"] != "owner", x["role"] != "coach"))

    my_membership = _is_member(db, club_id, user.id)
    is_owner = club.owner_id == user.id

    # Leaderboard: members ranked by ELO
    leaderboard = sorted(member_users.values(), key=lambda u: u.elo_rating, reverse=True)

    return _resp(request, "club_detail.html", _ctx(
        request, user,
        club=club,
        members=members,
        leaderboard=leaderboard,
        my_membership=my_membership,
        is_owner=is_owner,
    ))


# ── API ───────────────────────────────────────────────────────────────────────

class ClubCreate(BaseModel):
    name: str
    description: str = ""


class MemberRole(BaseModel):
    role: str   # member | coach


@api_router.post("")
def create_club(body: ClubCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not body.name.strip():
        raise HTTPException(400, "Nom requis")
    code = secrets.token_urlsafe(6)[:8]
    club = Club(name=body.name.strip()[:128], description=body.description[:512],
                owner_id=user.id, invite_code=code)
    db.add(club)
    db.flush()
    db.add(ClubMember(club_id=club.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(club)
    return {"id": club.id, "name": club.name, "invite_code": club.invite_code}


@api_router.post("/join/{invite_code}")
def join_club(invite_code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    club = db.query(Club).filter(Club.invite_code == invite_code).first()
    if not club:
        raise HTTPException(404, "Code d'invitation invalide")
    if _is_member(db, club.id, user.id):
        raise HTTPException(409, "Vous êtes déjà membre de ce club")
    db.add(ClubMember(club_id=club.id, user_id=user.id, role="member"))
    db.commit()
    return {"ok": True, "club_id": club.id, "club_name": club.name}


@api_router.delete("/{club_id}/leave")
def leave_club(club_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(404)
    if club.owner_id == user.id:
        raise HTTPException(400, "Le propriétaire ne peut pas quitter le club — transférez d'abord la propriété")
    m = _is_member(db, club_id, user.id)
    if not m:
        raise HTTPException(404, "Vous n'êtes pas membre")
    db.delete(m)
    db.commit()
    return {"ok": True}


@api_router.put("/{club_id}/members/{member_id}/role")
def set_member_role(club_id: int, member_id: int, body: MemberRole,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club or club.owner_id != user.id:
        raise HTTPException(403, "Propriétaire uniquement")
    if body.role not in ("member", "coach"):
        raise HTTPException(400, "Rôle invalide")
    m = _is_member(db, club_id, member_id)
    if not m:
        raise HTTPException(404)
    m.role = body.role
    db.commit()
    return {"ok": True}


@api_router.delete("/{club_id}")
def delete_club(club_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club or club.owner_id != user.id:
        raise HTTPException(403)
    db.delete(club)
    db.commit()
    return {"ok": True}
