"""Reglas de negocio: ventanas de reserva, disponibilidad sin duplicados y validación de acceso."""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, time, timedelta
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class ReglaError(Exception):
    """Error de negocio con un mensaje apto para mostrar al usuario."""


# ---------- tiempo -----------------------------------------------------------
def now() -> datetime:
    try:
        tz = ZoneInfo(current_app.config["TIMEZONE"])
    except ZoneInfoNotFoundError:      # Windows sin tzdata: México no usa horario de verano (UTC-6)
        tz = timezone(timedelta(hours=-6))
    return datetime.now(tz).replace(tzinfo=None, microsecond=0)


def today() -> date:
    return now().date()


def fmt_hora(h: int) -> str:
    h = h % 24
    suf = "am" if h < 12 else "pm"
    return f"{(h % 12) or 12}:00 {suf}"


def fmt_rango(ini: int, fin: int) -> str:
    return f"{fmt_hora(ini)} – {fmt_hora(fin)}"


def fmt_fecha(d: date | str, corta: bool = False) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    if corta:
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fmt_fecha_dia(d: date | str) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def _dt(fecha: str, hora: int) -> datetime:
    return datetime.combine(date.fromisoformat(fecha), time(hora % 24))


# ---------- validación de ventanas ------------------------------------------
def validar_ventana(fecha_s: str, modo: str, inicio, fin) -> tuple[str, str, int, int]:
    cfg = current_app.config
    try:
        d = date.fromisoformat(str(fecha_s))
    except ValueError:
        raise ReglaError("Elige una fecha válida.")
    if modo not in ("hora", "dia"):
        raise ReglaError("Elige si reservas por hora o por día completo.")
    if modo == "dia":
        inicio, fin = cfg["OPEN_HOUR"], cfg["CLOSE_HOUR"]
    else:
        try:
            inicio, fin = int(inicio), int(fin)
        except (TypeError, ValueError):
            raise ReglaError("Elige un horario válido.")
        if inicio < cfg["OPEN_HOUR"] or fin > cfg["CLOSE_HOUR"] or fin <= inicio:
            raise ReglaError(f"El horario debe estar entre {fmt_hora(cfg['OPEN_HOUR'])} y {fmt_hora(cfg['CLOSE_HOUR'])}.")
    hoy = today()
    if d < hoy:
        raise ReglaError("No puedes reservar en una fecha pasada.")
    if d > hoy + timedelta(days=cfg["MAX_ADVANCE_DAYS"]):
        raise ReglaError(f"Solo puedes reservar con {cfg['MAX_ADVANCE_DAYS']} días de anticipación.")
    if d.weekday() in cfg["CLOSED_WEEKDAYS"]:
        raise ReglaError("El coworking permanece cerrado los domingos.")
    if d == hoy:
        h = now().hour
        if h >= cfg["CLOSE_HOUR"]:
            raise ReglaError("El coworking ya cerró por hoy.")
        if modo == "hora" and inicio < h:
            raise ReglaError("Ese horario ya pasó. Elige una hora desde ahora en adelante.")
    return d.isoformat(), modo, inicio, fin


# ---------- disponibilidad ---------------------------------------------------
def disponibilidad_completa(db, fecha: str, inicio: int, fin: int):
    """(estados, asientos). estados[numero] = libre | parcial | ocupado.
    asientos[numero][k] = libre | ocupado (solo salas)."""
    ocup: dict[int, dict] = {}
    for r in db.execute(
            """SELECT espacio_id, asiento FROM reservas
               WHERE fecha = ? AND estado = 'confirmada' AND hora_inicio < ? AND ? < hora_fin""",
            (fecha, fin, inicio)):
        o = ocup.setdefault(r["espacio_id"], {"todo": False, "asientos": set()})
        if r["asiento"] is None:
            o["todo"] = True
        else:
            o["asientos"].add(r["asiento"])
    estados, asientos = {}, {}
    for e in db.execute("SELECT id, numero, tipo, capacidad FROM espacios WHERE activo = 1"):
        o = ocup.get(e["id"], {"todo": False, "asientos": set()})
        if e["tipo"] == "sala":
            tomados = set(range(1, e["capacidad"] + 1)) if o["todo"] else o["asientos"]
            asientos[e["numero"]] = {k: ("ocupado" if k in tomados else "libre") for k in range(1, e["capacidad"] + 1)}
            estados[e["numero"]] = ("ocupado" if len(tomados) >= e["capacidad"]
                                    else "parcial" if tomados else "libre")
        else:
            estados[e["numero"]] = "ocupado" if (o["todo"] or o["asientos"]) else "libre"
    return estados, asientos


def disponibilidad(db, fecha: str, inicio: int, fin: int) -> dict[int, str]:
    return disponibilidad_completa(db, fecha, inicio, fin)[0]


def horas_ocupadas_por_usuario(db, usuario_id: int, fecha: str) -> list[tuple[int, int]]:
    return [(r["hora_inicio"], r["hora_fin"]) for r in db.execute(
        "SELECT hora_inicio, hora_fin FROM reservas WHERE usuario_id = ? AND fecha = ? AND estado = 'confirmada'",
        (usuario_id, fecha))]


# ---------- altas, cambios y cancelaciones ----------------------------------
def _guardar(db, reserva_id, usuario_id, espacio_id, fecha, modo, inicio, fin, asiento=None):
    """Valida y guarda dentro de una transacción inmediata: evita reservas duplicadas
    incluso con dos peticiones simultáneas. Devuelve el id de la reserva."""
    db.execute("BEGIN IMMEDIATE")
    try:
        esp = db.execute("SELECT * FROM espacios WHERE id = ? AND activo = 1", (espacio_id,)).fetchone()
        if not esp:
            raise ReglaError("Ese espacio no existe o no está disponible.")
        if asiento is not None:
            if esp["tipo"] != "sala" or not (1 <= int(asiento) <= esp["capacidad"]):
                raise ReglaError("Ese asiento no existe.")
            asiento = int(asiento)
        choque_esp = db.execute(
            """SELECT 1 FROM reservas WHERE espacio_id = ? AND fecha = ? AND estado = 'confirmada'
               AND hora_inicio < ? AND ? < hora_fin AND id != ?
               AND (? IS NULL OR asiento IS NULL OR asiento = ?)""",
            (espacio_id, fecha, fin, inicio, reserva_id or -1, asiento, asiento)).fetchone()
        if choque_esp:
            if asiento is not None:
                raise ReglaError(f"El asiento {asiento} de {esp['nombre']} ya está apartado en ese horario. Elige otro lugar.")
            raise ReglaError(f"{esp['nombre']} ya tiene lugares apartados en ese horario. Elige otra hora, otro espacio o una silla libre.")
        choque = db.execute(
            """SELECT folio FROM reservas WHERE usuario_id = ? AND fecha = ? AND estado = 'confirmada'
               AND hora_inicio < ? AND ? < hora_fin AND id != ?""",
            (usuario_id, fecha, fin, inicio, reserva_id or -1)).fetchone()
        if choque:
            raise ReglaError(f"Ya tienes la reserva {choque['folio']} que se cruza con ese horario.")
        if reserva_id is None:
            cur = db.execute(
                """INSERT INTO reservas (usuario_id, espacio_id, fecha, hora_inicio, hora_fin, modo, token, asiento)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (usuario_id, espacio_id, fecha, inicio, fin, modo, secrets.token_urlsafe(16), asiento))
            reserva_id = cur.lastrowid
            db.execute("UPDATE reservas SET folio = ? WHERE id = ?", (f"DF-{reserva_id:03d}", reserva_id))
        else:
            db.execute(
                "UPDATE reservas SET espacio_id=?, fecha=?, hora_inicio=?, hora_fin=?, modo=?, asiento=? WHERE id=?",
                (espacio_id, fecha, inicio, fin, modo, asiento, reserva_id))
        db.execute("COMMIT")
        return reserva_id
    except Exception:
        db.execute("ROLLBACK")
        raise


def crear_reserva(db, usuario_id, espacio_id, fecha, modo, inicio, fin, asiento=None) -> int:
    fecha, modo, inicio, fin = validar_ventana(fecha, modo, inicio, fin)
    return _guardar(db, None, usuario_id, espacio_id, fecha, modo, inicio, fin, asiento)


def editar_reserva(db, reserva_id, espacio_id, fecha, modo, inicio, fin) -> int:
    r = db.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
    if not r or r["estado"] != "confirmada":
        raise ReglaError("Solo se pueden editar reservas confirmadas.")
    fecha, modo, inicio, fin = validar_ventana(fecha, modo, inicio, fin)
    asiento = r["asiento"] if espacio_id == r["espacio_id"] else None
    return _guardar(db, reserva_id, r["usuario_id"], espacio_id, fecha, modo, inicio, fin, asiento)


def cancelar_reserva(db, reserva_id, usuario_id: int | None = None):
    """Cancela una reserva. Un cliente solo puede cancelar las suyas y antes de que inicien."""
    r = db.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
    if not r or (usuario_id is not None and r["usuario_id"] != usuario_id):
        raise ReglaError("No encontramos esa reserva.")
    if r["estado"] == "cancelada":
        raise ReglaError("La reserva ya estaba cancelada.")
    if usuario_id is not None and now() >= _dt(r["fecha"], r["hora_inicio"]):
        raise ReglaError("Una reserva que ya inició no se puede cancelar. Contacta a recepción.")
    db.execute("UPDATE reservas SET estado = 'cancelada' WHERE id = ?", (reserva_id,))


def estado_visible(r, tiene_acceso: bool) -> tuple[str, str]:
    """(clave, etiqueta) del estado que ve el usuario, derivado de la hora actual."""
    if r["estado"] == "cancelada":
        return "cancelada", "Cancelada"
    ahora = now()
    ini, fin = _dt(r["fecha"], r["hora_inicio"]), _dt(r["fecha"], r["hora_fin"])
    if tiene_acceso:
        return ("finalizada", "Finalizada") if ahora >= fin else ("usada", "Check-in hecho")
    if ahora >= fin:
        return "finalizada", "Finalizada"
    if ahora >= ini:
        return "encurso", "En curso"
    return "confirmada", "Confirmada"


# ---------- check-in ---------------------------------------------------------
_FOLIO = re.compile(r"^DF-\d+$", re.I)


def extraer_codigo(texto: str) -> str:
    """Acepta el folio, el token o la URL completa del QR (…/admin/checkin?codigo=TOKEN)."""
    from urllib.parse import parse_qs, urlsplit
    t = (texto or "").strip()
    if "codigo=" in t:
        vals = parse_qs(urlsplit(t).query).get("codigo")
        if vals:
            return vals[0].strip()
    t = re.split(r"[?#]", t)[0].rstrip("/")
    return t.rsplit("/", 1)[-1].strip()


def validar_acceso(db, texto: str, operador_id: int, forzar: bool = False) -> dict:
    """Valida un QR/folio, registra el resultado (autorizado o denegado) y lo devuelve."""
    codigo = extraer_codigo(texto)
    r = None
    if codigo:
        col = "r.folio" if _FOLIO.match(codigo) else "r.token"
        r = db.execute(
            f"""SELECT r.*, u.nombre AS cliente,
                e.nombre || CASE WHEN r.asiento IS NOT NULL THEN ' · asiento ' || r.asiento ELSE '' END AS espacio FROM reservas r
                JOIN usuarios u ON u.id = r.usuario_id JOIN espacios e ON e.id = r.espacio_id
                WHERE {col} = ?""", (codigo.upper() if col == "r.folio" else codigo,)).fetchone()
    ahora = now()
    ok, motivo, forzable = False, "", False
    if not r:
        motivo = "Código no reconocido."
    elif r["estado"] == "cancelada":
        motivo = "La reserva fue cancelada."
    elif r["fecha"] != ahora.date().isoformat():
        motivo = f"La reserva es para el {fmt_fecha(r['fecha'])}, no para hoy ({fmt_fecha(ahora.date())})."
        forzable = True
    else:
        ini, fin = _dt(r["fecha"], r["hora_inicio"]), _dt(r["fecha"], r["hora_fin"])
        antes = timedelta(minutes=current_app.config["CHECKIN_EARLY_MIN"])
        previo = db.execute(
            "SELECT registrado_en FROM accesos WHERE reserva_id = ? AND resultado = 'autorizado'",
            (r["id"],)).fetchone()
        if ahora < ini - antes:
            motivo = f"Aún no es hora de entrada. Abre a las {(ini - antes).strftime('%H:%M')}."
            forzable = True
        elif ahora >= fin:
            motivo = "El horario de la reserva ya terminó."
            forzable = True
        elif previo:
            motivo = f"Este código ya se usó (entrada a las {previo['registrado_en'][11:16]})."
        else:
            ok = True
    nota = None
    if not ok and forzar and forzable:
        ok, nota = True, f"Autorizado manualmente (motivo original: {motivo})"
    db.execute(
        "INSERT INTO accesos (reserva_id, operador_id, codigo, resultado, motivo, registrado_en) VALUES (?,?,?,?,?,?)",
        (r["id"] if r else None, operador_id, (codigo or "")[:64], "autorizado" if ok else "denegado",
         nota if ok else motivo, ahora.strftime("%Y-%m-%d %H:%M:%S")))
    res = {"ok": ok, "motivo": nota or motivo, "hora": ahora.strftime("%H:%M"), "forzable": bool(forzable and not ok),
           "codigo": codigo}
    if r:
        res.update(folio=r["folio"], cliente=r["cliente"], espacio=r["espacio"],
                   fecha=fmt_fecha(r["fecha"]), horario=fmt_rango(r["hora_inicio"], r["hora_fin"]))
    return res
