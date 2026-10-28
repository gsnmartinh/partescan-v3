"""Pruebas del puente ParteScan <-> motor de tecleo (ventana única). Usan un «sistema» falso: no tocan ninguna pantalla.
Ejecutar:  python tests/prueba_tecleador.py"""
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["PARTESCAN_PERFIL"] = tempfile.mkdtemp()

if sys.platform != "win32":        # el motor es de Windows: se simula solo para poder importarlo en otro sistema
    import ctypes
    ctypes.windll = MagicMock()
    if not hasattr(ctypes, "WINFUNCTYPE"):
        ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE

from parte_scan import tecleador   # noqa: E402

fallas = []


def ok(cond, msg):
    if not cond:
        fallas.append(msg)
        print("FALLA:", msg)


def reg(uid, n, boleta, **kw):
    r = {"origen": "carab", "oficina": "Reten Isla Teja", "n_parte": n, "boleta": boleta, "fecha_parte": "27/10/2026",
         "fecha_citacion": "", "descripcion": "PRUEBA", "lugar": "CALLE DE PRUEBA 1", "hora": "2130",
         "rut": "11.111.111-1", "nombre": "PERSONA DE PRUEBA", "direccion": "SIN DIRECCION", "comuna": "VALDIVIA",
         "placa": "", "tipo_vehiculo": "", "marca": "", "infracciones": ["300"], "uid": uid, "ingresado": False}
    r.update(kw)
    return r


T, motivo = tecleador.motor()
ok(T is not None, "el motor debe poder importarse: %s" % motivo)

# 1) carga: dos infractores con el mismo N° de parte son dos partes distintos y quedan pendientes
tecleador.cargar([reg(0, "5555", "70001"), reg(1, "5555", "70002"), reg(2, "6000", "70003", ingresado=True)])
est = tecleador.estado()
ok(len(est["partes"]) == 3, "deben quedar 3 partes")
ok([f["estado"] for f in est["partes"]] == ["pendiente", "pendiente", "ingresado"], "estados iniciales incorrectos")
ok(est["partes"][0]["n_parte"] == est["partes"][1]["n_parte"] == "5555", "mismo N° de parte en dos causas seguidas")

# 2) corregir un dato y volver a enviar no pierde lo ya ingresado
tecleador.marcar(0, "ingresado")
tecleador.cargar([reg(0, "5555", "70001"), reg(1, "5555", "70002", placa="ABCD12"), reg(2, "6000", "70003")])
est = tecleador.estado()
ok([f["estado"] for f in est["partes"]] == ["ingresado", "pendiente", "ingresado"], "al reenviar se perdió el avance")
ok(est["partes"][1]["placa"] == "ABCD12", "el dato corregido debe llegar al motor")

# 3) patente de motos con 6 caracteres: se teclea tal cual y no genera aviso de largo
tecleador.LISTA.clear()          # escenario nuevo: lista limpia
tecleador.cargar([reg(0, "1", "1", placa="TV0880")])
f = tecleador.estado()["partes"][0]
ok(f["placa"] == "TV0880" and not any("placa" in a for a in f["avisos"]), "patente de moto de 6 caracteres")

# 4) marca vacía y tipo AUTOMOVIL: sin errores ni avisos
tecleador.LISTA.clear()          # escenario nuevo: lista limpia
tecleador.cargar([reg(0, "1", "1", placa="ABCD12", tipo_vehiculo="AUTOMOVIL", marca="")])
f = tecleador.estado()["partes"][0]
ok(not f["errores"] and not f["avisos"], "marca vacía no debe dar error ni aviso: %s %s" % (f["errores"], f["avisos"]))

# 5) un parte con error fatal (sin N° de parte) no se puede teclear
tecleador.LISTA.clear()          # escenario nuevo: lista limpia
tecleador.cargar([reg(0, "", "1")])
T.WIN, T.send_keys = True, object()          # se hace pasar por Windows con pywinauto
try:
    tecleador.iniciar()
    ok(False, "debía rechazar un parte sin N° de parte")
except ValueError as e:
    ok("Corrige" in str(e), "mensaje de error inesperado: %s" % e)

# 6) ingreso completo con un «sistema» falso: estados, registro y detener
class SisFalso:
    avisos = []


def lote_falso(sis, partes, indices, on_estado=None, aceptar_auto=False):
    for i in indices:
        print("\n=== Parte %d/%d: N %s ===" % (i + 1, len(partes), partes[i]["n_parte"]))
        on_estado(i, "tecleando", "")
        time.sleep(0.05)
        if T.PARAR.is_set():
            on_estado(i, "interrumpido", "detenido")
            raise T.Detener("Detenido desde la interfaz.")
        on_estado(i, "ingresado", "")
    print("Terminado.")


T.Sistema, T.procesar_lote = SisFalso, lote_falso
tecleador.LISTA.clear()          # escenario nuevo: lista limpia
tecleador.cargar([reg(0, "10", "1"), reg(1, "11", "2"), reg(2, "12", "3", ingresado=True)])
tecleador.iniciar(actuario="Automatico")
tecleador.HILO.join(5)
est = tecleador.estado()
ok([f["estado"] for f in est["partes"]] == ["ingresado"] * 3, "debían quedar los 3 ingresados: %s" % [f["estado"] for f in est["partes"]])
ok(any("Parte 1/3" in l for l in est["log"]), "el registro debe traer lo que escribe el motor")
ok(not est["corriendo"], "no debe seguir corriendo")

# 7) mientras corre no se puede reenviar datos, y Detener interrumpe
def lote_lento(sis, partes, indices, on_estado=None, aceptar_auto=False):
    for i in indices:
        on_estado(i, "tecleando", "")
        for _ in range(100):
            if T.PARAR.is_set():
                on_estado(i, "interrumpido", "detenido")
                raise T.Detener("Detenido desde la interfaz.")
            time.sleep(0.02)
        on_estado(i, "ingresado", "")


T.procesar_lote = lote_lento
tecleador.LISTA.clear()          # escenario nuevo: lista limpia
tecleador.cargar([reg(0, "20", "1"), reg(1, "21", "2")])
tecleador.iniciar()
time.sleep(0.2)
try:
    tecleador.cargar([reg(0, "20", "1")])
    ok(False, "no debía permitir reenviar datos mientras teclea")
except ValueError:
    pass
tecleador.detener()
tecleador.HILO.join(5)
est = tecleador.estado()
ok(est["partes"][0]["estado"] == "interrumpido" and est["partes"][1]["estado"] == "pendiente", "Detener debe dejar el primero interrumpido y el resto pendiente")
ok(any("[detenido]" in l for l in est["log"]), "el registro debe indicar que se detuvo")

# 8) comuna: se escribe como está en la lista del sistema (con tilde); si no existe, queda limpia
ok(T.comuna_sistema("rio bueno") == "RÍO BUENO" and T.comuna_sistema("Ñuñoa") == "ÑUÑOA" and T.comuna_sistema("VALDIVIA") == "VALDIVIA", "comuna con tilde como en el sistema")
ok(T.comuna_sistema("Pueblo Inventado") == "PUEBLO INVENTADO", "comuna fuera de la lista")
ok(open(RAIZ / "teclea" / "comunas_sistema.txt", encoding="utf-8").read() == open(RAIZ / "parte_scan" / "comunas_sistema.txt", encoding="utf-8").read(), "las dos copias de la lista de comunas deben ser iguales")
tecleador.LISTA.clear()
tecleador.cargar([reg(0, "1", "1", comuna="río bueno")])
ok(tecleador.LISTA[0]["comuna"] == "RÍO BUENO", "el motor recibe la comuna con tilde: %r" % tecleador.LISTA[0]["comuna"])

if fallas:
    print("\n%d falla(s)" % len(fallas))
    sys.exit(1)
print("Pruebas del tecleador: todo OK")
