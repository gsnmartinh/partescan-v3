"""Pruebas del perfil de juzgado y del reconocimiento de infracciones/oficinas. Ejecutar:  python tests/prueba_perfil.py"""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["PARTESCAN_PERFIL"] = tempfile.mkdtemp()

from parte_scan import catalogo, equivalencia, extractor_carab, perfil   # noqa: E402

fallas = []


def ok(cond, msg):
    if not cond:
        fallas.append(msg)
        print("FALLA:", msg)


# 1) con la lista de fabrica, cada concepto resuelve al código verificado y «ok»
L = perfil.infracciones()
for ab, cod in list(catalogo.CODIGOS.items()):
    x = catalogo.por_abrev(ab)
    c, est, _, _ = equivalencia.sugerir(ab, x["t"], L)
    ok(c == cod and est == "ok", f"equivalencia de {ab}: esperaba {cod} y dio {c} ({est})")

# 2) reglas del catálogo
_, its = catalogo.resolver("Estacionar en linea amarilla, sobre acera")
ok([i["cod"] for i in its] == ["48"], "línea amarilla + acera = solo 48")
_, its = catalogo.resolver("CONDUCIR SIN LA TOTALIDAD DE LA DOCUMENTACION")
ok([i["cod"] for i in its] == ["92", "37", "33"], "documentación = 92, 37, 33")

# 3) otro juzgado: otra numeración y otras palabras
d = Path(os.environ["PARTESCAN_PERFIL"])
(d / "Busca_Infracciones.csv").write_text(
    "codigo;descripcion\n7001;ESTACIONAR EN LA ACERA\n7002;VEHICULO SIN SEGURO OBLIGATORIO VIGENTE\n"
    "7003;CIRCULAR SIN PERMISO DE CIRCULACION\n7004;CIRCULAR SIN REVISION TECNICA\n", encoding="utf-8-sig")
perfil._cache.clear()
_, its = catalogo.resolver("Estacionar en linea amarilla, sobre acera")
ok([i["cod"] for i in its] == ["7001"], "otro juzgado: acera = 7001")
_, its = catalogo.resolver("CONDUCIR SIN LA TOTALIDAD DE LA DOCUMENTACION")
ok([i["cod"] for i in its] == ["7002", "7003", "7004"], "otro juzgado: documentación = 7002, 7003, 7004")
cfg = perfil.cargar()
cfg["equivalencias"] = {"48": "7002"}
perfil.guardar(cfg)
_, its = catalogo.resolver("Estacionar sobre acera")
ok([i["cod"] for i in its] == ["7002"], "lo confirmado por el usuario manda")

# 4) unidad de Carabineros según la lista de oficinas
perfil.restaurar_lista("infracciones")
for texto, esperado in (("CARABINEROS\n1RA COM. VALDIVIA\nT.SUBTE.R.MOGOLLONFS", "Tenencia Mogollones"),
                        ("RETEN PUNUCAPR", "Tenencia Punucapa"), ("1ª Comisaría", "1ra. Comisaria Carabineros")):
    ok(extractor_carab._oficina(texto)[0] == esperado, f"oficina de «{texto[:25]}» = {esperado}")

# 5) actuarias
cfg = perfil.cargar()
cfg["actuarios"], cfg["rol_actuario"] = {"ANA": "3"}, {"1": "ANA"}
perfil.guardar(cfg)
ok(perfil.actuario_por_digito("1") == ("ANA", "3") and perfil.actuario_por_digito("2") == ("", ""), "actuarias del perfil")

# 6) comodín: infracción que no calza con la lista -> código 67 y la descripción lleva lo que dice el parte
from parte_scan import catalogo  # noqa: E402
causa, items, lit = catalogo.resolver_o_comodin("  texto   sin sentido alguno qzxw  ")
ok(lit and len(items) == 1 and items[0]["cod"] == "67" and items[0]["estado"] == "check", "comodín 67 para texto desconocido")
ok(causa == "TEXTO SIN SENTIDO ALGUNO QZXW", "la descripción lleva el texto del parte en mayúsculas: %r" % causa)
causa, items, lit = catalogo.resolver_o_comodin("x " * 300)
ok(len(causa) <= catalogo.LARGO_LITERAL, "el literal se corta a %d" % catalogo.LARGO_LITERAL)
cfg = perfil.cargar(); cfg["infraccion_comodin"] = "99"; perfil.guardar(cfg)
ok(catalogo.resolver_o_comodin("qzxw")[1][0]["cod"] == "99", "el código comodín es configurable")
cfg["infraccion_comodin"] = "67"; perfil.guardar(cfg)

# 7) comunas del sistema y eñe
from parte_scan import exportar  # noqa: E402
ok(catalogo.comuna_en_sistema("Chillán") and catalogo.comuna_en_sistema("ÑUÑOA") and catalogo.comuna_en_sistema("VALDIVIA"), "comunas válidas")
ok(not catalogo.comuna_en_sistema("VALDIVIAX") and catalogo.comuna_en_sistema(""), "comuna inexistente / vacía")
ok(exportar.sin_tildes("PIÑA CONCEPCIÓN ñuñoa") == "PIÑA CONCEPCION ñuñoa", "se conserva la eñe y se quitan los acentos")

ok(catalogo.resolver_o_comodin("ñandú señalizado qzx")[0] == "ÑANDU SEÑALIZADO QZX", "la descripción conserva la Ñ y quita acentos")

from parte_scan import extractor_carab  # noqa: E402
_inf = extractor_carab._infractor("JUAN PEREZ SOTO, 28 años, Run Nro. 11.111.111-1, domiciliado en el sector Ejemplo sin Nro., de Valdivia. "
                                  "DISPOSICION INFRINGIDA: Articulo Nro. 25 de la Ley 19.925, sobre expendio y consumo de bebidas alcoholicas.")
ok(_inf[3] == "VALDIVIA" and "BEBIDAS" not in _inf[2], "la comuna no arrastra la «disposición infringida»: %r" % (_inf[2:4],))

print("TODO BIEN" if not fallas else f"{len(fallas)} falla(s)")
sys.exit(1 if fallas else 0)
