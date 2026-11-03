"""Genera el manifiesto y el paquete de archivos para las Releases de ParteScan."""
import hashlib
import json
from pathlib import Path
import sys
import zlib


def generar(origen, destino, version):
    destino.mkdir(parents=True, exist_ok=True)
    archivos = {}
    with (destino / "ParteScan-archivos.bin").open("wb") as paquete:
        for ruta in sorted(origen.rglob("*")):
            if not ruta.is_file():
                continue
            datos = ruta.read_bytes()
            bloque = zlib.compress(datos)
            archivos[ruta.relative_to(origen).as_posix()] = {
                "sha256": hashlib.sha256(datos).hexdigest(), "inicio": paquete.tell(),
                "largo": len(bloque), "tamano": len(datos),
            }
            paquete.write(bloque)
    (destino / "ParteScan-archivos.json").write_text(
        json.dumps({"version": version, "archivos": archivos}), encoding="utf-8"
    )


if __name__ == "__main__":
    generar(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
