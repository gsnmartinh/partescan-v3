"""Lee el texto OCR de un «Extracto de inscripción en el R.V.M.» (certificado del Registro Civil)."""
import re
from difflib import SequenceMatcher


def _limpiar(s):
    return re.sub(r"\s+", " ", s).strip(" _-—.:;|\"'“”*")


def rut_ok(rut):
    """Valida el dígito verificador (módulo 11). rut = '11111111-1'."""
    m = re.fullmatch(r"(\d{6,9})-([\dK])", rut or "")
    if not m:
        return False
    s, f = 0, 2
    for d in reversed(m.group(1)):
        s += int(d) * f
        f = 2 if f == 7 else f + 1
    r = 11 - s % 11
    return ("0" if r == 11 else "K" if r == 10 else str(r)) == m.group(2)


def es_certificado(t):
    return bool(re.search(r"EXTRACTO\s+DE\s+INSCRIP|DATOS\s+DEL\s+PROPIETARIO|Uso\s+exclusivo\s+Juzgados", t, re.I))


RUIDO_FINAL = re.compile(r"(?:\s+[|!\\/\[\]\u2018\u2019'`´‘’:;,.\-_]+|\s+[IilLjJ1](?![\w/-]))+\s*$")


def _sin_ruido(v):
    """El borde del escáner deja una raya vertical que el OCR lee como «I», «1», «!», «|», «\\» al final de la línea."""
    return _limpiar(RUIDO_FINAL.sub("", " " + v + " ")) if v else v


def _valor(t, etiqueta):
    # el OCR a veces lee los dos puntos como "?", "*", "—", "1", "g"...
    m = re.search(etiqueta + r"\W{0,4}(?:[:;?*1!|]|\b[gGjJ]\b)\s*(.+)", t, re.I)
    return _sin_ruido(_limpiar(m.group(1))) if m else ""


def _propietario(t):
    """Líneas de «DATOS DEL PROPIETARIO» sin su rótulo: [nombre, rut, domicilio, comuna, ...]. Sirve cuando el OCR
    estropea el rótulo («Nombre», «Comuna»...) y la búsqueda por rótulo falla."""
    m = re.search(r"PROPIETARIO", t, re.I)
    if not m:
        return []
    out = []
    for l in t[m.end():].splitlines()[1:]:      # el resto de la línea del encabezado es ruido
        l = l.strip()
        if not l:
            continue
        if re.match(r"\W*(?:Fec\.?\s*adq|Repertorio|FECHA)", l, re.I):
            break
        v = re.sub(r"^[^:;]{0,22}[:;?*]\s*", "", l) if re.match(r"^[^:;]{0,22}[:;?*]", l) else re.sub(r"^[A-Za-z.]{1,12}\s+(?:[gGjJiIl1|]\s+)?(?=\S)", "", l)
        out.append(_sin_ruido(_limpiar(v)))
    return out


def leer(t):
    o, av = {}, []
    # Inscripción: PLACA.NN-D  (el dígito final es el verificador de la placa)
    m = re.search(r"Inscripci\S{1,3}n\s*[:;1l|]?\s*([A-Z]{2,5})[\s.\-]*(\d{1,4})\s*[-–]\s*([0-9K])", t, re.I)
    o["placa"] = (m.group(1) + m.group(2)).upper() if m else ""
    o["dv_placa"] = m.group(3).upper() if m else ""
    tipo = _valor(t, r"Tipo\s+Veh\S{1,3}culo")
    o["anio"] = ""
    m = re.search(r"A\S{1,2}o\s*[:;?]?\s*((?:19|20)\d{2})", tipo, re.I)
    if m:
        o["anio"] = m.group(1)
    tipo = re.sub(r"\s*A\S{1,2}o\b.*$", "", tipo, flags=re.I)
    o["tipo_vehiculo"] = re.sub(r"[^A-ZÁÉÍÓÚÑ ]", "", tipo.upper()).strip()
    if not o["anio"]:
        m = re.search(r"\bA\S{1,2}o\s*[:;]?\s*((?:19|20)\d{2})", t, re.I)
        o["anio"] = m.group(1) if m else ""
    o["marca"] = _valor(t, r"Marca").upper()
    o["modelo"] = _valor(t, r"Modelo").upper()
    o["color"] = _valor(t, r"Color").upper()
    prop = _propietario(t)
    o["nombre"] = _valor(t, r"Nombre").upper()
    if not o["nombre"] and prop:
        o["nombre"] = prop[0].upper()
    # RUN: tolera coma por punto, espacios y letras confundidas
    m = re.search(r"R\.?\s*U\.?\s*N\.?\s*[:;]\s*([\d.,\s]{6,12})\s*[-–]\s*([\dKk])", t)
    rut = ""
    if m:
        rut = re.sub(r"\D", "", m.group(1)) + "-" + m.group(2).upper()
    if not rut:
        zona = t[re.search(r"PROPIETARIO", t, re.I).start():] if re.search(r"PROPIETARIO", t, re.I) else t
        m = re.search(r"(?<!\d)(\d{1,2})\s*[.,]\s*(\d{3})\s*[.,]\s*(\d{3})\s*[-–]\s*([\dKk])", zona)
        if m:
            rut = m.group(1) + m.group(2) + m.group(3) + "-" + m.group(4).upper()
    o["rut"] = rut
    if not rut:
        av.append("No pude leer el RUT del certificado.")
    elif not rut_ok(rut):
        av.append("El RUT del certificado (%s) no cumple el dígito verificador: revísalo." % rut)
    dom = _valor(t, r"Domicilio")
    if not dom and len(prop) > 2:
        dom = prop[2]
    o["direccion"] = _sin_ruido(_limpiar(re.sub(r"\s\.\s", " ", dom))).upper().strip(" ,")
    from . import catalogo
    def _com(v):
        return catalogo.comuna_oficial(re.sub(r"[^A-ZÁÉÍÓÚÑ ]", "", v.upper()).strip())
    def _en_lista(c):
        return bool(c) and catalogo.comuna_en_sistema(c)
    com = _com(_valor(t, r"Comuna"))
    if not _en_lista(com):          # rótulo ilegible o valor raro: se prueba la línea que sigue al domicilio
        for cand in prop[3:4] + prop[2:3]:
            if _en_lista(_com(cand)):
                com = _com(cand)
                break
    o["comuna"] = com
    for k, nom in (("nombre", "el nombre"), ("direccion", "la dirección"), ("comuna", "la comuna"),
                   ("marca", "la marca"), ("tipo_vehiculo", "el tipo de vehículo"), ("placa", "la placa")):
        if not o[k]:
            av.append("No pude leer %s del certificado." % nom)
    o["avisos"] = av
    return o


def _parecidas(a, b):
    return SequenceMatcher(None, a, b).ratio()


def conciliar_placa(placa_parte, placa_cert):
    """Devuelve (placa_elegida, aviso). La placa del certificado manda si cumple formato."""
    fmt = re.compile(r"[A-Z]{4}\d{2}|[A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{3}\d{3}|[A-Z]{2}\d{3}")
    a, b = placa_parte or "", placa_cert or ""
    if a == b and a:
        return a, ""
    if a and b and _parecidas(a, b) >= 0.7:
        # difieren en 1-2 caracteres: probablemente el OCR confundió una letra
        ok_a, ok_b = bool(fmt.fullmatch(a)), bool(fmt.fullmatch(b))
        elegida = b if ok_b and not ok_a else a if ok_a and not ok_b else b
        return elegida, "La placa del parte (%s) y la del certificado (%s) se leyeron distinto: comprueba cuál es." % (a, b)
    if a and b:
        return a, "La placa del parte (%s) NO coincide con la del certificado (%s): ¿el certificado es de otro parte?" % (a, b)
    return a or b, ""
