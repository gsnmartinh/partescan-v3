"""Puente entre ParteScan y el motor de tecleo (teclea/teclea_contextual.py): una sola ventana.

ParteScan entrega los partes ya revisados (sin pasar por un .json en Descargas), el motor los teclea en el sistema
del Juzgado en un hilo aparte y el avance se consulta por la API local. Todo ocurre en este computador, sin internet.
El motor de tecleo es el mismo de PartesTeclea: aquí solo se le da otra puerta de entrada."""
import json
import os
import sys
import threading
import traceback

from . import perfil

LOCK = threading.RLock()
LISTA = []          # partes en el formato del motor, con _uid (posición en ParteScan), _estado y _aviso
LOG = []            # líneas que va escribiendo el motor
HILO = None
_T = None
_ERROR_MOTOR = ""

ESTADOS_PENDIENTES = ("pendiente", "interrumpido", "cancelado")


def _carpeta_teclea():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "teclea")


def motor():
    """Carga el motor la primera vez. Devuelve (modulo, '') o (None, motivo)."""
    global _T, _ERROR_MOTOR
    if _T is not None:
        return _T, ""
    if _ERROR_MOTOR:
        return None, _ERROR_MOTOR
    try:
        c = _carpeta_teclea()
        if os.path.isdir(c) and c not in sys.path:
            sys.path.insert(0, c)
        import teclea_contextual as T
        _T = T
    except Exception as e:      # noqa: BLE001 - cualquier fallo de importación deja el tecleo como «no disponible»
        _ERROR_MOTOR = "El tecleo no está disponible en este equipo: %s" % e
        return None, _ERROR_MOTOR
    return _T, ""


def _puede_teclear(T):
    return bool(T and getattr(T, "WIN", False) and getattr(T, "send_keys", None) is not None)


def corriendo():
    return bool(HILO and HILO.is_alive())


def _log(texto):
    with LOCK:
        for linea in str(texto).replace("\r", "\n").split("\n"):
            if linea.strip() and not linea.lstrip().startswith("Empiezo en"):
                LOG.append(linea.rstrip())


class _Salida:
    """Recoge lo que el motor escribe con print() para mostrarlo en pantalla."""
    def write(self, s):
        if s:
            _log(s)
        return len(s or "")

    def flush(self):
        pass


def _ajustes_velocidad(T):
    """Usa la misma velocidad que se haya elegido en PartesTeclea (si existe esa configuración)."""
    try:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        with open(os.path.join(base, "PartesTeclea", "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        T.PAUSA_TECLA = float(cfg.get("pausa_tecla", T.PAUSA_TECLA))
        T.ESPERA_INICIO = int(float(cfg.get("espera_inicio", T.ESPERA_INICIO)))
    except Exception:       # noqa: BLE001
        pass


# ------------------------------------------------------------------ datos
def cargar(registros):
    """Recibe los partes de ParteScan (cada uno con 'uid' = posición en el lote). Conserva el avance de los que ya
    estaban: así se puede corregir un dato y volver a enviar sin perder lo ingresado."""
    T, motivo = motor()
    if T is None:
        raise ValueError(motivo)
    with LOCK:
        if corriendo():
            raise ValueError("Hay un ingreso en curso: deténlo antes de actualizar los datos.")
        previos = {p["_uid"]: p for p in LISTA}
        nuevos = T.partes_desde_lista(registros)
        for p, r in zip(nuevos, registros):
            uid = r.get("uid")
            ant = previos.get(uid)
            p["_uid"] = uid
            if r.get("ingresado") or (ant and ant["_estado"] in ("ingresado", "tecleado")):
                p["_estado"] = ant["_estado"] if ant and ant["_estado"] in ("ingresado", "tecleado") else "ingresado"
            else:
                p["_estado"] = "pendiente"
            p["_aviso"] = ant["_aviso"] if ant and ant["_estado"] == p["_estado"] else ""
        LISTA[:] = nuevos
    return {"ok": True, "partes": len(LISTA)}


def _fila(T, p):
    fat, avi = T.validar_parte(p)
    avi = [a for a in avi if not a.startswith("sin rut")]
    infr = T.resolver_infraccion(p["infracciones"][0])[0] if p["infracciones"] else ""
    return {"uid": p["_uid"], "estado": p["_estado"], "aviso": p["_aviso"], "errores": fat, "avisos": avi,
            "n_parte": p["n_parte"], "fecha_parte": p["fecha_parte"], "oficina": p.get("oficina", ""),
            "placa": T.placa(p["placa"]), "rut": p["rut"], "infraccion": infr}


def estado(desde=0):
    T, motivo = motor()
    disponible = _puede_teclear(T)
    if T is not None and not disponible:
        motivo = "Para teclear se necesita Windows y el componente pywinauto."
    with LOCK:
        return {"disponible": disponible, "motivo": "" if disponible else motivo, "corriendo": corriendo(),
                "partes": [_fila(T, p) for p in LISTA] if T is not None else [],
                "actuarios": sorted(perfil.actuarios()), "log": LOG[desde:], "nlog": len(LOG)}


# ------------------------------------------------------------------ ejecución
def _on_estado(i, e, detalle=""):
    with LOCK:
        LISTA[i]["_estado"] = e
        LISTA[i]["_aviso"] = detalle if e in ("tecleado", "interrumpido") else ""


def _trabajo(T, idx, auto):
    viejo = sys.stdout
    sys.stdout = _Salida()
    try:
        sis = T.Sistema()
        T.procesar_lote(sis, LISTA, idx, on_estado=_on_estado, aceptar_auto=auto)
    except T.Detener as e:
        _log("[detenido] %s\nNo se hizo clic en nada." % e)
    except Exception:       # noqa: BLE001
        _log("[error inesperado]\n" + traceback.format_exc())
    finally:
        sys.stdout = viejo
        _log("--- fin ---")


def iniciar(uids=None, auto=False, actuario=""):
    """Teclea los partes pendientes (o solo los indicados por uid)."""
    global HILO
    T, motivo = motor()
    if not _puede_teclear(T):
        raise ValueError(motivo or "Para teclear se necesita Windows y el componente pywinauto.")
    with LOCK:
        if corriendo():
            raise ValueError("Ya hay un ingreso en curso.")
        if uids is None:
            idx = [i for i, p in enumerate(LISTA) if p["_estado"] in ESTADOS_PENDIENTES]
        else:
            quiero = set(uids)
            idx = [i for i, p in enumerate(LISTA) if p["_uid"] in quiero]
        if not idx:
            raise ValueError("No hay partes para teclear.")
        graves = []
        for i in idx:
            fat, _ = T.validar_parte(LISTA[i])
            if fat:
                graves.append("Parte %s: %s" % (LISTA[i]["n_parte"], "; ".join(fat)))
        if graves:
            raise ValueError("Corrige estos datos en ParteScan:\n" + "\n".join(graves))
        T.cargar_perfil()       # por si cambió el perfil (listas, actuarias)
        _ajustes_velocidad(T)
        T.ACTUARIO = "" if not actuario or actuario.lower().startswith("auto") else actuario.upper()
        T.PARAR.clear()
        T.SALTAR.clear()
        _log("--- Ingresando %d parte(s) ---" % len(idx))
        HILO = threading.Thread(target=_trabajo, args=(T, idx, bool(auto)), daemon=True)
        HILO.start()
    return {"ok": True, "partes": len(idx)}


def detener():
    T, _ = motor()
    if T is not None:
        T.PARAR.set()
        _log("Deteniendo...")
    return {"ok": True}


def marcar(uid, nuevo):
    """Marca a mano un parte como ingresado o de nuevo pendiente."""
    if nuevo not in ("ingresado", "pendiente"):
        raise ValueError("Estado no válido.")
    with LOCK:
        for p in LISTA:
            if p["_uid"] == uid:
                p["_estado"], p["_aviso"] = nuevo, ""
                return {"ok": True}
    raise ValueError("No encuentro ese parte.")


def limpiar():
    """Vacía la lista y el registro para empezar una tanda nueva (no se puede mientras se está tecleando)."""
    with LOCK:
        if corriendo():
            raise ValueError("Hay un ingreso en curso: detenlo o espera a que termine.")
        LISTA.clear()
        LOG.clear()
    return {"ok": True}


def accion(nombre, datos):
    if nombre == "cargar":
        return cargar(datos.get("partes", []))
    if nombre == "iniciar":
        return iniciar(datos.get("uids"), datos.get("auto", False), datos.get("actuario", ""))
    if nombre == "limpiar":
        return limpiar()
    if nombre == "detener":
        return detener()
    if nombre == "marcar":
        return marcar(datos.get("uid"), datos.get("estado"))
    raise ValueError("Acción desconocida.")
