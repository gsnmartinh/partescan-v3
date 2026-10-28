# -*- coding: utf-8 -*-
"""
Exporta a un archivo TODA la lista de un cuadro de busqueda del sistema (infracciones, oficinas remisoras, etc.).
SOLO LEE: no escribe nada en el sistema.

Uso:
  1. En el sistema, abre el cuadro de busqueda (ej. 'Busca Infracciones': en la grilla de Infracciones, Enter
     hasta que aparezca el cuadro; o 'Busca Oficinas Remisoras' con Enter en el campo Oficina Emisora).
  2. Ejecuta:  python exportar_lista.py
  3. Tienes 8 segundos para dejar el cuadro abierto y a la vista. No lo cierres hasta que termine.
  4. Se crea <titulo>.csv y <titulo>.txt junto al script. Enviamelos.
"""
import csv
import ctypes
import ctypes.wintypes as wt
import os
import re
import time
import traceback

CARPETA = os.path.dirname(os.path.abspath(__file__))
user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT,
                                       ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_size_t


def smto(h, msg, w, l, t=500):
    r = ctypes.c_size_t()
    ok = user32.SendMessageTimeoutW(h, msg, w, l, 2, t, ctypes.byref(r))
    return r.value if ok else None


def clase(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def titulo(h):
    n = smto(h, 0x000E, 0, 0) or 0
    b = ctypes.create_unicode_buffer(n + 1)
    smto(h, 0x000D, n + 1, ctypes.addressof(b))
    return b.value


def hijos(h):
    res = []
    user32.EnumChildWindows(h, WNDENUMPROC(lambda hh, lp: res.append(hh) or True), 0)
    return res


def buscar_cuadros():
    res = []

    def cb(h, lp):
        if user32.IsWindowVisible(h) and "busca" in titulo(h).lower():
            res.append(h)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def leer_todo(lb):
    n = smto(lb, 0x018B, 0, 0)          # LB_GETCOUNT
    if not n or n > 200000:
        return []
    items = []
    for i in range(n):
        ln = smto(lb, 0x018A, i, 0) or 0     # LB_GETTEXTLEN
        buf = ctypes.create_unicode_buffer(ln + 2)
        smto(lb, 0x0189, i, ctypes.addressof(buf))   # LB_GETTEXT
        items.append(buf.value)
    return items


def main():
    print("Deja abierto el cuadro de busqueda (Busca Infracciones / Oficinas...). Empiezo en 8 s...")
    for s in range(8, 0, -1):
        print(f"  {s}...", end="\r", flush=True)
        time.sleep(1)
    cuadros = buscar_cuadros()
    if not cuadros:
        print("No encontre ningun cuadro de busqueda abierto.")
        return
    for w in cuadros:
        nom = re.sub(r"[^A-Za-z0-9]+", "_", titulo(w)).strip("_") or "lista"
        lbs = [h for h in hijos(w) if clase(h) == "ThunderRT6ListBox"]
        if not lbs:
            print(f"'{titulo(w)}': no tiene una lista legible.")
            continue
        items = leer_todo(lbs[0])
        filas = []
        for it in items:
            m = re.match(r"^\s*(\S+)\s+(.*?)\s*$", it.replace("\t", "  "))
            filas.append((m.group(1), m.group(2)) if m else ("", it.strip()))
        with open(os.path.join(CARPETA, nom + ".csv"), "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f, delimiter=";").writerows([("codigo", "descripcion")] + filas)
        with open(os.path.join(CARPETA, nom + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(items))
        print(f"'{titulo(w)}': {len(items)} elementos guardados en {nom}.csv y {nom}.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
    input("\nPresiona Enter para cerrar...")
