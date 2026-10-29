import hmac
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, redirect, request, session, url_for, flash

from .db import get_db


def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]


def check_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "La sesión del formulario expiró. Recarga la página e inténtalo de nuevo.")


def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        u = get_db().execute("SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,)).fetchone()
        if u:
            g.user = u
        else:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Inicia sesión para continuar.", "info")
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if g.user["rol"] != "admin":
            abort(403)
        return view(*a, **kw)
    return wrapped


def client_required(view):
    """Pantallas de cliente: un administrador es redirigido a su panel."""
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if g.user["rol"] == "admin":
            return redirect(url_for("admin.dashboard"))
        return view(*a, **kw)
    return wrapped


def safe_next(target: str | None) -> str | None:
    if not target:
        return None
    p = urlparse(target)
    return target if not p.netloc and not p.scheme and target.startswith("/") and not target.startswith("//") else None
