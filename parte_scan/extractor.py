"""Lee el texto OCR de un parte (modelo 1) línea por línea y devuelve campos + avisos."""
import re
from . import perfil

MESES = {m: i + 1 for i, m in enumerate(
    "ENERO FEBRERO MARZO ABRIL MAYO JUNIO JULIO AGOSTO SEPTIEMBRE OCTUBRE NOVIEMBRE DICIEMBRE".split())}
RE_FECHA = re.compile(r"(\d{1,2})\s*DE\s*(" + "|".join(MESES) + r")\s*(?:DEL?\.?\s*)?(\d{4})", re.I)
RE_HORA = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")


def fecha_de(linea):
    m = RE_FECHA.search(linea)
    return "%02d/%02d/%s" % (int(m.group(1)), MESES[m.group(2).upper()], m.group(3)) if m else ""


def hora_de(linea):
    h = RE_HORA.findall(linea)
    return "%d:%s" % (int(h[-1][0]), h[-1][1]) if h else ""


def numero(linea, despues=None):
    if despues:
        i = re.search(despues, linea, re.I)
        linea = linea[i.end():] if i else linea
    m = re.search(r"\d{5,8}", linea)
    if not m:
        return ""
    n = m.group(0)
    return n[-6:] if len(n) in (7, 8) else n  # "N9111187": la N° se leyó como un dígito (los folios municipales tienen 6)


def limpiar(s):
    return re.sub(r"\s+", " ", s).strip(" _-—.:;|\"'“”*")


def primera(lines, patron):
    for i, l in enumerate(lines):
        if re.search(patron, l, re.I):
            return i, l
    return -1, ""


def corta(s):
    return re.split(r"[—_\[\]|]{1,}", s)[0]


def limpia_ratio(s):
    return sum(ch.isalnum() or ch.isspace() or ch in ".,°" for ch in s) / max(1, len(s))


def placa_ok(p):
    return bool(re.fullmatch(r"[A-Z]{4}\d{2}|[A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{3}\d{3}|[A-Z]{2}\d{3}", p))


def parte(t):
    L = [l.strip() for l in t.splitlines() if l.strip()]
    o, av = {}, []

    _, l = primera(L, r"SEGURIDAD CIUDADANA|INSPECCI.N GENERAL")
    o["departamento"] = "SEGURIDAD CIUDADANA" if re.search(r"SEGURIDAD", l, re.I) else (
        "INSPECCION GENERAL" if re.search(r"INSPECC", l, re.I) else "")

    _, l = primera(L, r"DENUNCI")
    o["n_parte"] = numero(l, r"DENUNCI\w*")
    _, l = primera(L, r"ADJUNTA\s+CITACI|^Observaciones")
    o["n_citacion_adjunta"] = numero(l, r"CITACI\w*")
    a, b = o["n_parte"], o["n_citacion_adjunta"]
    if a and b and a != b and (a.endswith(b) or b.endswith(a)):      # un dígito de más (la «N°» leída como número): vale el más corto
        o["n_parte"] = o["n_citacion_adjunta"] = min(a, b, key=len)
    elif len(a) == 7 and not b:
        o["n_parte"] = a[1:]
    if o["n_parte"] and o["n_citacion_adjunta"] and o["n_parte"] != o["n_citacion_adjunta"]:
        av.append("El N° del encabezado (%s) no coincide con el de la citación adjunta (%s)." % (o["n_parte"], o["n_citacion_adjunta"]))

    for l in L:
        if re.match(r"\W*" + re.escape(perfil.cargar()["comuna"]) + r"\W", l, re.I) and fecha_de(l):
            o["fecha_parte"] = fecha_de(l)
            break
    else:
        o["fecha_parte"] = ""
    _, l = primera(L, r"Doy cuenta")
    o["fecha_infraccion"] = fecha_de(l)
    o["hora_infraccion"] = hora_de(l)

    _, l = primera(L, r"en\s*la\s*calle")
    m = re.search(r"calle\s+(.+?)\s+se\s+sorprendi", l, re.I) or re.search(r"calle\s+(.+)$", l, re.I)
    lugar = m.group(1) if m else ""
    lugar = re.sub(r"\b(FRTE|FTE)\.?\s*", "", lugar, flags=re.I)
    lugar = re.sub(r"\bN\W{0,2}(?=\d)", "", lugar)
    o["lugar"] = limpiar(lugar).upper()

    # el OCR a veces lee "intracción", "inftacción", etc.
    PAT_INF = r"^\W*[il1]n\w{0,4}cci[oó0]n"
    i, l = primera(L, PAT_INF)
    if i >= 0:
        texto = corta(re.sub(PAT_INF + r"\S*\s*", "", l, flags=re.I))
    else:
        # sin la palabra "infracción" legible: usar lo que sigue a "se sorprendió la siguiente"
        i, l = primera(L, r"sorprendi\w*\s+la\s+siguiente|se\s+sorprendi")
        m = re.search(r"siguiente\s+(\S.*)$", l, re.I) if i >= 0 else None
        if m:
            texto = corta(re.sub(r"^\S*cci[oó0]n\s+|^\S{1,8}\s+(?=[A-ZÁÉÍÓÚÑ]{4,})", "", m.group(1)))
        else:
            texto = ""
            i = i  # el texto vendrá de la(s) línea(s) siguiente(s)
        if i >= 0 and not texto and i + 1 < len(L):
            texto = corta(re.sub(r"^\S*cci[oó0]n\s+", "", L[i + 1]))
            i += 1
    j = i + 1
    while 0 <= i and j < len(L) and not re.match(r"Actividad|Veh", L[j], re.I):
        c = corta(L[j])
        if len(re.findall(r"[A-Za-zÁÉÍÓÚÑ]{3,}", c)) >= 2 and limpia_ratio(c) >= 0.85:
            texto += " " + c
        j += 1
    o["infraccion_texto"] = limpiar(texto).upper()

    _, l = primera(L, r"^Veh")
    m = re.search(r"Veh\S*\s+(.+?)\s*Marca\s+(.+?)\s+(?:C\w{3,4}r\s+)?Placa\s*(.*)$", l, re.I)
    if m:
        o["tipo_vehiculo"] = re.sub(r"\s+[A-Za-z]$", "", limpiar(m.group(1))).upper()
        o["marca"] = limpiar(m.group(2)).upper()
        placa = re.sub(r"[^A-Z0-9]", "", m.group(3).upper())
    else:
        o["tipo_vehiculo"], o["marca"], placa = "", "", ""
    o["placa"] = placa
    if placa and not placa_ok(placa):
        av.append("La placa «%s» no tiene un formato conocido." % placa)

    _, l = primera(L, r"audiencia")
    o["fecha_citacion"] = fecha_de(l)
    o["hora_citacion"] = hora_de(l)

    _, l = primera(L, r"\bART")
    m = re.search(r"ART\.?\s*(\d+)(?:\s*N\W{0,2}\s*(\d+))?", l, re.I)
    o["articulo"] = (m.group(1) + (" N°" + m.group(2) if m.group(2) else "")) if m else ""
    o["avisos"] = av
    return o
