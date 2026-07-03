"""Style profile, evolution, and recommendation analysis."""
import csv
import io
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from web.models.session import GameSession
from web.models.stroke import Stroke
from web.models.summary import SessionSummary


# ── Style computation ────────────────────────────────────────────────────────

def compute_style(r: Dict[str, int]) -> str:
    total = r.get("total", 1) or 1
    if (r.get("fh_smash", 0) + r.get("bh_smash", 0)) / total > 0.30:
        return "Smasher"
    if r.get("fh_loop", 0) / total > 0.25:
        return "Attaquant"
    if (r.get("bh_drive", 0) + r.get("bh_smash", 0)) / total > 0.50:
        return "Défenseur"
    return "All-court"


def compute_radar(r: Dict[str, Any]) -> Dict[str, float]:
    """5-axis radar values (0-100)."""
    total = r.get("total", 1) or 1
    spm = r.get("strokes_per_min", 0)
    return {
        "Puissance": round(min(100, (r.get("fh_smash", 0) + r.get("bh_smash", 0)) / total * 200), 1),
        "Technique":  round(min(100, r.get("fh_loop", 0) / total * 300), 1),
        "Régularité": round(min(100, r.get("fh_drive", 0) / total * 200), 1),
        "Revers":     round(min(100, (r.get("bh_drive", 0) + r.get("bh_smash", 0)) / total * 200), 1),
        "Vitesse":    round(min(100, spm / 60 * 100), 1),
    }


def compute_dominant(r: Dict[str, int]) -> str:
    shots = {
        "BH Drive": r.get("bh_drive", 0),
        "BH Smash": r.get("bh_smash", 0),
        "FH Drive": r.get("fh_drive", 0),
        "FH Loop":  r.get("fh_loop", 0),
        "FH Smash": r.get("fh_smash", 0),
    }
    return max(shots, key=shots.get) if any(shots.values()) else "—"


def compute_summary(sess: GameSession, strokes: list, player_id: int) -> SessionSummary:
    """Build a SessionSummary ORM object from stroke list."""
    if not strokes:
        return SessionSummary(
            session_id=sess.id,
            player_id=player_id,
        )

    last = strokes[-1]
    total = last.cum_total or 1
    dur = (sess.duration_s or 1) / 60

    r = {
        "bh_drive": last.cum_bh_drive,
        "bh_smash": last.cum_bh_smash,
        "fh_drive": last.cum_fh_drive,
        "fh_loop":  last.cum_fh_loop,
        "fh_smash": last.cum_fh_smash,
        "total":    total,
        "strokes_per_min": total / dur,
    }
    fh = last.cum_fh_drive + last.cum_fh_loop + last.cum_fh_smash
    fh_ratio = fh / total if total else 0
    dominant = compute_dominant(r)
    style = compute_style(r)
    spm = total / dur

    return SessionSummary(
        session_id=sess.id,
        player_id=player_id,
        total_strokes=total,
        bh_drive=last.cum_bh_drive,
        bh_smash=last.cum_bh_smash,
        fh_drive=last.cum_fh_drive,
        fh_loop=last.cum_fh_loop,
        fh_smash=last.cum_fh_smash,
        fh_ratio=round(fh_ratio, 3),
        dominant_shot=dominant,
        style_profile=style,
        strokes_per_min=round(spm, 2),
        consistency=round(min(1.0, 1 - abs(fh_ratio - 0.5)), 3),
    )


# ── Queries ──────────────────────────────────────────────────────────────────

def get_profile(db: Session, player_id: int) -> Dict[str, Any]:
    summaries = (
        db.query(SessionSummary)
        .filter(SessionSummary.player_id == player_id)
        .order_by(SessionSummary.id.desc())
        .limit(20)
        .all()
    )
    if not summaries:
        return {"player_id": player_id, "sessions": 0, "style": "N/A", "radar": {}}

    totals = {k: 0 for k in ["bh_drive", "bh_smash", "fh_drive", "fh_loop", "fh_smash", "total"]}
    spm_list = []
    for s in summaries:
        totals["bh_drive"] += s.bh_drive
        totals["bh_smash"] += s.bh_smash
        totals["fh_drive"] += s.fh_drive
        totals["fh_loop"]  += s.fh_loop
        totals["fh_smash"] += s.fh_smash
        totals["total"]    += s.total_strokes
        spm_list.append(s.strokes_per_min)

    totals["strokes_per_min"] = sum(spm_list) / len(spm_list) if spm_list else 0
    style = compute_style(totals)
    radar = compute_radar(totals)

    return {
        "player_id": player_id,
        "sessions": len(summaries),
        "style": style,
        "radar": radar,
        "totals": totals,
        "dominant": compute_dominant(totals),
    }


def get_evolution(db: Session, player_id: int, limit: int = 15) -> List[Dict]:
    summaries = (
        db.query(SessionSummary, GameSession)
        .join(GameSession, SessionSummary.session_id == GameSession.id)
        .filter(SessionSummary.player_id == player_id)
        .order_by(GameSession.started_at.asc())
        .limit(limit)
        .all()
    )
    result = []
    for s, sess in summaries:
        result.append({
            "session_id": s.session_id,
            "date": sess.started_at.isoformat() if sess.started_at else "",
            "total": s.total_strokes,
            "spm": s.strokes_per_min,
            "style": s.style_profile,
            "fh_ratio": s.fh_ratio,
        })
    return result


def get_session_coaching_tips(db: Session, session_id: int, player_id: int) -> List[str]:
    """Generate 2-3 actionable tips for a specific just-completed session."""
    summary = (
        db.query(SessionSummary)
        .filter(SessionSummary.session_id == session_id,
                SessionSummary.player_id == player_id)
        .first()
    )
    if not summary or summary.total_strokes < 5:
        return []

    total = summary.total_strokes or 1
    spm   = summary.strokes_per_min or 0
    fh_drive_pct  = summary.fh_drive / total
    fh_loop_pct   = summary.fh_loop  / total
    fh_smash_pct  = summary.fh_smash / total
    bh_pct        = (summary.bh_drive + summary.bh_smash) / total

    tips = []

    if fh_drive_pct > 0.60:
        tips.append(
            f"FH Drive dominant ({round(fh_drive_pct*100)}% des coups) — "
            "variez avec du FH Loop pour devenir imprévisible."
        )
    if bh_pct < 0.12:
        tips.append(
            f"Revers quasi absent ({round(bh_pct*100)}%) — "
            "intégrez-le pour couvrir tout le terrain."
        )
    if fh_smash_pct > 0.40:
        tips.append(
            f"Beaucoup de smash ({round(fh_smash_pct*100)}%) — "
            "construisez plus l'échange avant de finir le point."
        )
    if fh_loop_pct < 0.08 and total > 15:
        tips.append(
            "FH Loop quasi absent — incorporez des topspins pour créer de la rotation."
        )
    if spm < 20 and total > 10:
        tips.append(
            f"Rythme lent ({round(spm)} coups/min) — "
            "accélérez la cadence pour mieux simuler un vrai match."
        )
    if spm > 70:
        tips.append(
            f"Rythme très élevé ({round(spm)} coups/min) — "
            "pensez à varier vitesse et placement plutôt que la seule rapidité."
        )
    # Fallback : toujours au moins un tip sur le coup dominant
    if not tips and summary.dominant_shot and summary.dominant_shot != "—":
        tips.append(
            f"Coup dominant : {summary.dominant_shot} — "
            "continuez à le renforcer tout en développant vos autres coups."
        )

    return tips[:3]


def get_recommendations(db: Session, player_id: int) -> List[str]:
    profile = get_profile(db, player_id)
    totals = profile.get("totals", {})
    total = totals.get("total", 1) or 1
    spm = totals.get("strokes_per_min", 0)
    recs = []

    fh_loop_pct = totals.get("fh_loop", 0) / total
    fh_smash_pct = totals.get("fh_smash", 0) / total
    fh_drive_pct = totals.get("fh_drive", 0) / total
    bh_pct = (totals.get("bh_drive", 0) + totals.get("bh_smash", 0)) / total

    if fh_loop_pct < 0.10:
        recs.append("Votre FH Loop est faible (< 10%) — travaillez le topspin contre balle coupée.")
    if fh_smash_pct > 0.35 and fh_drive_pct < 0.20:
        recs.append("Trop de smash FH (> 35%) — améliorez la régularité avec des drives avant de smasher.")
    if bh_pct < 0.15:
        recs.append("Votre revers est sous-exploité (< 15%) — intégrez-le davantage dans vos échanges.")
    if spm < 25:
        recs.append("Rythme lent (< 25 coups/min) — augmentez la cadence lors des entraînements.")
    if fh_loop_pct > 0.40:
        recs.append("Vous êtes très technique (FH Loop > 40%) — variez avec plus de vitesse directe.")
    if all(v / total < 0.25 for v in [
        totals.get("bh_drive", 0), totals.get("fh_drive", 0),
        totals.get("fh_loop", 0), totals.get("fh_smash", 0)
    ]):
        recs.append("Style équilibré — pour progresser, choisissez un coup finisseur à spécialiser.")

    if not recs:
        recs.append("Profil bien équilibré — continuez sur cette lancée et visez la régularité.")
    return recs


def _latin1(text: str) -> str:
    """Replace characters outside Latin-1 range with ASCII equivalents."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf_report(db: Session, player_id: int) -> bytes:
    """Generate a PDF report using fpdf2 (Helvetica, Latin-1 native)."""
    from fpdf import FPDF

    profile = get_profile(db, player_id)
    recs = get_recommendations(db, player_id)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 12, "TT Tracker - Rapport d'analyse", ln=True, align="C")

    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Joueur ID: {player_id}  |  Sessions: {profile.get('sessions', 0)}", ln=True, align="C")
    pdf.ln(6)

    # Style profile
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, "Profil de style", ln=True)
    pdf.set_draw_color(99, 102, 241)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, _latin1(f"Style dominant: {profile.get('style', 'N/A')}"), ln=True)
    pdf.cell(0, 8, _latin1(f"Coup dominant: {profile.get('dominant', 'N/A')}"), ln=True)
    pdf.ln(4)

    # Radar
    radar = profile.get("radar", {})
    if radar:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Radar de style (0-100)", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for axis, val in radar.items():
            bar_w = int(val * 1.2)
            pdf.set_fill_color(99, 102, 241)
            pdf.cell(40, 7, f"{axis}:", ln=False)
            pdf.cell(bar_w, 7, "", fill=True, ln=False)
            pdf.cell(0, 7, f"  {val}", ln=True)
        pdf.ln(4)

    # Totals
    totals = profile.get("totals", {})
    if totals:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Repartition des coups", ln=True)
        pdf.set_font("Helvetica", "", 11)
        total = totals.get("total", 1) or 1
        for label, key in [("BH Drive", "bh_drive"), ("BH Smash", "bh_smash"),
                            ("FH Drive", "fh_drive"), ("FH Loop", "fh_loop"),
                            ("FH Smash", "fh_smash")]:
            count = totals.get(key, 0)
            pct = round(count / total * 100, 1)
            pdf.cell(0, 7, f"  {label}: {count} ({pct}%)", ln=True)
        pdf.ln(4)

    # Recommendations
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Recommandations", ln=True)
    pdf.set_draw_color(245, 158, 11)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    for i, rec in enumerate(recs, 1):
        pdf.multi_cell(0, 7, _latin1(f"{i}. {rec}"))
        pdf.ln(2)

    return bytes(pdf.output())


def generate_csv_evolution(db: Session, player_id: int) -> str:
    """Generate CSV of session evolution."""
    evolution = get_evolution(db, player_id, limit=100)
    output = io.StringIO()
    fieldnames = ["session_id", "date", "total", "spm", "style", "fh_ratio"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in evolution:
        writer.writerow(row)
    return output.getvalue()


def get_player_profile_full(db: Session, player_id: int) -> Dict[str, Any]:
    """Full public profile: stats, stroke distribution, recent matches."""
    from web.models.session import GameSession
    from web.models.user import User

    summaries = (
        db.query(SessionSummary)
        .filter(SessionSummary.player_id == player_id)
        .all()
    )

    total_sessions = len(summaries)

    totals = {k: 0 for k in ["bh_drive", "bh_smash", "fh_drive", "fh_loop", "fh_smash", "total"]}
    for s in summaries:
        totals["bh_drive"] += s.bh_drive
        totals["bh_smash"] += s.bh_smash
        totals["fh_drive"] += s.fh_drive
        totals["fh_loop"]  += s.fh_loop
        totals["fh_smash"] += s.fh_smash
        totals["total"]    += s.total_strokes

    stroke_distribution = {
        "FH Drive": totals["fh_drive"],
        "FH Loop":  totals["fh_loop"],
        "FH Smash": totals["fh_smash"],
        "BH Drive": totals["bh_drive"],
        "BH Smash": totals["bh_smash"],
    }

    dominant_stroke = compute_dominant(totals) if totals["total"] > 0 else "—"

    # Recent matches (sessions with mode="match")
    recent_sessions = (
        db.query(GameSession)
        .filter(
            GameSession.player1_id == player_id,
            GameSession.mode == "match",
            GameSession.status == "completed",
        )
        .order_by(GameSession.started_at.desc())
        .limit(10)
        .all()
    )

    recent_matches = []
    for sess in recent_sessions:
        opponent = None
        if sess.player2_id:
            opp_user = db.query(User).filter(User.id == sess.player2_id).first()
            opponent = opp_user.display_name or opp_user.username if opp_user else None
        won = sess.winner_id == player_id if sess.winner_id else None
        recent_matches.append({
            "date": sess.started_at.strftime("%d/%m/%Y") if sess.started_at else "—",
            "opponent": opponent or "Entraînement libre",
            "won": won,
        })

    return {
        "total_sessions": total_sessions,
        "dominant_stroke": dominant_stroke,
        "stroke_distribution": stroke_distribution,
        "recent_matches": recent_matches,
    }


def get_training_vs_match(db: Session, player_id: int) -> Dict:
    def _avg(mode: str) -> Dict:
        rows = (
            db.query(SessionSummary, GameSession)
            .join(GameSession, SessionSummary.session_id == GameSession.id)
            .filter(SessionSummary.player_id == player_id, GameSession.mode == mode)
            .all()
        )
        if not rows:
            return {}
        total = len(rows)
        return {
            "sessions": total,
            "avg_total": sum(r.SessionSummary.total_strokes for r in rows) / total,
            "avg_spm":   sum(r.SessionSummary.strokes_per_min for r in rows) / total,
            "avg_fh_smash_pct": sum(
                r.SessionSummary.fh_smash / (r.SessionSummary.total_strokes or 1) for r in rows
            ) / total,
        }

    return {
        "training": _avg("training"),
        "match": _avg("match"),
    }
