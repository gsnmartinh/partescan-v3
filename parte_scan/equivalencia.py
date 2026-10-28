"""Busca, en la lista de infracciones de CUALQUIER juzgado, el código que corresponde a cada concepto del catálogo.

Cada concepto («ESTACIONAR SOBRE ACERA», «seguro obligatorio»…) tiene una frase clave que se busca en las descripciones
de la lista del juzgado. Si hay un solo candidato, se usa; si hay varios o ninguno claro, se marca «Revisar» y se
muestran las opciones. Lo que el usuario confirme queda guardado en el perfil («equivalencias») y manda siempre.
"""
import re

from . import perfil

# concepto del catálogo -> frase clave (regex sobre la descripción sin tildes y en mayúsculas)
HINTS = {
    "19": r"SITIO PROHIBIDO", "48": r"ACERA", "DOBLE": r"DOBLE FILA", "ESQUINA": r"ESQUINA",
    "DISCA": r"MINUSVALID|DISCAPACIT", "GRIFO": r"GRIFO", "PARE": r"(SIGNO|SENAL|DISCO) PARE",
    "PARAD": r"PARADERO", "CEDA": r"CEDA", "AREA": r"AREA VERDE", "PASO": r"PASO (PEATONAL|DE PEATONES|CEBRA)",
    "IZQ": r"COSTADO IZQUIERDO", "SENTID": r"ESTACIONAR.*(SENTIDO CONTRARIO|CONTRA SENTIDO)",
    "CONTRA": r"CONDUCIR.*(SENTIDO CONTRARIO|CONTRA SENTIDO)", "HABER": r"SIN HABER OBTENIDO LICENCIA",
    "ENTRADA": r"ENTRADA.*SALIDA", "SALI": r"ENTRADA.*SALIDA", "LV": r"LICENCIA.*FECHA CONTROL",
    "BEBER": r"BEBER.*VIA PUBLICA", "EBRIO": r"TRANSITAR.*EBRI|EBRI.*TRANSITAR", "SEGURO": r"SEGURO OBLIGATORIO",
    "PERMISO": r"PERMISO.*CIRCULACION", "REVISION": r"REVISION TECNICA", "CELULAR": r"CELULAR|TELEFONO MOVIL",
    "ROJA": r"LUZ ROJA", "RUIDOS": r"RUIDOS? MOLESTOS?", "CHOQUE": r"DANOS.*CHOQUE", "COLISION": r"DANOS.*COLISION",
    "ANIMALES": r"^ANIMALES|ANIMALES SUELTOS", "FACILITAR": r"FACILITAR.*VEHICULO", "ESPE": r"ESPECIES ABANDONADAS",
    "BNUP": r"B\.?N\.?U\.?P|BIEN(ES)? NACIONAL(ES)? DE USO PUBLICO|ESPACIO.*USO PUBLICO", "LOCAL": r"LOCAL.*PATENTE",
    "AMBU": r"AMBULANTE", "PARAB": r"PARABRISAS", "PUER": r"PUERTAS ABIERTAS",
    "LUCES": r"LUCES (ANTIREGLAMENTARIAS|DISTINTAS)", "PESO": r"PESOS? MAXIMOS?", "EXCESO": r"EXCESO.*VELOCIDAD",
    "RECLA": r"RECLAMACION", "FISCAL": r"INSPECTOR FISCAL", "CARABI": r"SENAL.*CARABINEROS|CARABINEROS.*SENAL",
    "MINIS": r"MINISTRATEL", "SINL": r"SIN (PORTAR )?LICENCIA",
}


def _toks(s):
    return {w[:5] for w in re.findall(r"[A-Z0-9]+", perfil.sin_tildes(s)) if len(w) >= 3}


def _afinidad(a, b):
    A, B = _toks(a), _toks(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def candidatos(abrev, texto_concepto, lista=None):
    """[(codigo, descripcion, puntaje)] ordenados de mejor a peor para un concepto del catálogo."""
    lista = lista if lista is not None else perfil.infracciones()
    rx = HINTS.get(abrev)
    out = []
    for c, d in lista.items():
        dn = " ".join(perfil.sin_tildes(d).split())
        hit = bool(rx and re.search(rx, dn))
        out.append((c, d, _afinidad(texto_concepto, d) + (1.0 if hit else 0.0), hit))
    out.sort(key=lambda z: -z[2])
    return [(c, d, round(s, 2), hit) for c, d, s, hit in out[:6]]


def sugerir(abrev, texto_concepto, lista=None):
    """(codigo, estado, nota, [candidatos]) · estado «ok» solo si hay un único candidato claro."""
    cand = candidatos(abrev, texto_concepto, lista)
    con_frase = [z for z in cand if z[3]]
    if len(con_frase) == 1:
        c, d, s, _ = con_frase[0]
        return c, "ok", "%s · %s" % (c, d), cand
    if len(con_frase) > 1:
        c, d, s, _ = con_frase[0]
        otros = " · ".join("%s %s" % (z[0], z[1]) for z in con_frase[1:3])
        if s - con_frase[1][2] >= 0.15:
            return c, "ok", "%s · %s" % (c, d), cand
        return c, "check", "Hay varias parecidas: elegí %s · %s. También: %s" % (c, d, otros), cand
    if cand and cand[0][2] >= 0.5:
        c, d, s, _ = cand[0]
        return c, "check", "Parecida a «%s»: %s · %s. Confirma que sea la correcta." % (texto_concepto, c, d), cand
    return "", "", "", cand
