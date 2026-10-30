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
    return re.sub(r"\s+", " ", t or "")


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
    m = re.search(r"(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(20\d{2})", s)
    return "%02d/%02d/%s" % (int(m.group(1)), int(m.group(2)), m.group(3)) if m else ""


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
    v = _sec(secs, "INFRACCION", ultimo=False)
    # «…la siguiente infracción:» es el primer rótulo; si está vacío, la infracción va después de INFRACTOR
    todas = [s for r, s in secs if r.startswith("INFRACCION") and s]
    v = todas[0] if todas else ""
    if not v:
        # «…notificaron la siguiente infracción.» y después, entre comillas, lo que hizo (a veces mal escrito: «INGRINGIR»)
        m = re.search(r"siguiente\s+infracci[oó]n\W{0,4}\s*[\"“”']?\s*(.{10,450}?)(?=\bINFRACTOR|\bREINCIDENCIA|\bDISP\.?\s*INFR|\bCITACI)",
                      re.sub(r"\s+", " ", t), re.I)
        v = m.group(1) if m else ""
    if not v:
        return ""
    v = limpiar(re.sub(r"\s+", " ", v)).strip()
    mq = re.match(r"[\"“”']\s*([^\"“”']+)", v)       # si viene entre comillas, solo lo que está dentro
    v = mq.group(1) if mq else v
    v = re.split(r"[\"“”]|\s+(?:HORA\s*:|LUGAR\s*:|NOMBRE\s+DEL\b|DISP\.?\s*INFR)", v, 1, flags=re.I)[0]
    v = v.strip("\"“”' ")
    return v.upper()


def _fin_nombre(s):
    m = re.search(r"\bC[eé]d(?:ula)?\b|\bC\.?\s?I\.?\s*[:\d]|\bR\.?U\.?[NT]\.?\b|\bDNI\b|\bpasaporte\b|\bnacid\w|\bfecha\s+de\b|"
                  r"\b\d{1,2}\s+a[ñn]os\b|\bdomicili\w|\bSituaci[oó]n\b|\b(?:" + NACION + r")\w*", s, re.I)
    return m.start() if m else None


def _infractor(texto_inf):
    """-> (nombre, rut, direccion, comuna, aviso, rut_leido)"""
    s = re.sub(r"^[\W_]+", "", limpiar(texto_inf))
    if not s or re.match(r"(?:por\s+escrito|ignorad|se\s+ignora|no\s+se\b|sin\s+datos)", s, re.I):
        return "", "", "", "", "", ""
    s = re.split(r"\bDISP\.?\s*INFR\w*|\bD[I1l|]SP[O0]S[I1l|]C\w{0,3}\b", s, 1, flags=re.I)[0].strip()   # tolera «INFRINCIDA» y otros errores del OCR
    cut = _fin_nombre(s)
    nombre = limpiar((s[:cut] if cut else s.split(".")[0]).replace(",", " ")).upper()
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
        d = re.sub(r"\bSituaci[oó]n\s+calle\b.*$", "", md.group(1), flags=re.I).strip(" .,")
        mc = re.search(r",?\s*comuna\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})$", d, re.I) \
            or re.search(r"\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})$", d) \
            or re.search(r",\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,25})$", d)
        if mc and not catalogo.comuna_en_sistema(limpiar(mc.group(1))):
            mc = None          # no es una comuna (arrastró otra frase del parte): se queda en la dirección y se supone la del juzgado
        if mc:
            comuna = limpiar(mc.group(1)).upper()
            d = d[:mc.start()]
            if re.match(r"(?:LAS\s+ANIMAS|NIEBLA|ISLA\s+TEJA|COLLICO|GUACAMAYO|PUNUCAPA|CURI[NÑ]ANCO|BARRIOS\s+BAJOS|LA\s+AGUADA|SECTOR\b)", comuna):
                d = d + ", " + comuna   # es un sector, no una comuna: queda en la dirección
                comuna = ""
        d = re.sub(r"^(?:calle|pasaje\s+)?\s*", "", d.strip(), flags=re.I) if re.match(r"calle\b", d.strip(), re.I) else d
        d = re.sub(r"\bsin\s+(?:Nro\.?|N[°º]|n[uú]mero)\b\.?", "S/N", d, flags=re.I)      # «sin Nro.» -> S/N
        d = re.sub(r"\b(?:Nro\.?|N[°º]|n[uú]mero)\s*", "", d, flags=re.I)
        direccion = limpiar(d).upper().strip(" ,.")
    return nombre, rut, direccion, comuna, aviso, leido


def _vehiculo(s):
    s = re.sub(r"^\s*tipo\s*[:;]?\s+", "", _plano(s), flags=re.I)
    tipo = ""
    mt = re.match(r"(.+?)[,\s]+(?:marca|P\.?\s?P\.?\s?U\.?|patente)\b", s, re.I)
    if mt:
        tipo = limpiar(mt.group(1)).upper()
        if re.search(r"\d|^(?:PPU|P\.P\.U|PLACA|PATENTE)", tipo):
            tipo = ""
    fin = r"(?:,|\bmodelo\b|\ba[ñn]o\b|\bcolor\b|\bP\.?\s?P\.?\s?U\b|\bpatente\b|$)"
    marca = re.search(r"marca\s+[\"“”']?(.+?)[\"“”']?\s*" + fin, s, re.I)
    modelo = re.search(r"modelo\s+[\"“”']?(.+?)[\"“”']?\s*" + fin, s, re.I)
    color = re.search(r"color\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+(?:[a-zñ]+))?)\s*(?:,|\ba[ñn]o\b|\bP\.?\s?P\.?\s?U\b|$)", s, re.I)
    anio = re.search(r"a[ñn]o\s+(\d{4})", s, re.I)
    NO_PLACA = ("NRO", "KM", "TO", "LEY", "ART", "INC", "DISP", "NO", "AO")
    RX = r"(?<![A-Z0-9])([A-Z]{2,5})\s*[-–—.]?\s*(\d{2})(?:\s*[-–—.]?\s*(\d{1,2}))?(?!\d)"
    ml = re.search(r"(?:PLACA\s+PATENTE(?:\s+UNICA)?|P\.?\s?P\.?\s?U\.?|PATENTE(?:\s+UNICA)?)\s*[:.]?\s*", s.upper())
    zona = re.sub(r"\b([A-Z]{4})0\s*-\s*(\d{2})\b", r"\1-\2", s.upper()[ml.end():]) if ml else ""   # «SVTO0-76» -> SVTO-76
    cz = [a + b + c for a, b, c in re.findall(RX, zona) if a not in NO_PLACA]
    cands = [a + b + c for a, b, c in re.findall(RX, s.upper()) if a not in NO_PLACA]
    placa = cz[0] if cz else (cands[-1] if cands else "")
    return {"tipo": tipo, "marca": limpiar(marca.group(1)).upper() if marca else "",
            "modelo": limpiar(modelo.group(1)).upper() if modelo else "",
            "color": limpiar(color.group(1)).upper() if color else "", "anio": anio.group(1) if anio else "", "placa": placa}


def _boleta(secs):

    patrones = (

        # BOLETA N° 12345
        r"BOLETA[^\d]{0,80}?(\d{4,8})",

        # BOLETA DE CITACION N° 12345
        r"BOLETA[^\d]{0,80}?CITACI[OÓ0]N[^\d]{0,40}?(\d{4,8})",

        # B/C 12345
        r"\b[8B]\s*[/\\|.\-]\s*[CGO]\b[^\d]{0,40}?(\d{4,8})",

        # B C 12345
        r"\b[8B]\s+[CGO]\b[^\d]{0,40}?(\d{4,8})",

        # BC12345
        r"\b[8B][CGO]\s*(\d{4,8})",

        # BC N° 12345
        r"\b[8B][CGO]\b[^\d]{0,40}?(\d{4,8})",

        # CITACION N° 12345
        r"CITACI[OÓ0]N[^\d]{0,40}?(\d{4,8})",

        # COMPROBANTE 12345
        r"COMPROBANTE[^\d]{0,30}?(\d{4,8})",
    )

    for nombre in ("CITACION", "OBSERVACION"):
        for r, s in secs:

            if not r.startswith(nombre):
                continue

            txt = _normalizar_ocr_boleta(s)

            for rx in patrones:
                m = re.search(rx, txt, re.I)

                if m:
                    return re.sub(r"\D", "", m.group(1))

            # último recurso
            for marca in (
                "BOLETA",
                "B/C",
                "BC",
                "8/C",
                "8C",
                "CITACION",
            ):

                pos = txt.find(marca)

                if pos >= 0:
                    ventana = txt[pos:pos + 150]

                    nums = re.findall(r"\d[\d ]{3,10}", ventana)

                    if nums:
                        return re.sub(r"\D", "", nums[0])

    return ""

def _normalizar_ocr_boleta(txt):
    s = (txt or "").upper()

    # Variantes típicas OCR
    s = s.replace("Nº", "N°")
    s = s.replace("NO.", "N°")
    s = s.replace("NRO.", "N°")
    s = s.replace("NUMERO", "N°")

    return s
def _boleta_texto(texto):
    """
    Respaldo global cuando el OCR destruye
    el rótulo CITACION.
    """

    t = _normalizar_ocr_boleta(
        re.sub(r"\s+", " ", texto or "")
    )

    patrones = (

        r"BOLETA\s+DE\s+\w{4,12}\s*(?:N°)?\s*[:.]?\s*(\d{4,8})",

        r"\w{0,3}LETA\s+DE\s+\w{4,12}\s*(?:N°)?\s*[:.]?\s*(\d{4,8})",

        r"MEDIANTE\s+\w{3,10}\s+DE\s+\w{4,12}\s*(?:N°)?\s*[:.]?\s*(\d{4,8})",

        r"\b[8B]\s*[/\\|.\-]\s*[CGO]\b[^\d]{0,40}?(\d{4,8})",

        r"\b[8B][CGO]\b[^\d]{0,40}?(\d{4,8})",

        r"CITACI[OÓ0]N[^\d]{0,40}?(\d{4,8})",

        r"COMPROBANTE[^\d]{0,30}?(\d{4,8})",
    )

    for rx in patrones:
        m = re.search(rx, t, re.I)

        if m:
            return re.sub(r"\D", "", m.group(1))

    # último recurso
    for marca in (
        "BOLETA",
        "B/C",
        "BC",
        "8/C",
        "8C",
        "CITACION",
    ):

        pos = t.find(marca)

        if pos >= 0:
            ventana = t[pos:180 + pos]

            nums = re.findall(r"\d[\d ]{3,10}", ventana)

            if nums:
                return re.sub(r"\D", "", nums[0])

    return ""


# Palabras que no sirven para reconocer una unidad (aparecen en casi todos los encabezados).
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
    """Unidad de Carabineros que emite el parte, según el encabezado y la lista de oficinas de ESTE juzgado.
    Devuelve (nombre exacto de la oficina en el sistema, reconocida: bool). Si no la reconoce, la unidad por defecto."""
    import difflib
    from . import perfil
    cab = _norm(texto)[:700]
    corte = re.search(r"\bD[AO]Y?\s+CUENTA|\bAL\s+2\s*D?O", cab)   # el encabezado termina donde empieza el cuerpo
    cab = cab[:corte.start()] if corte and corte.start() > 25 else cab[:300]
    oficinas = perfil.oficinas_ordenadas()
    # 1) palabra propia de la unidad (Punucapa, Corral, Mogollones…), tolerando errores del OCR
    palabras_cab = re.findall(r"[A-Z]{4,}", cab)
    for _cod, desc in oficinas:
        pal = [w for w in re.findall(r"[A-Z]{4,}", _norm(desc)) if w not in _GENERICAS and w not in ("LOS", "LAS")]
        if not pal:
            continue
        # cada palabra propia de la unidad debe aparecer (las cortas, tal cual; las largas, tolerando errores del OCR)
        if all((w in palabras_cab) if len(w) < 6 else any(difflib.SequenceMatcher(None, p, w).ratio() >= 0.8 for p in palabras_cab)
               for w in pal):
            return desc, True
    # 2) «1ra. Comisaría», «2da. Comisaría»…
    m = re.search(r"\b(\d)\s*(?:RA|DA|ERA|TA|MA|VA|[ªº°])?\W*\s*COM", cab)
    num = int(m.group(1)) if m else next((n for n, (_, w) in _ORDINALES.items() if re.search(w + r"\s*COM", cab)), 0)
    if num in _ORDINALES:
        for _cod, desc in oficinas:
            d = _norm(desc)
            if "COMISAR" in d and any(re.search(r"\b" + o + r"\b", d) for o in _ORDINALES[num]):
                return desc, True
    return perfil.cargar().get("oficina_carabineros", ""), False


def problemas(r):
    """Cantidad de datos que faltan o salen raros (sirve para decidir si conviene releer la hoja)."""
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


def parte(texto):
    t = _plano(texto)
    av = []
    secs = _secciones(t)
    m = re.search(r"Parte\s*N\w{0,4}[.\s:*°º]*(\d{2,5})", t, re.I)
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
    nombre, rut, direccion, comuna, aviso_inf, rut_leido = _infractor(_sec(secs, "INFRACTOR"))
    infractores = []
    for rot, sec in secs:   # partes con varios infractores: uno por rótulo INFRACTOR, o varios seguidos en el mismo párrafo
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
    # respaldo «por significado»: personas con cédula/domicilio aunque no lleven el rótulo INFRACTOR o vengan fuera de lugar
    pers = [x for x in (_infractor(p) for p in SM.personas(texto)) if x[0]]
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
    if not tiene_vehiculo or not (v["placa"] or v["marca"] or v["tipo"]):
        clausula = SM.vehiculo(texto)       # vehículo sin rótulo («AUTOMOVIL, MARCA TOYOTA… PATENTE XX-99»)
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
        "fecha_parte": fecha_parte, "anio_leido": anio_leido, "fecha_infraccion": fecha_parte, "hora_infraccion": hora,
        "lugar": _u(_lugar_final(t)), "infraccion_texto": infr, "tipo_vehiculo": v["tipo"], "marca": v["marca"],
        "modelo": v["modelo"], "color": v["color"], "anio": v["anio"], "placa": v["placa"],
        "tiene_vehiculo": tiene_vehiculo,
        "fecha_citacion": fecha_cit, "hora_citacion": "", "articulo": "",
        "infractores": infractores, "infractor_nombre": nombre, "infractor_rut": rut, "infractor_direccion": _u(direccion),
        "infractor_comuna": re.sub(r"^COMUNA\s+(DE\s+)?", "", comuna), "aviso_infractor": aviso_inf, "rut_leido": rut_leido,
        "avisos": av, "texto_ocr": texto,
    }
