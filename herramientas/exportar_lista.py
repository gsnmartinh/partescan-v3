# -*- coding: utf-8 -*-
"""
Exporta a un archivo TODA la lista de un cuadro de busqueda del sistema (infracciones, oficinas remisoras, etc.).
Solo lee las listas. El usuario cambia manualmente las vocales en el sistema.

Uso:
  1. En el sistema, abre el cuadro de busqueda (ej. 'Busca Infracciones': en la grilla de Infracciones, Enter
     hasta que aparezca el cuadro; o 'Busca Oficinas Remisoras' con Enter en el campo Oficina Emisora).
  2. Ejecuta:  python exportar_lista.py
  3. Tienes 8 segundos para dejar el cuadro abierto y a la vista. Cambia el filtro a la siguiente vocal cuando lo indique la herramienta.
  4. Se crea <titulo>.csv y <titulo>.txt junto al script. Enviamelos.
"""
import sys
import csv
import ctypes
import ctypes.wintypes as wt
import os
import re
import time
import traceback

CARPETA = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
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


def cuenta_atras(vocal):
    print(f"\nEscribe {vocal} en Tipo Vehiculo y abre su lista. La recogere en 8 segundos.", flush=True)
    for segundos in range(8, 0, -1):
        print(f"  {vocal}: {segundos} segundos...  ", end="\r", flush=True)
        time.sleep(1)


def capturar_lista():
    cuadros = buscar_cuadros()
    if len(cuadros) != 1:
        raise RuntimeError("Debe haber un solo buscador abierto al terminar la cuenta atras.")
    w = cuadros[0]
    lbs = [h for h in hijos(w) if clase(h) == "ThunderRT6ListBox"]
    if len(lbs) != 1:
        raise RuntimeError("No pude identificar una unica lista legible en el buscador.")
    items = leer_todo(lbs[0])
    if not items:
        raise RuntimeError("La lista esta vacia. Abre los resultados antes de que termine la cuenta atras.")
    return titulo(w), items


def guardar(items, nom):
    filas = []
    for it in items:
        m = re.match(r"^\s*(\S+)\s+(.*?)\s*$", it.replace("\t", "  "))
        filas.append((m.group(1), m.group(2)) if m else ("", it.strip()))
    with open(os.path.join(CARPETA, nom + ".csv"), "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows([("codigo", "descripcion")] + filas)
    with open(os.path.join(CARPETA, nom + ".txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(items))


def main():
    print("LECTURA DE TIPOS DE VEHICULO: A, E, I, O, U")
    print("Tu cambias la letra y abres el buscador; esta herramienta solo lee.")
    print("No acepta ni modifica registros. Deja el buscador visible al terminar cada cuenta atras.")
    encontrados = {}
    nombre = None
    for vocal in "AEIOU":
        cuenta_atras(vocal)
        while True:
            try:
                titulo_actual, items = capturar_lista()
                if nombre is not None and titulo_actual != nombre:
                    raise RuntimeError("El buscador cambio. Abre nuevamente el de tipos de vehiculo.")
                break
            except RuntimeError as error:
                print(f"\n{error}")
                input(f"No avance a otra vocal. Presiona Enter para reintentar {vocal} con otros 8 segundos...")
                cuenta_atras(vocal)
        nombre = titulo_actual
        for item in items:
            clave = " ".join(item.split()).casefold()
            if clave:
                encontrados.setdefault(clave, item)
        nom = re.sub(r"[^A-Za-z0-9]+", "_", nombre).strip("_") or "Tipos_vehiculo"
        guardar(sorted(encontrados.values(), key=str.casefold), nom)
        print(f"\n{vocal} recogida: {len(items)} filas. Total sin duplicados: {len(encontrados)}.", flush=True)
    print(f"\nTerminado. Archivos guardados en {CARPETA}: {nom}.csv y {nom}.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
    input("\nPresiona Enter para cerrar...")
