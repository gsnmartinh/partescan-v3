"""Motor de lectura: imagen/PDF -> campos del parte. Todo local (Tesseract), sin internet."""
import os, re, sys
from collections import Counter

import pytesseract
from PIL import Image

from . import extractor, tablas


def _base():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def configurar_tesseract():
    """Usa el Tesseract incluido junto al programa; en desarrollo usa el del sistema."""
    emb = os.path.join(_base(), "tesseract")
    exe = os.path.join(emb, "tesseract.exe")
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
        os.environ["TESSDATA_PREFIX"] = os.path.join(emb, "tessdata")
    elif os.path.isdir(os.path.join(_base(), "tessdata")):
        os.environ.setdefault("TESSDATA_PREFIX", os.path.join(_base(), "tessdata"))


configurar_tesseract()
EXTS_IMG = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def paginas(ruta, dpi=200):
    """Devuelve lista de imágenes PIL (una por página) de un PDF o imagen."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".pdf":
        import pypdfium2 as pdfium
        out = []
        doc = pdfium.PdfDocument(ruta)
        try:
            for i in range(len(doc)):
                out.append(doc[i].render(scale=dpi / 72).to_pil().convert("L"))
        finally:
            doc.close()
        return out
    if ext in EXTS_IMG:
        im = Image.open(ruta)
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        return [im.convert("L")]
    return []


def _lineas(d):
    L = {}
    for i, w in enumerate(d["text"]):
        if w.strip():
            L.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(i)
    return sorted(L.values(), key=lambda idx: min(d["top"][i] for i in idx))


def _folio_recorte(g):
    """Lee el N° de parte recortando a la derecha de 'DENUNCIO' solo con dígitos."""
    W = g.width
    top = g.crop((0, 0, W, int(g.height * 0.30)))   # el folio está en el encabezado
    d = pytesseract.image_to_data(top, lang="spa", config="--psm 6", output_type=pytesseract.Output.DICT)
    for idx in _lineas(d):
        w = [i for i in idx if d["text"][i].upper().startswith("DENUNC")]
        if w:
            i0 = w[0]
            xr = d["left"][i0] + d["width"][i0]
            yt = d["top"][i0]
            yb = yt + d["height"][i0]
            crop = g.crop((xr, max(0, yt - 10), min(W, xr + int(0.32 * W)), yb + 10))
            crop = crop.resize((crop.width * 2, crop.height * 2), Image.BICUBIC)
            t = pytesseract.image_to_string(crop, lang="spa",
                                            config="--psm 7 -c tessedit_char_whitelist=0123456789")
            r = [x for x in re.findall(r"\d+", t) if len(x) >= 5]
            return r[0] if r else ""
    return ""


def votar(*lecturas):
    vals = [x for x in lecturas if x]
    if not vals:
        return "", ["No se pudo leer el N° de parte: escríbelo."]
    v, n = Counter(vals).most_common(1)[0]
    av = []
    if len(set(vals)) > 1:
        av.append("El N° de parte se leyó distinto (%s); se eligió %s." % (" / ".join(vals), v))
        if n == 1:
            av.append("Las lecturas no coinciden: revisa bien el folio.")
    return v, av


def preparar(img):
    g = img.convert("L")
    if g.width > 2600:  # fotos grandes: bajar a un tamaño razonable
        f = 2600 / g.width
        g = g.resize((2600, int(g.height * f)), Image.BICUBIC)
    return g


def texto_pagina(g):
    """OCR de la página completa (una sola pasada)."""
    big = g.resize((int(g.width * 1.4), int(g.height * 1.4)), Image.BICUBIC)
    return pytesseract.image_to_string(big, lang="spa", config="--psm 6")


def tipo_pagina(texto):
    """'parte', 'carab' (parte de Carabineros), 'mtt' (denuncia del MTT), 'certificado' u 'otra' (hoja que no sirve, p. ej. segunda hoja del certificado)."""
    from . import certificado, extractor_carab, extractor_mtt
    if certificado.es_certificado(texto):
        return "certificado"
    if extractor_mtt.es_mtt(texto):
        return "mtt"
    if extractor_carab.es_carab(texto):
        return "carab"
    if re.search(r"DENUNCI|Doy\s+cuenta|JUZGADO\s+DE\s+POLIC", texto, re.I):
        return "parte"
    return "otra"


def leer_parte(img, texto=None, g=None):
    """Imagen PIL (gris) -> dict con los campos leídos."""
    g = g or preparar(img)
    texto = texto if texto is not None else texto_pagina(g)
    r = extractor.parte(texto)
    r["folio_recorte"] = _folio_recorte(g)
    r["n_parte_final"], av = votar(r["n_parte"], r["folio_recorte"], r["n_citacion_adjunta"])
    r["avisos"] = [a for a in r["avisos"] if "encabezado" not in a] + av
    r["texto_ocr"] = texto
    return r


# ---------- denuncia del MTT: lectura por celdas ----------
CLAVES_TABLAS = (("nombre", "rut", "direccion", "comuna", "calidad"),
                 ("placa", "tipo", "marca", "modelo", "anio"),
                 ("boleta", "fecha_cit", "hora_cit", "inspector"))
CONSONANTES = "BCDFGHJKLPRSTVWXYZ"


def _cfg(psm=7, lista=None):
    return "--psm %d" % psm + (" -c tessedit_char_whitelist=" + lista if lista else "")


def _leer(c, cfg, lang="spa", punto=False):
    v = re.sub(r"\s+", " ", pytesseract.image_to_string(c, lang=lang, config=cfg)).strip(" |_-—,;:'\"")
    return v if punto else v.strip(".")


def _celda_placa(c):
    """Las patentes nuevas solo usan consonantes: así 'I' y 'J' no se confunden."""
    v = _leer(c, _cfg(7, CONSONANTES + "0123456789-K"))
    if re.fullmatch(r"[%s]{4}\d{2}-?[\dK]" % CONSONANTES, v):
        return v
    for lang in ("spa", "eng"):
        w = _leer(c, _cfg(7), lang).upper().replace(" ", "")
        if re.fullmatch(r"[A-Z]{2,4}\d{2,4}-?[\dK]", w):
            return w
    return v


def _celda_rut(c):
    from . import certificado
    vistos = []
    for cfg, lang in ((_cfg(7, "0123456789Kk-."), "spa"), (_cfg(7), "spa"), (_cfg(7, "0123456789Kk-."), "eng"), (_cfg(8, "0123456789Kk-."), "spa")):
        v = re.sub(r"[^0-9Kk-]", "", _leer(c, cfg, lang)).upper()
        m = re.fullmatch(r"(\d{6,9})-?([\dK])", v)
        if m:
            r = m.group(1) + "-" + m.group(2)
            if certificado.rut_ok(r):
                return r
            vistos.append(r)
    return vistos[0] if vistos else ""


def leer_celdas(g):
    """Imagen gris de una denuncia del MTT -> {clave: valor} leyendo cada celda por separado, o None."""
    g2 = tablas.enderezar(g)
    tb = tablas.tablas(g2)
    if [len(t[0]) - 1 for t in tb] != [5, 5, 4]:
        return None
    out = {}
    for (ys, xd, xr), claves in zip(tb, CLAVES_TABLAS):
        for i, k in enumerate(claves):
            c = tablas.celda(g2, ys[i], ys[i + 1], xd, xr)
            if k == "placa":
                out[k] = _celda_placa(c)
            elif k == "rut":
                out[k] = _celda_rut(c)
            elif k == "boleta":
                out[k] = _leer(c, _cfg(7, "0123456789"))
            elif k == "anio":
                out[k] = _leer(c, _cfg(7, "0123456789"))
            elif k in ("fecha_cit", "hora_cit"):
                out[k] = _leer(c, _cfg(7, "0123456789-:/"))
            else:
                v = _leer(c, _cfg(7), punto=(k == "inspector"))
                out[k] = re.sub(r"^([A-Za-z]),\s*", r"\1. ", v) if k == "inspector" else v
    return out


# ---------- parte de Carabineros: releer con otros contrastes si faltan datos ----------
def _realzar(g, modo):
    import numpy as np
    from PIL import ImageOps
    if modo == "auto":
        return ImageOps.autocontrast(g, cutoff=2)
    a = np.array(ImageOps.autocontrast(g, cutoff=1))
    fondo = np.percentile(a, 90)
    return Image.fromarray(np.where(a < fondo * 0.8, 0, 255).astype(np.uint8))


CAMPOS_CARAB = ("n_parte_carab", "boleta", "fecha_parte", "hora_infraccion", "lugar", "infraccion_texto",
                "infractor_nombre", "fecha_citacion")


def _combinar_carab(pasadas):
    from . import extractor_carab as EC
    mejor = min(pasadas, key=lambda r: (EC.problemas(r), -EC.placa_puntaje(r["placa"])))
    r = dict(mejor)
    for k in CAMPOS_CARAB:
        if not r[k]:
            for o in pasadas:
                if o[k]:
                    r[k] = o[k]
                    break
    if r["tiene_vehiculo"]:
        cand = [o["placa"] for o in pasadas if o["placa"]]
        if cand:
            r["placa"] = max(cand, key=lambda p: (EC.placa_puntaje(p), cand.count(p)))
            r["placas_leidas"] = sorted(set(cand))
    if not r["infractor_rut"]:
        for o in pasadas:
            if o["infractor_rut"]:
                r["infractor_rut"] = o["infractor_rut"]
                r["aviso_infractor"] = o["aviso_infractor"]
                break
    return r


def _dudoso_carab(r):
    from . import extractor_carab as EC
    return (EC.problemas(r) > 0 or (r["tiene_vehiculo"] and EC.placa_puntaje(r["placa"]) < 2)
            or "?" in r["fecha_parte"])


def leer_carab(g, texto):
    """Lee un parte de Carabineros. Los escaneos tenues a veces salen con datos que faltan o dudosos: en ese caso
    se vuelve a leer la hoja con más contraste y se completa con lo mejor de cada lectura."""
    from . import extractor_carab as EC
    pasadas = [EC.parte(texto)]
    r = _combinar_carab(pasadas)
    for modo in ("auto", "thr"):
        if not _dudoso_carab(r):
            break
        big = _realzar(g, modo)
        big = big.resize((int(big.width * 1.4), int(big.height * 1.4)), Image.BICUBIC)
        pasadas.append(EC.parte(pytesseract.image_to_string(big, lang="spa", config="--psm 6")))
        r = _combinar_carab(pasadas)
    if r["tiene_vehiculo"]:   # siempre se relee la patente: un 8 leído como 3 también «parece» una patente válida
        otra = releer_placa(g)
        if otra and otra != r["placa"] and r["placa"]:
            r["placas_leidas"] = sorted({otra, r["placa"]})
        if otra and EC.placa_puntaje(otra) > EC.placa_puntaje(r["placa"]) or (otra and not r["placa"]):
            r["placa"] = otra
    if not r["boleta"]:
        otras = releer_boleta(g)
        if len(otras) == 1:
            r["boleta"] = otras[0]
    av = []
    if not r["n_parte_carab"]:
        av.append("No pude leer el número del parte de Carabineros.")
    if not r["boleta"]:
        av.append("No pude leer el N° de la boleta; escríbelo a mano.")
    else:
        conf = boleta_confianza(g)
        if conf is not None and conf < 80:
            av.append("N° de boleta (folio) leído con poca seguridad (%s): puede haber una firma encima; compáralo con el parte." % r["boleta"])

    av += cotejar_segundo_motor(g, r)

    if not r["infraccion_texto"]:
        av.append("No pude leer la infracción.")
    if r["tiene_vehiculo"] and not r["placa"]:
        av.append("No pude leer la patente.")
    elif r["placa"] and EC.placa_puntaje(r["placa"]) == 0:
        av.append("La patente leída (%s) no tiene un formato válido: revísala." % r["placa"])
    elif r["placa"] and EC.placa_puntaje(r["placa"]) == 1:
        av.append("La patente leída (%s) tiene una vocal, poco común: compárala con el parte." % r["placa"])
    if len(r.get("placas_leidas", [])) > 1:
        av.append("La patente se leyó distinto en las pasadas (%s): compárala con el parte." % " / ".join(r["placas_leidas"]))
    if not r["fecha_parte"]:
        av.append("No pude leer la fecha del parte.")
    elif r.get("anio_leido"):
        av.append("El año de la fecha del parte se leyó «%s»: se corrigió al año en curso (%s)." % (r["anio_leido"], r["fecha_parte"][-4:]))
    r["avisos"] = av
    r["texto_ocr"] = texto
    r["pasadas"] = len(pasadas)
    return r


def boleta_confianza(g):
    """Seguridad (0-100) con que el OCR leyó el número que sigue a «BOLETA … NRO.»; None si no lo ubica.
    Una firma encima del número baja mucho este valor."""
    from pytesseract import Output
    big = _realzar(g, "auto")
    big = big.resize((int(big.width * 1.4), int(big.height * 1.4)), Image.BICUBIC)
    d = pytesseract.image_to_data(big, lang="spa", config="--psm 6", output_type=Output.DICT)
    ws = [i for i in range(len(d["text"])) if d["text"][i].strip()]
    vals = []
    for k, i in enumerate(ws):
        if re.fullmatch(r"(?i)boleta", d["text"][i].strip()):
            for j in range(k + 1, min(k + 7, len(ws))):
                if re.fullmatch(r"(?i)(nro\.?|n[°º*]|n[uú]mero),?", d["text"][ws[j]].strip()) and j + 1 < len(ws):
                    t = ws[j + 1]
                    if re.search(r"\d{4}", d["text"][t]):
                        vals.append(float(d["conf"][t]))
                    break
    return min(vals) if vals else None


def _boleta_cerca(plano):
    """El segundo lector entrega los cuadros de texto en otro orden: el número puede quedar antes o después de la
    palabra BOLETA. Busca un número de 5-6 dígitos a menos de 70 caracteres (primero después, luego antes)."""
    rx = r"(?<![\d.])\d{5,6}(?![\d.])"
    for m in re.finditer(r"BOLETA", plano, re.I):
        despues = [x for x in re.findall(rx, plano[m.end():m.end() + 70]) if x not in ("18290", "19925")]
        antes = [x for x in re.findall(rx, plano[max(0, m.start() - 70):m.start()]) if x not in ("18290", "19925")]
        if despues:
            return despues[0]
        if antes:
            return antes[-1]
    return ""


def cotejar_segundo_motor(g, r):
    """Relee con un segundo OCR (RapidOCR) la boleta, la patente y el RUT. Completa lo que Tesseract no leyó y avisa
    cuando los dos motores leen distinto. Devuelve la lista de avisos; si el motor no está instalado, no hace nada."""
    from . import extractor_carab as EC, ocr2
    if not ocr2.disponible():
        return []
    txt = ocr2.leer(g)
    if not txt:
        return []
    b = EC.parte(txt)
    av = []
    plano = re.sub(r"\s+", " ", txt)
    bol2 = b["boleta"] or _boleta_cerca(plano)
    n = lambda x: (x or "").lstrip("0")
    if bol2:
        if not r["boleta"]:
            r["boleta"] = bol2
            av.append("N° de boleta (%s) leído solo por el segundo lector: compáralo con el parte." % bol2)
        elif n(bol2) != n(r["boleta"]):
            r["boleta_alt"] = bol2
            av.append("N° de boleta: los dos lectores leyeron distinto (%s / %s). Mira el parte y elige el correcto." % (r["boleta"], bol2))
    if r["tiene_vehiculo"] and b["placa"] and EC.placa_puntaje(b["placa"]) >= 1:
        if not r["placa"]:
            r["placa"] = b["placa"]
            av.append("Patente (%s) leída solo por el segundo lector: compárala con el parte." % b["placa"])
        elif b["placa"] != r["placa"]:
            r["placa_alt"] = b["placa"]
            av.append("Patente: los dos lectores leyeron distinto (%s / %s). Mira el parte y elige la correcta." % (r["placa"], b["placa"]))
    rut1 = r.get("rut_leido") or r.get("infractor_rut") or ""
    rut2 = b.get("rut_leido") or b.get("infractor_rut") or ""
    if rut1 and rut2 and rut1 != rut2:
        av.append("RUT del infractor: los dos lectores leyeron distinto (%s / %s). Compáralo con el parte." % (rut1, rut2))
    return av


def releer_boleta(g):
    """Vuelve a leer, ampliado y solo con dígitos, el número que sigue a «BOLETA … NRO.» (a veces la firma lo cruza).
    Devuelve la lista de lecturas distintas de 4 a 7 dígitos (puede ser vacía)."""
    from pytesseract import Output
    from PIL import ImageOps
    out = []
    for modo in ("auto", "thr"):
        big = _realzar(g, modo)
        big = big.resize((int(big.width * 1.4), int(big.height * 1.4)), Image.BICUBIC)
        d = pytesseract.image_to_data(big, lang="spa", config="--psm 6", output_type=Output.DICT)
        ws = [i for i in range(len(d["text"])) if d["text"][i].strip()]
        txt = lambda i: d["text"][i].strip()
        ks = [k for k, i in enumerate(ws) if re.fullmatch(r"(?i)boleta", txt(i))]
        for k in ks:
            for j in range(k + 1, min(k + 7, len(ws))):
                if re.fullmatch(r"(?i)(nro\.?|n[°º*]|n[uú]mero),?", txt(ws[j])) and j + 1 < len(ws):
                    sel = [ws[j + 1]]
                    box = (max(0, d["left"][sel[0]] - 20), max(0, d["top"][sel[0]] - 14),
                           min(big.width, d["left"][sel[0]] + d["width"][sel[0]] + 20), min(big.height, d["top"][sel[0]] + d["height"][sel[0]] + 14))
                    c = big.crop(box)
                    c = ImageOps.expand(c.resize((c.width * 3, c.height * 3), Image.BICUBIC), border=25, fill=255)
                    v = re.sub(r"\D", "", pytesseract.image_to_string(c, lang="spa", config="--psm 7 -c tessedit_char_whitelist=0123456789"))
                    if 4 <= len(v) <= 7 and v not in out:
                        out.append(v)
                    break
    return out


def releer_placa(g):
    """Ubica el párrafo «VEHICULO: …» de la hoja y lee solo su última palabra (la patente), ampliada y con el
    alfabeto de las patentes (consonantes y números). Devuelve '' si no la encuentra."""
    from pytesseract import Output
    from PIL import ImageOps
    from . import extractor_carab as EC
    big = _realzar(g, "auto")
    big = big.resize((int(big.width * 1.4), int(big.height * 1.4)), Image.BICUBIC)
    d = pytesseract.image_to_data(big, lang="spa", config="--psm 6", output_type=Output.DICT)
    ws = [i for i in range(len(d["text"])) if d["text"][i].strip()]
    txt = lambda i: d["text"][i].strip()
    etiquetas = [k for k, i in enumerate(ws) if re.fullmatch(r"(?i)veh[ií]culo\s*:", txt(i)) or
                 (re.fullmatch(r"(?i)veh[ií]culo", txt(i)) and k + 1 < len(ws) and txt(ws[k + 1]).startswith(":"))]
    if not etiquetas:
        etiquetas = [k for k, i in enumerate(ws) if re.fullmatch(r"(?i)veh[ií]culo", txt(i)) and
                     any(re.search(r"(?i)marca|modelo|tipo", txt(j)) for j in ws[k + 1:k + 4])]
    if not etiquetas:
        return ""
    k0 = etiquetas[-1]
    fin = len(ws)
    for k in range(k0 + 1, len(ws)):
        if re.fullmatch(r"(?i)(TESTIGO|DENUNCIANTE|OBSERVACI\w*|CITACI\w*|LICENCIA|DOCUMENTOS|REINCIDENCIAS?|INFRACCI\w*|INFRACTOR)\s*:?", txt(ws[k])):
            fin = k
            break
    par = ws[k0 + 1:fin]
    if len(par) < 2:
        return ""
    for n in (1, 2):
        sel = par[-n:]
        box = (max(0, min(d["left"][i] for i in sel) - 14), max(0, min(d["top"][i] for i in sel) - 12),
               min(big.width, max(d["left"][i] + d["width"][i] for i in sel) + 14),
               min(big.height, max(d["top"][i] + d["height"][i] for i in sel) + 12))
        c = big.crop(box)
        c = ImageOps.expand(c.resize((c.width * 2, c.height * 2), Image.BICUBIC), border=25, fill=255)
        cfg = "--psm 7 -c tessedit_char_whitelist=" + EC.CONSONANTES + "0123456789-. "
        v = re.sub(r"\s+", " ", pytesseract.image_to_string(c, lang="spa", config=cfg)).upper()
        m = re.findall(r"([A-Z]{2,4})\s*[-.]?\s*(\d{2})(?:\s*[-.]?\s*(\d{2}))?", v)
        if m:
            return "".join(m[-1])
    return ""
