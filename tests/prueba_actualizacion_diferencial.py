"""Comprueba que el actualizador descarga únicamente los archivos distintos."""
import io
from pathlib import Path
import tempfile
from unittest.mock import patch
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from herramientas.empaquetar_actualizacion import generar
from parte_scan.actualizacion_diferencial import preparar


class Respuesta(io.BytesIO):
    status = 206

    def __init__(self, bloque, rango, total):
        super().__init__(bloque)
        self.headers = {"Content-Range": f"bytes {rango}/{total}"}


with tempfile.TemporaryDirectory() as tmp:
    raiz = Path(tmp)
    instalada, release, assets = [raiz / n for n in ("instalada", "release", "assets")]
    instalada.mkdir()
    release.mkdir()
    (instalada / "ParteScan.exe").write_bytes(b"anterior")
    (instalada / "comun.dll").write_bytes(b"igual")
    (instalada / "retirado.dll").write_bytes(b"obsoleto")
    (release / "ParteScan.exe").write_bytes(b"nueva")
    (release / "comun.dll").write_bytes(b"igual")
    generar(release, assets, "v3.1.0")
    manifiesto = json.loads((assets / "ParteScan-archivos.json").read_text(encoding="utf-8"))
    paquete = (assets / "ParteScan-archivos.bin").read_bytes()

    def responder(req, timeout):
        rango = req.get_header("Range").split("=")[1]
        inicio, fin = map(int, rango.split("-"))
        return Respuesta(paquete[inicio:fin + 1], rango, len(paquete))

    with patch("urllib.request.urlopen", side_effect=responder) as red:
        nueva = preparar(instalada, manifiesto, "https://example.com/paquete", "v3.1.0") / "nueva"
        red.assert_called_once()
    assert (nueva / "ParteScan.exe").read_bytes() == b"nueva"
    assert (nueva / "comun.dll").read_bytes() == b"igual"
    assert not (nueva / "retirado.dll").exists()
    assert (instalada / "ParteScan.exe").read_bytes() == b"anterior"
    manifiesto["archivos"]["ParteScan.exe"]["sha256"] = "0" * 64
    with patch("urllib.request.urlopen", side_effect=responder):
        try:
            preparar(instalada, manifiesto, "https://example.com/paquete", "v3.1.0")
        except ValueError as e:
            assert "huella" in str(e)
        else:
            raise AssertionError("Debió rechazar el archivo alterado")
print("Actualización diferencial OK")
