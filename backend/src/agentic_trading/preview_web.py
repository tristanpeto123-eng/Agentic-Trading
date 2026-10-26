"""Opt-in Railway/iPhone preview: same-origin SPA plus one-time CEO setup.

The setup token is an environment secret, never committed to this repository.
No order placement, broker connection, training promotion or trading activation is
exposed by the preview. Existing API permission gates remain unchanged.
"""
from __future__ import annotations

from hmac import compare_digest
from pathlib import Path
from threading import Lock
import os
import re

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from agentic_trading.auth import password_hash
from agentic_trading.storage import CEO


class PreviewCEOSetup(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)
    setup_token: str = Field(min_length=1, max_length=256)


SETUP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Agentic Trading — CEO setup</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui,-apple-system,sans-serif; }
    body { margin: 0; background: #0b1220; color: #e6edf7; min-height: 100vh;
           display: grid; place-items: center; padding: 20px; box-sizing: border-box; }
    main { width: min(100%,440px); background: #142034; border: 1px solid #31415c;
           border-radius: 18px; padding: 26px; box-sizing: border-box; }
    h1 { font-size: 1.6rem; margin: 0 0 7px; }
    p { color: #b9c8db; line-height: 1.5; }
    label { display: block; font-weight: 600; margin-top: 16px; }
    input { width: 100%; box-sizing: border-box; padding: 13px; margin-top: 6px;
            border-radius: 9px; border: 1px solid #657795; background: #080f1c; color: white;
            font-size: 16px; }
    button { margin-top: 22px; padding: 15px; width: 100%; border: 0; border-radius: 9px;
             background: #4a95e7; color: #05172b; font-size: 16px; font-weight: 700; }
    button:disabled { opacity: .6; }
    #message { min-height: 24px; }
  </style>
</head>
<body><main>
  <h1>Create your CEO login</h1>
  <p>One-time setup for the private Agentic Trading research preview. Your setup code is
     stored in Railway, not in GitHub. Trading will remain disabled.</p>
  <form id="setup">
    <label for="email">Email</label>
    <input id="email" type="email" autocomplete="username" required maxlength="254">
    <label for="password">Choose a password (12+ characters)</label>
    <input id="password" type="password" autocomplete="new-password" required minlength="12">
    <label for="confirm">Confirm password</label>
    <input id="confirm" type="password" autocomplete="new-password" required minlength="12">
    <label for="token">One-time Railway setup code</label>
    <input id="token" type="password" autocomplete="off" required>
    <button id="submit" type="submit">Create CEO account</button>
    <p id="message" role="status" aria-live="polite"></p>
  </form>
</main>
<script>
  document.getElementById('setup').addEventListener('submit', async function (event) {
    event.preventDefault();
    const button = document.getElementById('submit');
    const message = document.getElementById('message');
    const password = document.getElementById('password').value;
    if (password !== document.getElementById('confirm').value) {
      message.textContent = 'Passwords do not match.';
      return;
    }
    button.disabled = true;
    message.textContent = 'Creating your account…';
    try {
      const response = await fetch('/v1/auth/setup', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          email: document.getElementById('email').value,
          password: password, setup_token: document.getElementById('token').value
        })
      });
      if (!response.ok) {
        const data = await response.json();
        throw Error(typeof data.detail === 'string' ? data.detail : 'Setup failed.');
      }
      document.getElementById('token').value = '';
      document.getElementById('password').value = '';
      document.getElementById('confirm').value = '';
      message.textContent = 'Account created. Opening your login…';
      window.location.replace('/');
    } catch (error) {
      message.textContent = error.message || 'Setup failed.';
    } finally { button.disabled = false; }
  });
</script>
</body></html>
"""


def install_preview_routes(api: FastAPI, cfg, session_factory, limiter) -> None:
    """Add only if an explicit built SPA directory is configured.

    The preview setup endpoint exists solely with APP_ENV=production and the
    WEB_DIST_DIR opt-in. A supplied secret cannot create a second CEO.
    """
    dist_str = os.getenv("WEB_DIST_DIR", "").strip()
    if not dist_str:
        return
    dist = Path(dist_str).resolve()
    if not (dist / "index.html").is_file() or not (dist / "assets").is_dir():
        raise RuntimeError("WEB_DIST_DIR must point to a built frontend with index.html/assets")
    if cfg.environment != "production":
        raise RuntimeError("WEB_DIST_DIR requires APP_ENV=production")

    setup_lock = Lock()
    setup_secret = os.getenv("PREVIEW_SETUP_TOKEN", "")

    def is_initialised() -> bool:
        with session_factory() as session:
            return session.scalar(select(CEO.id).limit(1)) is not None

    @api.get("/setup", include_in_schema=False)
    def setup_page():
        if is_initialised():
            return RedirectResponse(url="/", status_code=303)
        if len(setup_secret) < 40:
            raise HTTPException(status_code=503, detail="Preview setup has not been configured")
        return HTMLResponse(
            SETUP_HTML,
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                    "script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; "
                    "base-uri 'none'; frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api.post("/v1/auth/setup", status_code=status.HTTP_201_CREATED)
    def create_initial_ceo(payload: PreviewCEOSetup, request: Request):
        if len(setup_secret) < 40:
            raise HTTPException(status_code=404, detail="Preview setup is disabled")
        origin = (request.headers.get("origin") or "").rstrip("/")
        if origin not in cfg.allowed_origins or request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(status_code=403, detail="Origin not permitted")
        ip = request.client.host if request.client else "unknown"
        limiter.check("ceo_setup:" + ip)
        with setup_lock:
            with session_factory() as session:
                if session.scalar(select(CEO.id).limit(1)) is not None:
                    raise HTTPException(status_code=409, detail="CEO account already initialised")
                if not compare_digest(payload.setup_token, setup_secret):
                    raise HTTPException(status_code=403, detail="Invalid setup code")
                email = payload.email.strip().casefold()
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                    raise HTTPException(status_code=422, detail="Enter a valid email")
                user = CEO(email=email, password_hash=password_hash(payload.password))
                session.add(user)
                try:
                    session.commit()
                except IntegrityError as exc:
                    session.rollback()
                    raise HTTPException(status_code=409, detail="Setup conflict") from exc
                return {"created": True, "next": "/"}

    api.mount("/assets", StaticFiles(directory=dist / "assets"), name="preview_assets")

    def index():
        return FileResponse(
            dist / "index.html",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @api.get("/", include_in_schema=False)
    def home():
        return index()

    @api.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        # Never disguise API errors or unknown static files as successful HTML.
        if path == "health" or path.startswith(("v1/", "docs", "openapi", "redoc")):
            raise HTTPException(status_code=404, detail="Not found")
        if "." in Path(path).name or path.startswith("/"):
            raise HTTPException(status_code=404, detail="Not found")
        return index()
