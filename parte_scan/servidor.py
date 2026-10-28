"""Servidor local: sirve la pantalla en el navegador y lee los partes con Tesseract.
Todo ocurre en este computador; no se envía nada a internet."""
import io, json, os, sys, zipfile, time, queue, re, shutil, tempfile, threading, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import catalogo, certificado, equivalencia, exportar, extractor_mtt, motor, perfil, tecleador

WEB = os.path.join(motor._base(), "parte_scan", "web")
if not os.path.isdir(WEB):
    WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

PARTES = []          # resultados, en orden
IMAGENES = {}        # id -> imagen PIL
COLA = queue.Queue()
ESTADO = {"pendientes": 0, "error": ""}
LOCK = threading.Lock()
TMP = tempfile.mkdtemp(prefix="partescan_")


def hora(h):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", h or "")
    return "%02d:%s" % (int(m.group(1)), m.group(2)) if m else ""


def armar(r, archivo, pagina, pid):
    causa, items, comodin = catalogo.resolver_o_comodin(r["infraccion_texto"])
    avisos = list(r["avisos"])
    if comodin:
        avisos.append("No reconocí la infracción: se ingresará con el código %s y la descripción dirá lo que dice el parte. "
                      "Revísalo." % catalogo.comodin())
    return {
        "id": pid, "archivo": archivo, "pagina": pagina, "img_cert": 0,
        "depto": r["departamento"], "folio": r["n_parte_final"],
        "fecha_parte": r["fecha_parte"], "fecha_infraccion": r["fecha_infraccion"],
        "hora_infraccion": hora(r["hora_infraccion"]), "lugar": r["lugar"],
        "infraccion_texto": r["infraccion_texto"], "tipo_vehiculo": exportar.tipo_limpio(r["tipo_vehiculo"]),
        "marca": exportar.marca_limpia(r["marca"]), "placa": exportar.placa6(r["placa"]),
        "fecha_citacion": r["fecha_citacion"], "hora_citacion": r["hora_citacion"],
        "articulo": r["articulo"], "avisos": avisos, "causa": causa, "causa_literal": comodin,
        "items": [{"cod": i["cod"], "estado": i["estado"], "nota": i["nota"]} for i in items],
        "cert": {"rut": "", "nombre": "", "direccion": "", "comuna": "", "marca": "", "modelo": "",
                 "tipo_vehiculo": "", "dv_placa": "", "anio": "", "color": ""},
        "cert_avisos": ["Falta el certificado del Registro Civil de este parte."],
    }


def armar_carab(r, archivo, pagina, pid):
    """Parte de Carabineros: el infractor sale del propio parte. Sin datos y con vehículo: SR + 'VEHICULO patente'.
    Sin vehículo (conducir/transitar ebrio): solo RUT y nombre. Extranjero: SR + su nombre."""
    p = armar(r, archivo, pagina, pid)
    veh = r["tiene_vehiculo"]
    nombre = r["infractor_nombre"]
    avisos = [r["aviso_infractor"]] if r["aviso_infractor"] else []
    if not nombre and veh:
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
        "cert": {"rut": r["infractor_rut"] or r["rut_leido"], "nombre": nombre,
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
    avisos = list(r["avisos"])
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
    p.update({
        "origen": "mtt", "boleta": r["boleta"], "inspector": r["inspector"], "norma": r["norma"],
        "calidad": r["calidad"], "observaciones": r["observaciones"], "causa": causa, "causa_literal": literal,
        "items": [{"cod": i["cod"], "estado": i["estado"], "nota": i["nota"]} for i in items],
        "avisos": avisos,
        "cert": {"rut": r["infractor_rut"], "nombre": r["infractor_nombre"], "direccion": r["infractor_direccion"],
                 "comuna": r["infractor_comuna"], "marca": r["marca"], "modelo": r["modelo"],
                 "tipo_vehiculo": exportar.tipo_limpio(r["tipo_vehiculo"]), "dv_placa": r["dv_placa"], "anio": r["anio"], "color": ""},
        "cert_avisos": [],
    })
    return p


def aplicar_certificado(p, c, pid_img):
    """Une los datos del certificado c (dict de certificado.leer) al parte p."""
    placa, aviso = certificado.conciliar_placa(exportar.placa6(p["placa"]), exportar.placa6(c["placa"]))
    p["placa"] = exportar.placa6(placa)
    p["img_cert"] = pid_img
    p["cert"] = {k: c[k] for k in ("rut", "nombre", "direccion", "comuna", "marca", "modelo",
                                   "tipo_vehiculo", "dv_placa", "anio", "color")}
    p["cert_avisos"] = list(c["avisos"]) + ([aviso] if aviso else [])
    # el tipo de vehículo y la marca del certificado son más fiables que los del parte
    if c["tipo_vehiculo"]:
        p["tipo_vehiculo"] = c["tipo_vehiculo"]
    if c["marca"]:
        p["marca"] = c["marca"]


def trabajador():
    while True:
        ruta, nombre = COLA.get()
        try:
            ultimo = None          # último parte leído del archivo, para pegarle su certificado
            for n, img in enumerate(motor.paginas(ruta), 1):
                g = motor.preparar(img)
                texto = motor.texto_pagina(g)
                tipo = motor.tipo_pagina(texto)
                if tipo == "parte":
                    r = motor.leer_parte(img, texto, g)
                    with LOCK:
                        pid = len(IMAGENES) + 1
                        IMAGENES[pid] = img
                        ultimo = armar(r, nombre, n, pid)
                        PARTES.append(ultimo)
                elif tipo == "mtt":
                    r = extractor_mtt.parte(texto, motor.leer_celdas(g))
                    with LOCK:
                        pid = len(IMAGENES) + 1
                        IMAGENES[pid] = img
                        ultimo = armar_mtt(r, nombre, n, pid)
                        PARTES.append(ultimo)
                elif tipo == "carab":
                    r = motor.leer_carab(g, texto)
                    with LOCK:
                        pid = len(IMAGENES) + 1
                        IMAGENES[pid] = img
                        ultimo = armar_carab(r, nombre, n, pid)
                        PARTES.append(ultimo)
                elif tipo == "certificado":
                    c = certificado.leer(texto)
                    with LOCK:
                        pid = len(IMAGENES) + 1
                        IMAGENES[pid] = img
                        if ultimo is not None and ultimo["img_cert"] == 0:
                            aplicar_certificado(ultimo, c, pid)
                        else:
                            ESTADO["error"] = "«%s» pág. %d: certificado sin parte (o repetido); lo ignoré." % (nombre, n)
                else:
                    ESTADO["error"] = "«%s» pág. %d: hoja que no es un parte ni un certificado; la ignoré." % (nombre, n)
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
        if u.path == "/api/estado":
            with LOCK:
                return self._send(200, {"pendientes": ESTADO["pendientes"], "error": ESTADO["error"],
                                        "partes": PARTES})
        if u.path == "/api/sesion/ultima":
            return self._send(200, info_sesion_auto())
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
        if u.path == "/api/subir":
            nombre = parse_qs(u.query).get("nombre", ["archivo"])[0]
            n = int(self.headers.get("Content-Length", 0))
            datos = self.rfile.read(n)
            ext = os.path.splitext(nombre)[1].lower()
            if ext != ".pdf" and ext not in motor.EXTS_IMG:
                return self._send(400, {"error": "Formato no válido: " + nombre})
            fd, ruta = tempfile.mkstemp(dir=TMP, suffix=ext)
            with os.fdopen(fd, "wb") as f:
                f.write(datos)
            with LOCK:
                ESTADO["pendientes"] += 1
                ESTADO["error"] = ""
            COLA.put((ruta, nombre))
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
        webview.create_window("ParteScan", url, width=1440, height=900, min_size=(1000, 650))
        webview.start(private_mode=False, storage_path=carpeta)      # espera hasta que se cierre la ventana
        return True
    except Exception:
        print("No pude abrir la ventana propia; uso el navegador.\n" + traceback.format_exc())
        return False


def main():
    _registro_en_archivo()
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
