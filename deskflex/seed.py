"""Datos iniciales y de demostración."""
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from . import rules
from .mapa import ESPACIOS

DEMO_USERS = [
    ("Administrador DeskFlex", "admin@deskflex.mx", "5555550100", "Admin2026!", "admin", 1),
    ("Carlos Pérez", "carlos.perez10@gmail.com", "5548961012", "Carlos2026!", "cliente", 1),
    ("Fernando Chávez", "fer15@hotmail.com", "5596120536", "DeskFlex2026!", "cliente", 1),
    ("Ana Lucía Torres", "ana.torres@studio-norte.mx", "5521347788", "DeskFlex2026!", "cliente", 1),
    ("Diego Ramírez", "diego@ramirezlab.mx", "5533001122", "DeskFlex2026!", "cliente", 1),
    ("Mariana Solís", "mariana.solis@gmail.com", "5544556677", "DeskFlex2026!", "cliente", 0),
]


def seed_espacios(db):
    db.executemany("INSERT OR IGNORE INTO espacios (numero, nombre, tipo, capacidad) VALUES (?,?,?,?)", ESPACIOS)


def _dia_habil(offset: int) -> str:
    d = rules.today() + timedelta(days=offset)
    while d.weekday() in (6,):
        d += timedelta(days=1)
    return d.isoformat()


def seed_demo(db):
    seed_espacios(db)
    for nombre, correo, tel, pwd, rol, activo in DEMO_USERS:
        db.execute("INSERT OR IGNORE INTO usuarios (nombre, correo, telefono, password_hash, rol, activo) VALUES (?,?,?,?,?,?)",
                   (nombre, correo, tel, generate_password_hash(pwd), rol, activo))
    uid = {r["correo"]: r["id"] for r in db.execute("SELECT id, correo FROM usuarios")}
    eid = {r["numero"]: r["id"] for r in db.execute("SELECT id, numero FROM espacios")}
    if db.execute("SELECT COUNT(*) c FROM reservas").fetchone()["c"]:
        return
    carlos, fer, ana, diego = (uid["carlos.perez10@gmail.com"], uid["fer15@hotmail.com"],
                               uid["ana.torres@studio-norte.mx"], uid["diego@ramirezlab.mx"])
    ahora = rules.now()
    h = min(max(ahora.hour, 7), 19)
    hoy_ok = ahora.hour <= 19 and ahora.date().weekday() != 6
    hoy = ahora.date().isoformat()
    ok = []
    # DF-001: Carlos, sala 1, ahora mismo (para probar el check-in) o el siguiente día hábil
    ok.append(rules.crear_reserva(db, carlos, eid[1], hoy if hoy_ok else _dia_habil(1), "hora", h if hoy_ok else 9, (h if hoy_ok else 9) + 2))
    ok.append(rules.crear_reserva(db, fer, eid[6], _dia_habil(1), "dia", 7, 21))
    ok.append(rules.crear_reserva(db, carlos, eid[25], _dia_habil(2), "hora", 9, 11))
    ok.append(rules.crear_reserva(db, ana, eid[12], hoy if hoy_ok else _dia_habil(1), "dia", 7, 21))
    ok.append(rules.crear_reserva(db, diego, eid[2], _dia_habil(2), "hora", 15, 17))
    ok.append(rules.crear_reserva(db, ana, eid[4], _dia_habil(3), "dia", 7, 21))
    # Historial: reservas pasadas con su check-in
    for usuario, esp, dias, ini, fin in [(carlos, 14, -3, 8, 12), (fer, 19, -5, 7, 21), (diego, 1, -2, 10, 12)]:
        d = date.fromisoformat(_dia_habil(dias)) if dias > 0 else rules.today() + timedelta(days=dias)
        while d.weekday() == 6:
            d -= timedelta(days=1)
        cur = db.execute(
            "INSERT INTO reservas (usuario_id, espacio_id, fecha, hora_inicio, hora_fin, modo, token) VALUES (?,?,?,?,?,?,?)",
            (usuario, eid[esp], d.isoformat(), ini, fin, "dia" if (ini, fin) == (7, 21) else "hora", f"hist-{usuario}-{esp}"))
        rid = cur.lastrowid
        db.execute("UPDATE reservas SET folio = ? WHERE id = ?", (f"DF-{rid:03d}", rid))
        db.execute("INSERT INTO accesos (reserva_id, operador_id, codigo, resultado, registrado_en) VALUES (?,?,?,?,?)",
                   (rid, uid["admin@deskflex.mx"], f"DF-{rid:03d}", "autorizado", f"{d.isoformat()} {ini:02d}:05:00"))
