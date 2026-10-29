from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, url_for)

from .. import mapa, rules
from ..db import get_db
from ..security import admin_required
from .auth import validar_telefono
from .client import SELECT_RESERVA

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("")
@admin_required
def dashboard():
    db, cfg = get_db(), current_app.config
    ahora = rules.now()
    hoy = ahora.date().isoformat()
    abierto = cfg["OPEN_HOUR"] <= ahora.hour < cfg["CLOSE_HOUR"] and ahora.weekday() not in cfg["CLOSED_WEEKDAYS"]
    estados = rules.disponibilidad(db, hoy, ahora.hour, ahora.hour + 1) if abierto else None
    total = db.execute("SELECT COUNT(*) c FROM espacios WHERE activo = 1").fetchone()["c"]
    ocupados = sum(1 for v in estados.values() if v == "ocupado") if estados else 0
    agenda = []
    for r in db.execute(SELECT_RESERVA + " WHERE r.fecha = ? AND r.estado = 'confirmada' ORDER BY r.hora_inicio, e.numero", (hoy,)):
        d = dict(r)
        d["estado_clave"], d["estado_txt"] = rules.estado_visible(r, bool(r["con_acceso"]))
        agenda.append(d)
    kpis = dict(
        reservas_hoy=len(agenda),
        ocupados=ocupados, total=total, abierto=abierto,
        accesos_hoy=db.execute("SELECT COUNT(*) c FROM accesos WHERE resultado='autorizado' AND substr(registrado_en,1,10)=?", (hoy,)).fetchone()["c"],
        denegados_hoy=db.execute("SELECT COUNT(*) c FROM accesos WHERE resultado='denegado' AND substr(registrado_en,1,10)=?", (hoy,)).fetchone()["c"],
        clientes=db.execute("SELECT COUNT(*) c FROM usuarios WHERE rol='cliente' AND activo=1").fetchone()["c"],
        pendientes=sum(1 for a in agenda if a["estado_clave"] in ("confirmada", "encurso")),
    )
    espacios = {r["numero"]: dict(r) for r in db.execute("SELECT * FROM espacios WHERE activo = 1")}
    return render_template("admin/dashboard.html", kpis=kpis, agenda=agenda, estados=estados, espacios=espacios,
                           formas=mapa.FORMAS, hora_actual=ahora.hour)


# ---- Reservas --------------------------------------------------------------
@bp.route("/reservas")
@admin_required
def reservas():
    db, cfg = get_db(), current_app.config
    q = request.args.get("q", "").strip()
    ver = request.args.get("ver", "proximas")
    sql, params = SELECT_RESERVA + " WHERE 1=1", []
    if q:
        sql += " AND (r.folio LIKE ? OR u.nombre LIKE ? OR e.nombre LIKE ? OR u.correo LIKE ?)"
        params += [f"%{q}%"] * 4
    if ver == "proximas":
        sql += " AND r.estado = 'confirmada' AND r.fecha >= ?"
        params.append(rules.today().isoformat())
    elif ver == "canceladas":
        sql += " AND r.estado = 'cancelada'"
    sql += " ORDER BY r.fecha " + ("ASC" if ver == "proximas" else "DESC") + ", r.hora_inicio, r.id"
    filas = []
    for r in db.execute(sql, params):
        d = dict(r)
        d["estado_clave"], d["estado_txt"] = rules.estado_visible(r, bool(r["con_acceso"]))
        filas.append(d)
    espacios = db.execute("SELECT numero, nombre FROM espacios WHERE activo = 1 ORDER BY numero").fetchall()
    return render_template("admin/reservas.html", filas=filas, q=q, ver=ver, espacios=espacios,
                           apertura=cfg["OPEN_HOUR"], cierre=cfg["CLOSE_HOUR"])


@bp.route("/reservas/<int:rid>/editar", methods=["POST"])
@admin_required
def reserva_editar(rid):
    db, f = get_db(), request.form
    try:
        esp = db.execute("SELECT id FROM espacios WHERE numero = ?", (f.get("espacio", type=int),)).fetchone()
        if not esp:
            raise rules.ReglaError("Elige un espacio válido.")
        rules.editar_reserva(db, rid, esp["id"], f.get("fecha"), f.get("modo"), f.get("inicio"), f.get("fin"))
        flash("Reserva actualizada.", "success")
    except rules.ReglaError as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("admin.reservas"))


@bp.route("/reservas/<int:rid>/cancelar", methods=["POST"])
@admin_required
def reserva_cancelar(rid):
    try:
        rules.cancelar_reserva(get_db(), rid)
        flash("Reserva cancelada. El espacio quedó libre.", "success")
    except rules.ReglaError as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("admin.reservas"))


# ---- Usuarios --------------------------------------------------------------
@bp.route("/usuarios")
@admin_required
def usuarios():
    q = request.args.get("q", "").strip()
    sql = """SELECT u.*, (SELECT COUNT(*) FROM reservas r WHERE r.usuario_id = u.id AND r.estado='confirmada') AS n_reservas
             FROM usuarios u WHERE 1=1"""
    params = []
    if q:
        sql += " AND (u.nombre LIKE ? OR u.correo LIKE ? OR u.telefono LIKE ?)"
        params = [f"%{q}%"] * 3
    return render_template("admin/usuarios.html", filas=get_db().execute(sql + " ORDER BY u.rol, u.nombre", params).fetchall(), q=q)


@bp.route("/usuarios/<int:uid>/editar", methods=["POST"])
@admin_required
def usuario_editar(uid):
    db, f = get_db(), request.form
    u = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
    if not u:
        abort(404)
    nombre = f.get("nombre", "").strip()
    tel, err = validar_telefono(f.get("telefono", ""))
    activo = 1 if f.get("activo") == "1" else 0
    if len(nombre) < 3 or err:
        flash(err or "Escribe el nombre completo.", "error")
    elif uid == g.user["id"] and not activo:
        flash("No puedes desactivar tu propia cuenta.", "error")
    else:
        db.execute("UPDATE usuarios SET nombre=?, telefono=?, activo=? WHERE id=?", (nombre, tel, activo, uid))
        flash("Usuario actualizado.", "success")
    return redirect(url_for("admin.usuarios"))


@bp.route("/usuarios/<int:uid>/eliminar", methods=["POST"])
@admin_required
def usuario_eliminar(uid):
    db = get_db()
    u = db.execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()
    if not u:
        abort(404)
    if u["rol"] == "admin":
        flash("Las cuentas de administrador no se eliminan desde aquí.", "error")
    else:
        db.execute("DELETE FROM usuarios WHERE id = ?", (uid,))
        flash(f"Eliminamos a {u['nombre']} y sus reservas.", "success")
    return redirect(url_for("admin.usuarios"))


# ---- Check-in --------------------------------------------------------------
@bp.route("/checkin")
@admin_required
def checkin():
    db = get_db()
    fecha = request.args.get("fecha") or rules.today().isoformat()
    esp = request.args.get("espacio", type=int)
    sql = """SELECT a.*, u.nombre AS cliente, e.nombre AS espacio, r.folio
             FROM accesos a LEFT JOIN reservas r ON r.id = a.reserva_id
             LEFT JOIN usuarios u ON u.id = r.usuario_id LEFT JOIN espacios e ON e.id = r.espacio_id
             WHERE substr(a.registrado_en, 1, 10) = ?"""
    params = [fecha]
    if esp:
        sql += " AND e.numero = ?"
        params.append(esp)
    filas = db.execute(sql + " ORDER BY a.registrado_en DESC", params).fetchall()
    espacios = db.execute("SELECT numero, nombre FROM espacios WHERE activo = 1 ORDER BY numero").fetchall()
    previo = None
    codigo = request.args.get("codigo")
    if codigo:
        c = rules.extraer_codigo(codigo)
        col = "r.folio" if c.upper().startswith("DF-") else "r.token"
        r = db.execute(SELECT_RESERVA + f" WHERE {col} = ?", (c.upper() if col == "r.folio" else c,)).fetchone()
        previo = dict(r) if r else {}
        if r:
            previo["estado_clave"], previo["estado_txt"] = rules.estado_visible(r, bool(r["con_acceso"]))
        previo["codigo"] = c
    return render_template("admin/checkin.html", filas=filas, fecha=fecha, esp=esp, espacios=espacios, previo=previo,
                           early=current_app.config["CHECKIN_EARLY_MIN"])


@bp.route("/checkin/validar", methods=["POST"])
@admin_required
def checkin_validar():
    res = rules.validar_acceso(get_db(), request.form.get("codigo", ""), g.user["id"])
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(res)
    flash(f"Acceso autorizado: {res['cliente']} · {res['espacio']}." if res["ok"] else f"Acceso denegado. {res['motivo']}",
          "success" if res["ok"] else "error")
    return redirect(url_for("admin.checkin"))
