"""Lee el texto OCR de un parte de Carabineros («Da cuenta de infracción…») y devuelve los mismos
campos que extractor.parte, más los propios de este modelo (boleta, infractor, vehículo).

Estos partes cambian de orden y de redacción según la unidad (a veces va primero el infractor, a veces la
infracción; los de alcohol no traen vehículo), así que se separan por rótulos y no por posición."""
import re, unicodedata

from . import catalogo, certificado, perfil
from . import semantica as SM
from .extractor import MESES, fecha_de, limpiar

# Para reconocer un parte de Carabineros basta con que aparezcan varios de estos rasgos (el texto de los
# escaneos tenues sale a veces con el encabezado ilegible).
RASGOS = [
    r"CAR\w{0,3}BINEROS", r"Parte\s*N\w{0,4}[.\s:*°º]*\d{2,5}", r"POL\w{0,3}\.?\s?LOCAL\s+V",
    r"SUBOFICIAL|\bGUARDIA\b", r"DA\s+CUENTA\s+(?:DE|AL)", r"INFRACTOR\s*:", r"\bCIUDAD\b|C\s?I\s?U\s?D\s?A\s?D", r"J[GC]DO\W{0,3}POL",
]
RE_ROTULO = re.compile(r"(INFRACTOR(?:ES)?(?:\s*\(A\))?(?:\s*(?:N[°º]\s*)?[12])?|INFRACCI[OÓ]N|VEH[IÍ]CULO|LICENCIA|REINCIDENCIAS?|DENUNCIANTE|TESTIGO|"
                       r"OBSERVACI[OÓ]N(?:ES)?|CITACI[OÓ]N)\s*[:;]|(?-i:\b(INFRACTOR|VEH[IÍ]CULO))\s+(?:[O0](?=\s+[A-ZÁÉÍÓÚÑ]{3})|\.(?=\s+\w))", re.I)
PLACA_OK = re.compile(r"[A-Z]{4}\d{2}|[A-Z]{2}\d{4}|[A-Z]{3}\d{2}|[A-Z]{3}\d{3}|[A-Z]{2}\d{3}")
CONSONANTES = "BCDFGHJKLPRSTVWXYZ"


def placa_puntaje(p):
    """2 = formato válido y solo consonantes (como las patentes nuevas y las de moto); 1 = formato válido; 0 = no sirve."""
    if not PLACA_OK.fullmatch(p or ""):
        return 0
    letras = re.sub(r"\d", "", p)
    return 2 if all(c in CONSONANTES for c in letras) else 1
NACION = (r"venezolan|chilen|peruan|colombian|haitian|bolivian|argentin|ecuatorian|brasile|dominican|cubano|cubana|"
          r"paraguay|uruguay|espa[ñn]ol")


def es_carab(texto):
    return sum(bool(re.search(r, texto or "", re.I)) for r in RASGOS) >= 3


def _plano(t):
    t = re.sub(r"\bINERACCI[OÓ]N\b", "INFRACCION", t or "", flags=re.I)
    return re.sub(r"\s+", " ", t)


def _hoy():
    import datetime
    return datetime.date.today()


def corregir_anio(fecha, hoy=None):
    """Los partes son de infracciones recientes: el año es el en curso (en enero pueden venir de diciembre, del año
    anterior). Si el OCR leyó otro (1926, 2025…) se corrige. -> (fecha, año leído si se corrigió, si no '')."""
    import datetime
    hoy = hoy or _hoy()
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", fecha or "")
    if not m:
        return fecha, ""
    d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        ok = datetime.date(hoy.year, mes, d) <= hoy + datetime.timedelta(days=7)
        anio = hoy.year if ok else hoy.year - 1       # un 15/12 leído en enero es de diciembre pasado
        datetime.date(anio, mes, d)
    except ValueError:
        return fecha, ""
    if a == anio:
        return fecha, ""
    return "%02d/%02d/%d" % (d, mes, anio), str(a)


def _fecha_num(s):
    m = re.search(r"(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(20\d\s*\d)(?!\d)", s)
    return "%02d/%02d/%s" % (int(m.group(1)), int(m.group(2)), re.sub(r"\s", "", m.group(3))) if m else ""


def _fecha_cabecera(t):
    """«VALDIVIA, 3 de Octubre de 2026»: solo si el día y el año se leyeron limpios."""
    i = t.lower().find("doy cuenta")
    cab = t[:i] if i > 0 else t[:600]
    m = re.search(re.escape(perfil.cargar()["comuna"]).upper() + r"\s*,?\s*(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+de\s+(20\d[\dA-Za-z€])(?!\d)", cab, re.I)
    if not m:
        return ""
    anio = m.group(3) if m.group(3).isdigit() else "????"
    return "%02d/%02d/%s" % (int(m.group(1)), MESES[m.group(2).upper()], anio)


def _fecha_texto(t):
    """Fecha del hecho tal como la escribe el parte: «el día 29 de septiembre del año 2026»."""
    m = re.search(r"(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+(?:del?\s+)?(?:presente\s+)?(?:a[ñn]o\s+)?(\d{4})", t, re.I)
    return "%02d/%02d/%s" % (int(m.group(1)), MESES[m.group(2).upper()], m.group(3)) if m else ""


def _secciones(t):
    """-> (lista de (rótulo, texto)) en el orden en que aparecen."""
    ms = list(RE_ROTULO.finditer(t))
    out = []
    for i, m in enumerate(ms):
        fin = ms[i + 1].start() if i + 1 < len(ms) else len(t)
        rot = m.group(1) or m.group(2)
        out.append((re.sub(r"[ÓóÍí]", lambda x: {"Ó": "O", "ó": "O", "Í": "I", "í": "I"}[x.group()], rot).upper(),
                    t[m.end():fin].strip()))
    return out


def _sec(secs, nombre, ultimo=False):
    v = [s for r, s in secs if r.startswith(nombre) and s]
    return (v[-1] if ultimo else v[0]) if v else ""


def _u(x):
    """«AG*ERO» (la Ü sale como asterisco en el OCR) -> «AGUERO»."""
    x = re.sub(r"(?<=[A-Za-z])\*(?=[A-Za-z])", "U", x or "")
    x = re.sub(r"(?<=\s)/N\b", "S/N", x)   # «s/n» a veces pierde la S
    return re.sub(r"[\s,;]*\b(?:LUGAR\s+DONDE|DONDE|M?NOTIFIC\w*|SORPRENDI\w*)\b.*$", "", x, flags=re.I).strip(" ,;")


def _lugar_final(t):
    """Lugar del hecho: por la redacción habitual o el rótulo LUGAR; si eso no sirve (vacío, arrastra a una persona o
    repite el domicilio del infractor porque las secciones vienen en otro orden), por significado."""
    pers = SM.personas(t)
    def sana(c):
        if not c or SM.MALO.search(c):
            return False
        cu = re.sub(r"\W+", " ", _norm(c)).strip()
        return not any(cu and cu in re.sub(r"\W+", " ", _norm(p)) for p in pers)
    for cand in (_lugar(t), _lugar_rotulo(t)):
        for p in pers:                           # el lugar no puede arrastrar el nombre de una persona
            nom = p.split(",")[0].upper()
            i = (cand or "").upper().find(nom)
            if i > 0:
                cand = cand[:i].rstrip(" .,")
        if sana(cand):
            return cand.strip(" ,.;")
    v = SM.lugar_narrativo(t) or SM.lugar(t)
    if v:
        c = _lugar("sorprendio en " + v + ", sorprendio la siguiente infraccion")
        if c and not SM.MALO.search(c):
            return c.strip(" ,.;")
    return ""


def _lugar_rotulo(t):
    """Respaldo: partes que traen «LUGAR: Baquedano intersección Doctor Labbé.» como rótulo propio."""
    m = re.search(r"\bLUGAR\s*:\s*(.+?)(?=\s+(?:INFRACTOR|VEH[IÍ]CULO|DISP\.|DENUNCIANTE|TESTIGO|HORA|LUGAR)\b|$)", t, re.I)
    if not m:
        return ""
    v = m.group(1).strip(" .,;")
    v = re.sub(r",?\s+(?:de\s+esta\s+\w+|valdivia)\s*$", "", v, flags=re.I)
    v = re.sub(r"\bfrente\s+(?:al|a\s+la|del|el)\s+(?:Nro\.?|N[°º])?\s*[\"“”']?\s*", " ", v, flags=re.I)
    v = re.sub(r"\bintersecci[oó]n(?:\s+con)?\b", " CON ", v, flags=re.I)
    v = re.sub(r"\b(?:Nro\.?|N[°º]|numeraci[oó]n|n[uú]mero)\s*(?=\d)", " ", v, flags=re.I)
    return re.sub(r"(?<=[A-Za-z])\*(?=[A-Za-z])", "U", limpiar(v)).upper()[:70]


def _lugar(t):
    """Lo que hay entre el último «en …» y «sorprendieron / la siguiente infracción»."""
    m1 = re.search(r"sorprendi\w*|notific\w*", t, re.I)
    m2 = re.search(r"infracci", t[m1.end():], re.I) if m1 else None
    if not m2:
        return _lugar_hasta(t)
    previo = t[:m1.end() + m2.start()]
    ms = [m for m in re.finditer(r"\ben\s+(?!la\s+poblaci|el\s+sector|esta\b|ese\b|momentos|el\s+lugar|el\s+veh)", previo, re.I)]
    if not ms:
        return _lugar_hasta(t)
    s = previo[ms[-1].end():]
    if len(s) > 140:
        return _lugar_hasta(t)
    s = re.split(r",?\s+(?:de\s+esta\b|personal\s+de\b|sorprendi\w*|notific\w*|comuna\s+de|la\s+siguiente)", s, 1, flags=re.I)[0]
    if not re.search(r"\d|calle|aven|avda|av\.|pasaje|ruta|camino", s, re.I):
        return _lugar_hasta(t) or limpiar(s).upper()[:70]
    s = re.sub(r"\bfrente\s+(?:al|a\s+la|del|el)\s+(?:Nro\.?|N[°º]|numeraci[oó]n|n[uú]mero)?\s*[\"“”']?\s*", " ", s, flags=re.I)
    s = re.sub(r"\b(?:altura\s+del?\s+)?(?:Nro\.?|N[°º]|numeraci[oó]n|n[uú]mero)\s*[\"“”']?\s*(?=\d)", " ", s, flags=re.I)
    s = re.sub(r"\s+con\s+(?=(?:calle|pasaje|avenida|avda|av\.|pje))", " / ", s, flags=re.I)
    s = re.sub(r"\besquina\s+(?:con\s+)?", " / ", s, flags=re.I)
    s = re.sub(r"^\W*(?:la\s+)?(?:calles?|\w{0,2}alle)\b\s*", "", s.strip(), flags=re.I)
    s = re.sub(r"^(?:la\s+|el\s+)", "", s, flags=re.I)
    return limpiar(s).upper()[:70]


def _lugar_hasta(t):
    """Redacción antigua: «concurrieron hasta Av. Picarte frente al Nro. 1211» / «por calle X de esta ciudad, frente a la numeración 950»."""
    m = re.search(r"\b(?:hasta|por)\s+(?:la\s+)?((?:calle|avenida|avda\.?|av\.?|pasaje|pje\.?|camino|ruta|costanera)\b.+?)"
                  r"(?=,?\s+(?:con\s+la\s+finalidad|sorprendi|notific|la\s+siguiente|una\s+vez)|$)", t, re.I)
    if not m:
        return ""
    s = re.sub(r",?\s+de\s+esta\s+(?:ciudad|comuna)\b,?", " ", m.group(1), flags=re.I)
    s = re.sub(r"\bfrente\s+(?:al|a\s+la|del|el)\s+(?:Nro\.?|N[°º]|numeraci[oó]n|n[uú]mero)?\s*[\"“”']?\s*", " ", s, flags=re.I)
    s = re.sub(r"\b(?:Nro\.?|N[°º]|numeraci[oó]n|n[uú]mero)\s*[\"“”']?\s*(?=\d)", " ", s, flags=re.I)
    s = re.sub(r"^(?:la\s+)?calles?\s+", "", s.strip(), flags=re.I)
    return limpiar(s).upper()[:70]


def _infraccion(t, secs):
    # La descripción citada puede contener palabras que también son rótulos,
    # como LICENCIA o VEHÍCULO. Léela completa antes de consultar las secciones.
    cita = re.search(r"\b(?:notificaron\s+al\s+infractor|si[gq]uiente\s*(?:in(?:fr|f|er)acci[oó]n\s*)?)"
                     r"(?:(?:(?:a\s+)?la\s+ley\s+de|al)\s+tr[aá]nsito\s*)?"
                     r"[.:;\s]*[\"“]\s*([^\"”]{10,450})[\"”]", t, re.I)
    if not cita:
        cita = re.search(r'\binfracci[oó]n\s+al\s+tr[aá]nsito\s*:\s*["“]\s*([^"”]{10,450})["”]', t, re.I)
    if cita:
        return limpiar(cita.group(1)).upper()
    todas = [s for r, s in secs if r.startswith("INFRACCION") and s]
    todas = [s for s in todas if not re.fullmatch(
        r"(?:A\s+LA\s+LEY\s+DE\s+TRANSITO|AL\s+TRANSITO)\W*", s, re.I)]
    v = todas[0] if todas else ""
    if not v:
        m = re.search(r"siguiente\s+infracci[oó]n\W{0,4}\s*[\"“”']?\s*(.{10,450}?)(?=\bINFRACTOR|\bREINCIDENCIA|\bDISP\.?\s*INFR|\bCITACI)",
                      re.sub(r"\s+", " ", t), re.I)
        v = m.group(1) if m else ""
    if not v:
        return ""
    v = limpiar(re.sub(r"\s+", " ", v)).strip()
    mq = re.match(r"[\"“”']\s*([^\"“”']+)", v)
    v = mq.group(1) if mq else v
    v = re.split(r"[\"“”]|\s+(?:HORA\s*:|LUGAR\s*:|NOMBRE\s+DEL\b|DISP\.?\s*INFR)", v, 1, flags=re.I)[0]
    return v.strip("\"“”' ").upper()


def _extraer_multiples_infracciones(infr_texto):
    """Detecta múltiples infracciones separadas por comas, conjunciones (y, e), puntos y comas o conectores en el texto."""
    if not infr_texto:
        return []
    texto_limpio = re.sub(r'\s+', ' ', infr_texto).strip()
    trozos = re.split(r'\s*,\s+|\s+(?:y|e)\s+|\s*;\s+', texto_limpio, flags=re.I)
    
    lista_final = []
    for t in trozos:
        limpio = t.strip(" ,.")
        if len(limpio) > 4:
            lista_final.append(limpio)
            
    return lista_final if lista_final else [infr_texto]


# Palabras que encabezan o rodean el nombre en el OCR y no forman parte de él.
_ETIQUETA_NOMBRE = re.compile(
    r"^(?:INFRACTOR(?:ES|A|AS)?(?:\s*\(A\))?|NOMBRE(?:\s+DEL?\s+INFRACTOR(?:A|ES)?)?|"
    r"(?:EL|LA|LOS|LAS)\s+INFRACTOR(?:A|ES)?|"
    r"SR\.?A?|SRA\.?|SRTA\.?|DON|DO[NÑ]A|SE[NÑ]OR(?:A|ITA)?)\s*[:.\-–—]?\s*",
    re.I)
_PARTICULA_NOM = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E", "DA", "DO", "SAN", "SANTA", "SANTO", "MC", "MAC"}
_RX_TOKEN_NOM = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ'’\-]{0,}$")


def _fin_nombre(s):
    """Posición donde termina el nombre: cédula/RUT/DNI, edad, domicilio, nacionalidad u otros datos."""
    m = re.search(
        r"\bC[eé]d(?:\.|ula)?(?:\s+(?:nacional\s+)?(?:de\s+)?ident\w*)?\b|"
        r"\bC\.?\s*N?\.?\s*I\.?\b\s*(?:Nro\.?|N[°º]|n[uú]mero)?\s*[:.\d]|"
        r"\bR\.?\s*U\.?\s*[NT]\.?\b|"
        r"\b(?:RUT|RUN|DNI|pasaporte|identificaci[oó]n)\b|"
        r"\bnacid\w+|\bfecha\s+de\s+nac|"
        r"\b\d{1,2}\s*a[ñn]os\b|\bde\s+edad\b|"
        r"\bdomicili\w+|\bSituaci[oó]n\b|"
        r"\bsexo\b|\bestado\s+civil\b|\bsolter[oa]\b|\bcasad[oa]\b|"
        r"\b(?:" + NACION + r")\w*|"
        r"\d{1,2}\s*[.,]\s*\d{3}\s*[.,]\s*\d{3}",
        s, re.I)
    return m.start() if m else None


def _tokens_nombre(bruto):
    """Queda solo con palabras de un nombre (preservando espacios correctamente entre nombres y apellidos)."""
    bruto = re.sub(r"(?<=[A-Za-z])\*(?=[A-Za-z])", "U", bruto or "")
    bruto = bruto.replace(",", " ")
    bruto = re.sub(r"[|\\/_*=~<>\[\]{}()«»“”\"']+", " ", bruto)
    toks = []
    for w in re.split(r"\s+", bruto):
        w = w.strip(" .;:`'’")
        if not w:
            continue
        w = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ'’\-]", "", w)
        if not w or not _RX_TOKEN_NOM.fullmatch(w):
            if toks:
                break
            continue
        nu = _norm(w)
        if not toks and nu in {"O", "Y", "E", "A", "I", "EL", "LA", "UN", "UNA"}:
            continue
        toks.append(w)
        if len(toks) >= 8:
            break
    while toks and _norm(toks[-1]) in _PARTICULA_NOM:
        toks.pop()
    while toks and _norm(toks[0]) in _PARTICULA_NOM and len(toks) > 2:
        toks.pop(0)
    if len(toks) < 2:
        return ""
    # Asegurar unión limpia respetando los espacios entre palabras
    return limpiar(" ".join(toks)).upper()


def _trozo_nombre(s):
    """Nombre limpio hasta el marcador de cédula/edad/domicilio, sin basura de OCR ni rótulos."""
    s = _ETIQUETA_NOMBRE.sub("", re.sub(r"^[\W\d_]+", "", s or "")).strip()
    s = _ETIQUETA_NOMBRE.sub("", re.sub(r"^[\W\d_]+", "", s)).strip()
    cut = _fin_nombre(s)
    if cut is not None:
        bruto = s[:cut]
    else:
        bruto = re.split(r"(?<!\b[A-ZÁÉÍÓÚÑ])\.(?=\s|$)", s, 1)[0]
        m = re.search(r",\s*(?:\d|\b(?:domicili|c[eé]d|r\.?u\.?[nt]|run|rut|dni)\b)", bruto, re.I)
        if m:
            bruto = bruto[:m.start()]
    return _tokens_nombre(bruto)


POR_ESCRITO = re.compile(r"^\W*" + r"\s*".join("PORESCRITO") + r"\b", re.I)


def _infractor(texto_inf):
    """-> (nombre, rut, direccion, comuna, aviso, rut_leido)"""
    s = re.sub(r"^[\W_]+", "", limpiar(texto_inf))
    if not s or POR_ESCRITO.match(s) or re.match(r"(?:ignorad|se\s+ignora|no\s+se\b|sin\s+datos)", s, re.I):
        return "", "", "", "", "", ""
    s = re.split(r"\bD[I1l]SP\.?\s*[I1l]NFR\w*|\bD[I1l]SP[O0]S[I1lÍ]C[I1l][OÓ0]N\s+[I1l]NFR\w*", s, 1, flags=re.I)[0].strip()
    nombre = _trozo_nombre(s)
    rut, leido, aviso = "", "", ""
    mr = re.search(r"(?:R\.?U\.?[NT]\.?|C\.?\s?I\.?|c[eé]d(?:ula)?\.?\s*(?:(?:nacional\s+)?de\s+)?(?:ident\w*)?|ident\w*)\.?\s*(?:Nro\.?|N[°º]|n[uú]mero)?\s*:?\s*"
                   r"(\d{1,2}\s*[.,]?\s*\d{3}\s*[.,]?\s*\d{3})\s*[-–—]\s*([\dKk])", s, re.I)
    if mr:
        leido = re.sub(r"\D", "", mr.group(1)) + "-" + mr.group(2).upper()
        if certificado.rut_ok(leido):
            rut = leido
        else:
            aviso = "El RUT del infractor (%s) no cuadra con su dígito verificador: compáralo con el parte." % leido
    elif re.search(r"\bDNI\b|pasaporte|(?:" + NACION + r")", s, re.I):
        aviso = "Infractor extranjero (sin RUT): irá con SR y su nombre."
    
    direccion, comuna = "", ""
    md = re.search(r"domicili\w+\s*:?\s*(?:en\s+)?(.+?)[\s.]*$", s, re.I)
    if md:
        d = md.group(1).strip()
        # CORRECCIÓN: Cortar estrictamente si se cola texto de secciones posteriores (como DOCUMENTOS, CITACION, OBSERVACIONES)
        d = re.split(r"\b(?:DOCUMENTOS?|OBSERVACI[OÓ]NES?|CITACI[OÓ]N|NOTIFICACI[OÓ]N|TESTIGOS?|DENUNCIANTE)\b.*$", d, flags=re.I)[0]
        
        d = re.sub(r"\bSituaci[oó]n\s+calle\b.*$", "", d, flags=re.I).strip(" .,")
        mc = re.search(r",?\s*comuna\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})$", d, re.I) \
            or re.search(r"\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})$", d) \
            or re.search(r",\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})$", d)
        if mc and not catalogo.comuna_en_sistema(limpiar(mc.group(1))):
            mc = None
        if mc:
            comuna = limpiar(mc.group(1)).upper()
            d = d[:mc.start()]
            if re.match(r"(?:LAS\s+ANIMAS|NIEBLA|ISLA\s+TEJA|COLLICO|GUACAMAYO|PUNUCAPA|CURI[NÑ]ANCO|BARRIOS\s+BAJOS|LA\s+AGUADA|SECTOR\b)", comuna):
                d = d + ", " + comuna
                comuna = ""
        d = re.sub(r"^(?:calle|pasaje\s+)?\s*", "", d.strip(), flags=re.I) if re.match(r"calle\b", d.strip(), re.I) else d
        d = re.sub(r"\bsin\s+(?:Nro\.?|N[°º]|n[uú]mero)(?!\w)\.?", "S/N", d, flags=re.I)
        d = re.sub(r"\b(?:Nro\.?|N[°º]|n[uú]mero)\s*", "", d, flags=re.I)
        direccion = limpiar(d).strip(" ,").upper()
    return nombre, rut, direccion, comuna, aviso, leido


def _vehiculo(s):
    s = re.sub(r"^\s*tipo\s*[:;]?\s+", "", _plano(s), flags=re.I)
    tipo = ""
    mt = re.match(r"(.+?)[,\s]+(?:marca|P\.?\s?P\.?\s?U\.?|patente)\b", s, re.I)
    if mt:
        tipo = limpiar(mt.group(1)).upper()
        if re.search(r"\d|^(?:PPU|P\.P\.U|PLACA|PATENTE|COLOR|MODELO|AÑO)\b", tipo):
            tipo = ""
    fin = r"(?:,|\bmodelo\b|\ba[ñn]o\b|\bcolor\b|\bP\.?\s?P\.?\s?U\b|\bpatente\b|$)"
    marca = re.search(r"marca\s+[\"“”']?(.+?)[\"“”']?\s*" + fin, s, re.I)
    modelo = re.search(r"modelo\s+[\"“”']?(.+?)[\"“”']?\s*" + fin, s, re.I)
    color = re.search(r"color\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+(?:[a-zñ]+))?)\s*(?:,|\ba[ñn]o\b|\bP\.?\s?P\.?\s?U\b|$)", s, re.I)
    anio = re.search(r"a[ñn]o\s+(\d{4})", s, re.I)
    NO_PLACA = ("NRO", "KM", "TO", "LEY", "ART", "INC", "DISP", "NO", "AO")
    RX = r"(?<![A-Z0-9])([A-Z]{2,5})\s*[-–—.]?\s*(\d{2})(?:\s*[-–—.]?\s*(\d{1,2}))?(?!\d)"
    ml = re.search(r"(?:PLACA\s+PATENTE(?:\s+UNICA)?|P\.?\s?P\.?\s?U\.?|PATENTE(?:\s+UNICA)?)\s*[:.]?\s*", s.upper())
    zona = re.sub(r"\b([A-Z]{4})0\s*-\s*(\d{2})\b", r"\1-\2", s.upper()[ml.end():]) if ml else ""
    cz = [a + b + c for a, b, c in re.findall(RX, zona) if a not in NO_PLACA]
    cands = [a + b + c for a, b, c in re.findall(RX, s.upper()) if a not in NO_PLACA]
    placa = cz[0] if cz else (cands[-1] if cands else "")
    return {"tipo": tipo, "marca": limpiar(marca.group(1)).upper() if marca else "",
            "modelo": limpiar(modelo.group(1)).upper() if modelo else "",
            "color": limpiar(color.group(1)).upper() if color else "", "anio": anio.group(1) if anio else "", "placa": placa}


def _boleta(secs):
    for nombre in ("CITACION", "OBSERVACION"):
        for r, s in secs:
            if r.startswith(nombre):
                m = re.search(r"boleta[^\d]{0,45}?(\d{4,7})|B\s*/\s*C\.?\s*(?:Nro\.?|N[°º])?\s*(\d{4,7})", s, re.I)
                if m:
                    return m.group(1) or m.group(2)
    for r, s in secs:
        if r.startswith("CITACION"):
            m = re.search(r"(?:citaci[oó]n|\w{3,6}leta)\s+(?:Nro\.?|N[°º]|n[uú]mero)\s*[:.]?\s*(\d{4,7})", s, re.I)
            if m:
                return m.group(1)
    return ""


def _boleta_texto(texto):
    t = re.sub(r"\s+", " ", texto or "")
    for rx in (r"copia\s+(?:de\s+(?:la\s+)?)?[B8][\s./\\]*[CG]\b\.?\s*(?:n[uú]mero|nro\.?|n[°º])?\s*[:.]?\s*(\d{4,7})",
               r"copia\s+(?:de\s+(?:la\s+)?)?boleta\s+de\s+\w{4,10}\s*(?:n[uú]mero|nro\.?|n[°º])?\s*[:.]?\s*(\d{4,7})",
               r"boleta\s+de\s+\w{4,10}\s*(?:n[uú]mero|nro\.?|n[°º])\s*[:.]?\s*(\d{4,7})",
               r"\w{0,3}leta\s+de\s+\w{4,10}\s*(?:n[uú]mero|nro\.?|n[°º])\s*[:.]?\s*(\d{4,7})",
               r"mediante\s+\w{3,8}\s+de\s+\w{4,10}\s+(?:n[uú]mero|nro\.?|n[°º])?\s*[:.]?\s*(\d{4,7})",
               r"(?:n[uú]mero|nro\.?|n[°º])\s*[:.]?\s*(\d{5})\s*,\s*de\s+esta\s+fecha"):
        m = re.search(rx, t, re.I)
        if m:
            return m.group(1)
    return ""


_GENERICAS = {"CARABINEROS", "CHILE", "COMISARIA", "SUBCOMISARIA", "TENENCIA", "RETEN", "PREFECTURA", "DIRECCION",
              "OFICINA", "DEPARTAMENTO", "LOCAL", "POLICIA", "INVESTIGACIONES", "MUNICIPAL", "JUZGADO", "DISTRITO",
              "SECCION", "UNIDAD", "SEGURIDAD", "PRIVADA", "TRANSITO", "TRANSPORTES", "MINISTERIO", "SERVICIO",
              "REGISTRO", "CIVIL", "VALDIVIA", "PATRULLAS", "RADIO"}
_ORDINALES = {1: ("1RA", "PRIMERA"), 2: ("2DA", "SEGUNDA"), 3: ("3RA", "TERCERA"), 4: ("4TA", "CUARTA"),
              5: ("5TA", "QUINTA"), 6: ("6TA", "SEXTA"), 7: ("7MA", "SEPTIMA"), 8: ("8VA", "OCTAVA")}


def _norm(t):
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").upper()


def _oficina(texto):
    import difflib
    from . import perfil
    cab = _norm(texto)[:700]
    corte = re.search(r"\bD[AO]Y?\s+CUENTA|\bAL\s+2\s*D?O", cab)
    cab = cab[:corte.start()] if corte and corte.start() > 25 else cab[:300]
    oficinas = perfil.oficinas_ordenadas()
    palabras_cab = re.findall(r"[A-Z]{4,}", cab)
    # En los partes impresos la unidad figura como «SUBCOM OSCAR C. GALLO».
    if re.search(r"\bOSCAR\s+(?:CRISTI\b|C\.?\s+GALLO\b)", cab):
        for _cod, desc in oficinas:
            if re.search(r"\bOSCAR\s+CRISTI\b", _norm(desc)):
                return desc, True
    for _cod, desc in oficinas:
        pal = [w for w in re.findall(r"[A-Z]{4,}", _norm(desc)) if w not in _GENERICAS and w not in ("LOS", "LAS")]
        if not pal:
            continue
        if all((w in palabras_cab) if len(w) < 6 else any(difflib.SequenceMatcher(None, p, w).ratio() >= 0.8 for p in palabras_cab)
               for w in pal):
            return desc, True
    m = re.search(r"\b(\d)\s*(?:RA|DA|ERA|TA|MA|VA|[ªº°])?\W*\s*COM", cab)
    num = int(m.group(1)) if m else next((n for n, (_, w) in _ORDINALES.items() if re.search(w + r"\s*COM", cab)), 0)
    if num in _ORDINALES:
        for _cod, desc in oficinas:
            d = _norm(desc)
            if "COMISAR" in d and any(re.search(r"\b" + o + r"\b", d) for o in _ORDINALES[num]):
                return desc, True
    return perfil.cargar().get("oficina_carabineros", ""), False


def problemas(r):
    n = 0
    n += not r["n_parte_carab"]
    n += not r["boleta"]
    n += not r["fecha_parte"]
    n += not r["infraccion_texto"]
    n += not r["lugar"]
    n += not r["hora_infraccion"]
    if r.get("tiene_vehiculo"):
        n += not PLACA_OK.fullmatch(r["placa"] or "")
    return n


def fechas_citacion_recorte(texto):
    fechas = set()
    for m in re.finditer(r"\b(?:audiencia|comparecer|citaci[oó]n)\b(?=[^\d]{0,45}(\d.{0,31}))", _plano(texto), re.I):
        fecha = _fecha_num(m[1]) or fecha_de(m[1])
        if fecha:
            fechas.add(fecha)
    return sorted(fechas)


def fecha_citacion_recorte(texto):
    fechas = fechas_citacion_recorte(texto)
    return fechas[0] if len(fechas) == 1 else ""


def parte(texto):
    t = _plano(texto)
    av = []
    secs = _secciones(t)
    m = re.search(r"Parte\s*N\w{0,4}[.,\s:*°º]*(\d{2,5})", t, re.I)
    n_parte = (m.group(1).lstrip("0") or m.group(1)) if m else ""
    fecha_parte = _fecha_cabecera(t) or _fecha_texto(t)
    m = re.search(r"(?:a\s+las|siendo,?\s+las)\s+(\d{1,2})\s*[:.;,]\s*(\d{2})", t, re.I) \
        or re.search(r"(?:a\s+las|siendo,?\s+las)\s+(\d{2})[5S](\d{2})\s*horas", t, re.I) \
        or re.search(r"\bHORA\s*:\s*\W?\s*(\d{1,2})\s*[:.]\s*(\d{2})", t, re.I)
    hora = "%d:%s" % (int(m.group(1)), m.group(2)) if m else ""
    seg_cit = _sec(secs, "CITACION", ultimo=True)
    fecha_cit = _fecha_num(seg_cit) or fecha_de(seg_cit)
    fecha_parte, anio_leido = corregir_anio(fecha_parte)
    if fecha_parte.endswith("????"):
        fecha_parte = fecha_parte[:-4] + str(_hoy().year)
    boleta = _boleta(secs) or _boleta_texto(texto)
    _of = _oficina(texto)
    infr = _infraccion(t, secs)
    
    bloques_infr = _extraer_multiples_infracciones(infr)
    
    nombre, rut, direccion, comuna, aviso_inf, rut_leido = _infractor(_sec(secs, "INFRACTOR"))
    infractores = []
    for rot, sec in secs:
        if rot.startswith("INFRACTOR") and sec:
            for trozo in re.split(r"(?<=[.])\s+(?=[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]{5,},)", limpiar(sec)):
                n_, r_, d_, c_, a_, l_ = _infractor(trozo)
                if n_:
                    infractores.append({"nombre": n_, "rut": r_, "direccion": d_, "comuna": re.sub(r"^COMUNA\s+(DE\s+)?", "", c_), "aviso": a_})
    mb = re.search(r"boleta[^\d]{0,45}?(\d{4,7}(?:\s*(?:,|y|e)\s*\d{4,7})+)", t, re.I)
    boletas = re.findall(r"\d{4,7}", mb.group(1)) if mb else []
    if len(boletas) == len(infractores) > 1:
        for x, bol in zip(infractores, boletas):
            x["boleta"] = bol
    pers = []
    for bloque in SM.personas(texto):
        x = _infractor(bloque)
        if not x[0]:
            cab = _trozo_nombre((bloque.split(",")[0] if "," in bloque else bloque))
            if cab:
                x = (cab,) + x[1:]
        if x[0]:
            pers.append(x)
    if not nombre and pers:
        nombre, rut, direccion, comuna, aviso_inf, rut_leido = pers[0]
    if len(pers) > len(infractores):
        infractores = [{"nombre": n_, "rut": r_, "direccion": d_, "comuna": re.sub(r"^COMUNA\s+(DE\s+)?", "", c_), "aviso": a_}
                       for n_, r_, d_, c_, a_, l_ in pers]
        if len(boletas) == len(infractores) > 1:
            for x, bol in zip(infractores, boletas):
                x["boleta"] = bol
    tiene_vehiculo = any(r.startswith("VEHICULO") for r, _ in secs)
    v = _vehiculo(_sec(secs, "VEHICULO")) if tiene_vehiculo else _vehiculo("")
    if tiene_vehiculo and not v["tipo"]:
        tipo_desplazado = re.search(r"\b(camioneta|autom[oó]vil|motocicleta|camión|furg[oó]n)\s*,?\s+marca\s*$",
                                    _sec(secs, "INFRACTOR"), re.I)
        if tipo_desplazado:
            v["tipo"] = tipo_desplazado[1].upper()
    if not tiene_vehiculo or not (v["placa"] or v["marca"] or v["tipo"]):
        clausula = SM.vehiculo(texto)
        if clausula:
            v2 = _vehiculo(clausula)
            if v2["placa"] or v2["marca"] or v2["tipo"]:
                tiene_vehiculo, v = True, v2
    if not n_parte:
        av.append("No pude leer el número del parte de Carabineros.")
    if not boleta:
        av.append("No pude leer el N° de la boleta; escríbelo a mano.")
    if not infr:
        av.append("No pude leer la infracción.")
    if tiene_vehiculo and not v["placa"]:
        av.append("No pude leer la patente.")
    elif v["placa"] and not PLACA_OK.fullmatch(v["placa"]):
        av.append("La patente leída (%s) no tiene un formato válido: revísala." % v["placa"])
    if not fecha_parte:
        av.append("No pude leer la fecha del parte.")
    return {
        "origen": "carab", "departamento": "CARABINEROS", "oficina": _of[0], "oficina_reconocida": _of[1], "n_parte": boleta, "n_parte_final": boleta,
        "n_parte_carab": n_parte, "boleta": boleta, "n_citacion_adjunta": "",
        "empadronado": bool(POR_ESCRITO.match(_sec(secs, "INFRACTOR"))),
        "fecha_parte": fecha_parte, "anio_leido": anio_leido, "fecha_infraccion": fecha_parte, "hora_infraccion": hora,
        "lugar": _u(_lugar_final(t)), "infraccion_texto": infr, "bloques_infraccion": bloques_infr, "tipo_vehiculo": v["tipo"], "marca": v["marca"],
        "modelo": v["modelo"], "color": v["color"], "anio": v["anio"], "placa": v["placa"],
        "tiene_vehiculo": tiene_vehiculo,
        "fecha_citacion": fecha_cit, "hora_citacion": "", "articulo": "",
        "infractores": infractores, "infractor_nombre": nombre, "infractor_rut": rut, "infractor_direccion": _u(direccion),
        "infractor_comuna": re.sub(r"^COMUNA\s+(DE\s+)?", "", comuna), "aviso_infractor": aviso_inf, "rut_leido": rut_leido,
        "avisos": av, "texto_ocr": texto,
    }
