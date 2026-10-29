"""Generador de códigos QR (ISO/IEC 18004), modo byte, corrección de errores nivel M.

Sin dependencias externas: devuelve la matriz de módulos o un SVG listo para incrustar.
Soporta versiones 1 a 10 (hasta 213 bytes), suficiente para una URL con token.
"""
from __future__ import annotations

# Nivel M: bytes de corrección por bloque y número de bloques, versiones 1..10
_ECC_PER_BLOCK = [None, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26]
_NUM_BLOCKS = [None, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5]
_FORMAT_BITS_M = 0  # indicador de nivel M en la información de formato


def _raw_data_modules(ver: int) -> int:
    n = (16 * ver + 128) * ver + 64
    if ver >= 2:
        na = ver // 7 + 2
        n -= (25 * na - 10) * na - 55
        if ver >= 7:
            n -= 36
    return n


def _data_codewords(ver: int) -> int:
    return _raw_data_modules(ver) // 8 - _ECC_PER_BLOCK[ver] * _NUM_BLOCKS[ver]


# ---- Reed-Solomon sobre GF(256) ------------------------------------------
def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _add_ecc_and_interleave(data: list[int], ver: int) -> list[int]:
    nblocks, ecc_len = _NUM_BLOCKS[ver], _ECC_PER_BLOCK[ver]
    raw = _raw_data_modules(ver) // 8
    short_blocks = nblocks - raw % nblocks
    short_len = raw // nblocks
    divisor = _rs_divisor(ecc_len)
    blocks, k = [], 0
    for i in range(nblocks):
        dlen = short_len - ecc_len + (0 if i < short_blocks else 1)
        chunk = data[k:k + dlen]
        k += dlen
        ecc = _rs_remainder(chunk, divisor)
        if i < short_blocks:
            chunk = chunk + [0]  # relleno para alinear la intercalación
        blocks.append(chunk + ecc)
    out = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != short_len - ecc_len or j >= short_blocks:
                out.append(blk[i])
    return out


# ---- Construcción de la matriz --------------------------------------------
class _Builder:
    def __init__(self, ver: int):
        self.ver = ver
        self.size = ver * 4 + 17
        self.m = [[False] * self.size for _ in range(self.size)]
        self.f = [[False] * self.size for _ in range(self.size)]
        self._draw_function_patterns()

    def _set(self, x, y, dark):
        self.m[y][x] = bool(dark)
        self.f[y][x] = True

    def _draw_function_patterns(self):
        n = self.size
        for i in range(n):
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self._set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = self._align_positions()
        last = len(pos) - 1
        for i, px in enumerate(pos):
            for j, py in enumerate(pos):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set(px + dx, py + dy, max(abs(dx), abs(dy)) != 1)
        self._draw_format(0)
        self._draw_version()

    def _align_positions(self):
        if self.ver == 1:
            return []
        na = self.ver // 7 + 2
        step = (self.ver * 4 + na * 2 + 1) // (na * 2 - 2) * 2
        res = [self.size - 7 - i * step for i in range(na - 1)] + [6]
        return res[::-1]

    def _draw_format(self, mask: int):
        data = _FORMAT_BITS_M << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        g = lambda i: (bits >> i) & 1
        n = self.size
        for i in range(6):
            self._set(8, i, g(i))
        self._set(8, 7, g(6))
        self._set(8, 8, g(7))
        self._set(7, 8, g(8))
        for i in range(9, 15):
            self._set(14 - i, 8, g(i))
        for i in range(8):
            self._set(n - 1 - i, 8, g(i))
        for i in range(8, 15):
            self._set(8, n - 15 + i, g(i))
        self._set(8, n - 8, True)

    def _draw_version(self):
        if self.ver < 7:
            return
        rem = self.ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.ver << 12 | rem
        for i in range(18):
            bit = (bits >> i) & 1
            a, b = self.size - 11 + i % 3, i // 3
            self._set(a, b, bit)
            self._set(b, a, bit)

    def place_codewords(self, data: list[int]):
        n, i = self.size, 0
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = n - 1 - vert if upward else vert
                    if not self.f[y][x] and i < len(data) * 8:
                        self.m[y][x] = bool((data[i >> 3] >> (7 - (i & 7))) & 1)
                        i += 1
            right -= 2

    def apply_mask(self, mask: int):
        fn = _MASKS[mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self.f[y][x] and fn(x, y):
                    self.m[y][x] = not self.m[y][x]

    def penalty(self) -> int:
        n, m, score = self.size, self.m, 0
        rows = [m[y] for y in range(n)]
        cols = [[m[y][x] for y in range(n)] for x in range(n)]
        for line in rows + cols:
            run, prev = 0, None
            for v in line:
                if v == prev:
                    run += 1
                    if run == 5:
                        score += 3
                    elif run > 5:
                        score += 1
                else:
                    prev, run = v, 1
            s = "".join("1" if v else "0" for v in line)
            score += 40 * (s.count("10111010000") + s.count("00001011101"))
        for y in range(n - 1):
            for x in range(n - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(v for row in m for v in row)
        total = n * n
        k = -(-abs(dark * 20 - total * 10) // total) - 1
        return score + max(k, 0) * 10


_MASKS = [
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
]


def matrix(text: str) -> list[list[bool]]:
    """Devuelve la matriz de módulos (True = oscuro) del QR para `text`."""
    payload = text.encode("utf-8")
    ver = next((v for v in range(1, 11)
                if len(payload) <= _data_codewords(v) - (2 if v < 10 else 3)), None)
    if ver is None:
        raise ValueError("Texto demasiado largo para el QR (máx. 213 bytes)")
    bits: list[int] = []

    def put(val, length):
        bits.extend((val >> i) & 1 for i in range(length - 1, -1, -1))

    put(0b0100, 4)
    put(len(payload), 8 if ver < 10 else 16)
    for b in payload:
        put(b, 8)
    cap = _data_codewords(ver) * 8
    put(0, min(4, cap - len(bits)))
    put(0, -len(bits) % 8)
    pad = 0xEC
    while len(bits) < cap:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    codewords = _add_ecc_and_interleave(data, ver)

    best, best_pen = None, None
    for mask in range(8):
        b = _Builder(ver)
        b.place_codewords(codewords)
        b.apply_mask(mask)
        b._draw_format(mask)
        pen = b.penalty()
        if best_pen is None or pen < best_pen:
            best, best_pen = b, pen
    return best.m


def svg(text: str, color: str = "#0F172A", border: int = 2, label: str = "Código QR") -> str:
    """SVG del QR (módulos como un único <path>), con zona de silencio de `border` módulos."""
    m = matrix(text)
    n = len(m)
    d = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                start = x
                while x < n and row[x]:
                    x += 1
                d.append(f"M{start + border},{y + border}h{x - start}v1h-{x - start}z")
            else:
                x += 1
    size = n + border * 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
            f'role="img" aria-label="{label}" shape-rendering="crispEdges">'
            f'<rect width="{size}" height="{size}" fill="#fff"/>'
            f'<path d="{"".join(d)}" fill="{color}"/></svg>')
