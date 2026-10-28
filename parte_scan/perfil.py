"""Perfil del juzgado.

Todo lo que cambia de un juzgado a otro (listas de infracciones y de oficinas con SUS códigos, actuarias y reparto
por Rol, nombre de la pantalla del sistema, etc.) vive en una carpeta de datos del usuario y la leen los dos
programas (ParteScan y PartesTeclea). Si la carpeta no tiene nada, se usan los datos del 2° Juzgado de Policía
Local de Valdivia, que vienen incluidos.

Carpeta:  %APPDATA%\\ParteScan\\perfil   (o ~/.parte_scan/perfil;  variable PARTESCAN_PERFIL para cambiarla)
   perfil.json            datos generales, actuarias, reparto y equivalencias
   Busca_Infracciones.csv lista exportada del sistema («codigo;descripcion»)
   Busca_Oficinas.csv     lista de oficinas remisoras exportada del sistema
"""
import copy
import csv
import io
import json
import os
import unicodedata
from pathlib import Path

from .codigos_sistema import SISTEMA, OFICINAS

DEFECTO = {
    "juzgado": "2° Juzgado de Policía Local de Valdivia",
    "titulo_ventana": "Procesos",          # la pantalla de ingreso empieza con este texto
    "comuna": "VALDIVIA",                    # ciudad/comuna del juzgado: se supone si el parte no la trae y sale en las fechas
    "oficina_carabineros": "1ra. Comisaria Carabineros",   # si el parte no dice qué unidad es
    "actuarios": {"KATHERINE": "19", "MARILYN": "16", "MONICA": "12", "YISSEL": "10", "SANDRA": "9"},
    "rol_actuario": {"1": "KATHERINE", "2": "KATHERINE", "3": "MARILYN", "4": "MARILYN", "5": "MONICA",
                     "6": "MONICA", "7": "YISSEL", "8": "YISSEL", "9": "SANDRA", "0": "SANDRA"},
    "oficina_municipal": {"INSPECCION GENERAL": "32", "SEGURIDAD CIUDADANA": "32"},   # depto. del encabezado -> código de oficina emisora
    "infraccion_comodin": "67",             # código que se usa cuando la infracción del parte no calza con la lista
    "equivalencias": {},                     # concepto del catálogo -> código de ESTE juzgado (lo confirma el usuario)
}
ARCHIVOS = {"infracciones": "Busca_Infracciones.csv", "oficinas": "Busca_Oficinas.csv"}
_cache = {}


def carpeta():
    p = os.environ.get("PARTESCAN_PERFIL")
    if p:
        return Path(p)
    base = os.environ.get("APPDATA")
    return (Path(base) / "ParteScan" / "perfil") if base else (Path.home() / ".parte_scan" / "perfil")


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").upper()


def _mtime(p):
    try:
        return p.stat().st_mtime_ns
    except OSError:
        return None


def cargar():
    """Perfil completo (los datos que falten salen del perfil de fábrica)."""
    f = carpeta() / "perfil.json"
    clave = ("cfg", str(f), _mtime(f))
    if clave in _cache:
        return copy.deepcopy(_cache[clave])
    cfg = copy.deepcopy(DEFECTO)
    try:
        usr = json.loads(f.read_text(encoding="utf-8"))
        for k, v in usr.items():
            cfg[k] = v
    except Exception:
        pass
    _cache.clear()
    _cache[clave] = copy.deepcopy(cfg)
    return cfg


def guardar(cfg):
    d = carpeta()
    d.mkdir(parents=True, exist_ok=True)
    (d / "perfil.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    _cache.clear()


def leer_csv(texto):
    """[(codigo, descripcion)] desde texto «codigo;descripcion» (con o sin encabezado). Ignora filas sin código."""
    filas = []
    texto = texto.lstrip("﻿")
    for lin in texto.splitlines():
        if ";" in lin:
            c, d = lin.split(";", 1)
        elif "\t" in lin:
            c, d = lin.split("\t", 1)
        else:
            continue
        c, d = c.strip().strip('"'), d.strip().strip('"')
        if c and c.lower() != "codigo" and d and d != ".":
            filas.append((c, d))
    return filas


def _lista(tipo):
    f = carpeta() / ARCHIVOS[tipo]
    clave = (tipo, str(f), _mtime(f))
    if clave in _cache:
        return _cache[clave]
    if f.exists():
        try:
            d = dict(leer_csv(f.read_text(encoding="utf-8-sig")))
            if d:
                _cache[clave] = d
                return d
        except Exception:
            pass
    d = dict(SISTEMA if tipo == "infracciones" else OFICINAS)
    _cache[clave] = d
    return d


def infracciones():
    """{codigo: descripcion} de «Busca Infracciones» de este juzgado."""
    return _lista("infracciones")


def oficinas():
    """{codigo: descripcion} de «Busca Oficinas Remisoras» de este juzgado."""
    return _lista("oficinas")


def es_lista_propia(tipo):
    return (carpeta() / ARCHIVOS[tipo]).exists()


def guardar_lista(tipo, filas):
    """Guarda la lista y devuelve un resumen frente a la anterior: n, nuevos, cambiados, quitados."""
    antes = dict(_lista(tipo))
    ahora = dict(filas)
    d = carpeta()
    d.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(("codigo", "descripcion"))
    w.writerows(filas)
    (d / ARCHIVOS[tipo]).write_text(buf.getvalue(), encoding="utf-8-sig")
    _cache.clear()
    return {"n": len(ahora), "nuevos": sorted(set(ahora) - set(antes), key=_clave_orden),
            "cambiados": sorted((c for c in ahora if c in antes and antes[c] != ahora[c]), key=_clave_orden),
            "quitados": sorted(set(antes) - set(ahora), key=_clave_orden)}


def importar(tipo, texto):
    filas = leer_csv(texto)
    if not filas:
        raise ValueError("El archivo no tiene filas «codigo;descripcion».")
    return guardar_lista(tipo, filas)


def restaurar_lista(tipo):
    try:
        (carpeta() / ARCHIVOS[tipo]).unlink()
    except OSError:
        pass
    _cache.clear()


def _clave_orden(c):
    return (0, int(c), "") if str(c).isdigit() else (1, 0, str(c))


def oficinas_ordenadas():
    """[(codigo, descripcion)] sin repetir descripciones (se queda el código menor), para listas desplegables."""
    vistas, out = set(), []
    for c, d in sorted(oficinas().items(), key=lambda kv: _clave_orden(kv[0])):
        k = sin_tildes(d)
        if k not in vistas:
            vistas.add(k)
            out.append((c, d))
    return out


def codigo_oficina(nombre):
    """Código de la oficina por su nombre exacto (sin tildes ni mayúsculas); '' si no está."""
    n = sin_tildes(nombre).strip()
    for c, d in sorted(oficinas().items(), key=lambda kv: _clave_orden(kv[0])):
        if sin_tildes(d).strip() == n:
            return c
    return ""


def oficina_municipal(depto):
    """Nombre de la oficina emisora para un parte municipal según el departamento del encabezado ('' si no se sabe)."""
    cod = str((cargar().get("oficina_municipal") or {}).get(str(depto or "").upper(), ""))
    if not cod:
        return ""
    for c, d in oficinas().items():
        if str(c) == cod:
            return d
    return ""


def actuarios():
    return {k.upper(): str(v) for k, v in cargar()["actuarios"].items()}


def rol_actuario():
    a = actuarios()
    return {str(d): n.upper() for d, n in cargar()["rol_actuario"].items() if n and n.upper() in a}


def actuario_por_digito(d):
    """(nombre, código) de la actuaria que corresponde al último dígito del Rol, o ('', '')."""
    n = rol_actuario().get(str(d), "")
    return (n, actuarios().get(n, "")) if n else ("", "")
