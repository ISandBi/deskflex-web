"""Geometría del plano cenital (viewBox 620×520). Corrige el wireframe: el número 10 aparecía
duplicado y faltaba una posición para el escritorio 8; aquí cada espacio 1-25 aparece una vez."""

VIEWBOX = (620, 520)

ESPACIOS = (  # numero, nombre, tipo, capacidad
    [(1, "Sala de juntas 1", "sala", 18), (2, "Sala de juntas 2", "sala", 10)]
    + [(n, f"Escritorio fijo {n}", "fijo", 1) for n in range(3, 10)]
    + [(n, f"Hot desk {n}", "hot", 1) for n in range(10, 26)]
)


def _sala1():
    chairs = []
    for i in range(8):
        x = 70 + i * 43
        chairs += [(x, 50, 22, 12), (x, 162, 22, 12)]
    chairs += [(36, 106, 12, 22), (400, 106, 12, 22)]
    return dict(numero=1, forma="sala", x=24, y=24, w=400, h=176,
                mesa=dict(cx=224, cy=112, rx=150, ry=34), sillas=chairs,
                etiqueta=(224, 112))


def _sala2():
    chairs = []
    for i in range(4):
        y = 76 + i * 40
        chairs += [(466, y, 12, 22), (570, y, 12, 22)]
    chairs += [(511, 40, 22, 12), (511, 222, 22, 12)]
    return dict(numero=2, forma="sala", x=448, y=24, w=148, h=232,
                mesa=dict(cx=524, cy=140, rx=30, ry=78), sillas=chairs, etiqueta=(524, 140))


def _escritorio(n, x, y):
    return dict(numero=n, forma="escritorio", x=x, y=y, w=52, h=44,
                sillas=[(x + 15, y + 48, 22, 10)], etiqueta=(x + 26, y + 24))


def _hot(n, cx, cy):
    return dict(numero=n, forma="hot", cx=cx, cy=cy, r=19, etiqueta=(cx, cy))


FORMAS = [_sala1(), _sala2(),
          _escritorio(9, 280, 232), _escritorio(7, 348, 232), _escritorio(8, 348, 300),
          _escritorio(3, 452, 292), _escritorio(4, 528, 292),
          _escritorio(5, 452, 360), _escritorio(6, 528, 360),
          _hot(16, 44, 238), _hot(17, 44, 284), _hot(18, 44, 330),
          _hot(14, 138, 242), _hot(12, 182, 242), _hot(10, 226, 242),
          _hot(15, 138, 304), _hot(13, 182, 304), _hot(11, 226, 304)] + [
    _hot(19 + i, 52 + i * 52, 446) for i in range(7)]

# Mobiliario decorativo (no interactivo)
MESAS = [
    dict(x=64, y=222, w=22, h=148, r=6),       # mesa de los puestos 16-18
    dict(x=104, y=252, w=144, h=40, r=6),      # mesa de los puestos 10-15
    dict(x=24, y=462, w=376, h=34, r=8),       # barra de los puestos 19-25
]
EXTRAS = [
    dict(tipo="cafe", x=280, y=300, w=52, h=44, texto="Café"),
    dict(tipo="recepcion", x=452, y=440, w=144, h=56, texto="Recepción · QR"),
]
ZONAS = [(24, 400, "HOT DESKS"), (280, 222, "ESCRITORIOS FIJOS")]
