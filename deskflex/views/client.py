from datetime import timedelta

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .. import mapa, qr, rules
from ..db import get_db
from ..security import client_required, login_required
from .auth import validar_password, validar_telefono

bp = Blueprint("client", __name__)

SELECT_RESERVA = """
    SELECT r.*, e.nombre || CASE WHEN r.asiento IS NOT NULL THEN ' · asiento ' || r.asiento ELSE '' END AS espacio,
           e.numero AS esp_numero, e.tipo AS esp_tipo, u.nombre AS cliente,
           EXISTS (SELECT 1 FROM accesos a WHERE a.reserva_id = r.id AND a.resultado = 'autorizado') AS con_acceso
    FROM reservas r JOIN espacios e ON e.id = r.espacio_id JOIN usuarios u ON u.id = r.usuario_id
"""


def qr_url(token: str) -> str:
    return request.host_url.rstrip("/") + url_for("admin.checkin", codigo=token)


def decorar(r):
    """Añade estado visible y QR (SVG) a una fila de reserva."""
    d = dict(r)
    d["estado_clave"], d["estado_txt"] = rules.estado_visible(r, bool(r["con_acceso"]))
    d["qr"] = qr.svg(qr_url(r["token"]), label=f"Código QR de la reserva {r['folio']}")
    return d


@bp.route("/inicio")
@client_required
def inicio():
    db = get_db()
    ahora = rules.now()
    filas = db.execute(SELECT_RESERVA + " WHERE r.usuario_id = ? AND r.estado = 'confirmada' ORDER BY r.fecha, r.hora_inicio",
                       (g.user["id"],)).fetchall()
    proximas = [decorar(r) for r in filas if rules.estado_visible(r, bool(r["con_acceso"]))[0] in ("confirmada", "encurso", "usada")]
    h = ahora.hour
    libres, estados = None, None
    cfg = current_app.config
    if cfg["OPEN_HOUR"] <= h < cfg["CLOSE_HOUR"] and ahora.weekday() not in cfg["CLOSED_WEEKDAYS"]:
        disp = rules.disponibilidad(db, ahora.date().isoformat(), h, h + 1)
        libres = sum(1 for v in disp.values() if v != "ocupado")
        total = len(disp)
        estados = disp
    else:
        total = db.execute("SELECT COUNT(*) c FROM espacios WHERE activo=1").fetchone()["c"]
    espacios = {r["numero"]: dict(r) for r in db.execute("SELECT * FROM espacios WHERE activo = 1")}
    return render_template("client/inicio.html", proxima=proximas[0] if proximas else None,
                           n_proximas=len(proximas), libres=libres, total=total, estados=estados,
                           espacios=espacios, formas=mapa.FORMAS)


@bp.route("/reservar", methods=["GET", "POST"])
@client_required
def reservar():
    db = get_db()
    if request.method == "POST":
        f = request.form
        try:
            num = int(f.get("espacio", ""))
            esp = db.execute("SELECT id FROM espacios WHERE numero = ? AND activo = 1", (num,)).fetchone()
            if not esp:
                raise rules.ReglaError("Selecciona un espacio en el mapa.")
            rid = rules.crear_reserva(db, g.user["id"], esp["id"], f.get("fecha"), f.get("modo"),
                                      f.get("inicio"), f.get("fin"), f.get("asiento", type=int))
        except ValueError:
            flash("Selecciona un espacio en el mapa.", "error")
        except rules.ReglaError as e:
            flash(str(e), "error")
        else:
            folio = db.execute("SELECT folio FROM reservas WHERE id = ?", (rid,)).fetchone()["folio"]
            flash("¡Reserva confirmada! Muestra tu código QR al llegar.", "success")
            return redirect(url_for("client.reserva", folio=folio))
    cfg = current_app.config
    hoy = rules.today()
    # primer día reservable
    d = hoy
    if rules.now().hour >= cfg["CLOSE_HOUR"]:
        d += timedelta(days=1)
    while d.weekday() in cfg["CLOSED_WEEKDAYS"]:
        d += timedelta(days=1)
    espacios = {r["numero"]: dict(r) for r in db.execute("SELECT * FROM espacios WHERE activo = 1")}
    return render_template("client/reservar.html", espacios=espacios, formas=mapa.FORMAS,
                           inicial=d.isoformat(), hoy=hoy.isoformat(),
                           maximo=(hoy + timedelta(days=cfg["MAX_ADVANCE_DAYS"])).isoformat(),
                           cerrados=list(cfg["CLOSED_WEEKDAYS"]),
                           apertura=cfg["OPEN_HOUR"], cierre=cfg["CLOSE_HOUR"])


@bp.route("/mis-reservas")
@client_required
def mis_reservas():
    filas = get_db().execute(SELECT_RESERVA + " WHERE r.usuario_id = ? ORDER BY r.fecha DESC, r.hora_inicio DESC",
                             (g.user["id"],)).fetchall()
    todas = [decorar(r) for r in filas]
    activas = [r for r in todas if r["estado_clave"] in ("confirmada", "encurso", "usada")]
    activas.sort(key=lambda r: (r["fecha"], r["hora_inicio"]))
    historial = [r for r in todas if r["estado_clave"] not in ("confirmada", "encurso", "usada")]
    return render_template("client/mis_reservas.html", activas=activas, historial=historial)


@bp.route("/reservas/<folio>")
@login_required
def reserva(folio):
    r = get_db().execute(SELECT_RESERVA + " WHERE r.folio = ?", (folio.upper(),)).fetchone()
    if not r or (g.user["rol"] != "admin" and r["usuario_id"] != g.user["id"]):
        abort(404)
    return render_template("client/reserva.html", r=decorar(r))


@bp.route("/reservas/<folio>/qr.svg")
@login_required
def reserva_qr(folio):
    r = get_db().execute("SELECT * FROM reservas WHERE folio = ?", (folio.upper(),)).fetchone()
    if not r or (g.user["rol"] != "admin" and r["usuario_id"] != g.user["id"]):
        abort(404)
    resp = Response(qr.svg(qr_url(r["token"]), label=f"QR {r['folio']}"), mimetype="image/svg+xml")
    resp.headers["Content-Disposition"] = f'attachment; filename="DeskFlex-{r["folio"]}.svg"'
    return resp


@bp.route("/reservas/<folio>/cancelar", methods=["POST"])
@client_required
def cancelar(folio):
    db = get_db()
    r = db.execute("SELECT id FROM reservas WHERE folio = ? AND usuario_id = ?", (folio.upper(), g.user["id"])).fetchone()
    if not r:
        abort(404)
    try:
        rules.cancelar_reserva(db, r["id"], g.user["id"])
        flash(f"Cancelamos la reserva {folio.upper()}. El espacio quedó libre.", "success")
    except rules.ReglaError as e:
        flash(str(e), "error")
    return redirect(url_for("client.mis_reservas"))


@bp.route("/perfil")
@login_required
def perfil():
    return render_template("client/perfil.html")


@bp.route("/perfil/editar", methods=["GET", "POST"])
@login_required
def perfil_editar():
    errores, datos = {}, {"nombre": g.user["nombre"], "telefono": g.user["telefono"]}
    if request.method == "POST":
        datos = {"nombre": request.form.get("nombre", "").strip(), "telefono": request.form.get("telefono", "")}
        if len(datos["nombre"]) < 3:
            errores["nombre"] = "Escribe tu nombre completo."
        datos["telefono"], err = validar_telefono(datos["telefono"])
        if err:
            errores["telefono"] = err
        nueva = request.form.get("password_nueva", "")
        if nueva:
            if not check_password_hash(g.user["password_hash"], request.form.get("password_actual", "")):
                errores["password_actual"] = "La contraseña actual no coincide."
            if err := validar_password(nueva):
                errores["password_nueva"] = err
        if not errores:
            db = get_db()
            db.execute("UPDATE usuarios SET nombre = ?, telefono = ? WHERE id = ?", (datos["nombre"], datos["telefono"], g.user["id"]))
            if nueva:
                db.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (generate_password_hash(nueva), g.user["id"]))
            flash("Guardamos los cambios de tu perfil.", "success")
            return redirect(url_for("client.perfil"))
    return render_template("client/perfil_editar.html", datos=datos, errores=errores)
