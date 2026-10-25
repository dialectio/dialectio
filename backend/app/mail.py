"""Emails to members: confirm the address, set a new password, sign in with a link (and the
weekly report to the project mailbox, app/report.py).

Sent through Brevo's transactional API (free plan: 300 emails a day) from MAIL_FROM. Without
BREVO_API_KEY, or with MAIL_TO_LOG=true (local testing with made-up addresses), the email is
written to the log instead, link included.
"""

import html
import logging

import httpx2

from app.config import settings

log = logging.getLogger("dialectio.mail")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"

# purpose -> locale -> (subject, text before the button, button, text after it)
TEXTS: dict[str, dict[str, tuple[str, str, str, str]]] = {
    "verify": {
        "uk": (
            "Підтвердіть пошту на Dialectio",
            "Вітаємо на Dialectio! Підтвердіть, що це ваша адреса пошти:",
            "Підтвердити пошту",
            "Посилання діє 3 дні. Якщо ви не реєструвалися на Dialectio, "
            "просто ігноруйте цей лист.",
        ),
        "en": (
            "Confirm your email on Dialectio",
            "Welcome to Dialectio! Please confirm that this email address is yours:",
            "Confirm email",
            "The link works for 3 days. If you didn't sign up for Dialectio, "
            "just ignore this email.",
        ),
        "pl": (
            "Potwierdź e-mail w Dialectio",
            "Witamy w Dialectio! Potwierdź, że to Twój adres e-mail:",
            "Potwierdź e-mail",
            "Link działa 3 dni. Jeśli nie zakładałeś konta w Dialectio, zignoruj tę wiadomość.",
        ),
        "de": (
            "Bestätigen Sie Ihre E-Mail-Adresse bei Dialectio",
            "Willkommen bei Dialectio! Bitte bestätigen Sie, "
            "dass diese E-Mail-Adresse Ihnen gehört:",
            "E-Mail bestätigen",
            "Der Link gilt 3 Tage. Wenn Sie sich nicht bei Dialectio registriert haben, "
            "ignorieren Sie diese E-Mail einfach.",
        ),
        "es": (
            "Confirma tu correo en Dialectio",
            "¡Bienvenido a Dialectio! Confirma que esta dirección de correo es tuya:",
            "Confirmar correo",
            "El enlace funciona 3 días. Si no te registraste en Dialectio, ignora este mensaje.",
        ),
        "fr": (
            "Confirmez votre e-mail sur Dialectio",
            "Bienvenue sur Dialectio ! Confirmez que cette adresse e-mail est bien la vôtre :",
            "Confirmer l'e-mail",
            "Le lien est valable 3 jours. Si vous ne vous êtes pas inscrit sur Dialectio, "
            "ignorez simplement ce message.",
        ),
    },
    "reset": {
        "uk": (
            "Новий пароль для Dialectio",
            "Хтось (сподіваємося, ви) попросив змінити пароль до акаунта Dialectio:",
            "Задати новий пароль",
            "Посилання діє годину. Якщо ви не просили змінити пароль, ігноруйте цей лист: "
            "старий пароль залишиться.",
        ),
        "en": (
            "A new password for Dialectio",
            "Someone (hopefully you) asked to change the password of your Dialectio account:",
            "Set a new password",
            "The link works for an hour. If you didn't ask for it, ignore this email: "
            "your password stays the same.",
        ),
        "pl": (
            "Nowe hasło do Dialectio",
            "Ktoś (mamy nadzieję, że Ty) poprosił o zmianę hasła do konta Dialectio:",
            "Ustaw nowe hasło",
            "Link działa godzinę. Jeśli nie prosiłeś o zmianę, zignoruj tę wiadomość: "
            "hasło pozostanie bez zmian.",
        ),
        "de": (
            "Neues Passwort für Dialectio",
            "Jemand (hoffentlich Sie) möchte das Passwort Ihres Dialectio-Kontos ändern:",
            "Neues Passwort festlegen",
            "Der Link gilt eine Stunde. Wenn Sie das nicht angefordert haben, ignorieren Sie "
            "diese E-Mail: Ihr Passwort bleibt unverändert.",
        ),
        "es": (
            "Nueva contraseña para Dialectio",
            "Alguien (esperamos que tú) pidió cambiar la contraseña de tu cuenta de Dialectio:",
            "Crear una contraseña nueva",
            "El enlace funciona una hora. Si no lo pediste, ignora este mensaje: "
            "tu contraseña no cambia.",
        ),
        "fr": (
            "Nouveau mot de passe pour Dialectio",
            "Quelqu'un (vous, nous l'espérons) a demandé à changer le mot de passe de votre "
            "compte Dialectio :",
            "Choisir un nouveau mot de passe",
            "Le lien est valable une heure. Si vous n'avez rien demandé, ignorez ce message : "
            "votre mot de passe reste le même.",
        ),
    },
    "login": {
        "uk": (
            "Вхід на Dialectio",
            "Щоб увійти на Dialectio, натисніть кнопку:",
            "Увійти",
            "Посилання діє 15 хвилин і спрацює один раз. Якщо ви не намагалися увійти, "
            "ігноруйте цей лист.",
        ),
        "en": (
            "Sign in to Dialectio",
            "To sign in to Dialectio, press the button:",
            "Sign in",
            "The link works for 15 minutes, once. If you didn't try to sign in, ignore this email.",
        ),
        "pl": (
            "Logowanie do Dialectio",
            "Aby zalogować się do Dialectio, naciśnij przycisk:",
            "Zaloguj się",
            "Link działa 15 minut i tylko raz. Jeśli nie próbowałeś się logować, "
            "zignoruj tę wiadomość.",
        ),
        "de": (
            "Anmeldung bei Dialectio",
            "Um sich bei Dialectio anzumelden, klicken Sie auf die Schaltfläche:",
            "Anmelden",
            "Der Link gilt 15 Minuten und nur einmal. Wenn Sie sich nicht anmelden wollten, "
            "ignorieren Sie diese E-Mail.",
        ),
        "es": (
            "Entrar en Dialectio",
            "Para entrar en Dialectio, pulsa el botón:",
            "Entrar",
            "El enlace funciona 15 minutos y una sola vez. Si no intentaste entrar, "
            "ignora este mensaje.",
        ),
        "fr": (
            "Connexion à Dialectio",
            "Pour vous connecter à Dialectio, appuyez sur le bouton :",
            "Se connecter",
            "Le lien est valable 15 minutes, une seule fois. Si vous n'avez pas essayé de vous "
            "connecter, ignorez ce message.",
        ),
    },
}


def render(purpose: str, locale: str, link: str) -> tuple[str, str, str]:
    """Subject, plain text and HTML of an email with one button."""
    subject, before, button, after = TEXTS[purpose].get(locale, TEXTS[purpose]["en"])
    text = f"{before}\n\n{link}\n\n{after}\n\n— Dialectio, https://dialectio.org\n"
    url = html.escape(link, quote=True)
    body = f"""<div style="font-family:system-ui,sans-serif;max-width:480px;color:#1f1f1f">
<p style="font-size:20px;font-weight:600;color:#6d28d9">Dialectio</p>
<p>{html.escape(before)}</p>
<p><a href="{url}" style="display:inline-block;background:#7c3aed;color:#fff;padding:10px 18px;
border-radius:8px;text-decoration:none;font-weight:600">{html.escape(button)}</a></p>
<p style="font-size:13px;color:#555">{html.escape(after)}</p>
<p style="font-size:12px;color:#888;word-break:break-all">{url}</p>
</div>"""
    return subject, text, body


def deliver(to: str, subject: str, text: str, body: str | None, tag: str) -> bool:
    """Send one email through Brevo (or write it to the log); False if it failed."""
    if not settings.brevo_api_key or settings.mail_to_log:
        log.warning("Email not sent (written to the log) to %s: %s\n%s", to, subject, text)
        return True
    message = {
        "sender": {"name": "Dialectio", "email": settings.mail_from},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
        "tags": [tag],
    }
    if body:
        message["htmlContent"] = body
    try:
        response = httpx2.post(
            BREVO_URL,
            headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
            json=message,
            timeout=20,
        )
        response.raise_for_status()
    except httpx2.HTTPError:
        log.exception("Email to %s (%s) failed", to, tag)
        return False
    return True


def send(to: str, purpose: str, locale: str, link: str) -> None:
    """Send one email with a link (run as a background task: the request does not wait)."""
    subject, text, body = render(purpose, locale, link)
    deliver(to, subject, text, body, purpose)
