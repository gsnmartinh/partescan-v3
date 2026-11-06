"""Motor de lectura: imagen/PDF -> campos del parte. Tesseract como principal y respaldo secundario."""
import os, re, sys
from collections import Counter

import pytesseract
from PIL import Image

from . import extractor, tablas, ocr2


def _base():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def configurar_tesseract():
    """Usa el Tesseract incluido junto al programa como respaldo; en desarrollo usa el del sistema."""
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


def preparar(img):
    g = img.convert("L")
    if g.width > 2600:  # fotos grandes: bajar a un tamaño razonable
        f = 2600 / g.width
        g = g.resize((2600, int(g.height * f)), Image.BICUBIC)
    return g


def texto_pagina(g):
    """OCR principal con Tesseract; si no entrega suficiente texto, utiliza RapidOCR como respaldo."""
    big = g.resize((int(g.width * 1.4), int(g.height * 1.4)), Image.BICUBIC)
    txt_tess = pytesseract.image_to_string(big, lang="spa", config="--psm 6")
    
    # Si Tesseract lee bien y trae suficiente contenido, lo devolvemos como principal
    if txt_tess and len(txt_tess.strip()) > 15:
        return txt_tess

    # Respaldo secundario con RapidOCR si Tesseract falla o queda muy pobre
    if ocr2.disponible():
        txt_rapid = ocr2.leer(g)
        if txt_rapid and len(txt_rapid.strip()) > 15:
            return txt_rapid

    return txt_tess


def _folio_recorte(g):
    """Lee el N° de parte recortando el encabezado usando Tesseract."""
    W = g.width
    top = g.crop((0, 0, W, int(g.height * 0.30)))
    d = pytesseract.image_to_data(top, lang="spa", config="--psm 6", output_type=pytesseract.Output.DICT)
    
    def _lineas(dt):
        L = {}
        for i, w in enumerate(dt["text"]):
            if w.strip():
                L.setdefault((dt["block_num"][i], dt["par_num"][i], dt["line_num"][i]), []).append(i)
        return sorted(L.values(), key=lambda idx: min(dt["top"][i] for i in idx))

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


def es_formulario_inspeccion(texto):
    """Reconoce el formulario municipal por sus campos, aunque cambie el encabezado."""
    return (all(re.search(campo, texto, re.I) for campo in (
        r"\bdisposici[oó]n\s+infringida\b",
        r"\b(?:e[lr]\s*)?infractor\s+qued[oó]\s+citado\b",
    )) and bool(re.search(r"\binspector\s+denunciante\b", texto, re.I)
                or re.search(r"\b(?:inspecci[oó]n\s+general|seguridad\s+ciudadana)\b",
                             texto[:400], re.I)))


def leer_certificado(g, texto):
    from . import catalogo, certificado

    datos = certificado.leer(texto)
    campos = ("nombre", "rut", "direccion", "comuna")

    def valido(campo, valor):
        if campo == "rut":
            return certificado.rut_ok(valor)
        if campo == "comuna":
            return bool(valor) and catalogo.comuna_en_sistema(valor)
        return bool(valor)

    faltan = [k for k in campos if not valido(k, datos[k])]
    if faltan:
        # La segmentación por columnas recupera líneas que el modo de bloque mezcla u omite.
        alternativo = pytesseract.image_to_string(g, lang="spa", config="--psm 4")
        if re.search(r"\bPROPIETARIO\b", alternativo, re.I):
            otros = certificado.leer(alternativo)
            etiquetas = {"nombre": "nombre", "rut": "rut", "direccion": "dirección", "comuna": "comuna"}
            for k in faltan:
                if valido(k, otros[k]):
                    datos[k] = otros[k]
                    datos["avisos"] = [a for a in datos["avisos"] if etiquetas[k] not in a.lower()]
    return datos


def tipo_pagina(texto):
    """'parte', 'carab' (parte de Carabineros), 'mtt' (denuncia del MTT), 'certificado' u 'otra'."""
    from . import certificado, extractor_carab, extractor_mtt
    if certificado.es_certificado(texto):
        return "certificado"
    if extractor.es_os10(texto):
        return "parte"
    if extractor.es_dom(texto):
        return "dom"
    if es_formulario_inspeccion(texto):
        return "parte"
    if extractor_mtt.es_mtt(texto):
        return "mtt"
    if extractor_carab.es_carab(texto):
        return "carab"
    if re.search(r"DENUNCI|Doy\s+cuenta|JUZGADO\s+DE\s+POLIC", texto, re.I):
        return "parte"
    return "otra"


def leer_parte(img, texto=None, g=None, *, solo_texto=False):
    """Imagen PIL (gris) -> dict con los campos leídos usando Tesseract como base."""
    if not solo_texto:
        g = g or preparar(img)
    texto = texto if texto is not None else texto_pagina(g)
    if extractor.es_os10(texto):
        from . import perfil
        r = extractor.parte_os10(texto)
        r["oficina"] = perfil.oficinas().get("33", "33")
        r["texto_ocr"] = texto
        return r
    if solo_texto:
        texto = extractor.completar_lineas_movil(texto)
    r = extractor.parte(texto)
    if es_formulario_inspeccion(texto):
        from . import perfil
        r["oficina"] = perfil.oficinas().get("32", "32")
    r["folio_recorte"] = "" if solo_texto else _folio_recorte(g)
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
    for cfg, lang in ((_cfg(7, "0123456789Kk-."), "spa"), (_cfg(7), "spa")):
        v = re.sub(r"[^0-9Kk-]", "", _leer(c, cfg, lang)).upper()
        m = re.fullmatch(r"(\d{6,9})-?([\dK])", v)
        if m:
            r = m.group(1) + "-" + m.group(2)
            if certificado.rut_ok(r):
                return r
            vistos.append(r)
    return vistos[0] if vistos else ""


def leer_celdas(g):
    """Imagen gris de una denuncia del MTT -> {clave: valor} leyendo cada celda."""
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


# ---------- parte de Carabineros con Tesseract principal ----------
CAMPOS_CARAB = ("n_parte_carab", "boleta", "fecha_parte", "hora_infraccion", "lugar", "infraccion_texto",
                "infractor_nombre", "fecha_citacion")


def cotejar_con_rapidocr(g, r):
    """Usa RapidOCR como motor secundario para cotejar datos críticos frente a Tesseract."""
    if not ocr2.disponible():
        return []
    from . import extractor_carab as EC
    try:
        txt_rapid = ocr2.leer(g)
        b = EC.parte(txt_rapid)
        av = []
        
        # Cotejar boleta
        n = lambda x: (x or "").lstrip("0")
        if b["boleta"] and r["boleta"] and n(b["boleta"]) != n(r["boleta"]):
            r["boleta_rapid"] = b["boleta"]
            av.append("N° de boleta: los dos motores difieren (Tesseract: %s / RapidOCR: %s). Revísalo." % (r["boleta"], b["boleta"]))
        elif b["boleta"] and not r["boleta"]:
            r["boleta"] = b["boleta"]
            av.append("N° de boleta (%s) recuperado por RapidOCR como respaldo." % b["boleta"])

        # Cotejar patente
        if r.get("tiene_vehiculo") and b["placa"] and EC.placa_puntaje(b["placa"]) >= 1:
            if r["placa"] and b["placa"] != r["placa"]:
                r["placa_rapid"] = b["placa"]
                av.append("Patente: los dos motores difieren (Tesseract: %s / RapidOCR: %s). Revísala." % (r["placa"], b["placa"]))
            elif not r["placa"]:
                r["placa"] = b["placa"]
                av.append("Patente (%s) recuperada por RapidOCR como respaldo." % b["placa"])
        return av
    except Exception:
        return []


def leer_carab(g, texto):
    """Lee un parte de Carabineros priorizando Tesseract y utilizando validación cruzada con RapidOCR."""
    from . import extractor_carab as EC
    
    # El texto de entrada ya viene procesado por Tesseract desde texto_pagina()
    r = EC.parte(texto)
    av = []

    # Validaciones y respaldos secundarios con RapidOCR
    if g is not None:
        av += cotejar_con_rapidocr(g, r)

    if not r["n_parte_carab"]:
        av.append("No pude leer el número del parte de Carabineros.")
    if not r["boleta"]:
        av.append("No pude leer el N° de la boleta; escríbelo a mano.")
    if not r["infraccion_texto"]:
        av.append("No pude leer la infracción.")
    if r["tiene_vehiculo"] and not r["placa"]:
        av.append("No pude leer la patente.")
    elif r["placa"] and EC.placa_puntaje(r["placa"]) == 0:
        av.append("La patente leída (%s) no tiene un formato válido: revísala." % r["placa"])
    if not r["fecha_parte"]:
        av.append("No pude leer la fecha del parte.")

    r["avisos"] = av
    r["texto_ocr"] = texto
    r["pasadas"] = 1
    return r
