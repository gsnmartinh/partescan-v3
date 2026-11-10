"""Servidor local: sirve la pantalla en el navegador y lee los partes con Tesseract.
Todo ocurre en este computador; no se envía nada a internet."""
import base64, secrets, socket
import io, json, os, sys, zipfile, time, queue, re, shutil, tempfile, threading, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import actualizador, busqueda, catalogo, certificado, equivalencia, exportar, extractor_mtt, motor, perfil, tecleador

WEB = os.path.join(motor._base(), "parte_scan", "web")
if not os.path.isdir(WEB):
    WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

PARTES = []          # resultados, en orden
TEXTOS = {}          # id de imagen -> OCR original
IMAGENES = {}        # id -> imagen PIL
COLA = queue.Queue()
ESTADO = {"pendientes": 0, "error": ""}
LOCK = threading.Lock()
LOCK_BUSQUEDA = threading.Lock()
TMP = tempfile.mkdtemp(prefix="partescan_")


def comprobar_actualizacion_segura():
    if ESTADO["pendientes"] or tecleador.corriendo():
        raise ValueError("Termina el escaneo y el tecleo antes de instalar la actualización.")


def hora(h):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", h or "")
    return "%02d:%s" % (int(m.group(1)), m.group(2)) if m else ""


def orden_natural(text):
    """Ordena los nombres de archivo de forma natural (ej. parte_2 va antes que parte_10)."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]


def armar(r, archivo, pagina, pid):
    causa, items, comodin = catalogo.resolver_o_comodin(r["infraccion_texto"])
    escrito = r.get("parte_escrito", False) or (not r["placa"] and catalogo.actividad_sin_patente(r["infraccion_texto"]))
    personal = r.get("notificado_personalmente", False)
    avisos = list(r["avisos"])
    for bloque in r.get("bloques_infraccion", []):
        _, adicionales = catalogo.resolver(bloque)
        for item in adicionales:
            if item["cod"] == "19" and any(i["cod"] == "43" for i in items) and re.search(r"LINEA\s+AMARILLA", catalogo.sin_tildes(bloque)):
                continue
            if item["cod"] not in {i["cod"] for i in items}:
                items.append(dict(item, estado="check", nota="Confirma esta infracción adicional en la imagen: " + bloque))
    if len(items) > 1:
        avisos.append("Revisa la imagen y confirma que estén todas las infracciones del parte.")
    if personal:
        avisos.append("Notificado personalmente: revisa los datos del infractor y el orden de nombres y apellidos.")
    if comodin:
        avisos.append("No reconocí la infracción: se ingresará con el código %s y la descripción dirá lo que dice el parte. "
                      "Revísalo." % catalogo.comodin())
    return {
        "id": pid, "archivo": archivo, "pagina": pagina, "img_cert": 0,
        "depto": r["departamento"], "folio": r["n_parte_final"], "oficina": r.get("oficina", ""),
        "fecha_parte": r["fecha_parte"], "fecha_infraccion": r["fecha_infraccion"],
        "hora_infraccion": hora(r["hora_infraccion"]), "lugar": r["lugar"],
        "infraccion_texto": r["infraccion_texto"], "tipo_vehiculo": exportar.tipo_limpio(r["tipo_vehiculo"]),
        "marca": exportar.marca_limpia(r["marca"]), "placa": exportar.placa6(r["placa"]),
        "fecha_citacion": r["fecha_citacion"], "hora_citacion": r["hora_citacion"],
        "articulo": r["articulo"], "avisos": avisos, "causa": causa, "causa_literal": comodin,
        "items": [{"cod": i["cod"], "estado": i["estado"], "nota": i["nota"]} for i in items],
        "cert": {"rut": "", "nombre": "", "direccion": "", "comuna": perfil.cargar()["comuna"] if escrito else "", "marca": "", "modelo": "",
                 **(r.get("persona", {}) if escrito or personal else {}),
                 "tipo_vehiculo": "", "dv_placa": "", "anio": "", "color": ""},
        "parte_escrito": escrito, "notificado_personalmente": personal,
        "cert_avisos": [] if escrito or personal else ["Falta el certificado del Registro Civil de este parte."],
    }


def armar_carab(r, archivo, pagina, pid):
    """Arma el parte de Carabineros y distingue al denunciado del vehículo empadronado."""
    p = armar(r, archivo, pagina, pid)
    p["lecturas"] = {}
    if r.get("fechas_citacion"):
        p["lecturas"]["Fecha de citación"] = [[fecha, "Recorte"] for fecha in r["fechas_citacion"]]
    if r.get("placa_rapid"):
        p["lecturas"]["Placa"] = [[p["placa"], "Tesseract"], [exportar.placa6(r["placa_rapid"]), "RapidOCR"]]
    if r.get("boleta_rapid"):
        p["lecturas"]["N° de boleta (folio)"] = [[r["boleta"], "Tesseract"], [r["boleta_rapid"], "RapidOCR"]]
    veh = r["tiene_vehiculo"]
    nombre = r["infractor_nombre"]
    empadronado = r.get("empadronado", False)
    avisos = [r["aviso_infractor"]] if r["aviso_infractor"] else []
    if empadronado:
        nombre = " ".join(filter(None, (p["tipo_vehiculo"] or "VEHICULO", p["placa"])))
        avisos = []
    elif not nombre and veh:
        nombre = ("VEHICULO " + p["placa"]).strip()
        avisos.append("Infractor «por escrito» / sin datos: irá sin RUT (el sistema pone SR) y con el nombre «VEHICULO + patente». "
                      "Si tienes su certificado, escanéalo a continuación del parte.")
    elif not nombre:
        avisos.append("No pude leer el nombre del infractor.")
    elif not r["infractor_rut"] and not r["rut_leido"]:
        avisos.append("Sin RUT en el parte: irá con SR y el nombre del infractor.")
    direccion = r["infractor_direccion"]
    if not veh and not r["infractor_rut"] and not direccion and p["lugar"]:
        direccion = p["lugar"]   # ruidos molestos «por escrito»: el infractor vive donde se cursó el parte
        avisos.append("Sin RUT y sin vehículo: se repite la dirección del hecho como dirección del infractor.")
    p.update({
        "origen": "carab", "oficina": r.get("oficina", ""), "oficina_reconocida": bool(r.get("oficina_reconocida")), "n_parte_carab": r["n_parte_carab"], "boleta": r["boleta"], "tiene_vehiculo": veh,
        "empadronado": empadronado,
        "cert": {"rut": "" if empadronado else r["infractor_rut"] or r["rut_leido"], "nombre": nombre,
                 "direccion": direccion, "comuna": r["infractor_comuna"] or perfil.cargar()["comuna"],
                 "marca": exportar.marca_limpia(r["marca"]), "modelo": r["modelo"], "tipo_vehiculo": exportar.tipo_limpio(r["tipo_vehiculo"]),
                 "dv_placa": "", "anio": "", "color": ""},
        "cert_avisos": avisos,
        "infractores": r.get("infractores", []) if len(r.get("infractores", [])) > 1 else [],
    })
    if not r.get("oficina_reconocida"):
        p["cert_avisos"].append("No reconocí la unidad de Carabineros en el encabezado: se usará la unidad por defecto del perfil. Elígela en la lista.")
    com = p["cert"]["comuna"]
    if not catalogo.comuna_en_sistema(com):
        p["cert_avisos"].append("La comuna «%s» no está en la lista del sistema: corrígela o el sistema no la aceptará." % com)
    if p["infractores"]:
        p["cert_avisos"].append("Este parte trae %d infractores: elige a cuál corresponde esta copia (paso 4)." % len(p["infractores"]))
    return p


def armar_mtt(r, archivo, pagina, pid):
    """Denuncia del MTT: trae al infractor y al vehículo en sus tablas; puede traer varias infracciones."""
    p = armar(r, archivo, pagina, pid)
    causa, items, literal = "", [], False
    for texto in r["infracciones"]:
        c, its, es_comodin = catalogo.resolver_o_comodin(texto)
        if not causa and c:
            causa, literal = c, es_comodin
        items += [i for i in its if i["cod"] not in [x["cod"] for x in items]]
    personal = r.get("notificado_personalmente", False)
    avisos = list(r["avisos"])
    modalidad = r.get("modalidad_mtt", "")
    if not modalidad:
        avisos.append("Revisa al pie del parte si fue notificado personalmente o empadronado antes de completar los datos del denunciado.")
    if literal:
        avisos.append("No reconocí la infracción: se ingresará con el código %s y la descripción dirá lo que dice el parte. "
                      "Revísalo." % catalogo.comodin())
    # folio del archivo = primeros 6 dígitos de la boleta de citación (más largos desbordan el sistema);
    # el N° de denuncia hace de «N° de parte» (como en Carabineros) y se corrige a mano después de cargar
    p["n_parte_carab"] = r["n_parte"]
    if r["boleta"]:
        p["folio"] = r["boleta"][:6]
        p["boleta_completa"] = r["boleta"]
    else:
        avisos.append("No pude leer el N° de la boleta de citación (al pie del parte): escribe sus primeros 6 dígitos como folio.")
    if len(r["infracciones"]) > 1:
        avisos.append("Este parte trae %d infracciones: la descripción de la causa es la primera; ingresa todas." % len(r["infracciones"]))
        for item in items:
            item["estado"] = "check"
            item["nota"] = (item["nota"] + " Confirma este código con la imagen del parte.").strip()
    p.update({
        "origen": "mtt", "modalidad_mtt": modalidad, "boleta": r["boleta"], "inspector": r["inspector"], "norma": r["norma"],
        "identidad_folio": {k: r["infractor_" + k] for k in ("rut", "nombre", "direccion", "comuna")},
        "calidad": r["calidad"], "observaciones": r["observaciones"], "causa": causa, "causa_literal": literal,
        "items": [{"cod": i["cod"], "estado": i["estado"], "nota": i["nota"]} for i in items],
        "avisos": avisos,
        "cert": {"rut": r["infractor_rut"] if personal else "", "nombre": r["infractor_nombre"] if personal else "",
                 "direccion": r["infractor_direccion"] if personal else "", "comuna": r["infractor_comuna"] if personal else "",
                 "marca": r["marca"], "modelo": r["modelo"],
                 "tipo_vehiculo": exportar.tipo_limpio(r["tipo_vehiculo"]), "dv_placa": r["dv_placa"], "anio": r["anio"], "color": ""},
        "cert_avisos": ["Falta el certificado del Registro Civil de este parte."] if modalidad == "empadronado" else [],
    })
    return p


def aplicar_certificado(p, c, pid_img, *, placa_verificada=""):
    """Une los datos del certificado c (dict de certificado.leer) al parte p."""
    placa, aviso = certificado.conciliar_placa(exportar.placa6(p["placa"]), exportar.placa6(c["placa"]))
    if not p.get("img_cert"):
        import copy
        p["sin_cert"] = {k: copy.deepcopy(p[k]) for k in ("cert", "cert_avisos", "placa", "marca", "tipo_vehiculo", "lecturas") if k in p}
        p["sin_cert"].setdefault("lecturas", {})
    if placa_verificada:
        placa, aviso = placa_verificada, ""
    elif p["placa"] and c["placa"] and exportar.placa6(p["placa"]) != exportar.placa6(c["placa"]):
        lecturas = p.setdefault("lecturas", {})
        lecturas.setdefault("Placa", [[p["placa"], "Parte"]]).append([exportar.placa6(c["placa"]), "Certificado"])
    p["placa"] = exportar.placa6(placa)
    c = dict(c, tipo_vehiculo=exportar.tipo_limpio(c["tipo_vehiculo"]))
    p["img_cert"] = pid_img
    persona = {k: p["cert"].get(k, "") for k in ("rut", "nombre", "direccion", "comuna")}
    p["cert"] = {k: c[k] for k in ("rut", "nombre", "direccion", "comuna", "marca", "modelo",
                                   "tipo_vehiculo", "dv_placa", "anio", "color")}
    if p.get("notificado_personalmente") or (p.get("origen") == "mtt" and p.get("modalidad_mtt") == ""):
        p["cert"].update(persona)
    if p.get("origen") == "mtt":
        p["identidad_registro"] = {k: c[k] for k in persona}
    p["cert_avisos"] = list(c["avisos"]) + ([aviso] if aviso else [])
    # el tipo de vehículo y la marca del certificado son más fiables que los del parte
    if c["tipo_vehiculo"]:
        p["tipo_vehiculo"] = c["tipo_vehiculo"]
    if c["marca"]:
        p["marca"] = c["marca"]


def paginas_ocr_movil(ruta):
    from PIL import Image, ImageOps

    with zipfile.ZipFile(ruta) as paquete:
        if paquete.getinfo("ocr.json").file_size > 2_000_000:
            raise ValueError("El manifiesto OCR es demasiado grande.")
        hojas = json.loads(paquete.read("ocr.json"))
        if not isinstance(hojas, list) or not 1 <= len(hojas) <= 500:
            raise ValueError("La tanda no tiene una cantidad válida de hojas.")
        anterior_cert = True
        for i, hoja in enumerate(hojas):
            if not isinstance(hoja, dict) or not isinstance(hoja.get("texto"), str):
                raise ValueError("Texto OCR inválido.")
            es_cert = hoja.get("certificado")
            if type(es_cert) is not bool or (es_cert and anterior_cert):
                raise ValueError("El certificado no tiene un parte anterior.")
            anterior_cert = es_cert
            archivo = paquete.getinfo(f"{i}.jpg")
            if archivo.file_size > 25_000_000:
                raise ValueError("Una foto supera el límite de 25 MB.")
        for i, hoja in enumerate(hojas):
            with paquete.open(f"{i}.jpg") as archivo, Image.open(archivo, formats=["JPEG"]) as foto:
                # JPEG reduce durante la decodificación, antes de reservar la imagen completa.
                # El texto OCR del teléfono ya está en el manifiesto.
                foto.draft("RGB", (2600, 2600))
                foto.thumbnail((2600, 2600), Image.Resampling.LANCZOS)
                yield ImageOps.exif_transpose(foto).convert("RGB"), hoja["texto"], hoja["certificado"]


def trabajador():
    while True:
        primero = COLA.get()
        lote_actual = [primero]
        while not COLA.empty():
            lote_actual.append(COLA.get())
        
        # Ordenar estrictamente por nombre de archivo usando orden natural
        lote_actual.sort(key=lambda x: orden_natural(x[1]))
        
        for ruta, nombre in lote_actual:
            try:
                ultimo = None          # último parte leído del archivo, para pegarle su certificado
                movil = ruta.lower().endswith(".psocr")
                hojas = paginas_ocr_movil(ruta) if movil else (
                    (img, None, False) for img in motor.paginas(ruta)
                )
                for n, (img, texto, es_cert) in enumerate(hojas, 1):
                    if movil:
                        g = None
                        tipo = "certificado" if es_cert else motor.tipo_pagina(texto)
                        # El OCR puede reconocer un certificado aunque su marca móvil sea errónea.
                        if tipo == "otra" and not es_cert:
                            tipo = "parte"
                        if tipo != "certificado":
                            ultimo = None
                    else:
                        g = motor.preparar(img)
                        texto = motor.texto_pagina(g)
                        tipo = motor.tipo_pagina(texto)
                    if tipo == "parte":
                        r = motor.leer_parte(img, texto, g, solo_texto=movil)
                        with LOCK:
                            pid = len(IMAGENES) + 1
                            IMAGENES[pid] = img
                            TEXTOS[pid] = texto
                            ultimo = armar(r, nombre, n, pid)
                            PARTES.append(ultimo)
                    elif tipo == "dom":
                        r = motor.extractor.parte_dom(texto)
                        if not r["fecha_parte"]:
                            cabecera = motor.releer_franja(g if g is not None else motor.preparar(img), 0, 0.32)
                            r["fecha_parte"] = motor.extractor.fecha_documento(cabecera)
                        r["oficina"] = perfil.oficinas().get("31", "31")
                        with LOCK:
                            pid = len(IMAGENES) + 1
                            IMAGENES[pid] = img
                            TEXTOS[pid] = texto
                            ultimo = armar(r, nombre, n, pid)
                            ultimo.update(origen="dom", tiene_vehiculo=False, cert_avisos=[])
                            ultimo["cert"].update(r["persona"], comuna=perfil.cargar()["comuna"])
                            PARTES.append(ultimo)
                    elif tipo == "mtt":
                        r = extractor_mtt.parte(texto, None if movil else motor.leer_celdas(g))
                        if not r["infracciones"] or not r["lugar"] or not r["hora_infraccion"]:
                            gris = g if g is not None else motor.preparar(img)
                            respaldo = extractor_mtt.parte(motor.releer_franja(gris, 0, 0.6))
                            for campo in ("infracciones", "infraccion_texto", "norma", "lugar", "hora_infraccion"):
                                if not r[campo] and respaldo[campo]:
                                    r[campo] = respaldo[campo]
                            if r["infracciones"]:
                                r["avisos"] = [a for a in r["avisos"] if a != "No pude leer la infracción."]
                        if not r["modalidad_mtt"]:
                            pie = motor.releer_franja(g if g is not None else motor.preparar(img), 0.65, 1)
                            r["modalidad_mtt"] = extractor_mtt.modalidad_notificacion(pie)
                            r["notificado_personalmente"] = r["modalidad_mtt"] == "personal"
                        with LOCK:
                            pid = len(IMAGENES) + 1
                            IMAGENES[pid] = img
                            TEXTOS[pid] = texto
                            ultimo = armar_mtt(r, nombre, n, pid)
                            PARTES.append(ultimo)
                    elif tipo == "carab":
                        r = motor.leer_carab(g, texto, imagen=img)
                        with LOCK:
                            pid = len(IMAGENES) + 1
                            IMAGENES[pid] = img
                            TEXTOS[pid] = texto
                            ultimo = armar_carab(r, nombre, n, pid)
                            PARTES.append(ultimo)
                    elif tipo == "certificado":
                        c = motor.leer_certificado(g, texto, imagen=img)
                        placa_verificada = ""
                        if ultimo is not None and ultimo["id"] in IMAGENES and not ultimo.get("parte_escrito") and not ultimo["img_cert"]:
                            a, b = (exportar.placa6(valor) for valor in (ultimo["placa"], c["placa"]))
                            if a and b and sum(x != y for x, y in zip(a, b)) == 1 and len(a) == len(b):
                                _, aviso_placa = certificado.conciliar_placa(a, b)
                                parte_zona = motor.releer_franja(motor.preparar(IMAGENES[ultimo["id"]]), 0.2, 0.8)
                                cert_zona = motor.releer_franja(g if g is not None else motor.preparar(img), 0, 0.53)
                                segunda = exportar.placa6(certificado.leer(cert_zona)["placa"])
                                if aviso_placa and segunda in (a, b) and re.search(r"\b" + r"[ .-]*".join(segunda) + r"\b", parte_zona, re.I):
                                    placa_verificada = segunda
                        with LOCK:
                            pid = len(IMAGENES) + 1
                            IMAGENES[pid] = img
                            TEXTOS[pid] = texto
                            if ultimo is not None and not ultimo.get("parte_escrito") and ultimo["img_cert"] == 0:
                                aplicar_certificado(ultimo, c, pid, placa_verificada=placa_verificada)
                            else:
                                ESTADO["error"] = "«%s» pág. %d: certificado sin parte (o repetido); lo ignoré." % (nombre, n)
                    else:
                        ESTADO["error"] = "«%s» pág. %d: hoja que no es un parte ni un certificado; la ignoré." % (nombre, n)
            except zipfile.BadZipFile:
                ESTADO["error"] = f"«{nombre}» está dañado o incompleto. Vuelve a exportar la tanda desde el teléfono."
            except Exception as e:  # no detener el programa por un archivo malo
                traceback.print_exc()
                ESTADO["error"] = "No pude leer «%s»: %s" % (nombre, e)
            finally:
                with LOCK:
                    ESTADO["pendientes"] -= 1
                try:
                    os.remove(ruta)
                except OSError:
                    pass


def encolar(datos, nombre, ext, longitud=None):
    fd, ruta = tempfile.mkstemp(dir=TMP, suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            if longitud is None:
                f.write(datos)
            else:
                while longitud:
                    bloque = datos.read(min(longitud, 1024 * 1024))
                    if not bloque:
                        raise ValueError("La transferencia del archivo quedó incompleta.")
                    f.write(bloque)
                    longitud -= len(bloque)
    except (OSError, ValueError):
        os.remove(ruta)
        raise
    with LOCK:
        ESTADO["pendientes"] += 1
        ESTADO["error"] = ""
    COLA.put((ruta, nombre))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, open(os.path.join(WEB, "index.html"), "rb").read(), "text/html; charset=utf-8")
        if u.path == "/fluent.css":
            return self._send(200, open(os.path.join(WEB, "fluent.css"), "rb").read(), "text/css; charset=utf-8")
        if u.path == "/calles-valdivia.txt":
            with open(os.path.join(WEB, "calles-valdivia.txt"), "rb") as archivo:
                return self._send(200, archivo.read(), "text/plain; charset=utf-8")
        logos = {"/brand/partescan.svg": ("partescan.svg", "image/svg+xml"),
                 "/brand/captura.svg": ("captura.svg", "image/svg+xml"),
                 "/favicon.ico": ("partescan.ico", "image/x-icon")}
        if u.path in logos:
            nombre, tipo = logos[u.path]
            with open(os.path.join(WEB, "brand", nombre), "rb") as archivo:
                return self._send(200, archivo.read(), tipo)
        if u.path == "/api/estado":
            with LOCK:
                return self._send(200, {"pendientes": ESTADO["pendientes"], "error": ESTADO["error"],
                                        "partes": PARTES})
        if u.path == "/api/sesion/ultima":
            return self._send(200, info_sesion_auto())
        if u.path == "/api/actualizacion":
            return self._send(200, actualizador.estado())
        if u.path == "/api/infracciones":
            lista = perfil.infracciones()
            ordenadas = sorted(([c, d] for c, d in lista.items()),
                               key=lambda x: (not str(x[0]).isdigit(), int(x[0]) if str(x[0]).isdigit() else 0, str(x[0])))
            return self._send(200, ordenadas)
        if u.path == "/api/perfil":
            return self._send(200, estado_perfil())
        if u.path == "/api/perfil/equivalencias":
            return self._send(200, equivalencias_actuales())
        if u.path == "/api/tecleo/estado":
            try:
                return self._send(200, tecleador.estado(int(parse_qs(u.query).get("desde", ["0"])[0] or 0)))
            except Exception as e:
                return self._send(500, {"error": "No se pudo: %s" % e})
        m = re.fullmatch(r"/api/img/(\d+)", u.path)
        if m:
            img = IMAGENES.get(int(m.group(1)))
            if not img:
                return self._send(404, "no existe", "text/plain")
            im = img.convert("L")
            if im.width > 1400:
                im = im.resize((1400, int(im.height * 1400 / im.width)))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=82)
            return self._send(200, b.getvalue(), "image/jpeg")
        self._send(404, "no existe", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/buscar-campo":
            if self.headers.get("X-ParteScan-Buscar") != "1":
                return self._send(403, {"error": "Solicitud de búsqueda no válida."})
            query = parse_qs(u.query)
            campo = query.get("campo", [""])[0]
            identificador = query.get("id", [""])[0]
            if campo not in busqueda.CAMPOS or not re.fullmatch(r"[0-9]{1,10}", identificador):
                return self._send(400, {"error": "Campo o parte no válido."})
            with LOCK:
                parte = next((p for p in PARTES if p["id"] == int(identificador)), None)
                fuentes = []
                if parte:
                    origen = parte.get("origen") or "inspeccion"
                    personal = parte.get("notificado_personalmente") or parte.get("parte_escrito")
                    modalidad = query.get("modalidad", [parte.get("modalidad_mtt", "")])[0]
                    if origen == "mtt":
                        personal = modalidad == "personal"
                    identidad = campo in busqueda.IDENTIDAD
                    if not identidad or origen != "mtt" or personal:
                        fuentes.append(("Parte", IMAGENES.get(parte["id"]), TEXTOS.get(parte["id"], "")))
                    cid = parte.get("img_cert")
                    usa_cert = identidad and not personal and (origen != "mtt" or modalidad == "empadronado")
                    if cid and (campo == "placa" or usa_cert):
                        if usa_cert:
                            fuentes.clear()
                        fuentes.append(("Certificado", IMAGENES.get(cid), TEXTOS.get(cid, "")))
            if parte is None:
                return self._send(404, {"error": "El parte ya no está en la tanda."})
            if not LOCK_BUSQUEDA.acquire(blocking=False):
                return self._send(409, {"error": "Hay otra búsqueda en curso. Intenta nuevamente."})
            try:
                if campo == "descripcion":
                    return self._send(200, busqueda.releer_descripcion(origen, fuentes))
                return self._send(200, {"resultados": busqueda.buscar(campo, origen, fuentes)})
            finally:
                LOCK_BUSQUEDA.release()
        if u.path == "/api/actualizacion":
            if self.headers.get("X-ParteScan-Actualizar") != "1":
                return self._send(403, {"error": "Solicitud de actualización no válida."})
            try:
                comprobar_actualizacion_segura()
                actualizador.iniciar(
                    diferencial=parse_qs(u.query).get("completa") != ["1"],
                    antes_de_cerrar=comprobar_actualizacion_segura,
                )
                return self._send(202, {"ok": True})
            except ValueError as e:
                return self._send(400, {"error": str(e)})
        if u.path == "/api/captura":
            try:
                import cv2

                url = iniciar_captura()
                qr = cv2.QRCodeEncoder_create().encode(url)
                qr = cv2.copyMakeBorder(qr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
                _, png = cv2.imencode(".png", qr)
                return self._send(200, {"url": url, "qr": base64.b64encode(png).decode("ascii")})
            except OSError:
                return self._send(503, {"error": "No se pudo abrir la captura en la red local."})
        if u.path == "/api/subir":
            nombre = parse_qs(u.query).get("nombre", ["archivo"])[0]
            ext = ".psocr" if nombre.lower().endswith(".psocr.zip") else os.path.splitext(nombre)[1].lower()
            if ext not in (".pdf", ".psocr") and ext not in motor.EXTS_IMG:
                return self._send(400, {"error": "Formato no válido: " + nombre})
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n <= 0:
                    raise ValueError("El archivo está vacío.")
                encolar(self.rfile, nombre, ext, longitud=n)
            except (ValueError, OSError) as e:
                return self._send(400, {"error": str(e)})
            return self._send(200, {"ok": True})
        if u.path == "/api/guardar":
            # guarda en la carpeta Descargas sin depender del navegador (que a veces bloquea descargas repetidas)
            n = int(self.headers.get("Content-Length", 0))
            cuerpo = self.rfile.read(n)
            q = parse_qs(u.query)
            nombre = re.sub(r"[^\w.\- ]", "_", q.get("nombre", ["partes.txt"])[0])
            ruta = guardar_en_descargas(nombre, cuerpo)
            return self._send(200, {"ruta": ruta})
        if u.path in ("/api/sesion/guardar", "/api/sesion/auto", "/api/sesion/abrir", "/api/sesion/continuar"):
            n = int(self.headers.get("Content-Length", 0))
            cuerpo = self.rfile.read(n)
            try:
                if u.path == "/api/sesion/abrir":
                    return self._send(200, cargar_sesion(cuerpo))
                if u.path == "/api/sesion/continuar":
                    with open(RUTA_AUTO, "rb") as f:
                        return self._send(200, cargar_sesion(f.read()))
                datos = armar_sesion(json.loads(cuerpo.decode("utf-8")))
                if u.path == "/api/sesion/auto":
                    os.makedirs(os.path.dirname(RUTA_AUTO), exist_ok=True)
                    with open(RUTA_AUTO + ".tmp", "wb") as f:
                        f.write(datos)
                    os.replace(RUTA_AUTO + ".tmp", RUTA_AUTO)
                    return self._send(200, {"ok": True})
                nombre = re.sub(r"[^\w.\- ]", "_", parse_qs(u.query).get("nombre", ["sesion.partescan"])[0])
                return self._send(200, {"ruta": guardar_en_descargas(nombre, datos)})
            except Exception as e:
                return self._send(400, {"error": "No se pudo: %s" % e})
        if u.path == "/api/tanda/editar":
            try:
                n = int(self.headers.get("Content-Length", 0))
                datos = json.loads(self.rfile.read(n))
                with LOCK:
                    if ESTADO["pendientes"] or tecleador.corriendo():
                        raise ValueError("Termina la lectura y detén el tecleo antes de modificar la tanda.")
                    nuevos = datos["partes"]
                    if not isinstance(nuevos, list) or any(not isinstance(p, dict) or p.get("id") not in IMAGENES or (p.get("img_cert") and p["img_cert"] not in IMAGENES) for p in nuevos):
                        raise ValueError("La tanda contiene imágenes no disponibles.")
                    if len({p["id"] for p in nuevos}) != len(nuevos):
                        raise ValueError("Un parte está repetido en la tanda.")
                    import copy
                    nuevos = copy.deepcopy(nuevos)
                    if datos.get("certificado"):
                        origen, destino = datos["certificado"]
                        donante = next(p for p in nuevos if p["id"] == origen)
                        receptor = next(p for p in nuevos if p["id"] == destino)
                        if donante is receptor:
                            raise ValueError("Elige otro parte como destino.")
                        if receptor.get("img_cert"):
                            raise ValueError("El destino ya tiene certificado. Reasígnalo primero.")
                        imagen = donante.get("img_cert") or donante["id"]
                        texto = TEXTOS.get(imagen)
                        if texto is None:
                            texto = motor.texto_pagina(motor.preparar(IMAGENES[imagen]))
                        c = certificado.leer(texto)
                        if not c.get("placa") or not any(c.get(k) for k in ("rut", "nombre", "modelo")):
                            raise ValueError("No pude reconocer un certificado en esa imagen. Revisa el original.")
                        aplicar_certificado(receptor, c, imagen)
                        for key in ("RUT (certificado)", "Nombre (certificado)", "Dirección (certificado)", "Comuna (certificado)", "Marca (certificado)", "Modelo (certificado)", "Tipo de vehículo (certificado)", "Placa"):
                            for bucket in ("ed", "ok", "done"):
                                receptor.get(bucket, {}).pop(key, None)
                        receptor.pop("avOk", None)
                        if donante.get("img_cert"):
                            previo = donante.pop("sin_cert", None)
                            if previo:
                                donante.update(previo)
                            else:
                                # Sesiones anteriores no guardaban los datos previos al certificado.
                                donante["cert"] = dict(donante.get("cert", {}), rut="", nombre="", direccion="", comuna="")
                                donante["cert_avisos"] = ["Certificado reasignado: revisa los datos del denunciado."]
                            donante["img_cert"] = 0
                            for key in ("RUT (certificado)", "Nombre (certificado)", "Dirección (certificado)", "Comuna (certificado)", "Marca (certificado)", "Modelo (certificado)", "Tipo de vehículo (certificado)", "Placa"):
                                for bucket in ("ed", "ok", "done"):
                                    donante.get(bucket, {}).pop(key, None)
                            donante.pop("avOk", None)
                        else:
                            nuevos.remove(donante)
                    PARTES[:] = nuevos
                    return self._send(200, {"partes": PARTES})
            except (ValueError, KeyError, TypeError, StopIteration) as e:
                return self._send(400, {"error": str(e) or "Parte no disponible."})
        if u.path.startswith("/api/tecleo/"):
            n = int(self.headers.get("Content-Length", 0))
            cuerpo = self.rfile.read(n)
            try:
                return self._send(200, tecleador.accion(u.path[len("/api/tecleo/"):],
                                                        json.loads(cuerpo.decode("utf-8") or "{}")))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:
                return self._send(500, {"error": "No se pudo: %s" % e})
        if u.path == "/api/limpiar":
            with LOCK:
                PARTES.clear()
                IMAGENES.clear()
                TEXTOS.clear()
            return self._send(200, {"ok": True})
        if u.path.startswith("/api/perfil"):
            n = int(self.headers.get("Content-Length", 0))
            cuerpo = self.rfile.read(n)
            try:
                return self._send(200, post_perfil(u, cuerpo))
            except Exception as e:
                return self._send(400, {"error": str(e)})
        if u.path == "/api/salir":
            self._send(200, {"ok": True})
            threading.Thread(target=lambda: (shutil.rmtree(TMP, ignore_errors=True), os._exit(0)), daemon=True).start()
            return
        self._send(404, "no existe", "text/plain")


def estado_perfil():
    cfg = perfil.cargar()
    return {
        "juzgado": cfg["juzgado"], "titulo_ventana": cfg["titulo_ventana"], "comuna": cfg["comuna"],
        "oficina_carabineros": cfg["oficina_carabineros"],
        "actuarios": perfil.actuarios(), "rol_actuario": perfil.rol_actuario(),
        "oficinas": perfil.oficinas_ordenadas(),
        "comunas": sorted(catalogo.comuna_oficial(c) for c in catalogo._cargar_comunas()),
        "n_infracciones": len(perfil.infracciones()), "n_oficinas": len(perfil.oficinas()),
        "propia_infracciones": perfil.es_lista_propia("infracciones"), "propia_oficinas": perfil.es_lista_propia("oficinas"),
        "carpeta": str(perfil.carpeta()),
    }


def equivalencias_actuales():
    """Cada concepto del catálogo con el código que le toca en la lista de ESTE juzgado (para que lo confirmen)."""
    lista = perfil.infracciones()
    conf = perfil.cargar().get("equivalencias", {})
    filas = []
    for ab in list(catalogo.CODIGOS) + list(catalogo.CODIGOS_CONFIRMAR):
        x = catalogo.por_abrev(ab)
        cod, est, nota = catalogo.codigo_concepto(ab, x["t"])
        cand = equivalencia.candidatos(ab, x["t"], lista)[:4]
        filas.append({"abrev": ab, "concepto": x["t"], "codigo": cod, "estado": est or "check",
                      "descripcion": lista.get(cod, ""), "confirmado": ab in conf,
                      "candidatos": [[c, d] for c, d, _s, _h in cand]})
    return {"filas": filas, "lista": sorted(([c, d] for c, d in lista.items()),
                                            key=lambda z: perfil._clave_orden(z[0]))}


def post_perfil(u, cuerpo):
    ruta = u.path[len("/api/perfil"):]
    q = parse_qs(u.query)
    if ruta == "":
        datos = json.loads(cuerpo.decode("utf-8"))
        cfg = perfil.cargar()
        for k in ("juzgado", "titulo_ventana", "comuna", "oficina_carabineros"):
            if k in datos:
                cfg[k] = str(datos[k]).strip()
        if "actuarios" in datos:
            cfg["actuarios"] = {str(k).strip().upper(): str(v).strip() for k, v in datos["actuarios"].items() if str(k).strip()}
            if not all(str(v).isdigit() for v in cfg["actuarios"].values()):
                raise ValueError("El código de cada actuaria debe ser un número.")
        if "rol_actuario" in datos:
            cfg["rol_actuario"] = {str(d): str(n).upper() for d, n in datos["rol_actuario"].items() if n}
        perfil.guardar(cfg)
        return {"ok": True}
    if ruta == "/lista":
        tipo = q.get("tipo", [""])[0]
        if tipo not in perfil.ARCHIVOS:
            raise ValueError("Tipo de lista desconocido.")
        texto = cuerpo.decode("utf-8-sig", errors="replace")
        return {"ok": True, "resumen": perfil.importar(tipo, texto)}
    if ruta == "/restaurar":
        tipo = q.get("tipo", [""])[0]
        if tipo not in perfil.ARCHIVOS:
            raise ValueError("Tipo de lista desconocido.")
        perfil.restaurar_lista(tipo)
        return {"ok": True}
    if ruta == "/equivalencias":
        datos = json.loads(cuerpo.decode("utf-8"))
        cfg = perfil.cargar()
        eq = dict(cfg.get("equivalencias", {}))
        for ab, cod in datos.items():
            if cod:
                eq[ab] = str(cod)
            else:
                eq.pop(ab, None)
        cfg["equivalencias"] = eq
        perfil.guardar(cfg)
        return {"ok": True}
    raise ValueError("Ruta desconocida.")


RUTA_AUTO = os.path.join(os.path.expanduser("~"), "ParteScan", "ultima-sesion.partescan")


def armar_sesion(estado):
    """Empaqueta el lote (partes + correcciones del usuario + imágenes de las hojas) en un solo archivo .partescan."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("estado.json", json.dumps(estado, ensure_ascii=False))
        z.writestr("textos.json", json.dumps(TEXTOS, ensure_ascii=False))
        with LOCK:
            for pid, img in list(IMAGENES.items()):
                im = img.convert("L")
                if im.width > 1800:
                    im = im.resize((1800, int(im.height * 1800 / im.width)))
                t = io.BytesIO()
                im.save(t, "JPEG", quality=85)
                z.writestr("img_%d.jpg" % pid, t.getvalue())
    return b.getvalue()


def cargar_sesion(datos):
    from PIL import Image
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        estado = json.loads(z.read("estado.json").decode("utf-8"))
        textos = json.loads(z.read("textos.json")) if "textos.json" in z.namelist() else {}
        imgs = {}
        for nom in z.namelist():
            m = re.fullmatch(r"img_(\d+)\.jpg", nom)
            if m:
                im = Image.open(io.BytesIO(z.read(nom)))
                im.load()
                imgs[int(m.group(1))] = im
    with LOCK:
        PARTES.clear()
        IMAGENES.clear()
        IMAGENES.update(imgs)
        TEXTOS.clear()
        TEXTOS.update({int(k): v for k, v in textos.items()})
        PARTES.extend(estado.get("partes", []))
    return estado


def info_sesion_auto():
    try:
        with zipfile.ZipFile(RUTA_AUTO) as z:
            est = json.loads(z.read("estado.json").decode("utf-8"))
        return {"existe": True, "partes": len(est.get("partes", [])),
                "fecha": time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(RUTA_AUTO)))}
    except Exception:
        return {"existe": False}


def guardar_en_descargas(nombre, datos):
    """Escribe el archivo en Descargas (sin pisar uno existente) y abre el Explorador de Windows sobre él."""
    carpeta = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(carpeta, exist_ok=True)
    base, ext = os.path.splitext(nombre)
    ruta, k = os.path.join(carpeta, nombre), 1
    while os.path.exists(ruta):
        k += 1
        ruta = os.path.join(carpeta, "%s (%d)%s" % (base, k, ext))
    with open(ruta, "wb") as f:
        f.write(datos)
    try:
        if os.name == "nt":
            import subprocess
            subprocess.Popen(["explorer", "/select,", ruta])
    except Exception:
        pass
    return ruta


def _registro_en_archivo():
    """Sin ventana negra no hay donde ver los mensajes: se guardan en %APPDATA%\\ParteScan\\registro.txt."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        carpeta = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ParteScan")
        os.makedirs(carpeta, exist_ok=True)
        f = open(os.path.join(carpeta, "registro.txt"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f
    except Exception:
        pass


def _abrir_ventana(url):
    """Ventana propia de ParteScan (usa WebView2, que ya trae Windows 11). Devuelve False si no se pudo abrir;
    entonces el programa sigue como siempre, en el navegador."""
    if os.environ.get("PARTESCAN_NAVEGADOR"):          # para forzar el navegador de siempre
        return False
    try:
        import webview
        carpeta = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ParteScan", "ventana")
        webview.create_window("ParteScan", url, width=1440, height=900, min_size=(440, 520))
        webview.start(private_mode=False, storage_path=carpeta,
                      icon=os.path.join(WEB, "brand", "partescan.ico"))
        return True
    except Exception:
        print("No pude abrir la ventana propia; uso el navegador.\n" + traceback.format_exc())
        return False


class Captura(H):
    def autorizada(self):
        return (time.monotonic() < self.server.vence and
                secrets.compare_digest(self.path.encode(), self.server.ruta.encode()))

    def do_GET(self):
        if not self.autorizada():
            return self._send(404, {"error": "Enlace inválido o vencido."})
        with open(os.path.join(WEB, "captura.html"), "rb") as archivo:
            return self._send(200, archivo.read(), "text/html; charset=utf-8")

    def do_POST(self):
        if not self.autorizada():
            return self._send(404, {"error": "Enlace inválido o vencido."})
        n = self.headers.get("Content-Length", "")
        if not re.fullmatch(r"[0-9]{1,7}", n) or not 0 < int(n) <= 4000000:
            return self._send(413, {"error": "La foto debe pesar hasta 4 MB."})
        self.connection.settimeout(20)
        try:
            datos = self.rfile.read(int(n))
        except TimeoutError:
            return self._send(408, {"error": "Se agotó el tiempo de carga."})
        if len(datos) != int(n) or not datos.startswith(b"\xff\xd8") or not datos.endswith(b"\xff\xd9"):
            return self._send(400, {"error": "No se recibió un JPEG completo."})
        with LOCK_CAPTURA:
            if not self.autorizada():
                return self._send(404, {"error": "Enlace inválido o vencido."})
            hojas = self.server.hojas + 1
            nombre = f"iPhone-{self.server.lote}-{hojas:03d}.jpg"
            encolar(datos, nombre, ".jpg")
            self.server.hojas = hojas
        return self._send(200, {"hojas": hojas})


CAPTURA = None
LOCK_CAPTURA = threading.Lock()


def iniciar_captura():
    global CAPTURA
    with LOCK_CAPTURA:
        if CAPTURA is None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as red:
                red.connect(("192.0.2.1", 80))
                ip = red.getsockname()[0]
            CAPTURA = ThreadingHTTPServer((ip, 0), Captura)
        CAPTURA.ruta = "/" + secrets.token_urlsafe(24)
        CAPTURA.vence = time.monotonic() + 900
        CAPTURA.hojas = 0
        CAPTURA.lote = time.strftime("%Y%m%d-%H%M%S")
        if not getattr(CAPTURA, "iniciado", False):
            threading.Thread(target=CAPTURA.serve_forever, daemon=True).start()
            CAPTURA.iniciado = True
        ip, puerto = CAPTURA.server_address
        return f"http://{ip}:{puerto}{CAPTURA.ruta}"


def main():
    _registro_en_archivo()
    actualizador.revisar_en_segundo_plano()
    threading.Thread(target=trabajador, daemon=True).start()
    for puerto in range(8765, 8785):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", puerto), H)
            break
        except OSError:
            continue
    else:
        print("No encontré un puerto libre."); return
    url = "http://127.0.0.1:%d/" % puerto
    print("ParteScan funcionando en", url)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    if _abrir_ventana(url):                              # se cerró la ventana: termina el programa
        shutil.rmtree(TMP, ignore_errors=True)
        os._exit(0)
    print("Se abrirá en tu navegador. NO cierres esta ventana negra mientras trabajas;")
    print("al terminar, usa el botón «Cerrar programa» o cierra esta ventana.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        hilo.join()
    except KeyboardInterrupt:
        pass
