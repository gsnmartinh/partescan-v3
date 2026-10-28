"""Denuncia de infracción del MTT (formulario con tablas). El texto corrido sale del OCR de la página;
los datos de las tablas vienen de la lectura por celdas (motor.leer_celdas), o del texto si eso falla."""
import re

from . import certificado
from . import perfil
from .extractor import limpiar

PAT_MTT = re.compile(r"DENUNCIA\s+DE\s+INFRACCI|Antecedentes\s+del\s+Infractor|N\W{0,3}\s*Denuncia\s*:", re.I)

FECHA = r"(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(20\d{2})"

ROTULOS = [  # respaldo cuando no se pudieron leer las tablas: etiqueta -> clave
    ("nombre", r"Nombre\s+Infractor"), ("rut", r"R\.?\s?U\.?\s?T\.?"), ("direccion", r"Direcci[oó]n"),
    ("comuna", r"Comuna"), ("calidad", r"Calidad\s+del\s+Infractor"), ("placa", r"Placa\s+Patente"),
    ("tipo", r"Tipo\s+de\s+Ve\w+"), ("marca", r"Marca"), ("modelo", r"Modelo"), ("anio", r"A[ñn]o"),
    ("boleta", r"N[uú]mero\s+Boleta"), ("fecha_cit", r"Fecha\s+Citaci[oó]n"), ("hora_cit", r"Hora\s+Citaci[oó]n"),
    ("inspector", r"Nombre\s+Inspector"),
]


def es_mtt(texto):
    return bool(PAT_MTT.search(texto or ""))


def _fecha(s):
    m = re.search(FECHA, s or "")
    return "%02d/%02d/%s" % (int(m.group(1)), int(m.group(2)), m.group(3)) if m else ""


def _desde_texto(texto):
    out = {}
    for k, rx in ROTULOS:
        m = re.search(r"(?m)^\W*" + rx + r"\W{0,3}[|:]?\s+(\S.*)$", texto)
        out[k] = limpiar(m.group(1)) if m else ""
    return out


def _lista(s):
    """'1. A 2. B' -> ['A', 'B']"""
    partes = re.split(r"(?:^|\s)\d\s*\.\s+(?=[A-ZÁÉÍÓÚÑ\"“])", " " + s)
    return [limpiar(x) for x in partes if limpiar(x)]


def _placa(v):
    """'ABCD12-3' -> ('ABCD12', '3')"""
    x = re.sub(r"[^A-Z0-9-]", "", (v or "").upper())
    m = re.fullmatch(r"([A-Z]{2,4}\d{2,4})-?([\dK])?", x)
    if not m:
        return re.sub(r"[^A-Z0-9]", "", x), ""
    return m.group(1), m.group(2) or ""


def parte(texto, celdas=None):
    t = re.sub(r"\s+", " ", texto or "")
    av = []
    c = celdas
    if not c:
        c = _desde_texto(texto or "")
        av.append("No pude leer las tablas celda por celda: revisa con cuidado nombre, RUT, patente y boleta.")
    m = re.search(r"N\W{0,3}\s*Denuncia\s*[:;]?\s*(\d{5,9})", t, re.I)
    n_den = m.group(1) if m else ""
    m = re.search(re.escape(perfil.cargar()["comuna"]) + r",?\s*" + FECHA, t, re.I)
    fecha_parte = "%02d/%02d/%s" % (int(m.group(1)), int(m.group(2)), m.group(3)) if m else ""
    m = re.search(r"d[ií]a\s*" + FECHA + r",?\s*siendo\s+las\s+(\d{1,2}):(\d{2})\s*horas,?\s*en\s+(.+?),?\s*se\s+sorprendi", t, re.I)
    if m:
        fecha_inf = "%02d/%02d/%s" % (int(m.group(1)), int(m.group(2)), m.group(3))
        hora = "%d:%s" % (int(m.group(4)), m.group(5))
        lugar = limpiar(m.group(6)).upper()
    else:
        fecha_inf, hora, lugar = fecha_parte, "", ""
    mi = re.search(r"infracci[oó]n\s*\(?e?s?\)?\s*\)?\s*[:;]\s*(.+?)\s*Disposici", t, re.I)
    infracciones = _lista(mi.group(1)) if mi else []
    md = re.search(r"Disposici[oó]n\s+Infringida\s*(.+?)\s*Antecedentes\s+del\s+Infractor", t, re.I)
    disposiciones = _lista(md.group(1)) if md else []
    mo = re.search(r"Observaciones\s*(.+)$", t, re.I)
    obs = limpiar(re.split(r"\s+(?:SERGIO|Divisi[oó]n\s+de)\b", mo.group(1))[0]) if mo else ""
    placa, dv = _placa(c.get("placa", ""))
    rut = c.get("rut", "")
    if rut and not certificado.rut_ok(rut):
        av.append("El RUT leído (%s) no cuadra con su dígito verificador: compáralo con el parte." % rut)
    if not n_den:
        av.append("No pude leer el N° de denuncia.")
    if not infracciones:
        av.append("No pude leer la infracción.")
    if not placa:
        av.append("No pude leer la patente.")
    comuna = re.sub(r"^\s*COMUNA\s+(DE\s+)?", "", (c.get("comuna") or "").upper()).strip()
    return {
        "origen": "mtt", "departamento": "MTT", "n_parte": n_den, "n_parte_final": n_den, "n_citacion_adjunta": "",
        "fecha_parte": fecha_inf or fecha_parte, "fecha_infraccion": fecha_inf, "hora_infraccion": hora,
        "lugar": lugar, "infraccion_texto": infracciones[0] if infracciones else "", "infracciones": infracciones,
        "norma": re.sub(r"N[*?°º]+\??", "N°", re.sub(r"\bART,", "ART.", " / ".join(disposiciones))), "tipo_vehiculo": (c.get("tipo") or "").upper(),
        "marca": (c.get("marca") or "").upper(), "modelo": (c.get("modelo") or "").upper(),
        "anio": re.sub(r"\D", "", c.get("anio") or "")[:4], "placa": placa, "dv_placa": dv,
        "fecha_citacion": _fecha(c.get("fecha_cit")), "hora_citacion": "", "articulo": "",
        "infractor_nombre": (c.get("nombre") or "").upper(), "infractor_rut": rut if certificado.rut_ok(rut) else "",
        "rut_leido": rut, "infractor_direccion": (c.get("direccion") or "").upper(), "infractor_comuna": comuna,
        "calidad": (c.get("calidad") or "").upper(), "boleta": re.sub(r"\D", "", c.get("boleta") or ""),
        "inspector": c.get("inspector", ""), "observaciones": obs, "avisos": av, "texto_ocr": texto,
    }
