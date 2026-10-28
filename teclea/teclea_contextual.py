# -*- coding: utf-8 -*-
"""
teclea_contextual.py - Teclea partes en el sistema del Juzgado LEYENDO la pantalla.

Cada accion se decide mirando que campo tiene el cursor (por su ID de control, medido en las
grabaciones) y se verifica despues (lee el valor que quedo). No depende del orden de Tab ni de F9.

NUNCA hace clic ni presiona Enter sobre un boton (por eso nunca acepta): tu revisas y aceptas.

Uso:
  python teclea_contextual.py --ensayo            (solo muestra que tecleara; no toca el sistema)
  python teclea_contextual.py                     (teclea todos los partes de Descargas)
  python teclea_contextual.py archivo.json --desde 3
  python teclea_contextual.py --solo 2

Teclas:  ESC = detener     F9 = pausar / reanudar
         F8 = (solo mientras espera que aceptes un parte) seguir con el siguiente igual
Mientras teclea NO toques el teclado ni el mouse.

Requiere:  pip install pywinauto
"""
VERSION = "2026.10.27a"

import argparse
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import re
import sys
import time
import traceback
import unicodedata
from pathlib import Path
from typing import NamedTuple

try:
    from parte_scan import perfil
except ImportError:          # desarrollo: este archivo vive en teclea/ y parte_scan/ esta en la carpeta superior
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from parte_scan import perfil

WIN = sys.platform == "win32"

# ============================= CONFIGURACION =============================
# Nombre del actuario tal como se escribe en el combo. Vacio = lo eliges tu a mano y el programa espera.
ACTUARIO = ""
# Actuarias, reparto por Rol, oficinas y titulo de la pantalla: salen del PERFIL del juzgado (ver cargar_perfil()).
ROL_ACTUARIO = {}
ACTUARIOS = {}
TITULO_VENTANA = "Procesos"
ESPERA_INICIO = 3      # segundos de aviso antes de empezar a teclear cada parte (ESC cancela)
PAUSA_TECLA = 0.02     # segundos entre teclas
T_FOCO = 4.0           # espera maxima a que el cursor llegue al campo siguiente
T_RUT = 20.0           # espera maxima tras el RUT (el sistema consulta la base de datos)
T_MANUAL = 300.0       # espera maxima cuando te toca hacer algo a ti

# ID de control -> nombre logico. Los IDs salen de las grabaciones (no cambian mientras no cambie el sistema).
CAMPOS = {
    11: "rol", 12: "rol", 193: "rol", 15: "oficina", 9: "fecha_ingreso",
    14: "n_parte", 10: "fecha_parte",
    190: "descripcion", 191: "actuario",
    195: "fecha_citacion", 196: "hora_citacion",
    189: "lugar", 159: "rut",
    138: "nombre", 137: "direccion", 136: "comuna",
    95: "veh", 93: "veh", 98: "veh", 92: "veh", 99: "veh",
}
# Texto que se escribe en Oficina Emisora (una parte reconocible). Por defecto se usa "origen" tal cual.
# Para corregir: {"CARABINEROS DE CHILE": "CARABINEROS"}
OFICINAS = {}


OFICINAS_SISTEMA = {}     # codigo (int si es numerico) -> descripcion, del perfil


def cargar_perfil():
    """Lee el perfil del juzgado (actuarias, reparto por Rol, oficinas, titulo de la pantalla) y lo deja en este modulo."""
    global TITULO_VENTANA
    ACTUARIOS.clear()
    ACTUARIOS.update(perfil.actuarios())
    ROL_ACTUARIO.clear()
    ROL_ACTUARIO.update(perfil.rol_actuario())
    OFICINAS_SISTEMA.clear()
    OFICINAS_SISTEMA.update({(int(c) if str(c).isdigit() else c): d for c, d in perfil.oficinas().items()})
    TITULO_VENTANA = perfil.cargar().get("titulo_ventana") or "Procesos"


cargar_perfil()


def _norm_of(t):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().upper()).strip()


def _palabras_of(d):
    return [w for w in re.findall(r"[A-Z0-9]+", _norm_of(d))]


_GENERICAS_OF = {"CARABINEROS", "CHILE", "COMISARIA", "SUBCOMISARIA", "TENENCIA", "RETEN", "DIRECCION", "OFICINA", "DE",
                 "DEL", "LA", "LOS", "LAS", "Y", "EL", "DEPARTAMENTO", "LOCAL", "SERVICIO"}


def oficina_exacta(origen):
    """(codigo, descripcion) si el texto es exactamente una oficina del perfil; si no, ('', '')."""
    cod = perfil.codigo_oficina(origen)
    return (cod, perfil.oficinas()[cod]) if cod else ("", "")


def palabra_unica_oficina(desc):
    """Palabra (o inicio de palabra) de la descripcion que identifica a UNA sola oficina del sistema, ej. JAZM, OSCA."""
    todas = [_palabras_of(d) for d in perfil.oficinas().values()]
    for w in _palabras_of(desc):
        if len(w) < 4 or w in _GENERICAS_OF or w.isdigit():
            continue
        for n in range(4, len(w) + 1):
            pre = w[:n]
            if sum(1 for pal in todas if any(x.startswith(pre) for x in pal)) == 1:
                return pre
    return ""


def oficina_texto(origen):
    """Texto corto que se escribe en Oficina Emisora (el sistema lo busca y expande)."""
    o = limpiar(origen).upper()
    if o in OFICINAS:
        return OFICINAS[o]
    cod, desc = oficina_exacta(origen)          # nombre exacto de la lista del juzgado (lo normal con ParteScan)
    if cod:
        if str(cod) == "1":
            return "1"                           # 1ra Comisaria: se escribe 1 (asi se probo)
        return palabra_unica_oficina(desc) or str(cod)
    if re.search(r"PRIMERA|\b1\s*(RA|ERA)\b", o) and "COM" in o and not any(
            k in o for k in ("RETEN", "TENENCIA", "SUBCOM", "PUNUCAPA", "JAZMINES", "OSCAR", "CORRAL", "NIEBLA")):
        return "1"
    if "JAZMINES" in o or "JAZM" in o:
        return "JAZM"
    if "OSCAR" in o or "CRISTI" in o or "CRITIS" in o or "OSCA" in o:
        return "OSCA"
    # coincidencia por la palabra distintiva (ej. RETEN PUNUCAPA -> Tenencia Punucapa), si es unica
    genericas = {"CARABINEROS", "CHILE", "COMISARIA", "VALDIVIA", "TENENCIA", "RETEN", "DIRECCION", "OFICINA",
                 "SUBCOMISARIA", "LOCAL", "DEPARTAMENTO", "MINISTERIO", "TRANSPORTES"}
    palabras = {w for w in re.findall(r"[A-Z]{5,}", o)} - genericas
    cand = [c for c, d in OFICINAS_SISTEMA.items() if palabras & set(re.findall(r"[A-Z]{5,}", limpiar(d).upper()))]
    if len(cand) == 1:
        return str(cand[0])
    for cod, desc in sorted(OFICINAS_SISTEMA.items()):
        d = limpiar(desc).upper()
        if len(o) >= 4 and (o == d or o in d or d in o):
            return str(cod)
    return o


def oficina_esperada(txt, origen=""):
    """Descripcion que debe quedar en el campo para el texto escrito ('' si no se puede verificar)."""
    cod, desc = oficina_exacta(origen)
    if cod:
        return limpiar(desc).upper()
    t = txt.upper()
    if t.isdigit() and int(t) in OFICINAS_SISTEMA:
        return limpiar(OFICINAS_SISTEMA[int(t)]).upper()
    return {"JAZM": "JAZMINES", "OSCA": "CRISTI"}.get(t, "")
ID_OVERLAY_BOL = 32     # caja flotante que aparece al escribir en la grilla Bol/N.Parte
ID_OVERLAY_INF = 119    # caja flotante de la grilla de Infracciones

BOTONES = {"ThunderRT6CommandButton", "Button"}
IGNORAR = {"IME", "MSCTFIME UI", "tooltips_class32", "Shell_TrayWnd"}
VK_ESC, VK_F8, VK_F9 = 0x1B, 0x77, 0x78


import threading
PARAR = threading.Event()     # lo activa la interfaz (boton Detener)
SALTAR = threading.Event()    # lo activa la interfaz (boton "Seguir igual", como F8)


class Detener(Exception):
    """Detiene el programa con un mensaje (no toca nada mas)."""


# ============================ FUNCIONES PURAS ============================
def limpiar(s):
    """Sin tildes (se ingresa en mayusculas); conserva la Ñ. Espacios normalizados."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s).replace("ñ", "\x01").replace("Ñ", "\x02"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode("ascii").replace("\x01", "Ñ").replace("\x02", "Ñ")
    return re.sub(r"\s+", " ", s).strip()


_COMUNAS = None


def comuna_sistema(s):
    """El campo Comuna del sistema solo completa si se escribe EXACTO como esta en su lista (con tilde: RIO no sirve,
    RÍO sí). Devuelve el nombre de la lista; si no calza con ninguno, el texto limpio y en mayusculas."""
    global _COMUNAS
    if _COMUNAS is None:
        _COMUNAS = {}
        base = Path(__file__).resolve().parent
        for c in (base / "comunas_sistema.txt", base.parent / "parte_scan" / "comunas_sistema.txt",
                  base / "parte_scan" / "comunas_sistema.txt"):
            if c.is_file():
                for linea in c.read_text(encoding="utf-8").splitlines():
                    if linea.strip():
                        _COMUNAS[limpiar(linea.upper())] = linea.strip()
                break
    x = limpiar(str(s or "").upper())
    return _COMUNAS.get(x, x)


def fecha(s):
    """Devuelve dd/mm/aaaa o None si no es una fecha valida."""
    s = (str(s or "")).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        d, mo, a = m.groups()
    else:
        m = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", s)
        if m:
            a, mo, d = m.groups()
        else:
            m = re.fullmatch(r"(\d{2})(\d{2})(\d{4})", s)
            if not m:
                return None
            d, mo, a = m.groups()
    if len(a) == 2:
        a = "20" + a
    try:
        datetime.date(int(a), int(mo), int(d))
    except ValueError:
        return None
    return f"{int(d):02d}/{int(mo):02d}/{a}"


def dv_rut(cuerpo):
    serie, suma = [2, 3, 4, 5, 6, 7], 0
    for i, c in enumerate(reversed(cuerpo)):
        suma += int(c) * serie[i % 6]
    r = 11 - (suma % 11)
    return "0" if r == 11 else "K" if r == 10 else str(r)


def rut(s):
    """Devuelve (rut 'NNNNNNNN-D' o '', dv_ok)."""
    crudo = str(s or "")
    limpio = re.sub(r"[^0-9kK]", "", crudo)
    if len(limpio) < 2:
        return "", True
    if "-" in crudo:
        cuerpo, dv = limpio[:-1], limpio[-1].upper()
        return f"{cuerpo}-{dv}", dv_rut(cuerpo) == dv
    if limpio[:-1].isdigit() and dv_rut(limpio[:-1]) == limpio[-1].upper():
        return f"{limpio[:-1]}-{limpio[-1].upper()}", True
    if limpio.isdigit():          # venia sin digito verificador
        return f"{limpio}-{dv_rut(limpio)}", True
    return "", False


PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "SAN", "SANTA", "Y", "MAC", "VAN", "VON"}


def split_nombre(nombre):
    """'JUAN PEDRO PEREZ SOTO' -> (paterno, materno, nombres). Los dos ultimos apellidos van al final."""
    t = limpiar(nombre).upper().split()
    if not t:
        return "", "", ""

    def ultimo_apellido(tt):
        i = len(tt) - 1
        while i > 0 and tt[i - 1] in PARTICULAS:
            i -= 1
        return " ".join(tt[i:]), tt[:i]

    if len(t) == 1:
        return t[0], "", ""
    mat, resto = ultimo_apellido(t)
    if not resto:
        return mat, "", ""
    pat, nombres = ultimo_apellido(resto)
    if not nombres:                       # solo un nombre y un apellido
        return mat, "", pat
    return pat, mat, " ".join(nombres)


def split_direccion(direccion):
    """'PASAJE CORVI 10 NRO. 4060' -> (calle, numero, resto)."""
    d = limpiar(direccion).upper()
    if not d or d == "SIN DIRECCION":
        return d, "", ""
    extra = ""
    k = re.search(r"\b(DEPTO|DPTO|DEPARTAMENTO|BLOCK|BLOQUE|CASA|OFICINA|OF|PARCELA|SITIO|LOTE|VILLA|POBLACION|SECTOR)\b", d)
    if k and k.start() > 0 and re.search(r"\d", d[:k.start()]):
        d, extra = d[:k.start()].strip(" ,."), d[k.start():]
    m = re.search(r"\b(?:NRO|NUMERO|NUM|N)\.?\s*[#]?\s*(\d+[A-Z]?|S/?N)\b", d) or \
        re.search(r"#\s*(\d+[A-Z]?)", d)
    if not m:
        nums = list(re.finditer(r"(?<![\w/])(\d+[A-Z]?|S/N)(?![\w/])", d))
        m = nums[-1] if nums else None
    if not m:
        return d, "", ""
    calle = d[:m.start()].strip(" ,.#")
    resto = (d[m.end():].strip(" ,.-") + " " + extra).strip()
    return calle, m.group(1), resto


# ---------------- Tabla de infracciones (exportada con exportar_lista.py -> Busca_Infracciones.csv) -------------
_TABLA_INF = None
_STOP = {"DE", "EN", "A", "LA", "EL", "LOS", "LAS", "DEL", "Y", "AL", "UN", "UNA", "POR", "CON", "ART", "NO", "LO"}


def _norm_inf(t):
    t = limpiar(t).upper().replace('"', " ")
    return re.sub(r"[^A-Z0-9 ]", " ", t).split()


def tabla_infracciones():
    """{codigo: descripcion} de «Busca Infracciones» de este juzgado (perfil)."""
    return perfil.infracciones()


def resolver_infraccion(texto):
    """Devuelve (codigo, descripcion, nota). Si no hay certeza: (texto_original, '', nota) y se busca en el sistema."""
    import difflib
    tabla = tabla_infracciones()
    t = limpiar(texto)
    if not t or not tabla:
        return t, "", ""
    if t in tabla:
        return t, tabla[t], ""
    tt = _norm_inf(t)
    ts = [w for w in tt if w not in _STOP]
    cand = []
    for cod, desc in tabla.items():
        if cod.startswith("Mig"):
            continue
        dd = _norm_inf(desc)
        if dd == tt:
            return cod, desc, ""
        ds = [w for w in dd if w not in _STOP]
        a, b = set(ts), set(ds)
        jac = len(a & b) / len(a | b) if a | b else 0
        rat = difflib.SequenceMatcher(None, " ".join(ts), " ".join(ds)).ratio()
        cont = 1.0 if len(" ".join(ds)) >= 12 and " ".join(ds) in " ".join(ts) else 0.0
        cand.append((max(jac, rat, cont * 0.95), cod, desc))
    cand.sort(reverse=True)
    if cand and cand[0][0] >= 0.8 and (len(cand) < 2 or cand[0][0] - cand[1][0] >= 0.05):
        return cand[0][1], cand[0][2], f"infraccion '{t}' -> codigo {cand[0][1]} ({cand[0][2]}), revisa"
    return t, "", f"infraccion '{t}' sin codigo claro: se buscara en el sistema"


def hora(s):
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) == 3:
        d = "0" + d
    return d if len(d) == 4 else ""


def placa(s):
    return re.sub(r"[^A-Za-z0-9]", "", str(s or "")).upper()


def esc_keys(t):
    """Escapa los caracteres especiales de pywinauto send_keys."""
    return "".join("{" + c + "}" if c in "+^%~(){}" else c for c in t)


def norm(s, modo="texto"):
    s = str(s or "")
    if modo == "digitos":
        return re.sub(r"\D", "", s)
    if modo == "alnum":
        return re.sub(r"[^A-Za-z0-9]", "", s).upper()
    return re.sub(r"\s+", " ", s).strip().upper()


def igual(visto, esperado, modo="texto"):
    return norm(visto, modo) == norm(esperado, modo)


def cargar_partes(ruta):
    with open(ruta, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return partes_desde_lista(data.get("partes", []) if isinstance(data, dict) else data)


def partes_desde_lista(lista):
    """Normaliza los registros (del .json o entregados directo por ParteScan) al formato que teclea el motor."""
    partes = []
    for raw in lista:
        def g(k):
            v = raw.get(k)
            return "" if v is None else v
        infs = raw.get("infracciones") or []
        if isinstance(infs, (str, int)):
            infs = [infs]
        res = []
        for it in infs:
            if isinstance(it, dict):
                it = it.get("codigo") or it.get("cod") or it.get("descripcion") or it.get("texto") or ""
            it = limpiar(it)
            if it:
                res.append(it)
        partes.append({
            "origen": limpiar(g("origen")),
            "oficina": limpiar(g("oficina")) or (perfil.cargar().get("oficina_carabineros", "") if limpiar(g("origen")).upper().startswith("CARAB") else ""),
            "oficina_supuesta": not limpiar(g("oficina")) and limpiar(g("origen")).upper().startswith("CARAB"),
            "n_parte": limpiar(g("n_parte")),
            "boleta": limpiar(g("boleta")),
            "fecha_parte": g("fecha_parte"),
            "fecha_citacion": g("fecha_citacion"),
            "descripcion": limpiar(g("descripcion")),
            "lugar": limpiar(g("lugar")),
            "hora": g("hora"),
            "rut": g("rut"),
            "nombre": limpiar(g("nombre")),
            "direccion": limpiar(g("direccion")),
            "comuna": comuna_sistema(g("comuna")),
            "placa": g("placa"),
            "tipo_vehiculo": limpiar(g("tipo_vehiculo")),
            "marca": limpiar(g("marca")),
            "infracciones": res,
        })
    return partes


def validar_parte(p):
    """Devuelve (fatales, avisos)."""
    fat, avi = [], []
    if not p["n_parte"]:
        fat.append("falta n_parte")
    if not fecha(p["fecha_parte"]):
        fat.append(f"fecha_parte invalida: {p['fecha_parte']!r}")
    if p["fecha_citacion"] and not fecha(p["fecha_citacion"]):
        avi.append(f"fecha_citacion invalida: {p['fecha_citacion']!r} (no se tecleara)")
    if p["hora"] and not hora(p["hora"]):
        avi.append(f"hora invalida: {p['hora']!r} (no se tecleara)")
    if p["rut"]:
        r, ok = rut(p["rut"])
        if not r:
            avi.append(f"rut no reconocible: {p['rut']!r} (lo ingresaras tu)")
        elif not ok:
            avi.append(f"el digito verificador del rut no cuadra: {r}")
    else:
        avi.append("sin rut (se deja vacio y se teclea el nombre del parte)")
    if p["placa"] and len(placa(p["placa"])) != 6:
        avi.append(f"placa con {len(placa(p['placa']))} caracteres (el campo admite 6)")
    # Oficina emisora y boleta si las exige el sistema; marca, placa, descripcion o infraccion pueden faltar.
    if p.get("oficina_supuesta"):
        avi.append("oficina asumida: 1ra. Comisaria (si es un reten o tenencia, corrigela con Editar)")
    elif not p.get("oficina"):
        avi.append("sin oficina emisora (la eliges tu en el cuadro)")
    if not p["boleta"]:
        avi.append("sin boleta (el sistema la pide)")
    if p["infracciones"]:
        nota = resolver_infraccion(p["infracciones"][0])[2]
        if nota:
            avi.append(nota)
    if len(p["infracciones"]) > 1:
        avi.append("varias infracciones: solo se tecleara la primera")
    return fat, avi


def duplicados(partes):
    """{indice: mensaje} para los N Parte repetidos dentro del mismo archivo (el sistema rechaza el segundo)."""
    vistos, res = {}, {}
    for i, p in enumerate(partes):
        k = p["n_parte"]
        if k in vistos:
            res[i] = f"N Parte {k} repetido (tambien en el parte {vistos[k] + 1}): usa Prefijo 99"
        else:
            vistos[k] = i
    return res


def mostrar_plan(i, n, p, fat, avi):
    print(f"\n--- Parte {i}/{n} ---")
    r, _ = rut(p["rut"])
    filas = [
        ("Rol (11/12/193)", "solo Enter"),
        ("Oficina Emisora (id 15)", oficina_texto(p["oficina"]) or "(la escribes tu)"),
        ("N Parte (id 14)", p["n_parte"]),
        ("Fecha Parte (id 10)", fecha(p["fecha_parte"]) or "(invalida)"),
        ("Grilla Bol/N.Parte, 1a celda", p["boleta"] or "(vacio)"),
        ("Descripcion (id 190)", p["descripcion"] or "(vacio)"),
        ("Actuario (id 191)", ACTUARIO or "segun el ultimo digito del Rol"),
        ("Fecha citacion (id 195)", fecha(p["fecha_citacion"]) or "(se deja la del sistema)"),
        ("Lugar (id 189)", p["lugar"] or "(vacio)"),
        ("Hora (mascara)", hora(p["hora"]) or "(se deja la del sistema)"),
        ("RUT (id 159)", r or "(lo ingresas tu)"),
        ("Nombre (id 138)", (p["nombre"] or "(vacio)") + "   [solo si el RUT es nuevo]"),
        ("Direccion (id 137)", (p["direccion"] or "SIN DIRECCION") + "   [solo si el RUT es nuevo]"),
        ("Comuna (id 136)", (p["comuna"] or "(se deja la del sistema)") + "   [solo si el RUT es nuevo]"),
        ("Placa (mascara)", placa(p["placa"]) or "(sin placa)"),
        ("Tipo vehiculo / Marca", f"{p['tipo_vehiculo'] or '(vacio)'} / {p['marca'] or '(vacio)'}"),
        ("Infraccion (grilla)", (lambda r: f"{r[0]} {r[1]}".strip())(resolver_infraccion(p["infracciones"][0]))
         if p["infracciones"] else "(ninguna)"),
    ]
    for k, v in filas:
        print(f"  {k:<30} {v}")
    for m in fat:
        print(f"  [ERROR] {m}")
    for m in avi:
        print(f"  [aviso] {m}")


# ============================ CAPA DE WINDOWS ============================
class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD),
                ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
                ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
                ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND),
                ("rcCaret", wt.RECT)]


send_keys = None
if WIN:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
    user32.FindWindowW.restype = wt.HWND
    user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
    user32.GetAncestor.restype = wt.HWND
    user32.GetParent.argtypes = [wt.HWND]
    user32.GetParent.restype = wt.HWND
    user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetDlgCtrlID.argtypes = [wt.HWND]
    user32.GetDlgCtrlID.restype = ctypes.c_int
    user32.IsWindow.argtypes = [wt.HWND]
    user32.IsWindowEnabled.argtypes = [wt.HWND]
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.IsWindowVisible.argtypes = [wt.HWND]
    user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetForegroundWindow.restype = wt.HWND
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetFocus.argtypes = [wt.HWND]
    user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
    user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
    user32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
                                           wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
    user32.SendMessageTimeoutW.restype = ctypes.c_size_t
    try:
        from pywinauto.keyboard import send_keys
    except Exception:
        send_keys = None


class Ctl(NamedTuple):
    hwnd: int
    id: int
    clase: str
    rect: tuple


def clase(h):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buf, 256)
    return buf.value


def pid_de(h):
    p = wt.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def rect(h):
    r = wt.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def _smto(h, msg, wparam, lparam, timeout=200):
    res = ctypes.c_size_t()
    ok = user32.SendMessageTimeoutW(h, msg, wparam, lparam, 2, timeout, ctypes.byref(res))
    return (res.value if ok else None)


def leer(h):
    """Texto de un control de otro proceso (WM_GETTEXT con timeout)."""
    n = _smto(h, 0x000E, 0, 0)
    if not n:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    ok = _smto(h, 0x000D, n + 1, ctypes.addressof(buf))
    return buf.value if ok is not None else ""


def hijos(h):
    res = []

    def cb(hh, lp):
        res.append(hh)
        return True

    user32.EnumChildWindows(h, WNDENUMPROC(cb), 0)
    return res


def ventanas_app(pid):
    res = []

    def cb(hh, lp):
        if user32.IsWindowVisible(hh) and pid_de(hh) == pid:
            res.append(hh)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def capturar_lista_abierta():
    """Lee COMPLETA la lista de un cuadro «Busca …» abierto en el sistema (solo lee, no escribe nada).
    Devuelve (tipo, titulo, [(codigo, descripcion)]) con tipo «infracciones», «oficinas» o ''; None si no hay cuadro."""
    cuadros = []

    def cb(hh, lp):
        if user32.IsWindowVisible(hh) and "busca" in leer(hh).lower():
            cuadros.append(hh)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    for w in cuadros:
        lb = next((h for h in hijos(w) if clase(h) == "ThunderRT6ListBox"), 0)
        if not lb:
            continue
        n = _smto(lb, 0x018B, 0, 0, 500)           # LB_GETCOUNT
        if not n or n > 200000:
            continue
        filas = []
        for i in range(n):
            ln = _smto(lb, 0x018A, i, 0, 500) or 0
            buf = ctypes.create_unicode_buffer(ln + 2)
            _smto(lb, 0x0189, i, ctypes.addressof(buf), 500)
            m = re.match(r"^\s*(\S+)\s+(.*?)\s*$", buf.value.replace("\t", "  "))
            if m:
                filas.append((m.group(1), m.group(2)))
        t = leer(w)
        tl = t.lower()
        tipo = "infracciones" if "infrac" in tl else ("oficina" in tl and "oficinas" or "")
        return tipo, t, filas
    return None


def foco_actual():
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus or info.hwndActive


def ctl_de(h):
    """Si es el Edit interno de un combo, devuelve el combo."""
    if h and clase(h) == "Edit":
        p = user32.GetParent(h)
        if p and clase(p).startswith("ThunderRT6"):
            return p
    return h


def foco_ctl():
    h = ctl_de(foco_actual())
    if not h:
        return None
    return Ctl(h, user32.GetDlgCtrlID(h), clase(h), rect(h))


def dar_foco(h):
    tid_app = user32.GetWindowThreadProcessId(h, None)
    tid_yo = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(tid_yo, tid_app, True)
    try:
        user32.SetFocus(h)
    finally:
        user32.AttachThreadInput(tid_yo, tid_app, False)


def leer_lista(lb):
    """Elementos de un ListBox (LB_GETCOUNT / LB_GETTEXT)."""
    n = _smto(lb, 0x018B, 0, 0, 300)
    if n is None or n > 100000:
        return []
    items = []
    for i in range(min(n, 60)):
        ln = _smto(lb, 0x018A, i, 0, 300) or 0
        if ln > 1000:
            ln = 0
        buf = ctypes.create_unicode_buffer(ln + 2)
        _smto(lb, 0x0189, i, ctypes.addressof(buf), 300)
        items.append(buf.value)
    if not items and n:
        items = [""] * n
    return items


# --- Teclas de control (ESC, F9, F8) ---
_prev = {}


def borde(vk):
    down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
    antes = _prev.get(vk, down)
    _prev[vk] = down
    return down and not antes


def revisar_teclas():
    if PARAR.is_set():
        raise Detener("Detenido desde la interfaz.")
    if borde(VK_ESC):
        raise Detener("Detenido con ESC.")
    if borde(VK_F9):
        print("PAUSADO. F9 para continuar, ESC para detener.")
        while True:
            time.sleep(0.1)
            if PARAR.is_set() or borde(VK_ESC):
                raise Detener("Detenido con ESC.")
            if borde(VK_F9):
                print("Continuando.")
                return


def pausa(seg):
    fin = time.time() + seg
    while time.time() < fin:
        revisar_teclas()
        time.sleep(max(0.0, min(0.05, fin - time.time())))


# ============================= EL SISTEMA ================================
class Sistema:
    def __init__(self):
        self.main = self.form = self.pid = 0
        self.todos = set()
        self.ids = {}
        self.base_ventanas = set()
        self.p = {}
        self.hechos = set()
        self.rut_hecho = False
        self.auto_calculado = False
        self.autocompletado = False
        self.avisos = []
        self.veh_existente = False
        self.rol_usado = ""

    def activar(self):
        """Trae el sistema al primer plano (la interfaz lo necesita al partir)."""
        try:
            user32.SetForegroundWindow(self.main)
        except Exception:
            pass
        pausa(0.4)

    # ---- conexion ----
    def conectar(self):
        avisado = False
        while True:
            revisar_teclas()
            main = user32.FindWindowW("ThunderRT6MDIForm", None)
            form = 0
            if main:
                for h in hijos(main):
                    if clase(h) == "ThunderRT6FormDC" and leer(h).strip().startswith(TITULO_VENTANA):
                        form = h
                        break
            if main and form:
                break
            if not avisado:
                print(f"Esperando la pantalla '{TITULO_VENTANA}...' (abrela en el sistema)...")
                avisado = True
            pausa(0.5)
        self.main, self.form, self.pid = main, form, pid_de(main)
        todos = hijos(form)
        ocultos = set()
        self.paneles = [h for h in todos if clase(h) == "ThunderRT6UserControlDC"]
        for h in todos:
            if clase(h) == "ThunderRT6UserControlDC":
                ocultos.update(hijos(h))      # panel oculto: repite los IDs del formulario
        self.todos = set(todos) - ocultos
        self.permitidos = set(todos)
        self.ids = {}
        for h in self.todos:
            i = user32.GetDlgCtrlID(h)
            if i and clase(h).startswith("ThunderRT6"):
                self.ids.setdefault(i, h)

    def leer_id(self, i):
        h = self.ids.get(i)
        return leer(h) if h else ""

    def rect_id(self, i):
        h = self.ids.get(i)
        return rect(h) if h else None

    def formulario_vacio(self):
        return all(not self.leer_id(i).strip() for i in (14, 10, 159, 190, 189))

    def aceptar(self):
        """Presiona el Aceptar del formulario (id 40) con un clic enviado al boton. Solo en modo automatico."""
        h = self.ids.get(40)
        if not h or not user32.IsWindowEnabled(h) or not user32.IsWindowVisible(h) or rect(h)[0] <= -900:
            raise Detener("El boton Aceptar no esta disponible (ficha abierta u otra ventana encima). "
                          "Acepta tu el parte.")
        l, t, r, b = rect(h)
        lp = ((b - t) // 2 << 16) | ((r - l) // 2)
        self.asegurar_primer_plano()
        user32.PostMessageW(h, 0x0201, 1, lp)      # WM_LBUTTONDOWN
        time.sleep(0.08)
        user32.PostMessageW(h, 0x0202, 0, lp)      # WM_LBUTTONUP
        print("  [auto] Aceptar presionado.")

    def esperar_vacio(self, mensaje, vigilar=False):
        avisado = False
        t_ini = time.time()
        while True:
            revisar_teclas()
            if not user32.IsWindow(self.form):
                self.conectar()
            if vigilar:
                self.chequear_avisos()          # ej. folio repetido: se detiene sin tocar nada
                if time.time() - t_ini > 20 and not self.formulario_vacio():
                    raise Detener("Presione Aceptar pero el formulario no se vacio.")
            if self.formulario_vacio():
                return
            if not avisado:
                print(mensaje)
                avisado = True
            if borde(VK_F8) or SALTAR.is_set():
                SALTAR.clear()
                print("Continuando sin esperar.")
                return
            time.sleep(0.25)

    # ---- estado de la pantalla ----
    def primer_plano(self):
        fg = user32.GetForegroundWindow()
        return bool(fg) and pid_de(user32.GetAncestor(fg, 2)) == self.pid

    def asegurar_primer_plano(self):
        t0, avisado = time.time(), False
        while not self.primer_plano():
            if not avisado:
                print("Pausado: la ventana del sistema no esta en primer plano. Haz clic en ella para seguir.")
                avisado = True
            revisar_teclas()
            time.sleep(0.2)
            if time.time() - t0 > T_MANUAL:
                raise Detener("La ventana del sistema no volvio al primer plano.")

    def transitorio(self, c):
        return c.rect[0] <= -1000 or not user32.IsWindowVisible(c.hwnd)

    def chequear_avisos(self):
        for w in ventanas_app(self.pid):
            if w == self.main or w in self.base_ventanas or clase(w) in IGNORAR:
                continue
            cw = clase(w)
            # Solo cuentan como aviso los cuadros de dialogo y formularios; las listas desplegables de
            # los combos y otras ventanas auxiliares sin contenido se ignoran.
            if not (cw == "#32770" or cw.startswith("ThunderRT6Form")):
                continue
            l, t, r, b = rect(w)
            if r - l <= 2 or b - t <= 2 or l <= -900:
                continue
            titulo = leer(w)
            if "Busca" in titulo or (clase(w).startswith("ThunderRT6Form") and
                                     any(clase(h) == "ThunderRT6ListBox" for h in hijos(w))):
                continue
            textos = [leer(hh).strip() for hh in hijos(w)]
            textos = [x for x in textos if x]
            plano = limpiar(" ".join(textos)).lower()
            if "existente" in plano and "cargar" in plano:
                if self.responder_si(w):
                    return
            raise Detener(f"El sistema mostro una ventana ({titulo!r}): " + " | ".join(textos[:8]) +
                          "\n  No la toque: leela y resuelvela tu.")

    def ficha_visible(self):
        for h in getattr(self, "paneles", []):
            if user32.IsWindow(h) and user32.IsWindowVisible(h) and rect(h)[0] > -900:
                return True
        return False

    def chequear_ficha(self):
        """RUT nuevo: el sistema abre la ficha de la persona (panel 'R.U.T.'). La completas tu."""
        if not self.ficha_visible():
            return False
        try:
            self.llenar_ficha()
        except Detener as e:
            if PARAR.is_set() or "ESC" in str(e):
                raise
            print(f"  [aviso] No pude completar toda la ficha ({e}). Termina tu.")
        print("  [tu turno] Revisa la ficha de la persona y presiona su Aceptar; sigo solo cuando se cierre.")
        t0 = time.time()
        while self.ficha_visible():
            revisar_teclas()
            if time.time() - t0 > T_MANUAL:
                raise Detener("La ficha de la persona sigue abierta.")
            time.sleep(0.2)
        pausa(0.6)
        self.auto_calculado = False        # se vuelve a leer si nombre/direccion quedaron completos
        self.recuperar_foco(tipo_si_falla=False)
        print("  [info] Ficha de la persona cerrada: continuo.")
        return True

    def _campos_ficha(self, panel):
        """Los 7 campos de la ficha en orden: paterno, materno, nombres, comuna, calle, numero, aclaracion.
        Primero por ID (medido en la grabacion); si la posicion en pantalla no cuadra, por posicion."""
        todos = [h for h in hijos(panel) if clase(h) in ("ThunderRT6TextBox", "ThunderRT6ComboBox")
                 and user32.IsWindowVisible(h) and rect(h)[0] > -900]
        por_id = {user32.GetDlgCtrlID(h): h for h in todos}
        orden = (22, 25, 23, 17, 24, 30, 29)
        if all(i in por_id for i in orden):
            r = {i: rect(por_id[i]) for i in orden}
            ok = (abs(r[22][1] - r[25][1]) < 8 and abs(r[25][1] - r[23][1]) < 8
                  and r[22][0] < r[25][0] < r[23][0] and r[17][1] > r[22][1] and r[24][1] > r[17][1]
                  and abs(r[30][1] - r[24][1]) < 8 and r[30][0] > r[24][0] and r[29][1] > r[24][1])
            if ok:
                return [por_id[i] for i in orden]
        cs = sorted((round(rect(h)[1] / 12), rect(h)[0], h) for h in todos
                    if user32.IsWindowEnabled(h) and rect(h)[2] - rect(h)[0] > 20)
        rut_p = re.sub(r"\D", "", self.p["rut"])
        cs = [x for x in cs if re.sub(r"\D", "", leer(x[2])) != rut_p]   # quita el campo del RUT
        if len(cs) < 7:
            raise Detener(f"la ficha tiene {len(cs)} campos reconocibles (se esperaban 7 o mas)")
        return [x[2] for x in cs[:7]]

    def llenar_ficha(self):
        """Ficha de persona nueva: Ap. paterno, Ap. materno, Nombres, (Comuna), Calle, Numero, Aclaracion."""
        panel = next(h for h in self.paneles if user32.IsWindow(h) and user32.IsWindowVisible(h)
                     and rect(h)[0] > -900)
        pausa(0.5)
        hs = self._campos_ficha(panel)
        pat, mat, nom = split_nombre(self.p["nombre"])
        calle, num, resto = split_direccion(self.p["direccion"])
        # orden: paterno, materno, nombres | comuna | calle, numero | aclaracion
        plan = [(hs[0], pat, "Apellido paterno"), (hs[1], mat, "Apellido materno"),
                (hs[2], nom, "Nombres"), (hs[3], comuna_sistema(self.p["comuna"]), "Comuna"),
                (hs[4], calle, "Calle"), (hs[5], num, "Numero"), (hs[6], resto, "Aclaracion de direccion")]
        for h, valor, etiqueta in plan:
            if not valor:
                continue
            if etiqueta == "Comuna" and igual(leer(h), valor):
                continue
            c = foco_ctl()
            if c is None or c.hwnd != h:
                dar_foco(h)
                pausa(0.25)
            ctl = Ctl(h, user32.GetDlgCtrlID(h), clase(h), rect(h))
            self.escribir(ctl, [valor], f"Ficha: {etiqueta}", verificar=(etiqueta != "Comuna"))
            self.enter()
            pausa(0.2)

    def responder_si(self, w):
        """'Vehiculo existente, desea cargar los datos?' -> boton Si (no es el Aceptar del formulario)."""
        for hh in hijos(w):
            if limpiar(leer(hh)).replace("&", "").strip().lower() == "si":
                _smto(hh, 0x00F5, 0, 0, 800)          # BM_CLICK
                t0 = time.time()
                while user32.IsWindow(w) and user32.IsWindowVisible(w) and time.time() - t0 < 3:
                    time.sleep(0.05)
                self.veh_existente = True
                print("  [info] Vehiculo existente: se cargaron sus datos (Si).")
                self.recuperar_foco()
                return True
        return False

    def recuperar_foco(self, tipo_si_falla=True):
        """Tras cerrar un cuadro, el foco puede quedar en la ventana principal: lo devuelve al formulario."""
        pausa(0.7)      # deja que el sistema termine de procesar la respuesta
        t0 = time.time()
        while time.time() - t0 < 2.0:
            c = foco_ctl()
            if c is not None and c.hwnd in self.todos:
                return
            if time.time() - t0 > 0.4:
                try:
                    user32.SetForegroundWindow(self.main)
                except Exception:
                    pass
            time.sleep(0.1)
        # sigue en la ventana principal: el campo que sigue a la placa es el tipo de vehiculo
        h = self.ids.get(95)
        if h and tipo_si_falla:
            dar_foco(h)
            pausa(0.2)

    def foco_estable(self, cond=lambda c: True, timeout=T_FOCO, que="el cursor", estable=0.15):
        t0, ult, desde = time.time(), None, 0.0
        while True:
            revisar_teclas()
            if not self.primer_plano():
                self.asegurar_primer_plano()
                t0, ult = time.time(), None
            if self.chequear_ficha():
                t0, ult = time.time(), None
            self.chequear_avisos()
            c = foco_ctl()
            if c is not None and not self.transitorio(c) and cond(c):
                if ult == c.hwnd:
                    if time.time() - desde >= estable:
                        return c
                else:
                    ult, desde = c.hwnd, time.time()
            else:
                ult = None
            if time.time() - t0 > timeout:
                raise Detener(f"Se agoto el tiempo esperando {que}.")
            time.sleep(0.03)

    # ---- teclado seguro ----
    def _seguro(self):
        self.asegurar_primer_plano()
        c = foco_ctl()
        if c is None:
            raise Detener("No detecto donde esta el cursor.")
        if c.clase in BOTONES:
            raise Detener(f"Por seguridad no tecleo sobre un boton (id={c.id}).")
        if c.hwnd not in self.permitidos and c.clase != "ThunderRT6ListBox":
            raise Detener(f"El cursor esta fuera del formulario (clase {c.clase}).")
        return c

    def teclear(self, texto):
        self._seguro()
        send_keys(esc_keys(texto), pause=PAUSA_TECLA, with_spaces=True)

    def tecla(self, k):
        self._seguro()
        send_keys(k, pause=PAUSA_TECLA)

    def enter(self):
        self.tecla("{ENTER}")

    def avanzar(self, ctl, desc="", timeout=T_FOCO):
        self.enter()
        return self.foco_estable(lambda c: c.hwnd != ctl.hwnd, timeout,
                                 f"que el cursor salga de {desc or ctl.id}")

    def escribir(self, ctl, variantes, etiqueta, modo="texto", limpiar_antes=True, verificar=True):
        esperado, visto, vistos = variantes[0], "", []
        for v in variantes:
            if limpiar_antes:
                self.tecla("{HOME}+({END}){DEL}")
            self.teclear(v)
            pausa(0.12)
            if not verificar:
                break
            visto = leer(ctl.hwnd)
            vistos.append(visto)
            if igual(visto, esperado, modo):
                break
            vs = visto.strip()
            if modo == "texto" and len(vs) >= 5 and norm(esperado).startswith(norm(vs)):
                self.avisos.append(f"{etiqueta}: el campo recorto el texto ({len(vs)} caracteres).")
                break
        else:
            raise Detener(f"En '{etiqueta}' escribi {esperado!r} pero el campo muestra {visto!r}. "
                          f"(intentos: {vistos}, id={ctl.id}, clase={ctl.clase}, rect={ctl.rect})")
        print(f"  [ok] {etiqueta}")

    def esperar_manual(self, ctl, que):
        print(f"  [tu turno] {que}. Cuando presiones Enter y el cursor avance, sigo solo.")
        return self.foco_estable(lambda c: c.hwnd != ctl.hwnd, T_MANUAL, que)

    # ---- grillas ----
    def escribir_en_grilla(self, texto, id_overlay, etiqueta):
        self._seguro()
        send_keys(esc_keys(texto[0]), pause=PAUSA_TECLA, with_spaces=True)
        ov = self.foco_estable(lambda c: c.id == id_overlay and c.hwnd in self.todos, 3.0,
                               f"la caja de edicion de {etiqueta}")
        if len(texto) > 1:
            self.teclear(texto[1:])
        pausa(0.12)
        visto = leer(ov.hwnd)
        if not igual(visto, texto):
            raise Detener(f"En '{etiqueta}' escribi {texto!r} pero la caja muestra {visto!r}.")
        print(f"  [ok] {etiqueta}")
        return ov

    # ---- clasificacion del campo con el cursor ----
    def clasificar(self, c):
        if c.clase == "MSFlexGridWndClass":
            return "grilla_inf" if self.rut_hecho else "grilla_bol"
        if c.clase == "MSMaskWndClass":
            r = self.rect_id(159)
            if r is None:
                return "desconocido"
            return "hora" if c.rect[1] < r[1] else "placa"
        if c.hwnd in self.todos and c.id in CAMPOS:
            return CAMPOS[c.id]
        return "desconocido"

    def ir_a_infracciones(self):
        """Lleva el cursor a la grilla de Infracciones (habilitada, bajo los datos del vehiculo)."""
        r99 = self.rect_id(99)
        limite = r99[3] - 5 if r99 else 0
        for h in self.todos:
            if clase(h) == "MSFlexGridWndClass" and user32.IsWindowEnabled(h):
                r = rect(h)
                if r[0] > -900 and r[1] >= limite and r[2] - r[0] > 300:
                    dar_foco(h)
                    pausa(0.2)
                    return True
        return False

    def poner_foco_en(self, i):
        h = self.ids.get(i)
        if not h:
            raise Detener(f"No encuentro el campo id={i} en la pantalla.")
        self.asegurar_primer_plano()
        dar_foco(h)
        return self.foco_estable(lambda c: c.hwnd == h, 3.0,
                                 "que el cursor llegue a Oficina Emisora (haz clic en la ventana 'Procesos' y reintenta)")

    def esperar_inicio(self):
        """Parte desde donde esta el cursor (Rol u Oficina). Si no esta en el formulario, espera."""
        avisado = False
        while True:
            revisar_teclas()
            c = foco_ctl()
            if c and c.hwnd in self.todos and self.clasificar(c) in ("rol", "oficina"):
                return
            if not avisado:
                print("  Pon el cursor en el campo Rol (haz clic en el formulario 'Procesos'); sigo solo.")
                avisado = True
            time.sleep(0.2)

    # ---- manejadores por campo ----
    def h_rol(self, ctl, p):
        self.avanzar(ctl, "Rol")                  # no se escribe nada: solo Enter

    def h_oficina(self, ctl, p):
        txt = oficina_texto(p["oficina"])
        if not txt:
            self.esperar_manual(ctl, "Escribe una parte reconocible de la Oficina Emisora")
            return
        self.escribir(ctl, [txt], "Oficina Emisora", verificar=False)
        self.enter()
        t0, w = time.time(), 0
        while time.time() - t0 < 2.0:
            revisar_teclas()
            w = self.ventana_busca()
            if w:
                break
            time.sleep(0.05)
        if w:
            self.resolver_busca(w, txt, primero=True)
        self.foco_estable(lambda c: c.hwnd != ctl.hwnd, T_FOCO, "que el cursor salga de Oficina Emisora")
        largo = leer(self.ids[15]).strip()
        esperado = oficina_esperada(txt, p["oficina"])
        if not re.search(r"[A-Za-z]{3}", largo) or igual(largo, txt):
            raise Detener(f"La Oficina Emisora quedo como {largo!r}: no se selecciono ninguna. "
                          "Elige la oficina tu y retoma con --desde.")
        if esperado and esperado not in norm(largo) and norm(largo) not in esperado:
            raise Detener(f"La Oficina Emisora quedo como {largo!r}, y se esperaba algo con '{esperado}'.")
        print(f"  [info] Oficina: {largo}")

    def h_fecha_ingreso(self, ctl, p):
        self.avanzar(ctl, "Fecha Ingreso")        # viene con la fecha de hoy

    def h_n_parte(self, ctl, p):
        self.escribir(ctl, [p["n_parte"]], "N Parte")
        self.avanzar(ctl, "N Parte")

    def h_fecha_parte(self, ctl, p):
        f = fecha(p["fecha_parte"])
        self.escribir(ctl, [f, f.replace("/", "")], "Fecha Parte")
        self.avanzar(ctl, "Fecha Parte")

    def h_grilla_bol(self, ctl, p):
        actual = ctl
        if p["boleta"]:
            actual = self.escribir_en_grilla(p["boleta"], ID_OVERLAY_BOL, "Bol/N.Parte")
        for _ in range(12):
            self.enter()
            nuevo = self.foco_estable(lambda c, a=actual: c.hwnd != a.hwnd, T_FOCO,
                                      "el avance de la grilla Bol/N.Parte")
            if nuevo.clase != "MSFlexGridWndClass" and not (nuevo.id == ID_OVERLAY_BOL and nuevo.hwnd in self.todos):
                return
            actual = nuevo
        raise Detener("La grilla Bol/N.Parte no termino de recorrerse (12 Enter).")

    def h_descripcion(self, ctl, p):
        if p["descripcion"]:
            self.escribir(ctl, [p["descripcion"]], "Descripcion")
        self.avanzar(ctl, "Descripcion")

    def actuario_del_rol(self):
        rol = re.sub(r"\D", "", self.leer_id(11))
        return rol, ROL_ACTUARIO.get(rol[-1:], "")

    def h_actuario(self, ctl, p):
        rol, auto = self.actuario_del_rol()
        self.rol_usado = rol
        quien = limpiar(ACTUARIO) or auto
        cod = ACTUARIOS.get(quien.upper(), quien if quien.isdigit() else "")
        if cod:
            self.escribir(ctl, [cod], "Actuario", verificar=False)
            self.avanzar(ctl, "Actuario")
            nom = leer(ctl.hwnd).strip()
            if not nom or nom == cod:
                raise Detener(f"El Actuario no quedo seleccionado (el campo muestra {nom!r}).")
            self.rol_usado = rol
            print(f"  [info] Rol {rol}: Actuario {nom}")
        else:
            self.esperar_manual(ctl, f"Elige el Actuario (el Rol {rol} termina en {rol[-1:] or '?'}, "
                                     "sin actuario definido en ROL_ACTUARIO)")

    def h_fecha_citacion(self, ctl, p):
        f = fecha(p["fecha_citacion"])
        if f:
            self.escribir(ctl, [f, f.replace("/", "")], "Fecha citacion")
        self.avanzar(ctl, "Fecha citacion")

    def h_hora_citacion(self, ctl, p):
        self.avanzar(ctl, "Hora citacion")          # se deja la hora que trae el sistema

    def h_lugar(self, ctl, p):
        if p["lugar"]:
            self.escribir(ctl, [p["lugar"]], "Lugar")
        self.avanzar(ctl, "Lugar")

    def h_hora(self, ctl, p):
        h = hora(p["hora"])
        if h:
            self.escribir(ctl, [h, h, h], "Hora", modo="digitos", limpiar_antes=True)
        self.avanzar(ctl, "Hora")

    def h_rut(self, ctl, p):
        r, _ = rut(p["rut"])
        self.rut_hecho = True
        if not r and not str(p["rut"] or "").strip():
            print("  [ok] RUT vacio (parte sin RUT): Enter")
            self.avanzar(ctl, "RUT", timeout=T_RUT)
            return
        if not r:
            self.esperar_manual(ctl, f"El RUT {p['rut']!r} no es valido: ingresalo tu y presiona Enter")
            return
        self.escribir(ctl, [r], "RUT", verificar=False)
        print("  [ok] RUT (esperando al sistema...)")
        self.avanzar(ctl, "RUT", timeout=T_RUT)

    def _calc_auto(self):
        if not self.auto_calculado:
            self.autocompletado = bool(self.leer_id(138).strip()) and bool(self.leer_id(137).strip())
            self.auto_calculado = True
            if self.autocompletado:
                print("  [info] El sistema reconocio el RUT y completo nombre y direccion.")
                sis, par = norm(limpiar(self.leer_id(138))), norm(self.p["nombre"])
                if par and sis != par:
                    self.avisos.append(f"El sistema tiene el RUT a nombre de '{self.leer_id(138).strip()}' "
                                       f"y el parte dice '{self.p['nombre']}'. Revisalo.")
            else:
                print("  [info] RUT nuevo: tecleo nombre y direccion.")

    def h_nombre(self, ctl, p):
        self._calc_auto()
        if not self.autocompletado:
            if p["nombre"]:
                self.escribir(ctl, [p["nombre"]], "Nombre")
            else:
                self.esperar_manual(ctl, "Escribe el Nombre")
                return
        self.avanzar(ctl, "Nombre")

    def h_direccion(self, ctl, p):
        self._calc_auto()
        if not self.autocompletado:
            self.escribir(ctl, [p["direccion"] or "SIN DIRECCION"], "Direccion")
        self.avanzar(ctl, "Direccion")

    def h_comuna(self, ctl, p):
        self._calc_auto()
        if not self.autocompletado and p["comuna"]:
            self.escribir(ctl, [p["comuna"]], "Comuna", verificar=False)
        self.avanzar(ctl, "Comuna")

    def h_placa(self, ctl, p):
        pl = placa(p["placa"])
        if pl:
            self.escribir(ctl, [pl, pl, pl], "Placa", modo="alnum", limpiar_antes=True)
        self.avanzar(ctl, "Placa")

    def rol_veh(self, ctl):
        """Tipo / color / rut propietario (fila 1, de izquierda a derecha) y anio / marca (fila 2)."""
        rs = [(self.rect_id(i), self.ids[i]) for i in (95, 93, 98, 92, 99) if i in self.ids]
        rs = [(r, h) for r, h in rs if r]
        if len(rs) < 5:
            return "otro"
        rs.sort(key=lambda x: x[0][1])
        fila1 = sorted([x for x in rs if abs(x[0][1] - rs[0][0][1]) < 12], key=lambda x: x[0][0])
        fila2 = sorted([x for x in rs if x not in fila1], key=lambda x: x[0][0])
        if len(fila1) != 3 or len(fila2) != 2:
            return "otro"
        nombres = dict(zip([h for _, h in fila1], ["tipo", "color", "rut_prop"]))
        nombres.update(dict(zip([h for _, h in fila2], ["anio", "marca"])))
        return nombres.get(ctl.hwnd, "otro")

    def h_veh(self, ctl, p):
        rol = self.rol_veh(ctl)
        if self.veh_existente:
            self.avanzar(ctl, f"campo de vehiculo ({rol}, datos ya cargados)")
            return
        if rol == "tipo" and p["tipo_vehiculo"]:
            self.escribir(ctl, [p["tipo_vehiculo"]], "Tipo de vehiculo", verificar=(ctl.clase != "ThunderRT6ComboBox"))
        elif rol == "marca" and p["marca"]:
            self.escribir(ctl, [p["marca"]], "Marca", verificar=(ctl.clase != "ThunderRT6ComboBox"))
        elif rol == "otro":
            self.avisos.append(f"Campo de vehiculo no identificado (id {ctl.id}); se paso con Enter.")
        self.avanzar(ctl, f"campo de vehiculo ({rol})")

    def ventana_busca(self):
        """Ventana de seleccion (lista) abierta por el sistema: 'Busca ...' o cualquier formulario nuevo con lista."""
        for w in ventanas_app(self.pid):
            if w == self.main or clase(w) in IGNORAR:
                continue
            if "Busca" in leer(w):
                return w
            if w not in self.base_ventanas and clase(w).startswith("ThunderRT6Form") and \
                    any(clase(h) == "ThunderRT6ListBox" for h in hijos(w)):
                return w
        return 0

    def resolver_busca(self, w, buscado, primero=False):
        pausa(0.3)
        lb = next((h for h in hijos(w) if clase(h) == "ThunderRT6ListBox"), 0)
        items = leer_lista(lb) if lb else []
        if not items and primero:
            items = ["(lista no legible)"]
        if not items:
            raise Detener(f"La busqueda no devolvio resultados para {buscado!r}.")
        if lb:
            c = foco_ctl()
            if c is None or c.hwnd != lb:
                dar_foco(lb)
                pausa(0.2)
        if len(items) > 1 and primero:
            self.avisos.append(f"La busqueda de {buscado!r} dio {len(items)} resultados; se acepto el primero "
                               f"({items[0].strip()!r}). Revisalo.")
        if len(items) == 1 or primero:
            print(f"  [ok] Busqueda: {len(items)} resultado(s); acepto {items[0].strip()!r}")
            self.enter()
        else:
            print(f"  [tu turno] La busqueda devolvio {len(items)} resultados; elige y confirma tu:")
            for it in items[:10]:
                print("     -", it.strip())
        t0 = time.time()
        while self.ventana_busca():
            revisar_teclas()
            if time.time() - t0 > (T_MANUAL if len(items) > 1 else 5.0):
                raise Detener("La ventana de busqueda no se cerro.")
            time.sleep(0.1)

    def h_grilla_inf(self, ctl, p):
        infs = p["infracciones"]
        if not infs:
            return True
        if len(infs) > 1:
            self.avisos.append(f"Hay {len(infs)} infracciones; solo tecleo la primera. Agrega las demas tu.")
        # La grilla parte en la columna Fecha: Enter abre su caja, otro Enter la acepta y pasa a Descripcion.
        self.enter()
        self.foco_estable(lambda c: c.id == ID_OVERLAY_INF and c.hwnd in self.todos, 3.0,
                          "la caja de la columna Fecha de Infracciones")
        self.enter()
        self.foco_estable(lambda c: c.clase == "MSFlexGridWndClass", 3.0,
                          "que el cursor pase a la columna Descripcion")
        cod, desc, _ = resolver_infraccion(infs[0])
        if desc:
            print(f"  [info] Infraccion {cod}: {desc}")
        self.escribir_en_grilla(cod, ID_OVERLAY_INF, "Infraccion")
        self.enter()
        t0, w = time.time(), 0
        while time.time() - t0 < 2.5:
            revisar_teclas()
            w = self.ventana_busca()
            if w:
                break
            time.sleep(0.05)
        if not w:
            self.foco_estable(lambda c: c.clase == "MSFlexGridWndClass", 4.0, "que vuelva el cursor a la grilla")
            return True
        self.resolver_busca(w, infs[0])
        self.foco_estable(lambda c: c.clase == "MSFlexGridWndClass", 4.0, "que vuelva el cursor a la grilla")
        return True

    # ---- un parte completo ----
    def teclear_parte(self, p):
        self.p = p
        self.hechos, self.avisos = set(), []
        self.rut_hecho = self.auto_calculado = self.autocompletado = False
        self.veh_existente = False
        self._saltos = 0
        self.base_ventanas = set(ventanas_app(self.pid))
        self.rol_usado = ""
        self.activar()
        self.esperar_inicio()
        while True:
            c = self.foco_estable()
            if self.veh_existente and c.hwnd not in self.todos and \
                    c.clase in ("ThunderRT6MDIForm", "ThunderRT6FormDC"):
                # tras 'Vehiculo existente' el foco queda en la ventana principal: se va a la infraccion
                saltos = getattr(self, "_saltos", 0) + 1
                self._saltos = saltos
                if saltos > 3 or not self.ir_a_infracciones():
                    raise Detener("No logro llevar el cursor a la grilla de Infracciones; sigue tu a mano.")
                continue
            nombre = self.clasificar(c)
            if c.hwnd in self.hechos:
                raise Detener(f"El cursor volvio a un campo ya completado (id={c.id}, {nombre}). "
                              "Algo no salio como se esperaba.")
            h = getattr(self, "h_" + nombre, None)
            if h is None:
                raise Detener(f"Campo no reconocido (id={c.id}, clase={c.clase}). "
                              "Probablemente falta grabarlo; completa el resto a mano.")
            self.hechos.add(c.hwnd)
            if h(c, p) is True:
                return


# ================================ MAIN ===================================
def ruta_por_defecto():
    """El partes-para-tecleo*.json mas reciente de Descargas (los nombres llevan fecha y hora)."""
    hallados = []
    for carpeta in ("Downloads", "Descargas"):
        d = Path.home() / carpeta
        if d.is_dir():
            hallados += [f for f in d.glob("partes-para-tecleo*.json") if not f.name.endswith(".estado.json")]
    if hallados:
        return max(hallados, key=lambda f: f.stat().st_mtime)
    return Path.home() / "Downloads" / "partes-para-tecleo.json"


def correr(args):
    global ACTUARIO
    if args.actuario:
        ACTUARIO = args.actuario
    if ACTUARIO and limpiar(ACTUARIO).upper() not in ACTUARIOS and not limpiar(ACTUARIO).isdigit():
        raise Detener(f"Actuario desconocido: {ACTUARIO!r}")
    ruta = Path(args.archivo) if args.archivo else ruta_por_defecto()
    if not ruta.exists():
        raise Detener(f"No encuentro el archivo de datos: {ruta}")
    partes = cargar_partes(ruta)
    if not partes:
        raise Detener("El archivo no trae partes.")
    for q in partes:
        if args.tipo:
            q["tipo_vehiculo"] = limpiar(args.tipo)
        if args.marca:
            q["marca"] = limpiar(args.marca)
    n = len(partes)
    print(f"{n} partes en {ruta}")
    indices = list(range(args.desde - 1, n))
    if args.solo:
        indices = [args.solo - 1]
    hay_fatal = False
    for i in indices:
        fat, avi = validar_parte(partes[i])
        if args.ensayo or fat or avi:
            mostrar_plan(i + 1, n, partes[i], fat, avi)
        hay_fatal = hay_fatal or bool(fat)
    if args.ensayo:
        print("\nEnsayo terminado: no se toco el sistema.")
        return
    if hay_fatal:
        raise Detener("Hay partes con errores graves; corrige los datos y reintenta.")
    if not WIN or send_keys is None:
        raise Detener("Este programa corre en Windows y requiere pywinauto (pip install pywinauto).")

    sis = Sistema()
    print("\nESC = detener   F9 = pausar/reanudar.   No toques el teclado ni el mouse mientras teclea.")
    procesar_lote(sis, partes, indices, aceptar_auto=args.aceptar)


def procesar_lote(sis, partes, indices, on_estado=None, aceptar_auto=False):
    """Teclea los partes indicados uno tras otro. on_estado(i, estado, detalle) informa el avance
    (estados: tecleando, tecleado, ingresado, interrumpido)."""
    def avisar(i, estado, detalle=""):
        if on_estado:
            on_estado(i, estado, detalle)

    n = len(partes)
    for k, i in enumerate(indices):
        p = partes[i]
        print(f"\n=== Parte {i + 1}/{n}: N {p['n_parte']} ===")
        try:
            sis.conectar()
            if k == 0:
                sis.esperar_vacio("El formulario no esta vacio: acepta o cancela el parte actual para empezar.")
            for s in range(int(ESPERA_INICIO), 0, -1):
                print(f"  Empiezo en {s}... (ESC cancela)", end="\r", flush=True)
                pausa(1)
            print(" " * 40, end="\r")
            avisar(i, "tecleando")
            sis.teclear_parte(p)
        except Detener as e:
            avisar(i, "interrumpido", str(e))
            raise
        avisar(i, "tecleado", " | ".join(sis.avisos))
        print(f"\nParte {i + 1} listo. Revisa la pantalla y presiona Aceptar TU (yo no lo hago).")
        for a in sis.avisos:
            print(f"  [revisa] {a}")
        if aceptar_auto and not sis.avisos:
            sis.aceptar()
            sis.esperar_vacio("Esperando que el sistema termine de ingresar el parte...", vigilar=True)
        else:
            if aceptar_auto:
                print("  [auto] Hay avisos en este parte: no lo acepto solo. Revisalo y acepta tu.")
            sis.esperar_vacio("Esperando que aceptes (o canceles) el parte. Cuando el formulario quede vacio "
                              "sigo con el siguiente. F8 = seguir igual.")
        ahora = re.sub(r"\D", "", sis.leer_id(11))
        # Al aceptar, el sistema pasa al Rol siguiente; si el Rol no cambio, el parte se cancelo.
        if sis.rol_usado and ahora and ahora == sis.rol_usado:
            avisar(i, "cancelado")
        else:
            avisar(i, "ingresado")
    print("\nTerminado.")


def main():
    ap = argparse.ArgumentParser(description="Teclea partes en el sistema del Juzgado (contextual).")
    ap.add_argument("archivo", nargs="?", help="partes-para-tecleo.json (por defecto, en Descargas)")
    ap.add_argument("--desde", type=int, default=1, help="empezar desde el parte N (1 = primero)")
    ap.add_argument("--solo", type=int, default=0, help="teclear solo el parte N")
    ap.add_argument("--actuario", default="", help="forzar un actuario (katherine, marilyn, monica, yissel, sandra); normalmente se deduce del Rol")
    ap.add_argument("--tipo", default="", help="forzar el tipo de vehiculo (ej. 'STATION WAGON') en todos los partes")
    ap.add_argument("--marca", default="", help="forzar la marca del vehiculo (ej. HONDA) en todos los partes")
    ap.add_argument("--aceptar", action="store_true",
                    help="presionar Aceptar solo al terminar cada parte (si no hay avisos); por defecto lo haces tu")
    ap.add_argument("--ensayo", action="store_true", help="solo mostrar que se tecleara; no toca el sistema")
    args = ap.parse_args()
    try:
        correr(args)
    except Detener as e:
        print(f"\n[detenido] {e}")
        print("No se hizo clic en nada. Revisa la pantalla; puedes retomar con --desde N.")
    except Exception:
        print("\n[error inesperado]")
        print(traceback.format_exc())
    try:
        input("\nPresiona Enter para cerrar...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
