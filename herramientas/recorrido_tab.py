"""
Recorrido de Tab del sistema del Juzgado.

SOLO mueve el foco con la tecla Tab y anota por donde pasa.
NO escribe texto, NO presiona Enter y NO hace clic.

Uso:
  1. Abre la pantalla de ingreso con el formulario VACIO.
  2. Ejecuta:  python recorrido_tab.py
  3. En los 8 segundos de espera, haz clic dentro del campo "Nº Parte".
  4. No toques nada mientras corre. ESC lo detiene.
  5. Pega recorrido_tab.txt en el chat (y, si puedes, una captura de la ventana).

Requiere:  pip install pywinauto
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
import traceback
from datetime import datetime

CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "recorrido_tab.txt")


def guardar(lineas):
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))


try:
    from pywinauto.controls.hwndwrapper import HwndWrapper
    from pywinauto.keyboard import send_keys
except Exception:
    guardar(["ERROR importando pywinauto (instala con: pip install pywinauto)",
             traceback.format_exc()])
    print("No se pudo importar pywinauto. Instala con:  pip install pywinauto")
    input("Presiona Enter para salir...")
    sys.exit(1)

user32 = ctypes.windll.user32
user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetDlgCtrlID.argtypes = [wt.HWND]
user32.GetDlgCtrlID.restype = ctypes.c_int
user32.IsWindowEnabled.argtypes = [wt.HWND]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.SetForegroundWindow.argtypes = [wt.HWND]

ESPERA = 8
MAX_PASOS = 60
PAUSA = 0.4
VK_ESCAPE = 0x1B


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD), ("flags", wt.DWORD),
        ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
        ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
        ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND),
        ("rcCaret", wt.RECT),
    ]


def clase(h):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, buf, 256)
    return buf.value


def texto(h):
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, buf, n + 1)
    return buf.value


def foco_actual():
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus or info.hwndActive


def describir(h):
    """Describe el control con foco. Si es el Edit interno de un combo,
    describe al combo (el control real de VB6)."""
    c = h
    if clase(h) == "Edit":
        p = user32.GetParent(h)
        if p and clase(p).startswith("ThunderRT6"):
            c = p
    r = wt.RECT()
    user32.GetWindowRect(c, ctypes.byref(r))
    return {
        "hwnd": c,
        "id": user32.GetDlgCtrlID(c),
        "clase": clase(c),
        "texto": texto(h),
        "hab": bool(user32.IsWindowEnabled(c)),
        "rect": (r.left, r.top, r.right, r.bottom),
    }


def fmt(d):
    return (f"id={d['id']} clase={d['clase']} hab={d['hab']} "
            f"rect={d['rect']} texto={d['texto']!r}")


def pid_de(h):
    p = wt.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def main():
    print(f"Tienes {ESPERA} s: haz clic dentro del campo 'N Parte'...")
    for i in range(ESPERA, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    print()

    foco = foco_actual()
    if not foco:
        msg = "No se detecto ningun control con foco. Intenta de nuevo."
        print(msg)
        guardar([msg])
        return

    top = user32.GetAncestor(foco, 2)
    pid_app = pid_de(top)
    perdidos = 0
    inicio = describir(foco)
    out = [
        f"Recorrido de Tab {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Ventana raiz: clase={clase(top)!r} texto={texto(top)!r}",
        f"INICIO: {fmt(inicio)}",
        "",
    ]

    for paso in range(1, MAX_PASOS + 1):
        if user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
            out.append("Detenido con ESC.")
            break

        send_keys("{TAB}")
        time.sleep(PAUSA)

        foco = foco_actual()
        if not foco:
            out.append(f"paso {paso}: sin foco detectable (posible cuadro de dialogo). Detenido.")
            break

        raiz = user32.GetAncestor(foco, 2)
        if raiz != top and pid_de(raiz) != pid_app:
            # El foco paso a OTRA aplicacion (barra de tareas, etc.): no es un aviso del sistema
            perdidos += 1
            out.append(f"paso {paso}: el foco paso a OTRA aplicacion (clase={clase(raiz)!r}); "
                       f"NO es un aviso del sistema. Reintento {perdidos}/3")
            if perdidos >= 3:
                out.append("Detenido: el foco se pierde repetidamente.")
                break
            user32.SetForegroundWindow(top)
            time.sleep(0.6)
            f2 = foco_actual()
            if f2 and user32.GetAncestor(f2, 2) == top:
                out.append(f"  restaurado en: {fmt(describir(f2))}")
            continue
        if raiz != top:
            out.append(f"paso {paso}: el foco salio de la ventana principal -> posible AVISO/DIALOGO")
            out.append(f"  clase={clase(raiz)!r} titulo={texto(raiz)!r}")
            try:
                for w in HwndWrapper(raiz).descendants():
                    t = w.window_text()
                    if t:
                        out.append(f"  texto interno: {t!r} (clase {w.class_name()})")
            except Exception as e:
                out.append(f"  (no se pudo leer el contenido: {e})")
            out.append("Detenido: no se toco nada del aviso.")
            break

        d = describir(foco)
        out.append(f"paso {paso}: {fmt(d)}")
        if d["hwnd"] == inicio["hwnd"]:
            out.append("Volvio al campo inicial: recorrido completo.")
            break
    else:
        out.append(f"Se alcanzo el maximo de {MAX_PASOS} pasos sin volver al inicio.")

    guardar(out)
    print(f"Listo. Guardado en: {SALIDA} ({len(out)} lineas). Pegalo en el chat.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        guardar(["ERROR durante el recorrido:", err])
        print(err)
        print("El error quedo guardado en:", SALIDA)
    input("Presiona Enter para cerrar...")
