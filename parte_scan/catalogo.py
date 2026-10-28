"""Catálogo de infracciones y reglas de ingreso (puerto de la lógica del prototipo)."""
import json, os, re, unicodedata

from . import equivalencia, perfil
from .codigos_sistema import SISTEMA   # lista de fábrica (2° Juzgado de Valdivia): {código: descripción}

_ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogo.json")
CATALOGO = [{"a": x["abrev"], "t": x["texto"]} for x in json.load(open(_ruta, encoding="utf-8"))["infracciones"]]

STOP = {"EN", "DE", "LA", "EL", "Y", "A", "CON", "SIN", "LOS", "LAS", "POR", "AL", "DEL", "SU", "UN", "UNA", "O", "LO", "DONDE", "SE"}
OVERR = {"SEGURO": "SEGURO", "PERMISO": "PERMISO", "REVISION": "REVISION"}
SUG = {"ENTRADA": "ENTRADA", "FISCAL": "FISCAL"}

# Códigos reales del sistema (de la lista completa «Busca Infracciones», codigos_sistema.py).
CODIGOS = {
    "19": "19", "48": "48", "DOBLE": "17", "ESQUINA": "43", "DISCA": "20", "GRIFO": "492", "PARE": "52",
    "PARAD": "53", "CEDA": "494", "AREA": "499", "PASO": "49", "IZQ": "11", "SENTID": "13", "CONTRA": "15",
    "HABER": "16", "ENTRADA": "483", "SALI": "483", "LV": "60", "BEBER": "300", "EBRIO": "301",
    "SEGURO": "92", "PERMISO": "37", "REVISION": "33", "CELULAR": "54", "ROJA": "91", "RUIDOS": "350",
    "CHOQUE": "500", "COLISION": "57", "ANIMALES": "62", "FACILITAR": "649", "ESPE": "461", "BNUP": "604",
    "LOCAL": "480", "AMBU": "503", "PARAB": "75", "PUER": "632", "LUCES": "58", "PESO": "630",
    "EXCESO": "94", "RECLA": "470", "FISCAL": "610", "CARABI": "38", "MINIS": "65",
}
# Parecidas pero no idénticas: se proponen con el código, pidiendo confirmar.
CODIGOS_CONFIRMAR = {"SINL": "66"}

# Cuando el parte nombra varias infracciones de estacionamiento, vale la más específica
# (ej.: «línea amarilla, sobre acera» = solo ACERA, 48).
ESPECIFICAS = [(r"\bACERA", "48"), (r"\bESQUINA", "ESQUINA"), (r"DOBLE FILA", "DOBLE"),
               (r"PASO PEATONAL|PASO DE PEATONES|PASO CEBRA", "PASO"), (r"\bGRIFO", "GRIFO"),
               (r"AREA VERDE", "AREA"), (r"PARADERO", "PARAD"), (r"SIGNO PARE|SENAL PARE|DISCO PARE", "PARE"),
               (r"DISCAPACIT|MINUSVALID", "DISCA")]


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").upper()


def palabras(s):
    return [w for w in re.findall(r"[A-Z0-9]+", sin_tildes(s)) if w not in STOP]


def raices(s):
    return {w[:5] for w in palabras(s)}


DF, DFR = {}, {}
for _x in CATALOGO:
    for _w in set(palabras(_x["t"])):
        DF[_w] = DF.get(_w, 0) + 1
    for _r in raices(_x["t"]):
        DFR[_r] = DFR.get(_r, 0) + 1


def palabra_clave(x):
    ws = [w for w in dict.fromkeys(palabras(x["t"])) if len(w) >= 4]
    ws.sort(key=lambda w: (DF[w], -len(w)))
    return ws[0] if ws else ""


def por_abrev(a):
    return next(x for x in CATALOGO if x["a"] == a)


def puntuar(texto):
    t = raices(texto)
    compacto = re.sub(r"[^A-Z0-9]", "", sin_tildes(texto))  # por si el OCR pegó palabras
    out = []
    for x in CATALOGO:
        c = raices(x["t"])
        if not c:
            continue
        primera = palabras(x["t"])[0][:5]
        n = extra = 0
        rara = float("inf")
        for r in c:
            if r in t or (len(r) >= 5 and r in compacto):
                n += 1
                if r != primera:
                    extra += 1
                    rara = min(rara, DFR[r])
        if not extra:
            continue
        out.append({"x": x, "s": (n + (0.5 if primera in t else 0)) / (len(c) + 0.5), "rara": rara})
    out.sort(key=lambda z: (z["rara"], -z["s"]))
    return out


def _norm(s):
    return " ".join(sin_tildes(s or "").split())


def codigo_concepto(a, texto):
    """(código, estado, nota) de un concepto del catálogo según la lista de ESTE juzgado; ('', '', '') si no hay."""
    lista = perfil.infracciones()
    elegido = perfil.cargar().get("equivalencias", {}).get(a)      # lo que el usuario confirmó manda siempre
    if elegido and elegido in lista:
        return elegido, "ok", "%s · %s (confirmado por ti)" % (elegido, lista[elegido])
    fijo = CODIGOS.get(a) or CODIGOS_CONFIRMAR.get(a)
    if fijo and fijo in lista and _norm(lista[fijo]) == _norm(SISTEMA.get(fijo)):
        # la lista de este juzgado trae el mismo código con la misma descripción que la verificada
        if a in CODIGOS_CONFIRMAR:
            return fijo, "check", "Propuesto %s · %s. Confirma que es el correcto para «%s»." % (fijo, lista[fijo], texto)
        return fijo, "ok", "%s · %s" % (fijo, lista[fijo])
    if a in CODIGOS or a in CODIGOS_CONFIRMAR:
        c, est, nota, _ = equivalencia.sugerir(a, texto, lista)
        if c:
            return c, ("check" if a in CODIGOS_CONFIRMAR else est), nota
    return "", "", ""


def crear_item(x):
    c, est, nota = codigo_concepto(x["a"], x["t"])
    if c:
        return {"x": x, "cod": c, "estado": est, "nota": nota}
    if re.fullmatch(r"\d+", x["a"]) or x["a"] in OVERR:
        return {"x": x, "cod": OVERR.get(x["a"], x["a"]), "estado": "ok", "nota": x["t"]}
    w = SUG.get(x["a"]) or palabra_clave(x)
    return {"x": x, "cod": w, "estado": "check",
            "nota": "Palabra sugerida «%s». Confirma que el sistema muestra «%s»." % (w, x["t"])}


def resolver(texto):
    """Devuelve (descripcion_causa, [items]) a partir del texto de la infracción del parte."""
    T = sin_tildes(texto)

    def tres():
        return [crear_item(por_abrev(a)) for a in ("SEGURO", "PERMISO", "REVISION")]

    # «no detenerse ante señal PARE de Carabineros» (código 38): se ingresa junto con las demás infracciones del parte
    # que sí tienen código (estacionar sobre la acera…). Atropello y vehículo abandonado no se ingresan.
    if re.search(r"SENAL\s+PARE\s+(DE\s+)?(LOS\s+)?CARABINEROS|CARABINEROS.{0,40}SENAL\s+PARE|NO DETENERSE ANTE SENAL PARE", T):
        its = [crear_item(por_abrev("CARABI"))]
        if re.search(r"ESTACION.{0,60}ACERA", T):
            its.append(crear_item(por_abrev("48")))
        return its[0]["x"]["t"], its
    # alcohol en la vía pública: el parte dice «ingerir», «ingringir» (mal escrito), «consumo», «beber», «bebidas alcohólicas»
    # o solo «art. 25 ley 19.925». Es siempre «BEBER ALCOHOL EN LA VIA PUBLICA» (300), salvo que conduzca ebrio.
    if (not re.search(r"CONDUC|MANEJ|EBRI|CONDICION", T)
            and re.search(r"ART\.?\s*25.{0,12}19\.?925|LEY\s*19\.?925|ALCOHOLES|INGER|INGIR|INGRING|INGRES\w*\s+(?:DE\s+)?ALCOHOL|CONSUM\w*\s+(?:DE\s+)?(?:BEBIDAS?|ALCOHOL)|"
                  r"BEBER|BEBIEND|BEBIDAS?\s+ALCOHOLICAS?", T)):
        it = crear_item(por_abrev("BEBER"))
        return por_abrev("BEBER")["t"], [it]
    if "ESTACION" in T and not re.search(r"GARAJE|FRENTE A (LAS )?PUERTAS|ENTRADA Y SALIDA|SENTIDO CONTRARIO|COSTADO IZQ|CEDA EL PASO|"
                                         r"ACERA|ESQUINA|DOBLE FILA|PASO (PEATONAL|DE PEATONES|CEBRA)|GRIFO|AREA VERDE|PARADERO|"
                                         r"DISCAPACIT|MINUSVALID|SENAL PARE|SIGNO PARE|DISCO PARE", T) \
            and re.search(r"AMARILL|DEMARC|CICLOV|CICLO VIA|SITIO PROHIBIDO|PROHIBID|SENALIZ|SOLERA|PINTAD|ZONA", T):
        # todo estacionamiento que no tiene su propia opción (línea amarilla, ciclovía, zona demarcada…) va como sitio prohibido y señalizado
        return por_abrev("19")["t"], [crear_item(por_abrev("19"))]
    if "ESTACION" in T:
        for rx, a in ESPECIFICAS:
            if re.search(rx, T):
                return por_abrev(a)["t"], [crear_item(por_abrev(a))]
    docs = [a for rx, a in ((r"SEGURO OBLIGATORIO|\bSOAP\b", "SEGURO"), (r"PERMISO (DE )?CIRCULACION", "PERMISO"),
                            (r"REVISION TECNICA", "REVISION"),
                            (r"SIN PORTAR .{0,25}LICENCIA|NO PORTAR .{0,25}LICENCIA|SIN LICENCIA", "SINL")) if re.search(rx, T)]
    if len(docs) >= 2 and not re.search(r"HABER|OBTENID", T):
        its = [crear_item(por_abrev(a)) for a in docs]
        return " Y ".join(i["x"]["t"] for i in its), its
    if re.search(r"SIN LA TOTALIDAD", T):
        return "CONDUCIR SIN LA TOTALIDAD DE LA DOCUMENTACION", tres()
    if re.search(r"CON LA TOTALIDAD", T):
        return "CONDUCIR " + por_abrev("VENCIDA")["t"], tres()
    if "LICENCIA" in T and re.search(r"\bSIN\b|NO PORTAR", T) and not re.search(r"HABER|OBTENID", T):
        it = crear_item(por_abrev("SINL"))
        return por_abrev("SINL")["t"], [it]
    if re.search(r"GARAJE|FRENTE A (LAS )?PUERTAS|ENTRADA Y SALIDA DE VEHICULOS", T):
        it = crear_item(por_abrev("ENTRADA"))
        return por_abrev("ENTRADA")["t"], [it]
    if "FUGA" in T and "CARABINEROS" not in T:   # el «inspector fiscal» es solo de inspectores municipales o de la Seremi
        it = crear_item(por_abrev("FISCAL"))
        it["nota"] = "«Darse a la fuga» se ingresa como no respetar señal de inspector fiscal. " + it["nota"]
        return por_abrev("FISCAL")["t"], [it]
    r = puntuar(texto)
    if not r or r[0]["s"] < 0.4:
        return "", []
    it = crear_item(r[0]["x"])
    segundo = r[1]["s"] if len(r) > 1 else 0
    if r[0]["s"] < 0.6 or r[0]["s"] - segundo < 0.15:
        it["estado"] = "check"
        it["nota"] = "Dudoso. También podría ser: " + " · ".join(z["x"]["t"] for z in r[1:3])
    return r[0]["x"]["t"], [it]


LARGO_LITERAL = 250     # tope de la descripción cuando se copia lo que dice el parte


def comodin():
    """Código que el juzgado usa cuando la infracción del parte no calza con su lista (67 en el 2° Juzgado de Valdivia)."""
    return str(perfil.cargar().get("infraccion_comodin") or "67").strip()


def _literal(texto):
    """Lo que dice el parte, en mayúsculas y en una sola línea, para la descripción de la causa."""
    from .exportar import sin_tildes
    t = re.sub(r"\s+", " ", sin_tildes(str(texto or "").upper())).strip(" .,;:-")   # sin acentos, con Ñ
    if len(t) > LARGO_LITERAL:
        t = t[:LARGO_LITERAL].rsplit(" ", 1)[0]
    return t


def resolver_o_comodin(texto):
    """Como resolver(), pero si no reconoce la infracción usa el código comodín del juzgado (67) y deja como
    descripción lo que dice el parte. Devuelve (descripcion, [items], es_comodin)."""
    causa, items = resolver(texto)
    if items:
        return causa, items, False
    cod = comodin()
    nombre = perfil.infracciones().get(cod) or perfil.infracciones().get(int(cod) if cod.isdigit() else cod, "")
    nota = ("La infracción del parte no calza con la lista: se usa el código %s%s y la descripción lleva lo que dice el parte. "
            "Confírmalo." % (cod, (" (" + str(nombre) + ")") if nombre else ""))
    return _literal(texto), [{"x": {"a": cod, "t": str(nombre)}, "cod": cod, "estado": "check", "nota": nota}], True


_COMUNAS = None


def comuna_en_sistema(nombre):
    """True si la comuna existe en la lista del sistema (sin importar acentos ni mayúsculas); vacía = True."""
    global _COMUNAS
    from .exportar import sin_tildes
    if _COMUNAS is None:
        try:
            ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comunas_sistema.txt")
            with open(ruta, encoding="utf-8") as f:
                _COMUNAS = {sin_tildes(l).strip().upper() for l in f if l.strip()}
        except OSError:
            _COMUNAS = set()
    if not _COMUNAS or not str(nombre or "").strip():
        return True
    return sin_tildes(nombre).strip().upper() in _COMUNAS


def actuario(rol):
    """(nombre, código) de la actuaria que corresponde al Rol, según el perfil del juzgado."""
    d = re.sub(r"\D", "", rol or "")
    if not d:
        return None
    n, c = perfil.actuario_por_digito(d[-1])
    return (n.title(), c) if n else None
