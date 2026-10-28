"""Actualización automática: al abrir (si hay internet) consulta la última Release en GitHub y ofrece instalarla.

- Sin internet o con cualquier error: no pasa nada, el programa sigue funcionando como siempre (todo lo demás es local).
- Solo descarga desde github.com/<REPO>/releases/download/ y comprueba la huella SHA-256 que publica la Release antes de ejecutar.
- Instala con el mismo instalador de siempre (en silencio): conserva el perfil y las sesiones, que viven en %APPDATA%.
- Se desactiva con la variable de entorno PARTESCAN_SIN_ACTUALIZACION=1."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from . import version

REPO = "gsnmartinh/partescan-v3"
API = "https://api.github.com/repos/%s/releases/latest" % REPO
PREFIJO_DESCARGA = "https://github.com/%s/releases/download/" % REPO
TIMEOUT = 6

LOCK = threading.Lock()
ESTADO = {"version": version.VERSION, "ultima": "", "hay": False, "notas": "", "estado": "", "error": "",
          "_url": "", "_sha_url": ""}


def numeros(tag):
    return tuple(int(x) for x in re.findall(r"\d+", str(tag or "")))


def es_mas_nueva(ultima, actual):
    """v3.0.1 > v3.0.0. Una versión «dev» (desarrollo) nunca se actualiza sola."""
    return bool(numeros(actual)) and numeros(ultima) > numeros(actual)


def _json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ParteScan"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _texto(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ParteScan"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def revisar(obtener=_json):
    """Consulta GitHub y deja el resultado en ESTADO. `obtener` se puede reemplazar en las pruebas."""
    if os.environ.get("PARTESCAN_SIN_ACTUALIZACION") or not numeros(version.VERSION):
        return
    try:
        rel = obtener(API)
        tag = rel.get("tag_name", "")
        exe = sha = ""
        for a in rel.get("assets", []):
            u = a.get("browser_download_url", "")
            if not u.startswith(PREFIJO_DESCARGA):
                continue
            if re.search(r"Instalador.*\.exe$", a.get("name", ""), re.I):
                exe = u
            elif re.search(r"Instalador.*\.exe\.sha256$", a.get("name", ""), re.I):
                sha = u
        with LOCK:
            ESTADO.update(ultima=tag, notas=(rel.get("body") or "")[:600],
                          hay=bool(exe and sha and es_mas_nueva(tag, version.VERSION)), _url=exe, _sha_url=sha, error="")
    except Exception as e:      # noqa: BLE001 - sin internet, límite de GitHub, etc.: se ignora en silencio
        with LOCK:
            ESTADO["error"] = str(e)[:200]


def revisar_en_segundo_plano():
    threading.Thread(target=revisar, daemon=True).start()


def estado():
    with LOCK:
        return {k: v for k, v in ESTADO.items() if not k.startswith("_")}


def instalar(lanzar=True):
    """Descarga el instalador, verifica su huella y lo ejecuta en silencio; el programa se cierra y el instalador
    lo vuelve a abrir. Devuelve la ruta del instalador (útil para las pruebas)."""
    with LOCK:
        url, sha_url = ESTADO["_url"], ESTADO["_sha_url"]
        if not ESTADO["hay"] or not url.startswith(PREFIJO_DESCARGA) or not sha_url.startswith(PREFIJO_DESCARGA):
            raise ValueError("No hay una actualización disponible.")
        ESTADO["estado"] = "descargando"
    try:
        esperado = _texto(sha_url).split()[0].strip().lower()
        carpeta = tempfile.mkdtemp(prefix="ParteScanActualizacion_")
        ruta = os.path.join(carpeta, os.path.basename(url))
        h = hashlib.sha256()
        req = urllib.request.Request(url, headers={"User-Agent": "ParteScan"})
        with urllib.request.urlopen(req, timeout=30) as r, open(ruta, "wb") as f:
            while True:
                bloque = r.read(1 << 20)
                if not bloque:
                    break
                h.update(bloque)
                f.write(bloque)
        if h.hexdigest().lower() != esperado:
            os.remove(ruta)
            raise ValueError("La descarga no coincide con la huella publicada; no se instaló.")
        with LOCK:
            ESTADO["estado"] = "instalando"
        if lanzar:
            if sys.platform != "win32":
                raise ValueError("La actualización automática es solo para Windows.")
            subprocess.Popen([ruta, "/SILENT", "/NOCANCEL", "/CLOSEAPPLICATIONS"],
                             creationflags=0x00000008 | 0x00000200, close_fds=True)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
            threading.Timer(1.5, lambda: os._exit(0)).start()      # el instalador necesita el programa cerrado
        return ruta
    except Exception as e:      # noqa: BLE001
        with LOCK:
            ESTADO.update(estado="error", error=str(e)[:200])
        raise
