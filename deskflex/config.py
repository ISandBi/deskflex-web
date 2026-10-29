import os
from datetime import timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


class Config:
    # En producción define SECRET_KEY como variable de entorno.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-cambia-esta-clave")
    DATABASE = os.environ.get("DESKFLEX_DB", str(BASE / "instance" / "deskflex.db"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    DEMO_HINT = True          # muestra las cuentas de demostración en el login (desactívalo en producción)
    MAX_CONTENT_LENGTH = 64 * 1024

    # Reglas de negocio del coworking
    TIMEZONE = "America/Mexico_City"
    OPEN_HOUR = 7            # primera hora reservable
    CLOSE_HOUR = 21          # el coworking cierra a las 21:00
    CLOSED_WEEKDAYS = (6,)   # domingo cerrado (0 = lunes)
    MAX_ADVANCE_DAYS = 60
    CHECKIN_EARLY_MIN = 30   # el QR vale desde 30 min antes de la hora de inicio
