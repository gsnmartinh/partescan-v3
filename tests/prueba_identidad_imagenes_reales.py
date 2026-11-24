"""Segunda lectura efectiva de fotografías reales; no incluye documentos en Git."""
import argparse
import io
import json
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageOps
from parte_scan import extractor_carab as EC, motor, servidor


def comprobar(sesion, ocr, tesseract):
    exe = Path(tesseract).resolve()
    motor.pytesseract.pytesseract.tesseract_cmd = str(exe)
    os.environ["TESSDATA_PREFIX"] = str(exe.parent / "tessdata")
    with zipfile.ZipFile(sesion) as z:
        partes = json.loads(z.read("estado.json"))["partes"]
    assert len(partes) == 53
    resumen = []
    with zipfile.ZipFile(ocr) as z:
        hojas = json.loads(z.read("ocr.json"))
        for pg in (7,13,18,25,34,26,37):
            original = EC.parte(hojas[pg-1]["texto"])
            r = EC.parte(hojas[pg-1]["texto"])
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(z.read(f"{pg-1}.jpg"))))
            motor.releer_identidad_carab(motor.preparar(im), r, imagen=im)
            p = next(p for p in partes if p["pagina"] == pg)
            assert r["infractor_rut"] == original["infractor_rut"], f"No cambiar el RUT en página {pg}"
            if pg in (7,13,34):
                assert r["infractor_nombre"] == p["ed"]["Nombre (certificado)"].upper(), f"Apellido página {pg}"
            if pg == 18:
                assert r["infractor_nombre"].startswith(original["infractor_nombre"] + " ")
                assert r["infractor_direccion"] != original["infractor_direccion"]
                assert "C.I." not in r["infractor_direccion"]
                assert "330" in r["infractor_direccion"]
            if pg == 25:
                assert r["infractor_nombre"] == p["ed"]["Nombre (certificado)"].upper()
                assert "CONSUMIENDO" not in r["infractor_direccion"]
            if pg == 34:
                assert r["infractor_direccion"] == p["ed"]["Dirección (certificado)"].upper()
            if pg in (26,37):
                assert "pasadas_identidad" not in r, "No corregir RUT inválidos por inferencia"
            resumen.append({"pagina":pg,"nombre_recuperado":r["infractor_nombre"]!=original["infractor_nombre"],
                            "direccion_recuperada":r["infractor_direccion"]!=original["infractor_direccion"]})
            print("Identidad página", pg, "correcto", flush=True)
        for pg, hora in ((29,"10:00"),(30,"11:00")):
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(z.read(f"{pg-1}.jpg"))))
            r = motor.leer_armada(None, hojas[pg-1]["texto"], imagen=im)
            assert r["fecha_parte"] == "16/11/2026"
            assert r["fecha_infraccion"] == "09/11/2026"
            assert r["hora_infraccion"] == "21:30" and r["hora_citacion"] == hora
            assert r["numero_armada"] == ("12352" if pg==29 else "")
            if pg==30:
                assert any("N° de parte" in a for a in r["avisos"]), "El manuscrito debe pedir confirmación"
            p = servidor.armar_armada(r,"real",pg,pg)
            assert p["fecha_infraccion"] != p["fecha_parte"]
            print("Armada página",pg,"correcto",flush=True)
    return resumen


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sesion",required=True);p.add_argument("--ocr",required=True)
    p.add_argument("--tesseract",required=True);p.add_argument("--informe")
    a=p.parse_args();resumen=comprobar(a.sesion,a.ocr,a.tesseract)
    if a.informe:Path(a.informe).write_text(json.dumps(resumen,indent=2),encoding="utf-8")
