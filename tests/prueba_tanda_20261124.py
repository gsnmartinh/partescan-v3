"""Regresión local sobre documentos reales; los documentos no se incluyen en Git."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parte_scan import busqueda, catalogo, certificado, extractor_carab as EC, extractor_armada as EA, motor, servidor


def comprobar(sesion, ocr):
    with zipfile.ZipFile(sesion) as z:
        partes = json.loads(z.read("estado.json"))["partes"]
    with zipfile.ZipFile(ocr) as z:
        hojas = json.loads(z.read("ocr.json"))
    assert len(partes) == 53 and len(hojas) == 60
    assert all(p["archivo"] == "ParteScan-20261124-124608.psocr" for p in partes)
    textos = {p["pagina"]: hojas[p["pagina"]-1]["texto"] for p in partes}
    datos = {pg: EA.parte(t) if EA.es_armada(t) else EC.parte(t) for pg, t in textos.items()}
    # RUT corregidos que están en el OCR original: no completar desde la ficha del juzgado.
    paginas_rut = (4,5,7,11,12,13,14,16,18,19,23,29,30,35,36,41)
    for pg in paginas_rut:
        p = next(p for p in partes if p["pagina"] == pg)
        esperado = p["ed"]["RUT (certificado)"].replace(".", "")
        d = datos[pg]
        assert (d.get("persona", {}).get("rut") if pg in (29,30) else d["infractor_rut"]) == esperado, f"RUT página {pg}"
    # El hecho no puede tomar el domicilio del infractor ni la hora de citación.
    for pg, calle in {4:"GAVIOTAS",11:"SAN PEDRO",13:"SCHNEIDER",16:"CIRCUNVALACIÓN",25:"PICARTE",35:"HELIOTROPOS"}.items():
        assert calle in datos[pg]["lugar"], f"Lugar página {pg}"
    for pg, hora in {4:"11:10",11:"16:49",16:"17:05",35:"18:30"}.items():
        assert datos[pg]["hora_infraccion"] == hora, f"Hora página {pg}"
    assert datos[4]["fecha_parte"] == "12/11/2026"
    assert datos[16]["fecha_parte"] == "09/11/2026"
    assert datos[1]["fecha_citacion"] == ""  # 93/12 es ilegible, no inventar el día.
    assert datos[7]["oficina"] == "SubComisaria Oscar Cristi Gallo"
    causa, items, _ = catalogo.resolver_o_comodin(datos[1]["infraccion_texto"])
    assert [i["cod"] for i in items] == ["48"] and items[0]["estado"] == "check"
    assert "aproximación" in items[0]["nota"]
    assert {i["cod"] for i in catalogo.resolver_o_comodin(datos[34]["infraccion_texto"])[1]} == {"16", "33"}
    for pg, bol, hora in ((29,"375596","10:00"),(30,"375597","11:00")):
        assert motor.tipo_pagina(textos[pg]) == "armada"
        p = servidor.armar_armada(datos[pg], "real", pg, pg)
        assert p["folio"] == bol and p["hora_infraccion"] == "21:30" and p["hora_citacion"] == hora
        assert p["oficina"] == "Armada de Chile"
        assert p["items"][0]["cod"] == "648" and p["items"][0]["estado"] == "check"
        assert busqueda.extraer(textos[pg], "rut", "armada", False) == p["cert"]["rut"]
        assert busqueda.sugerir_infracciones(textos[pg], "armada")["codigos"][0]["codigo"] == "648"
    assert datos[29]["numero_armada"] == "12352"
    assert datos[30]["numero_armada"] == ""  # «HrJPL»: requiere recorte o revisión.
    # Comprobación visual posterior: ambos originales traen el mismo RUT inválido
    # que leyó el OCR. No usar la corrección manual para inventar una lectura.
    for pg in (26,37):
        p = next(p for p in partes if p["pagina"] == pg)
        assert datos[pg]["rut_leido"] == p["cert"]["rut"]
        assert not certificado.rut_ok(datos[pg]["rut_leido"])
        assert datos[pg]["infractor_rut"] == ""
        assert datos[pg]["rut_leido"] != p["ed"]["RUT (certificado)"]
    p = next(p for p in partes if p["pagina"] == 51)
    assert certificado.leer(hojas[p["img_cert"]-1]["texto"])["rut"] == p["ed"]["RUT (certificado)"]
    print("Pendientes: RUN del certificado recuperado; dos RUT impresos inválidos conservados para revisión.")
    print("53 partes reales: 16 RUT recuperados, lugares y horas, fechas inválidas, Armada e infracciones verificados.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sesion", required=True)
    p.add_argument("--ocr", required=True)
    a = p.parse_args()
    comprobar(a.sesion, a.ocr)
