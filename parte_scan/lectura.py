"""Validación y disposición espacial compartidas por las lecturas locales."""
import datetime
import re
import unicodedata


def valido(campo, valor):
    texto = str(valor or "").strip()
    if not texto:
        return False
    if "fecha" in campo:
        try:
            datetime.datetime.strptime(texto, "%d/%m/%Y")
            return True
        except ValueError:
            return False
    if "hora" in campo:
        return bool(re.fullmatch(r"(?:[01]?\d|2[0-3]):[0-5]\d", texto))
    if "rut" in campo:
        from .certificado import rut_ok
        return rut_ok(texto)
    if campo == "placa":
        from .extractor import placa_ok
        return placa_ok(texto) and not re.fullmatch(r"(?=[A-Z]{4}\d{2}$)[A-Z]*[AEIOU][A-Z]*\d{2}", texto)
    if "nombre" in campo or campo in ("direccion", "lugar"):
        return len(texto) >= 3 and not re.search(
            r"DATOS DEL|R[.]?U[.]?[NT][.]?\s*:|FECHA DE|DENUNCIANTE:|POR\s*ES\s*CRITO|MARCA:|COMUNA:", texto, re.I)
    return len(texto) >= 3


def puntaje(texto):
    """Premia datos y etiquetas reconocibles sin premiar texto repetido."""
    limpio = unicodedata.normalize("NFD", texto.upper())
    limpio = "".join(c for c in limpio if not unicodedata.combining(c))
    etiquetas = ("DATO", "PROPIETARIO", "DOMICILIO", "INFRACCION", "DENUNC", "CITACION", "INFRACTOR", "DOY CUENTA")
    return (sum(etiqueta in limpio for etiqueta in etiquetas) * 4
            + len(set(re.findall(r"\b\d{1,2}[:/]\d{2}(?:/\d{4})?\b", limpio))) * 2
            + min(len(set(re.findall(r"[A-Z]{3,}", limpio))), 40) / 10)


def lineas_espaciales(datos):
    if not isinstance(datos, list) or len(datos) > 2000:
        return []
    lineas = []
    for item in datos:
        if not isinstance(item, dict) or not isinstance(item.get("texto"), str):
            continue
        caja = item.get("caja")
        if (not isinstance(caja, list) or len(caja) != 4
                or not all(type(v) in (int, float) and 0 <= v <= 1 for v in caja)
                or caja[2] <= caja[0] or caja[3] <= caja[1]):
            continue
        lineas.append({"texto": item["texto"][:2000], "caja": caja})
    return lineas


def ordenar_lineas(lineas):
    filas = []
    for linea in sorted(lineas, key=lambda x: x["caja"][1]):
        caja = linea["caja"]
        centro = (caja[1] + caja[3]) / 2
        fila = next((f for f in reversed(filas) if abs(f[0] - centro) < min(f[1], caja[3] - caja[1]) * .45), None)
        if fila is None:
            filas.append([centro, caja[3] - caja[1], [linea]])
        else:
            fila[2].append(linea)
    return "\n".join(" ".join(l["texto"] for l in sorted(f[2], key=lambda l: l["caja"][0])) for f in filas)


def zona_etiqueta(imagen, patron, margen=.12):
    lineas = imagen.info.get("ocr_lineas", [])
    coincidencias = [l for l in lineas if re.search(patron, l["texto"], re.I)]
    if len(coincidencias) != 1:
        return None
    caja = coincidencias[0]["caja"]
    return imagen.crop((0, max(0, int((caja[1] - .025) * imagen.height)),
                        imagen.width, min(imagen.height, int((caja[3] + margen) * imagen.height))))
