# -*- coding: utf-8 -*-
"""
Copia la lista de COMUNAS tal como esta guardada en el sistema (con sus Ñ y acentos, sin tocar nada).
SOLO LEE: no escribe nada en el sistema.

Uso:
  1. En el sistema, deja a la vista la lista de comunas. Sirve cualquiera de estas dos formas:
       - el cuadro «Busca Comunas» (normalmente con Enter dentro del campo Comuna), o
       - el campo Comuna con su lista desplegada.
  2. Ejecuta:  python exportar_comunas.py
  3. Tienes 8 segundos para dejar la lista a la vista. No la cierres hasta que termine.
  4. La lista queda COPIADA en el portapapeles (pegala en el chat) y guardada en tu carpeta Descargas como
     comunas_sistema.txt y comunas_sistema.csv. Solo contiene comunas: no hay datos de personas.
  Si no encuentra la lista, deja un resumen de lo que vio en Descargas\\diagnostico_listas.txt para estudiarlo.
"""
import csv
import ctypes
import ctypes.wintypes as wt
import os
import re
import time
import traceback

DESCARGAS = os.path.join(os.path.expanduser("~"), "Downloads")
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetDlgCtrlID.argtypes = [wt.HWND]
user32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
                                       ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_size_t

# mensajes de solo lectura: listas (LB_*) y combos (CB_*)
LB = (0x018B, 0x018A, 0x0189)       # GETCOUNT, GETTEXTLEN, GETTEXT
CB = (0x0146, 0x0149, 0x0148)
CLASES_LISTA = {"ThunderRT6ListBox": (LB, CB), "ListBox": (LB, CB), "ComboLBox": (LB, CB),
                "ThunderRT6ComboBox": (CB, LB), "ComboBox": (CB, LB)}


def smto(h, msg, w, l, t=500):
    r = ctypes.c_size_t()
    ok = user32.SendMessageTimeoutW(h, msg, w, l, 2, t, ctypes.byref(r))
    return r.value if ok else None


def clase(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def hijos(h):
    res = []
    user32.EnumChildWindows(h, WNDENUMPROC(lambda hh, lp: res.append(hh) or True), 0)
    return res


def ventanas():
    res = []
    user32.EnumWindows(WNDENUMPROC(lambda h, lp: res.append(h) or True), 0)
    return res


def leer_items(h, juego):
    cuenta, largo, texto = juego
    n = smto(h, cuenta, 0, 0)
    if not n or n > 200000 or n == 0xFFFFFFFF or n >= 0x7FFFFFFF:
        return []
    items = []
    for i in range(n):
        ln = smto(h, largo, i, 0)
        if ln is None or ln >= 0x7FFFFFFF:
            return []
        buf = ctypes.create_unicode_buffer(ln + 2)
        smto(h, texto, i, ctypes.addressof(buf))
        items.append(buf.value)
    return items


def listas_a_la_vista():
    """[(clase, id, items)] de todas las listas y combos de las ventanas visibles."""
    vistos, res = set(), []
    for w in ventanas():
        if not user32.IsWindowVisible(w):
            continue
        for h in [w] + hijos(w):
            c = clase(h)
            if h in vistos or c not in CLASES_LISTA:
                continue
            vistos.add(h)
            for juego in CLASES_LISTA[c]:
                items = leer_items(h, juego)
                if items:
                    res.append((c, user32.GetDlgCtrlID(h), items))
                    break
    return res


def copiar(texto):
    """Copia al portapapeles (Unicode, conserva Ñ y acentos)."""
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    datos = (texto + "\0").encode("utf-16-le")
    h = kernel32.GlobalAlloc(0x0002, len(datos))        # GMEM_MOVEABLE
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, datos, len(datos))
    kernel32.GlobalUnlock(h)
    if not user32.OpenClipboard(None):
        return False
    user32.EmptyClipboard()
    user32.SetClipboardData(13, h)                      # CF_UNICODETEXT
    user32.CloseClipboard()
    return True


def main():
    print("Deja a la vista la lista de comunas del sistema (cuadro «Busca Comunas» o el campo Comuna desplegado).")
    print("Empiezo en 8 segundos...")
    for s in range(8, 0, -1):
        print(f"  {s}...", end="\r", flush=True)
        time.sleep(1)
    print(" " * 20)
    listas = listas_a_la_vista()
    candidatas = [x for x in listas if any("VALDIVIA" in i.upper() for i in x[2])]
    if not candidatas:
        ruta = os.path.join(DESCARGAS, "diagnostico_listas.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("Listas y combos a la vista (clase, id, cantidad, primer elemento):\n")
            for c, i, items in listas:
                f.write(f"{c}\t{i}\t{len(items)}\t{items[0][:40]!r}\n")
        print("No encontre una lista de comunas a la vista (busque una que incluya VALDIVIA).")
        print("Despliega la lista del campo Comuna o abre «Busca Comunas» y ejecuta de nuevo.")
        print(f"Deje un resumen de lo que vi en: {ruta}")
        return
    clase_, id_, items = max(candidatas, key=lambda x: len(x[2]))
    items = [i.strip() for i in items if i.strip()]
    texto = "\n".join(items)
    os.makedirs(DESCARGAS, exist_ok=True)
    txt = os.path.join(DESCARGAS, "comunas_sistema.txt")
    csv_ = os.path.join(DESCARGAS, "comunas_sistema.csv")
    with open(txt, "w", encoding="utf-8") as f:
        f.write(texto)
    filas = []
    for it in items:
        m = re.match(r"^(\d+)\s+(.*)$", it.replace("\t", "  "))
        filas.append((m.group(1), m.group(2).strip()) if m else ("", it))
    with open(csv_, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows([("codigo", "descripcion")] + filas)
    especiales = sorted({c for c in texto if ord(c) > 127})
    print(f"Lista encontrada ({clase_}, id {id_}): {len(items)} comunas.")
    print("Caracteres especiales que trae: " + (" ".join(especiales) if especiales else "ninguno"))
    print(f"Guardada en:\n  {txt}\n  {csv_}")
    print("COPIADA al portapapeles: pegala en el chat." if copiar(texto) else
          "No pude copiar al portapapeles: abre comunas_sistema.txt y copia su contenido.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
    input("\nPresiona Enter para cerrar...")
