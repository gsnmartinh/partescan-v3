"""Lectura por celdas de los formularios con tablas (denuncia del MTT): se detectan las líneas de cada tabla,
se recorta la celda del valor y se lee sola, con lo que el OCR no se confunde con los bordes."""
import numpy as np
from PIL import Image, ImageOps


def _ang(g):
    sm = g.resize((900, max(1, int(g.height * 900 / g.width))))
    bn = Image.fromarray(((np.array(sm) < 150) * 255).astype(np.uint8))
    best, ang = -1.0, 0.0
    for t in np.arange(-2, 2.01, 0.1):
        v = (np.array(bn.rotate(t, resample=Image.NEAREST)) > 0).sum(axis=1).astype(float).var()
        if v > best:
            best, ang = v, t
    return ang


def enderezar(g):
    """Corrige la inclinación del escaneo (hasta ±2°)."""
    t = _ang(g)
    return g.rotate(t, resample=Image.BICUBIC, fillcolor=255) if abs(t) > 0.05 else g


def _grupos(idx, sep=4):
    gr = []
    for y in idx:
        if gr and y - gr[-1][-1] <= sep:
            gr[-1].append(y)
        else:
            gr.append([y])
    return [int(np.mean(x)) for x in gr]


def _tramos(a, k, eje):
    """Posiciones (centro) donde hay un tramo oscuro continuo de al menos k píxeles a lo largo de `eje`
    (1 = horizontal, 0 = vertical). Devuelve una máscara con la forma de a."""
    x = a.astype(np.int32)
    if eje == 0:
        x = x.T
    c = np.concatenate([np.zeros((x.shape[0], 1), np.int32), np.cumsum(x, axis=1)], axis=1)
    win = c[:, k:] - c[:, :-k]
    m = np.zeros(x.shape, bool)
    m[:, k // 2:k // 2 + win.shape[1]] = win >= k
    return m if eje == 1 else m.T


def _dil(a, ejes, n=1):
    d = a.copy()
    for s in range(1, n + 1):
        d |= np.roll(a, s, axis=ejes) | np.roll(a, -s, axis=ejes)
    return d


def lineas_h(a):
    H, W = a.shape
    m = _tramos(_dil(_dil(a, 1, 4), 0, 1), int(0.2 * W), 1)
    return _grupos([y for y in np.where(m.any(axis=1))[0] if 20 < y < H - 20])


def tablas(g):
    """-> lista de tablas; cada una = (lineas_y, x_divisor, x_derecha). Una tabla = líneas con el paso normal de fila."""
    a = np.array(g) < 190
    ys = lineas_h(a)
    if len(ys) < 3:
        return []
    med = float(np.median(np.diff(ys)))
    grupos = []
    for y in ys:
        if grupos and y - grupos[-1][-1] <= 1.25 * med:
            grupos[-1].append(y)
        else:
            grupos.append([y])
    medidas = []
    for gr in grupos:
        if len(gr) < 3:
            continue
        y0, y1 = gr[0], gr[-1]
        d = _dil(a[y0:y1 + 1], 1, 1)
        m = _tramos(d, max(5, int(0.8 * (y1 - y0))), 0)
        xs = [x for x in _grupos(list(np.where(m.any(axis=0))[0]), sep=6) if 30 < x < a.shape[1] - 30]
        izq, der, xd = (xs[0], xs[-1], None) if len(xs) >= 2 else (None, None, None)
        if izq is not None:
            frac = d.mean(axis=0)
            lo, hi = izq + int(0.08 * (der - izq)), izq + int(0.45 * (der - izq))
            xd = lo + int(np.argmax(frac[lo:hi]))
            if frac[xd] < 0.5:
                xd = None
        medidas.append([gr, izq, der, xd])
    if not medidas:
        return []
    # lo que no se pudo medir (o sale raro) se toma de las otras tablas, que tienen el mismo ancho
    def med(k, tol):
        v = [m[k] for m in medidas if m[k] is not None]
        return int(np.median(v)) if v else None
    mi, md, mx = med(1, 0), med(2, 0), med(3, 0)
    W = a.shape[1]
    mi = mi if mi is not None else int(0.065 * W)
    md = md if md is not None else int(0.69 * W)
    mx = mx if mx is not None else mi + int(0.27 * (md - mi))
    out = []
    for gr, izq, der, xd in medidas:
        if xd is None or abs(xd - mx) > 25:
            xd = mx
        if der is None or abs(der - md) > 40:
            der = md
        out.append((gr, xd, der))
    return out


def celda(g, y0, y1, x0, x1, margen=5):
    c = g.crop((x0 + margen, y0 + margen, x1 - margen, y1 - margen))
    c = c.resize((int(c.width * 2.5), int(c.height * 2.5)), Image.BICUBIC)
    return ImageOps.expand(c, border=25, fill=255)
