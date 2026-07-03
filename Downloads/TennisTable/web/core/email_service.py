"""Async email service via SMTP. Falls back to log stub if SMTP not configured."""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from web.core.config import settings

logger = logging.getLogger("email_service")

# ── Shared layout ─────────────────────────────────────────────────────────────

def _base_template(preheader: str, header_emoji: str, header_title: str,
                   header_subtitle: str, body: str, cta_url: str = "",
                   cta_label: str = "") -> str:
    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
        <tr>
          <td align="center" style="padding:8px 0 32px;">
            <a href="{cta_url}"
               style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);
                      color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;
                      padding:16px 40px;border-radius:12px;letter-spacing:0.3px;
                      box-shadow:0 4px 15px rgba(99,102,241,0.4);">
              {cta_label}
            </a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="x-apple-disable-message-reformatting">
  <title>TT Tracker</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

  <!-- preheader invisible -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
    {preheader}&nbsp;&#847;&nbsp;&#847;&nbsp;&#847;&nbsp;&#847;&nbsp;&#847;
  </div>

  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#f4f4f8;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;">

          <!-- ── Logo bar ── -->
          <tr>
            <td align="center" style="padding-bottom:24px;">
              <span style="font-size:28px;">🏓</span>
              <span style="font-size:20px;font-weight:800;color:#1e1b4b;letter-spacing:-0.5px;vertical-align:middle;margin-left:8px;">TT Tracker</span>
            </td>
          </tr>

          <!-- ── Card ── -->
          <tr>
            <td style="background:#ffffff;border-radius:20px;
                       box-shadow:0 4px 30px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header gradient -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);
                             padding:48px 40px 40px;text-align:center;border-radius:20px 20px 0 0;">
                    <div style="font-size:52px;margin-bottom:16px;line-height:1;">{header_emoji}</div>
                    <h1 style="margin:0 0 8px;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">{header_title}</h1>
                    <p style="margin:0;color:rgba(255,255,255,0.8);font-size:15px;">{header_subtitle}</p>
                  </td>
                </tr>
              </table>

              <!-- Body -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="padding:40px 40px 8px;">
                    {body}
                  </td>
                </tr>
                {cta_block}
              </table>

            </td>
          </tr>

          <!-- ── Footer ── -->
          <tr>
            <td style="padding:32px 0 8px;text-align:center;">
              <p style="margin:0 0 8px;color:#9ca3af;font-size:13px;">
                TT Tracker — Ping-Pong Connecté &copy; 2026
              </p>
              <p style="margin:0;font-size:12px;color:#d1d5db;">
                Vous recevez cet email car vous avez un compte sur
                <a href="http://localhost:8000" style="color:#6366f1;text-decoration:none;">TT Tracker</a>.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #f0f0f5;margin:24px 0;">'


def _feature_row(emoji: str, title: str, desc: str) -> str:
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;">
      <tr>
        <td width="48" valign="top">
          <div style="width:40px;height:40px;background:#eef2ff;border-radius:10px;
                      text-align:center;line-height:40px;font-size:20px;">{emoji}</div>
        </td>
        <td style="padding-left:14px;" valign="top">
          <p style="margin:0 0 2px;font-weight:700;color:#1e1b4b;font-size:14px;">{title}</p>
          <p style="margin:0;color:#6b7280;font-size:13px;line-height:1.5;">{desc}</p>
        </td>
      </tr>
    </table>"""


def _info_box(text: str, color: str = "#eef2ff", border: str = "#6366f1") -> str:
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="background:{color};border-left:4px solid {border};
                   border-radius:8px;padding:16px 20px;margin:16px 0;">
          <p style="margin:0;color:#374151;font-size:14px;line-height:1.6;">{text}</p>
        </td>
      </tr>
    </table>"""


# ── Send helpers ──────────────────────────────────────────────────────────────

def _send_sync(to: str, subject: str, html: str) -> None:
    cfg = settings.email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"TT Tracker <{cfg.smtp_from}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(cfg.smtp_user, cfg.smtp_password)
        smtp.sendmail(cfg.smtp_from, to, msg.as_string())


async def send_email(to: str, subject: str, html: str) -> None:
    cfg = settings.email
    if not cfg.smtp_host or not cfg.smtp_user:
        logger.info("[EMAIL STUB] To=%s Subject=%s", to, subject)
        return
    try:
        await asyncio.to_thread(_send_sync, to, subject, html)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)


# ── Templates ─────────────────────────────────────────────────────────────────

async def send_welcome(to: str, name: str) -> None:
    app_url = settings.email.app_url

    body = f"""
    <p style="margin:0 0 20px;font-size:16px;color:#374151;line-height:1.7;">
      Bonjour <strong style="color:#1e1b4b;">{name}</strong>,
    </p>
    <p style="margin:0 0 28px;font-size:15px;color:#6b7280;line-height:1.7;">
      Votre compte TT Tracker est prêt. Commencez dès maintenant à analyser
      votre jeu, suivre votre progression et affronter vos adversaires.
    </p>

    {_feature_row("📊", "Analyse en temps réel", "Visualisez chaque coup — Drive, Smash, Loop — dès la première session.")}
    {_feature_row("🏆", "Classement ELO", "Affrontez d'autres joueurs et grimpez dans le leaderboard.")}
    {_feature_row("🎾", "Tournois", "Créez ou rejoignez des tournois et suivez votre bracket en direct.")}

    {_divider()}
    <p style="margin:0 0 8px;font-size:14px;color:#9ca3af;text-align:center;">
      Prêt à jouer ?
    </p>
    """

    html = _base_template(
        preheader=f"Bienvenue {name} ! Votre compte TT Tracker est actif.",
        header_emoji="🏓",
        header_title=f"Bienvenue, {name} !",
        header_subtitle="Votre compte est prêt — le jeu peut commencer.",
        body=body,
        cta_url=f"{app_url}/dashboard",
        cta_label="Accéder à mon dashboard →",
    )
    await send_email(to, "🏓 Bienvenue sur TT Tracker !", html)


async def send_reset(to: str, token: str) -> None:
    app_url = settings.email.app_url
    reset_url = f"{app_url}/reset-password?token={token}"

    body = f"""
    <p style="margin:0 0 20px;font-size:16px;color:#374151;line-height:1.7;">
      Vous avez demandé la réinitialisation de votre mot de passe TT Tracker.
    </p>

    {_info_box("⏱️&nbsp; Ce lien est valable <strong>1 heure</strong>. Après expiration, vous devrez faire une nouvelle demande.", color="#fff7ed", border="#f59e0b")}

    <p style="margin:24px 0 8px;font-size:15px;color:#6b7280;line-height:1.7;">
      Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe :
    </p>

    {_divider()}

    <p style="margin:16px 0 4px;font-size:12px;color:#9ca3af;">
      Vous n'avez pas fait cette demande ? Ignorez simplement cet email — votre compte reste sécurisé.
    </p>
    """

    html = _base_template(
        preheader="Réinitialisez votre mot de passe TT Tracker — lien valable 1 heure.",
        header_emoji="🔑",
        header_title="Réinitialisation du mot de passe",
        header_subtitle="Une demande de réinitialisation a été effectuée.",
        body=body,
        cta_url=reset_url,
        cta_label="Choisir un nouveau mot de passe →",
    )
    await send_email(to, "🔑 Réinitialisation de votre mot de passe — TT Tracker", html)


async def send_tournament_start(to: str, name: str, tournament_name: str = "Tournoi") -> None:
    app_url = settings.email.app_url

    body = f"""
    <p style="margin:0 0 20px;font-size:16px;color:#374151;line-height:1.7;">
      Bonjour <strong style="color:#1e1b4b;">{name}</strong>,
    </p>
    <p style="margin:0 0 24px;font-size:15px;color:#6b7280;line-height:1.7;">
      Le tournoi auquel vous participez vient d'être lancé. Consultez le bracket
      pour découvrir vos adversaires et planifier vos matchs.
    </p>

    {_info_box(f'🏆&nbsp; <strong>{tournament_name}</strong> est maintenant en cours. Bonne chance !', color="#f0fdf4", border="#22c55e")}

    {_divider()}

    {_feature_row("📋", "Consultez le bracket", "Découvrez l'arbre du tournoi et vos prochains adversaires.")}
    {_feature_row("⚡", "Résultats en direct", "Les scores sont mis à jour en temps réel après chaque match.")}

    <p style="margin:24px 0 8px;font-size:14px;color:#9ca3af;text-align:center;">
      Que le meilleur gagne !
    </p>
    """

    html = _base_template(
        preheader=f"Le tournoi {tournament_name} a démarré — consultez votre bracket.",
        header_emoji="🏆",
        header_title="Le tournoi a démarré !",
        header_subtitle=f"{tournament_name} — Que le meilleur gagne.",
        body=body,
        cta_url=f"{app_url}/tournaments",
        cta_label="Voir mon bracket →",
    )
    await send_email(to, f"🏆 {tournament_name} a démarré — TT Tracker", html)
