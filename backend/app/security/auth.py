"""Sessão, usuário atual e proteção CSRF (sem dependências extras).

- Senha: hash scrypt do Werkzeug (nunca guardamos a senha).
- Sessão: cookie assinado do Flask (HttpOnly, SameSite=Lax; Secure em produção).
- CSRF: token por sessão em todo POST (campo `csrf_token` ou header `X-CSRF-Token`).
"""
from __future__ import annotations

import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from app.extensions import db
from app.models import User

SESSION_KEY = "uid"


def current_user() -> User | None:
    uid = session.get(SESSION_KEY)
    if g.get("user_uid", object()) != uid:  # cache por requisição, atrelado à sessão atual
        g.user_uid = uid
        g.user = db.session.get(User, uid) if uid else None
        if uid and g.user is None:  # conta excluída em outra aba
            session.pop(SESSION_KEY, None)
    return g.user


def login_user(user: User, remember: bool = False) -> None:
    session.clear()  # evita fixação de sessão
    session[SESSION_KEY] = user.id
    session.permanent = remember
    csrf_token()


def logout_user() -> None:
    session.clear()
    g.pop("user", None)
    g.pop("user_uid", None)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("web.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)

    return wrapper


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf() -> None:
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("csrf", "")
    # vazio nunca vale (sem sessão, "" == "" passaria)
    if not sent or not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="Sessão expirada. Recarregue a página e tente de novo.")


def safe_next(target: str | None) -> str | None:
    """Só aceita redirecionar para caminhos internos (evita open redirect)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None
