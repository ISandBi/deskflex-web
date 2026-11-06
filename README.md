# DeskFlex México — Control de acceso y reservas para coworking

Prototipo funcional: mapa interactivo, reservas por hora/día completo sin duplicados, QR de acceso y check-in.

## Ejecutar
    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python run.py                                        # http://127.0.0.1:5000

La base (SQLite) se crea sola en `instance/deskflex.db` con datos de demostración.

- Administrador: admin@deskflex.mx / Admin2026!
- Cliente: carlos.perez10@gmail.com / Carlos2026!

Producción: define `SECRET_KEY`, pon `DEMO_HINT = False` en `deskflex/config.py` y usa HTTPS (la cámara lo exige).

## Estructura
- `deskflex/rules.py`: reglas de negocio · `qr.py`: QR ISO/IEC 18004 sin dependencias
- `deskflex/views/`: auth, cliente, admin, API · `mapa.py`: geometría del plano
- `static/css/deskflex.css`: tokens ET-UI-001 + derivados de contraste

## Reglas (config.py)
Horario 7–21 h, domingo cerrado, 60 días de anticipación, QR válido desde 30 min antes y de un solo uso.

## Pendiente vs. documentación
Usa SQLite y CSS propio (sin Bootstrap) porque en el entorno de construcción no se podían instalar paquetes. Migrar a PostgreSQL/Flask-SQLAlchemy queda pendiente; el SQL está en `schema.sql`, `rules.py` y `views/`.

## Cámara del check-in
Abre el sistema con `http://127.0.0.1:5000` o `https://` (el navegador no da cámara en otras direcciones http).
El decodificador de QR usa `BarcodeDetector` del navegador o, si no existe, jsQR desde internet. Para usarlo sin internet,
guarda `jsQR.js` en `deskflex/static/vendor/jsQR.js`.

## Base de datos existente
Si ya tenías `instance/deskflex.db`, se actualiza sola al arrancar (agrega la columna de asientos); no hace falta borrarla.
