"""Cloudflare Turnstile: a check that a form was sent by a person, not a script.

The page's widget gives a one-time token; the API asks Cloudflare whether it is genuine. Off
while TURNSTILE_SECRET is empty (development, tests). If Cloudflare can't be reached, the
request goes through: the per-IP limits still apply, and nobody gets locked out.
"""

import logging

import httpx2
from fastapi import HTTPException, Request, status

from app.config import settings

log = logging.getLogger("dialectio.turnstile")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def require_human(request: Request, token: str) -> None:
    """Refuse the request (400 "captcha") unless its Turnstile token is genuine."""
    if not settings.turnstile_secret:
        return
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "captcha")
    try:
        response = httpx2.post(
            VERIFY_URL,
            data={
                "secret": settings.turnstile_secret,
                "response": token,
                "remoteip": request.client.host if request.client else "",
            },
            timeout=10,
        )
        response.raise_for_status()
        passed = response.json().get("success") is True
    except (httpx2.HTTPError, ValueError):
        log.exception("Turnstile check failed, letting the request through")
        return
    if not passed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "captcha")
