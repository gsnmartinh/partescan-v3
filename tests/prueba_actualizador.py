"""Pruebas de la actualización automática (sin internet: usan un servidor local falso).
Ejecutar:  python tests/prueba_actualizador.py"""
import hashlib
import http.server
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["PARTESCAN_PERFIL"] = tempfile.mkdtemp()
from parte_scan import actualizador as A, version  # noqa: E402

fallas = []


def ok(c, m):
    if not c:
        fallas.append(m)
        print("FALLA:", m)


ok(A.es_mas_nueva("v3.0.1", "v3.0.0") and A.es_mas_nueva("v3.1.0", "v3.0.9") and A.es_mas_nueva("v4.0.0", "v3.9.9"), "comparación de versiones")
ok(not A.es_mas_nueva("v3.0.0", "v3.0.0") and not A.es_mas_nueva("v2.9.0", "v3.0.0"), "igual o anterior no actualiza")
ok(not A.es_mas_nueva("v3.0.0", "dev"), "una versión de desarrollo nunca se actualiza sola")

P = A.PREFIJO_DESCARGA


def release(tag, url_exe=None, url_sha=None):
    return {"tag_name": tag, "body": "Novedades", "assets": [
        {"name": "ParteScan-Instalador-%s.exe" % tag, "browser_download_url": url_exe or P + tag + "/ParteScan-Instalador-%s.exe" % tag},
        {"name": "ParteScan-Instalador-%s.exe.sha256" % tag, "browser_download_url": url_sha or P + tag + "/ParteScan-Instalador-%s.exe.sha256" % tag}]}


def reset():
    A.ESTADO.update(ultima="", hay=False, notas="", estado="", error="", _url="", _sha_url="")


# 1) hay versión nueva
version.VERSION = "v3.0.0"
reset(); A.revisar(lambda u: release("v3.0.1"))
ok(A.estado()["hay"] and A.estado()["ultima"] == "v3.0.1", "debe detectar la versión nueva")
ok("_url" not in A.estado(), "las direcciones internas no se exponen")
# 2) misma versión
reset(); A.revisar(lambda u: release("v3.0.0"))
ok(not A.estado()["hay"], "misma versión: nada que hacer")
# 3) assets de otro origen se ignoran
reset(); A.revisar(lambda u: release("v3.0.1", url_exe="https://ejemplo.com/malo.exe"))
ok(not A.estado()["hay"], "un instalador fuera de la Release del proyecto no se acepta")
# 4) sin internet: no pasa nada
def sin_red(u):
    raise OSError("sin internet")
reset(); A.revisar(sin_red)
ok(not A.estado()["hay"] and A.estado()["error"], "sin internet queda en silencio")
# 5) en desarrollo ni consulta
version.VERSION = "dev"
reset(); A.revisar(lambda u: release("v9.9.9"))
ok(not A.estado()["hay"], "en desarrollo no consulta")
version.VERSION = "v3.0.0"

# 6) descarga con verificación de huella (servidor local)
contenido = b"instalador de prueba" * 1000
huella = hashlib.sha256(contenido).hexdigest()
archivos = {"/x/ParteScan-Instalador-v3.0.1.exe": contenido,
            "/x/ParteScan-Instalador-v3.0.1.exe.sha256": (huella + "  ParteScan-Instalador-v3.0.1.exe").encode()}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        d = archivos.get(self.path)
        self.send_response(200 if d is not None else 404)
        self.end_headers()
        if d is not None:
            self.wfile.write(d)

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/x/" % srv.server_port
A.PREFIJO_DESCARGA = base
reset()
A.ESTADO.update(hay=True, ultima="v3.0.1", _url=base + "ParteScan-Instalador-v3.0.1.exe", _sha_url=base + "ParteScan-Instalador-v3.0.1.exe.sha256")
ruta = A.instalar(lanzar=False)
ok(open(ruta, "rb").read() == contenido, "el instalador se descargó completo")
# huella incorrecta: se rechaza y se borra
archivos["/x/ParteScan-Instalador-v3.0.1.exe.sha256"] = b"0" * 64
try:
    A.instalar(lanzar=False)
    ok(False, "debía rechazar una huella distinta")
except ValueError as e:
    ok("huella" in str(e) and A.estado()["estado"] == "error", "mensaje de huella: %s" % e)
# sin versión nueva no instala
A.ESTADO.update(hay=False)
try:
    A.instalar(lanzar=False)
    ok(False, "sin actualización disponible no debe instalar")
except ValueError:
    pass

if fallas:
    print("%d falla(s)" % len(fallas))
    sys.exit(1)
print("Pruebas del actualizador: todo OK")
