from flask import Flask, g, render_template, request, session

from . import db as database
from . import rules
from .config import Config
from .security import check_csrf, csrf_token, load_user


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    database.init_app(app)

    with app.app_context():
        database.init_db()
        db = database.get_db()
        if app.config.get("SEED_DEMO", True) and not db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            from .seed import seed_demo
            seed_demo(db)

    from .views import admin, api, auth, client
    for bp in (auth.bp, client.bp, admin.bp, api.bp):
        app.register_blueprint(bp)

    @app.before_request
    def _before():
        load_user()
        check_csrf()

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if g.get("user") is not None:
            resp.headers["Cache-Control"] = "no-store"
        return resp

    from . import mapa
    app.jinja_env.globals.update(
        mapa=mapa,
        ART_ESPACIOS={n: {'nombre': nm, 'tipo': t, 'capacidad': c} for n, nm, t, c in mapa.ESPACIOS})
    app.jinja_env.filters.update(
        hora=rules.fmt_hora, rango=lambda r: rules.fmt_rango(r["hora_inicio"], r["hora_fin"]),
        fecha=rules.fmt_fecha, fecha_corta=lambda d: rules.fmt_fecha(d, corta=True),
        fecha_dia=rules.fmt_fecha_dia,
        iniciales=lambda n: "".join(p[0] for p in n.split()[:2]).upper(),
        primer_nombre=lambda n: n.split()[0],
    )

    @app.context_processor
    def _ctx():
        return dict(csrf_token=csrf_token, user=g.get("user"), endpoint=request.endpoint or "")

    def _error(code, titulo, texto):
        def handler(e):
            msg = getattr(e, "description", texto) if code == 400 else texto
            return render_template("error.html", code=code, titulo=titulo, texto=msg), code
        return handler

    app.register_error_handler(400, _error(400, "No pudimos procesar la solicitud", ""))
    app.register_error_handler(403, _error(403, "Zona restringida", "Esta sección es solo para el personal de DeskFlex."))
    app.register_error_handler(404, _error(404, "No encontramos esa página", "Puede que el enlace haya cambiado o que la reserva ya no exista."))
    return app
