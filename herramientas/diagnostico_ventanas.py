"""
Diagnostico de ventanas del sistema del Juzgado (solo LEE, no teclea nada).

Uso:
  1. Abre el sistema en la pantalla de ingreso ("Procesos 2DO. JUZGADO").
  2. Ejecuta:  python diagnostico_ventanas.py
  3. Tienes 8 segundos: haz clic DENTRO de la ventana de ingreso del sistema
     (y, si quieres, deja el cursor en el campo Nº Parte).
  4. Se crea diagnostico.txt junto al script. Pegalo en el chat.

Requiere:  pip install pywinauto
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time
import traceback
from datetime import datetime

# Siempre se guarda junto al script, sin importar desde donde se ejecute
CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "diagnostico.txt")


def guardar(lineas):
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))


try:
    from pywinauto.controls.hwndwrapper import HwndWrapper
except Exception:
    guardar(["ERROR importando pywinauto (instala con: pip install pywinauto)",
             traceback.format_exc()])
    print("No se pudo importar pywinauto. Detalle guardado en:", SALIDA)
    print("Instala con:  pip install pywinauto")
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
ESPERA = 8


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD), ("flags", wt.DWORD),
        ("hwndActive", wt.HWND), ("hwndFocus", wt.HWND),
        ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
        ("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND),
        ("rcCaret", wt.RECT),
    ]


def clase(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def texto(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def raiz(hwnd):
    return user32.GetAncestor(hwnd, 2)  # GA_ROOT


def foco_actual():
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    user32.GetGUIThreadInfo(0, ctypes.byref(info))
    return info.hwndFocus, info.hwndActive


def linea(w, foco):
    try:
        h = w.handle
        r = w.rectangle()
        padre = user32.GetParent(h)
        marca = "  <== FOCO" if h == foco else ""
        return (
            f"hwnd={h:#010x} padre={padre:#010x} id={w.control_id()} "
            f"clase={w.class_name()!r} texto={w.window_text()!r} "
            f"vis={w.is_visible()} hab={w.is_enabled()} "
            f"rect=({r.left},{r.top},{r.right},{r.bottom}){marca}"
        )
    except Exception as e:
        return f"(error leyendo control: {e})"


def main():
    print(f"Tienes {ESPERA} s: haz clic dentro de la ventana de ingreso del sistema...")
    for i in range(ESPERA, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    print()

    foco, activa = foco_actual()
    if not foco:
        foco = activa
    if not foco:
        msg = "No se detecto ninguna ventana con foco. Intenta de nuevo."
        print(msg)
        guardar([msg])
        return

    top = raiz(foco)
    out = []
    out.append(f"Diagnostico {datetime.now():%Y-%m-%d %H:%M:%S}")
    out.append("")
    out.append("== CONTROL CON FOCO ==")
    out.append(f"hwnd={foco:#010x} clase={clase(foco)!r} texto={texto(foco)!r}")
    out.append("")
    out.append("== CADENA DE PADRES (del foco hacia arriba) ==")
    h = foco
    while h:
        out.append(f"hwnd={h:#010x} clase={clase(h)!r} texto={texto(h)!r}")
        h = user32.GetParent(h)
    out.append("")

    out.append("== VENTANA RAIZ Y TODOS SUS DESCENDIENTES (orden z / de creacion) ==")
    wr = HwndWrapper(top)
    out.append(linea(wr, foco))
    desc = wr.descendants()
    out.append(f"({len(desc)} descendientes)")
    for w in desc:
        out.append("  " + linea(w, foco))
    out.append("")

    out.append("== SOLO CONTROLES MDI (clase MDIClient y sus hijos directos) ==")
    for w in desc:
        try:
            if "MDIClient" in w.class_name():
                out.append(linea(w, foco))
                for hijo in w.children():
                    out.append("  " + linea(hijo, foco))
                    for nieto in hijo.children():
                        out.append("    " + linea(nieto, foco))
        except Exception as e:
            out.append(f"(error en MDI: {e})")
    out.append("")

    out.append("== PRUEBA CON BACKEND UIA (por si expone mas texto) ==")
    try:
        from pywinauto import Desktop
        vent = Desktop(backend="uia").window(handle=top)
        for d in vent.descendants():
            try:
                i = d.element_info
                out.append(
                    f"  tipo={i.control_type!r} nombre={i.name!r} "
                    f"clase={i.class_name!r} id={i.automation_id!r}"
                )
            except Exception:
                pass
    except Exception as e:
        out.append(f"  UIA no disponible: {e}")

    guardar(out)
    print(f"Listo. Guardado en: {SALIDA} ({len(out)} lineas). Pegalo en el chat.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        guardar(["ERROR durante el diagnostico:", err])
        print(err)
        print("El error quedo guardado en:", SALIDA)
    input("Presiona Enter para cerrar...")
