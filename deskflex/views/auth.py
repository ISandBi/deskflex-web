import re
import time

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from ..security import safe_next

bp = Blueprint("auth", __name__)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_intentos: dict[str, list[float]] = {}  # limitador sencillo en memoria (por IP + correo)


def _bloqueado(clave: str) -> bool:
    ahora = time.time()
    recientes = [t for t in _intentos.get(clave, []) if ahora - t < 300]
    _intentos[clave] = recientes
    return len(recientes) >= 6


def _home_for(u):
    return url_for("admin.dashboard") if u["rol"] == "admin" else url_for("client.inicio")


def _iniciar_sesion(u):
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True


def validar_password(pwd: str) -> str | None:
    if len(pwd) < 8 or not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
        return "La contraseña debe tener al menos 8 caracteres, con letras y números."
    return None


def validar_telefono(tel: str) -> tuple[str, str | None]:
    limpio = re.sub(r"[\s\-().]", "", tel or "")
    if not re.fullmatch(r"\d{10}", limpio):
        return limpio, "Escribe tu teléfono a 10 dígitos."
    return limpio, None


@bp.route("/")
def raiz():
    if g.user:
        return redirect(_home_for(g.user))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(_home_for(g.user))
    correo = ""
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        pwd = request.form.get("password", "")
        clave = f"{request.remote_addr}|{correo}"
        if _bloqueado(clave):
            flash("Demasiados intentos. Espera unos minutos e inténtalo de nuevo.", "error")
        else:
            u = get_db().execute("SELECT * FROM usuarios WHERE correo = ?", (correo,)).fetchone()
            if u and check_password_hash(u["password_hash"], pwd):
                if not u["activo"]:
                    flash("Tu cuenta está inactiva. Contacta a recepción.", "error")
                else:
                    _iniciar_sesion(u)
                    return redirect(safe_next(request.args.get("next")) or _home_for(u))
            else:
                _intentos.setdefault(clave, []).append(time.time())
                flash("Correo o contraseña incorrectos.", "error")
    return render_template("auth/login.html", correo=correo)


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if g.user:
        return redirect(_home_for(g.user))
    datos = {"nombre": "", "correo": "", "telefono": ""}
    errores = {}
    if request.method == "POST":
        datos = {k: request.form.get(k, "").strip() for k in datos}
        pwd = request.form.get("password", "")
        datos["correo"] = datos["correo"].lower()
        if len(datos["nombre"]) < 3:
            errores["nombre"] = "Escribe tu nombre completo."
        if not _EMAIL.match(datos["correo"]):
            errores["correo"] = "Escribe un correo válido."
        datos["telefono"], err = validar_telefono(datos["telefono"])
        if err:
            errores["telefono"] = err
        if err := validar_password(pwd):
            errores["password"] = err
        db = get_db()
        if "correo" not in errores and db.execute("SELECT 1 FROM usuarios WHERE correo = ?", (datos["correo"],)).fetchone():
            errores["correo"] = "Ya existe una cuenta con ese correo."
        if not errores:
            cur = db.execute(
                "INSERT INTO usuarios (nombre, correo, telefono, password_hash) VALUES (?,?,?,?)",
                (datos["nombre"], datos["correo"], datos["telefono"], generate_password_hash(pwd)))
            u = db.execute("SELECT * FROM usuarios WHERE id = ?", (cur.lastrowid,)).fetchone()
            _iniciar_sesion(u)
            flash(f"¡Bienvenido a DeskFlex, {datos['nombre'].split()[0]}! Tu cuenta está lista.", "success")
            return redirect(url_for("client.inicio"))
    return render_template("auth/registro.html", datos=datos, errores=errores)


@bp.route("/salir", methods=["POST"])
def salir():
    session.clear()
    flash("Cerraste sesión. ¡Hasta pronto!", "info")
    return redirect(url_for("auth.login"))
