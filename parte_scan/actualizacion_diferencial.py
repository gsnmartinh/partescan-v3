"""Prepara una copia actualizada y la intercambia después de cerrar ParteScan."""
import hashlib
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zlib


def _hash(ruta):
    with ruta.open("rb") as archivo:
        return hashlib.file_digest(archivo, "sha256").hexdigest()


def preparar(raiz, manifiesto, paquete, version):
    archivos = manifiesto["archivos"]
    if manifiesto["version"] != version or "ParteScan.exe" not in archivos:
        raise ValueError("El manifiesto no corresponde a la versión anunciada.")
    rutas = set()
    for nombre, ficha in archivos.items():
        partes = nombre.split("/")
        if (any(not re.fullmatch(r"[\w .()+@,-]+", p) or p in (".", "..")
                or p.endswith((".", " ")) or PureWindowsPath(p).is_reserved() for p in partes)
                or nombre.casefold() in rutas
                or not re.fullmatch(r"[a-f0-9]{64}", ficha["sha256"])
                or ficha["inicio"] < 0 or ficha["largo"] < 1 or ficha["tamano"] < 0):
            raise ValueError("El manifiesto contiene un archivo inválido.")
        rutas.add(nombre.casefold())

    trabajo = Path(tempfile.mkdtemp(prefix="ParteScan-actualizar-", dir=raiz.parent))
    nueva = trabajo / "nueva"
    nueva.mkdir()
    try:
        for nombre, ficha in archivos.items():
            origen = raiz / nombre
            destino = nueva / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            if origen.is_file() and _hash(origen) == ficha["sha256"]:
                shutil.copy2(origen, destino)
            else:
                inicio, largo = ficha["inicio"], ficha["largo"]
                rango = f"bytes={inicio}-{inicio+largo-1}"
                req = urllib.request.Request(paquete, headers={"Range": rango, "User-Agent": "ParteScan"})
                with urllib.request.urlopen(req, timeout=30) as respuesta:
                    if respuesta.status != 206 or not respuesta.headers.get("Content-Range", "").startswith(rango.replace("=", " ") + "/"):
                        raise ValueError("GitHub no entregó el rango solicitado.")
                    bloque = respuesta.read(largo + 1)
                datos = zlib.decompress(bloque)
                if len(bloque) != largo or len(datos) != ficha["tamano"]:
                    raise ValueError("El tamaño del archivo descargado no coincide.")
                destino.write_bytes(datos)
            if _hash(destino) != ficha["sha256"]:
                raise ValueError(f"La huella de {nombre} no coincide.")
        for archivo in raiz.glob("unins[0-9][0-9][0-9].*"):
            if archivo.is_file() and not (nueva / archivo.name).exists():
                shutil.copy2(archivo, nueva / archivo.name)
        return trabajo
    except Exception:
        shutil.rmtree(trabajo, ignore_errors=True)
        raise


def lanzar(raiz, trabajo):
    script = trabajo / "aplicar.ps1"
    script.write_text(r"""param([string]$Raiz,[int]$Proceso)
$ErrorActionPreference = 'Stop'
$Nueva = Join-Path $PSScriptRoot 'nueva'
$Anterior = Join-Path $PSScriptRoot 'anterior'
Wait-Process -Id $Proceso -Timeout 20 -ErrorAction SilentlyContinue
if (Get-Process -Id $Proceso -ErrorAction SilentlyContinue) { exit 1 }
try {
    Move-Item -LiteralPath $Raiz -Destination $Anterior
    try {
        Move-Item -LiteralPath $Nueva -Destination $Raiz
        Start-Process -FilePath (Join-Path $Raiz 'ParteScan.exe') -WorkingDirectory $Raiz -WindowStyle Hidden
    } catch {
        if (Test-Path -LiteralPath $Raiz) { Move-Item -LiteralPath $Raiz -Destination $Nueva }
        Move-Item -LiteralPath $Anterior -Destination $Raiz
        throw
    }
} catch {
    $_ | Out-File (Join-Path $PSScriptRoot 'error.txt')
    $Exe = Join-Path $Raiz 'ParteScan.exe'
    if (Test-Path -LiteralPath $Exe) { Start-Process -FilePath $Exe -WorkingDirectory $Raiz -WindowStyle Hidden }
    exit 1
}
""", encoding="utf-8")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.Popen([str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                      "-File", str(script), str(raiz), str(os.getpid())],
                     cwd=trabajo, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
