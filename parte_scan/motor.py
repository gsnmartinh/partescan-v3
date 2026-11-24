"""Motor de lectura: imagen/PDF -> campos del parte. Tesseract como principal y respaldo secundario."""
import os, re, sys
from collections import Counter

import pytesseract
from PIL import Image

from . import extractor, tablas, ocr2, lectura


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
        doc = pdfium.PdfDocument(ruta)
        try:
            for i in range(len(doc)):
                yield doc[i].render(scale=dpi / 72).to_pil().convert("L")
        finally:
            doc.close()
        return
    if ext in EXTS_IMG:
        im = Image.open(ruta)
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        yield im.convert("L")
    return


def preparar(img):
    g = img.convert("L")
    if g.width > 2600:  # fotos grandes: bajar a un tamaño razonable
        f = 2600 / g.width
        g = g.resize((2600, int(g.height * f)), Image.BICUBIC)
    g.info.update(img.info)
    return g


def texto_pagina(g):
    """OCR principal con Tesseract; si no entrega suficiente texto, utiliza RapidOCR como respaldo."""
    big = g.resize((int(g.width * 1.4), int(g.height * 1.4)), Image.BICUBIC)
    txt_tess = _releer_zona(big, 6)
    
    # Si Tesseract lee bien y trae suficiente contenido, lo devolvemos como principal
    if lectura.puntaje(txt_tess) >= 12:
        return txt_tess

    # Respaldo secundario con RapidOCR si Tesseract falla o queda muy pobre
    if ocr2.disponible():
        txt_rapid = ocr2.leer(g)
        if lectura.puntaje(txt_rapid) > lectura.puntaje(txt_tess):
            return txt_rapid

    return txt_tess


def _folio_recorte(g):
    """Lee el N° de parte recortando el encabezado usando Tesseract."""
    W = g.width
    top = g.crop((0, 0, W, int(g.height * 0.30)))
    d = pytesseract.image_to_data(top, lang="spa", config="--psm 6", output_type=pytesseract.Output.DICT, timeout=20)
    
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
                                            config="--psm 7 -c tessedit_char_whitelist=0123456789", timeout=20)
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


def _releer_zona(imagen, modo):
    try:
        return pytesseract.image_to_string(imagen, lang="spa", config=f"--psm {modo}", timeout=20)
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError, RuntimeError):
        return ""



def zona_por_etiqueta(imagen, patron, margen=.12):
    if not imagen.info.get("ocr_lineas"):
        try:
            datos = pytesseract.image_to_data(imagen, lang="spa", config="--psm 6",
                                             output_type=pytesseract.Output.DICT, timeout=20)
            grupos = {}
            for i, palabra in enumerate(datos["text"]):
                if palabra.strip():
                    clave = tuple(datos[k][i] for k in ("block_num", "par_num", "line_num"))
                    grupos.setdefault(clave, []).append(i)
            lineas = []
            for indices in grupos.values():
                caja = [min(datos["left"][i] for i in indices) / imagen.width,
                        min(datos["top"][i] for i in indices) / imagen.height,
                        max(datos["left"][i] + datos["width"][i] for i in indices) / imagen.width,
                        max(datos["top"][i] + datos["height"][i] for i in indices) / imagen.height]
                lineas.append({"texto": " ".join(datos["text"][i] for i in indices), "caja": caja})
            imagen.info["ocr_lineas"] = lectura.lineas_espaciales(lineas)
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError, RuntimeError):
            pass
    return lectura.zona_etiqueta(imagen, patron, margen)


def texto_respaldo(imagen):
    from PIL import ImageOps
    variantes = [_releer_zona(imagen, 6), _releer_zona(ImageOps.autocontrast(imagen), 4)]
    if ocr2.disponible():
        variantes.append(ocr2.leer(imagen))
    return max(variantes, key=lectura.puntaje)

def releer_franja(imagen, inicio, fin):
    ancho, alto = imagen.size
    return _releer_zona(imagen.crop((0, int(alto * inicio), ancho, int(alto * fin))), 6)


def leer_certificado(g, texto, *, imagen=None):
    from . import catalogo, certificado

    datos = certificado.leer(texto)
    campos = ("nombre", "rut", "direccion", "comuna", "placa")

    def valido(campo, valor):
        if campo == "rut":
            return certificado.rut_ok(valor)
        if campo == "comuna":
            return bool(valor) and catalogo.comuna_en_sistema(valor)
        if campo == "placa":
            return extractor.placa_ok(valor) and not re.fullmatch(r"(?=[A-Z]{4}\d{2}$)[A-Z]*[AEIOU][A-Z]*\d{2}", valor)
        return lectura.valido(campo, valor)

    faltan = [k for k in campos if not valido(k, datos[k])]
    if faltan:
        if g is None:
            g = preparar(imagen)
        ancho, alto = g.size
        etiquetas = {"nombre": "nombre", "rut": "rut", "direccion": "dirección", "comuna": "comuna", "placa": "placa"}
        for k, limites in (("placa", (0, 0.53)), ("rut", (0.25, 0.85))):
            if k not in faltan:
                continue
            zona = g.crop((0, int(alto * limites[0]), ancho, int(alto * limites[1])))
            recorte = _releer_zona(zona, 6)
            otros = certificado.leer(recorte)
            if valido(k, otros[k]):
                datos[k] = otros[k]
                if k == "placa":
                    datos["dv_placa"] = otros["dv_placa"]
                datos["avisos"] = [a for a in datos["avisos"] if etiquetas[k] not in a.lower()]
                faltan.remove(k)
    if faltan:
        # La segmentación por columnas recupera líneas que el modo de bloque mezcla u omite.
        zona = zona_por_etiqueta(g, r"DATOS\s+DEL\s+PROPIETARIO", .4) or g
        alternativo = _releer_zona(zona, 4)
        if re.search(r"\bPROPIETARIO\b", alternativo, re.I):
            otros = certificado.leer(alternativo)
            for k in faltan:
                if valido(k, otros[k]):
                    datos[k] = otros[k]
                    if k == "placa":
                        datos["dv_placa"] = otros["dv_placa"]
                    datos["avisos"] = [a for a in datos["avisos"] if etiquetas[k] not in a.lower()]
    return datos


def tipo_pagina(texto):
    """'parte', 'carab' (parte de Carabineros), 'mtt' (denuncia del MTT), 'certificado' u 'otra'."""
    from . import certificado, extractor_carab, extractor_mtt, extractor_armada
    if certificado.es_certificado(texto):
        return "certificado"
    if extractor_armada.es_armada(texto):
        return "armada"
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
        if not r["fecha_parte"] and img is not None:
            cabecera = releer_franja(g if g is not None else preparar(img), 0, 0.32)
            r["fecha_parte"] = extractor.fecha_documento(cabecera)
        r["oficina"] = perfil.oficinas().get("33", "33")
        r["texto_ocr"] = texto
        return r
    if solo_texto:
        texto = extractor.completar_lineas_movil(texto)
    r = extractor.parte(texto)
    if es_formulario_inspeccion(texto):
        from . import perfil
        r["oficina"] = perfil.oficinas().get("32", "32")
        if not lectura.valido("fecha", r["fecha_infraccion"]) or not lectura.valido("hora", r["hora_infraccion"]):
            gris = g if g is not None else preparar(img)
            ancho, alto = gris.size
            zona = zona_por_etiqueta(gris, r"Doy\s+cuenta") or gris.crop((0, int(alto * 0.18), ancho, int(alto * 0.48)))
            respaldo = _releer_zona(zona, 6)
            fecha, hora = extractor.momento_infraccion(respaldo.splitlines())
            r["fecha_infraccion"] = r["fecha_infraccion"] if lectura.valido("fecha", r["fecha_infraccion"]) else fecha
            r["hora_infraccion"] = r["hora_infraccion"] if lectura.valido("hora", r["hora_infraccion"]) else hora
    campos = ["fecha_parte", "fecha_infraccion", "hora_infraccion", "lugar", "infraccion_texto", "fecha_citacion"]
    if r["tipo_vehiculo"] or r["marca"]:
        campos.append("placa")
    if img is not None and any(not lectura.valido(k, r[k]) for k in campos):
        gris = g if g is not None else preparar(img)
        respaldo = extractor.parte(texto_respaldo(gris))
        if ocr2.disponible():
            segundo = extractor.parte(ocr2.leer(gris))
            for campo in campos:
                if not lectura.valido(campo, respaldo[campo]) and lectura.valido(campo, segundo[campo]):
                    respaldo[campo] = segundo[campo]
                elif (lectura.valido(campo, respaldo[campo]) and lectura.valido(campo, segundo[campo])
                      and respaldo[campo] != segundo[campo]):
                    r["avisos"].append("Segunda lectura de %s: alternativas %s / %s. Revisa la imagen." %
                                       (campo, respaldo[campo], segundo[campo]))
                    respaldo[campo] = ""
        for campo in campos:
            if not lectura.valido(campo, r[campo]) and lectura.valido(campo, respaldo[campo]):
                r[campo] = respaldo[campo]
    r["folio_recorte"] = _folio_recorte(g if g is not None else preparar(img)) if (
        not solo_texto or (img is not None and not (r["n_parte"] or r["n_citacion_adjunta"]))
    ) else ""
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
    v = re.sub(r"\s+", " ", pytesseract.image_to_string(c, lang=lang, config=cfg, timeout=20)).strip(" |_-—,;:'\"")
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


def leer_armada(g, texto, *, imagen=None):
    from . import extractor_armada as EA
    r = EA.parte(texto)
    anterior = any("anterior al patrullaje" in a for a in r["avisos"])
    if (not r["numero_armada"] or not r["fecha_parte"] or anterior) and (g is not None or imagen is not None):
        gris = g if g is not None else preparar(imagen)
        cabecera = releer_franja(gris, 0, .30)
        b = EA.parte(cabecera)
        if anterior and (not b["fecha_parte"] or b["fecha_parte"] == r["fecha_parte"]):
            color = imagen if imagen is not None else gris
            zona = color.crop((0, 0, color.width, int(color.height*.30)))
            zona.thumbnail((1700, 1500), Image.Resampling.LANCZOS)
            alternativo = EA.parte(_releer_zona(zona, 6))
            if alternativo["fecha_parte"]:
                b["fecha_parte"] = alternativo["fecha_parte"]
        if not r["numero_armada"] and b["numero_armada"]:
            r["numero_armada"] = b["numero_armada"]
        if (not r["fecha_parte"] or anterior) and b["fecha_parte"]:
            r["fecha_parte"] = b["fecha_parte"]
        r["avisos"] = [a for a in r["avisos"] if not ((r["numero_armada"] and "N° de parte" in a) or (r["fecha_parte"] and a.startswith("Revisa la fecha del informe")))]
        if r["fecha_parte"] and r["fecha_infraccion"]:
            import datetime
            if datetime.datetime.strptime(r["fecha_parte"], "%d/%m/%Y") >= datetime.datetime.strptime(r["fecha_infraccion"], "%d/%m/%Y"):
                r["avisos"] = [a for a in r["avisos"] if "anterior al patrullaje" not in a]
    return r


def releer_identidad_carab(gris, r, *, imagen=None):
    """Recupera líneas mezcladas solo si el recorte confirma el mismo RUT válido."""
    from . import extractor_carab as EC
    if r.get("empadronado") or len(r.get("infractores", [])) > 1 or not lectura.valido("rut", r.get("infractor_rut", "")):
        return
    dudosos = EC.identidad_dudosa(r)
    if not any(dudosos.values()):
        return
    zona = zona_por_etiqueta(gris, r"\bINFRACTOR\s*:", .22)
    if zona is None:
        zona = gris.crop((0, int(gris.height*.15), gris.width, int(gris.height*.72)))
    b = EC.parte(_releer_zona(zona, 6))
    r["pasadas_identidad"] = 1
    if b["infractor_rut"] != r["infractor_rut"] and imagen is not None:
        zona = imagen.crop((0, int(imagen.height*.37), imagen.width, int(imagen.height*.72)))
        zona.thumbnail((1700, 1500), Image.Resampling.BICUBIC)
        b = EC.parte(_releer_zona(zona, 6))
    if b["infractor_rut"] != r["infractor_rut"]:
        return
    malos = EC.identidad_dudosa(b)
    if dudosos["infractor_direccion"] and b["infractor_nombre"].startswith(r["infractor_nombre"] + " "):
        dudosos["infractor_nombre"] = True
    for campo, dudoso in dudosos.items():
        if dudoso and not malos[campo] and lectura.valido(campo, b[campo]):
            r[campo] = b[campo]
    if len(r.get("infractores", [])) == 1:
        for k in ("nombre", "direccion", "comuna"):
            r["infractores"][0][k] = r["infractor_" + k]


def leer_carab(g, texto, *, imagen=None):
    """Lee un parte de Carabineros priorizando Tesseract y utilizando validación cruzada con RapidOCR."""
    from . import extractor_carab as EC
    
    # El texto de entrada ya viene procesado por Tesseract desde texto_pagina()
    r = EC.parte(texto)
    av = []

    # Validaciones y respaldos secundarios con RapidOCR
    if g is not None:
        av += cotejar_con_rapidocr(g, r)
    elif imagen is not None:
        campos = ["n_parte_carab", "fecha_parte", "hora_infraccion", "lugar", "infraccion_texto"]
        if r["tiene_vehiculo"]:
            campos.append("placa")
        if any(not lectura.valido(campo, r[campo]) for campo in campos):
            gris = preparar(imagen)
            respaldo = EC.parte(texto_respaldo(gris))
            for campo in campos:
                if not lectura.valido(campo, r[campo]) and lectura.valido(campo, respaldo[campo]):
                    r[campo] = respaldo[campo]
                    if campo == "infraccion_texto":
                        r["bloques_infraccion"] = respaldo["bloques_infraccion"]
    if (g is not None or imagen is not None) and any(EC.identidad_dudosa(r).values()):
        releer_identidad_carab(g if g is not None else preparar(imagen), r, imagen=imagen)
    if (not r["fecha_citacion"] or not r["boleta"]) and (g is not None or imagen is not None):
        franja = releer_franja(g if g is not None else preparar(imagen), 0.45, 1)
        fechas = EC.fechas_citacion_recorte(franja) if not r["fecha_citacion"] else []
        if len(fechas) == 1:
            r["fecha_citacion"] = fechas[0]
        elif fechas:
            r["fechas_citacion"] = fechas
        if not r["boleta"]:
            r["boleta"] = EC._boleta_texto(franja)
            r["n_parte_final"] = r["boleta"]
    if not r["fecha_citacion"]:
        av.append("Revisa la fecha en el bloque de citación del parte.")

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
