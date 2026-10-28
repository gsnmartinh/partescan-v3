"""
Grabadora PASIVA del ingreso de un parte.

NO envia teclas, NO hace clic, NO escribe nada. Solo observa mientras TU
ingresas un parte normalmente, y anota:
  - por que campos pasas (por ID de control)
  - que valor quedo en cada campo al salir de el
  - que campos se habilitan / deshabilitan / se llenan solos (RUT, placa, Rol...)
  - que teclas importantes presionas (Enter, Tab, Esc, F1-F11) y donde hacias clic
  - cualquier ventana de aviso que aparezca, con su texto

Uso:
  1. Abre la pantalla de ingreso con el formulario VACIO.
  2. Ejecuta:  python grabadora_ingreso.py
  3. En los 8 s de espera haz clic en el campo "N Parte".
  4. Ingresa UN parte completo como siempre (RUT, placa, infracciones...)
     y haz clic en Aceptar tu mismo.
  5. Para terminar: haz clic en la ventana negra (consola) y presiona Enter,
     o presiona F12. Se guarda grabacion_ingreso.txt.
     La grabacion dura todo lo que tu quieras: los 8 s son solo la espera inicial.

PRIVACIDAD: con MASCARAR = True los valores se anotan solo con su formato
(digitos -> 9, letras -> A), asi el archivo no contiene RUT, nombres ni
direcciones reales. Los textos de ventanas de aviso SI se anotan completos.
"""
import ctypes
import ctypes.wintypes as wt
import faulthandler
import os
import sys
import threading
import time
import traceback
from datetime import datetime

MASCARAR = True
ESPERA = 8
SONDEO = 0.05
CADA_SNAPSHOT = 0.3

CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "grabacion_ingreso.txt")

# Si el programa se cae de forma nativa (sin error de Python), queda registro aqui
_fallos = open(os.path.join(CARPETA, "grabadora_fallo.txt"), "w")
faulthandler.enable(file=_fallos)
parar = threading.Event()

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetDlgCtrlID.argtypes = [wt.HWND]
user32.GetDlgCtrlID.restype = ctypes.c_int
user32.IsWindowEnabled.argtypes = [wt.HWND]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.WindowFromPoint.argtypes = [wt.POINT]
user32.WindowFromPoint.restype = wt.HWND
user32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
                                       wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_size_t

TIPOS = {
    "ThunderRT6TextBox": "Texto",
    "ThunderRT6ComboBox": "Combo",
    "MSMaskWndClass": "Mascara",
    "DTPicker20WndClass": "Fecha",
    "ThunderRT6CheckBox": "Check",
    "ThunderRT6OptionButton": "Opcion",
    "ThunderRT6CommandButton": "Boton",
    "MSFlexGridWndClass": "Grilla",
}
CON_TEXTO = {"Texto", "Combo", "Mascara", "Fecha"}
IGNORAR = {"IME", "MSCTFIME UI", "tooltips_class32", "Shell_TrayWnd"}
TECLAS = {0x0D: "ENTER", 0x09: "TAB", 0x1B: "ESC"}
TECLAS.update({0x70 + i: f"F{i + 1}" for i in range(11)})  # F1..F11
VK_F12 = 0x7B
VK_LBUTTON = 0x01

T0 = time.time()
_f = None
labels = {}
tipos = {}
prev = {}


@ctypes.WINFUNCTYPE(wt.BOOL, wt.DWORD)
def _ctrl(evt):
    """Deja constancia si la ventana negra se cierra o se interrumpe."""
    if _f:
        try:
            log(f"INTERRUMPIDO: evento de consola {evt} (2 = se cerro la ventana negra, 0 = Ctrl+C)")
        except Exception:
            pass
    return False


def log(msg):
    linea = f"[{time.time() - T0:8.2f}s] {msg}"
    if _f:
        _f.write(linea + "\n")
        _f.flush()
    print(linea)


def mask(s):
    return "".join("9" if c.isdigit() else ("A" if c.isalpha() else c) for c in s)


def vis(s):
    return mask(s) if MASCARAR else s


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


def activo(h):
    l, t, r, b = rect(h)
    return bool(user32.IsWindowVisible(h)) and l > -1000 and r > l


def leer(h):
    """Lee el texto de un control de otro proceso (WM_GETTEXT con timeout)."""
    res = ctypes.c_size_t()
    ok = user32.SendMessageTimeoutW(h, 0x000E, 0, 0, 2, 150, ctypes.byref(res))
    if not ok or res.value <= 0:
        return ""
    n = res.value
    buf = ctypes.create_unicode_buffer(n + 1)
    ok = user32.SendMessageTimeoutW(h, 0x000D, n + 1, ctypes.addressof(buf), 2, 150, ctypes.byref(res))
    return buf.value if ok else ""


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


def foco_actual():
    class GTI(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD),
                    ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
                    ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
                    ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND),
                    ("rcCaret", wt.RECT)]
    info = GTI()
    info.cbSize = ctypes.sizeof(GTI)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus or info.hwndActive


def ctl_de(h):
    """Si es el Edit interno de un combo, devuelve el combo."""
    if h and clase(h) == "Edit":
        p = user32.GetParent(h)
        if p and clase(p).startswith("ThunderRT6"):
            return p
    return h


def etiqueta(h):
    if not h:
        return "(nada)"
    return labels.get(h) or f"{clase(h)}[hwnd={h:#x}]"


def estado(h, con_texto=True):
    hab = bool(user32.IsWindowEnabled(h))
    act = activo(h)
    txt = None
    if con_texto and act and tipos.get(h) in CON_TEXTO:
        txt = leer(h)
    return hab, act, txt


def cambio_txt(viejo, nuevo):
    mv, mn = vis(viejo), vis(nuevo)
    if mv != mn:
        return f"{mv!r} -> {mn!r}"
    return f"cambio de valor (mismo formato {mn!r})"


def comparar(h, nuevo, al_salir=False):
    viejo = prev.get(h)
    if viejo is None:
        prev[h] = nuevo
        return
    lab = etiqueta(h)
    if viejo[0] != nuevo[0]:
        log(f"{lab}: {'HABILITADO' if nuevo[0] else 'DESHABILITADO'}")
    if viejo[1] != nuevo[1]:
        log(f"{lab}: {'pasa a estar visible/activo' if nuevo[1] else 'se oculta'}")
    if nuevo[2] is not None and viejo[2] is not None and viejo[2] != nuevo[2]:
        log(f"{lab}: valor {cambio_txt(viejo[2], nuevo[2])}")
    elif al_salir and nuevo[2] and viejo[2] is None:
        # campo que no estaba visible al inicio (p. ej. la caja flotante de una grilla)
        log(f"{lab}: valor {vis(nuevo[2])!r}")
    prev[h] = (nuevo[0], nuevo[1], nuevo[2] if nuevo[2] is not None else viejo[2])


def main():
    global _f
    print(f"Tienes {ESPERA} s: haz clic en el campo 'N Parte' del sistema...")
    for i in range(ESPERA, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    print()

    foco = ctl_de(foco_actual())
    if not foco:
        print("No se detecto ningun control con foco. Intenta de nuevo.")
        return
    top = user32.GetAncestor(foco, 2)
    pid_app = pid_de(top)

    form = None
    h = foco
    while h:
        if clase(h) == "ThunderRT6FormDC":
            form = h
            break
        h = user32.GetParent(h)
    if not form:
        print("El foco no esta dentro de un formulario del sistema. Haz clic en N Parte e intenta de nuevo.")
        return

    _f = open(SALIDA, "w", encoding="utf-8")
    log(f"Grabacion {datetime.now():%Y-%m-%d %H:%M:%S}  MASCARAR={MASCARAR}")
    log(f"Ventana raiz: clase={clase(top)!r}   Formulario: hwnd={form:#x}")

    # Inventario de controles. Se excluye el panel oculto (control de usuario),
    # porque sus controles repiten los IDs del formulario principal.
    ocultos = set()
    for hh in hijos(form):
        if clase(hh) == "ThunderRT6UserControlDC":
            ocultos.update(hijos(hh))
    for hh in hijos(form):
        if hh in ocultos:
            continue
        c = clase(hh)
        if c in TIPOS:
            tipo = TIPOS[c]
            tipos[hh] = tipo
            ident = user32.GetDlgCtrlID(hh)
            lab = f"{tipo}[id={ident}]" if ident else f"{tipo}[hwnd={hh:#x}]"
            if tipo == "Boton":
                lab += f" {leer(hh)!r}"
            labels[hh] = lab
    log(f"{len(labels)} controles inventariados.")

    log("--- ESTADO INICIAL (solo controles visibles) ---")
    for hh, tipo in tipos.items():
        e = estado(hh)
        prev[hh] = e
        if e[1]:
            val = f" valor={vis(e[2])!r}" if e[2] else ""
            log(f"  {labels[hh]} hab={e[0]} rect={rect(hh)}{val}")
    log("--- FIN ESTADO INICIAL. Ingresa el parte; F12 para terminar ---")

    def esperar_enter():
        try:
            input()
        except Exception:
            pass
        parar.set()

    ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl, True)
    print("GRABANDO. Para terminar: haz clic en ESTA ventana negra y presiona Enter (o presiona F12).")
    threading.Thread(target=esperar_enter, daemon=True).start()

    vistos_foco = {}
    est_tecla = {vk: False for vk in TECLAS}
    est_clic = False
    ultimo_foco = foco
    ultimo_snap = 0.0
    ventanas_vistas = set()

    def en_app():
        fg = user32.GetForegroundWindow()
        return bool(fg) and pid_de(user32.GetAncestor(fg, 2)) == pid_app

    log(f"FOCO inicial -> {etiqueta(foco)}")

    while True:
        if parar.is_set() or (user32.GetAsyncKeyState(VK_F12) & 0x8000):
            break

        app = en_app()

        # Teclas
        for vk, nombre in TECLAS.items():
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            if down and not est_tecla[vk] and app:
                log(f"TECLA {nombre}  (foco en {etiqueta(ctl_de(foco_actual()))})")
            est_tecla[vk] = down

        # Clic izquierdo
        down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        if down and not est_clic and app:
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            w = ctl_de(user32.WindowFromPoint(pt))
            log(f"CLIC sobre {etiqueta(w)}")
        est_clic = down

        # Cambio de foco
        if app:
            fh = ctl_de(foco_actual())
            if fh and fh != ultimo_foco:
                if ultimo_foco in tipos:
                    e = estado(ultimo_foco)
                    txt = e[2] if e[2] is not None else vistos_foco.get(ultimo_foco)
                    comparar(ultimo_foco, (e[0], e[1], txt), al_salir=True)
                log(f"FOCO -> {etiqueta(fh)}")
                vistos_foco.pop(fh, None)
                ultimo_foco = fh
            elif ultimo_foco in tipos:
                # recuerda el ultimo valor visto del campo con foco (por si se oculta al salir)
                e = estado(ultimo_foco)
                if e[2] is not None:
                    vistos_foco[ultimo_foco] = e[2]

        # Cambios de estado en los demas controles y ventanas nuevas
        ahora = time.time()
        if ahora - ultimo_snap >= CADA_SNAPSHOT:
            ultimo_snap = ahora
            for hh in tipos:
                if hh == ultimo_foco:
                    comparar(hh, estado(hh, con_texto=False))
                else:
                    comparar(hh, estado(hh))

            actuales = set()
            for w in ventanas_app(pid_app):
                if w == top or clase(w) in IGNORAR:
                    continue
                l, t, r, b = rect(w)
                if r - l <= 2 or b - t <= 2 or l <= -900:
                    continue
                actuales.add(w)
                if w not in ventanas_vistas:
                    log(f"VENTANA NUEVA: clase={clase(w)!r} titulo={leer(w)!r} rect={(l, t, r, b)}")
                    n = 0
                    for hh in hijos(w):
                        txt = leer(hh)
                        if txt and n < 40:
                            log(f"    contenido: {txt!r} (clase {clase(hh)})")
                            n += 1
            for w in ventanas_vistas - actuales:
                log(f"VENTANA CERRADA: hwnd={w:#x}")
            ventanas_vistas = actuales

        time.sleep(SONDEO)

    log("Grabacion terminada (Enter en la consola o F12).")
    _f.close()
    print(f"\nListo. Guardado en: {SALIDA}. Pegalo en el chat.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        print(err)
        try:
            with open(SALIDA, "a", encoding="utf-8") as f:
                f.write("\nERROR:\n" + err)
        except Exception:
            pass
        print("El error quedo guardado en:", SALIDA)
    input("Presiona Enter para cerrar...")
