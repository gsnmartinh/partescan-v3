"""Lectura «por significado» de un parte de Carabineros: busca cada dato por lo que ES (una persona con cédula y
domicilio, un vehículo con marca y patente, un lugar con calle y número) y no por el rótulo ni por el orden en que
viene en la hoja.  Se usa como respaldo cuando la lectura por rótulos no encuentra el dato (partes sin «INFRACTOR:»,
con las secciones en otro orden, etc.)."""
import re
import unicodedata

RUT_RX = r"\d{1,2}\s*[.,]?\s*\d{3}\s*[.,]?\s*\d{3}\s*[-–—]\s*[\dKk]"
# lo que sigue al nombre de una persona en estos partes
MARCADOR = re.compile(
    r"[,.]?\s*(?:fecha\s+de\s+nacim\w*|c[eé]d(?:ula)?\b|\d{1,2}\s+a[ñn]os\b|chilen[oa]\b|venezolan[oa]\b|peruan[oa]\b|"
    r"colombian[oa]\b|haitian[oa]\b|bolivian[oa]\b|argentin[oa]\b|ecuatorian[oa]\b|R\.?U\.?[NT]\b|"
    r"domicili\w*)", re.I)
FIN_PERSONA = re.compile(r"\b(?:DENUNCIANTE|TESTIGOS?|REINCIDENCIAS?|CITACI[OÓ]N|OBSERVACI[OÓ]N(?:ES)?|DISP\.?\s*INFR\w*|"
                         r"VEH[IÍ]CULO|LICENCIA|INFRACCI[OÓ]N)\b|\b(?:AUTOM[OÓ]VIL|STATION\s+WAGON|CAMIONETA|FURG[OÓ]N|MOTOCICLETA|"
                         r"MOTO|CAMI[OÓ]N|BUS|TAXI|JEEP)\s*,\s*MARCA\b|\b(?:PLACA\s+PATENTE|P\.?\s?P\.?\s?U\.?)\s*[:.]", re.I)
NO_NOMBRE = {"INFRACTOR", "INFRACTORES", "NOMBRE", "DEL", "DE", "LA", "EL", "LOS", "LAS", "A", "CEDULA", "CARABINEROS",
             "INFRACCION", "DENUNCIANTE", "TESTIGO", "CITACION", "VEHICULO", "LEY", "TRANSITO", "TRIBUNAL", "JUZGADO",
             "POR", "PARA", "ANTE", "SIGUIENTE", "OBSERVACION", "REINCIDENCIA", "PATENTE", "PLACA", "MARCA", "CIUDAD",
             "DESTACAMENTO", "SGTO", "CABO", "SARGENTO", "SUBOFICIAL", "ESCRITO", "DOMICILIO", "DOMICILIADO", "NRO",
             "VALDIVIA", "CHILE", "ART", "ARTICULO", "INGERIR", "ESTACIONAR", "CONDUCIR", "BEBER", "TRANSITAR", "INFRINGIR"}
TIPOS = (r"AUTOM[OÓ]VIL|STATION\s+WAGON|CAMIONETA|FURG[OÓ]N|MOTOCICLETA|MOTO|CAMI[OÓ]N|TRACTOCAMI[OÓ]N|BUS|MINIBUS|"
         r"MICROBUS|TAXI|JEEP|SEMIRREMOLQUE|CARRO|BICICLETA|SEDAN|SED[AÁ]N|SUV|VEH[IÍ]CULO")
PLACA = r"[A-Z]{2,5}\s*[-–—.]?\s*\d{2}(?:\s*[-–—.]?\s*\d{1,2})?"
FIN_VEH = r"\b(?:DENUNCIANTE|TESTIGOS?|CITACI[OÓ]N|OBSERVACI[OÓ]N|DISP\.?\s*INFR\w*|INFRACTOR|REINCIDENCIAS?|LICENCIA)\b"


def _sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").upper()


def _plano(t):
    return re.sub(r"\s+", " ", t or "").strip()


def _nombre_antes(t, pos):
    """Nombre propio que termina justo antes de t[pos]: desde el último límite («. », «: », rótulo) hasta pos."""
    ini = max(0, pos - 110)
    previo = t[ini:pos]
    cortes = [m.end() for m in re.finditer(r"[.:;]\s+|INFRACTOR(?:ES)?(?:\s*\(A\))?\s*[:;]?\s*", previo)]
    previo = previo[cortes[-1]:] if cortes else previo
    palabras = [w for w in re.split(r"[\s,]+", previo.strip(" ,.:;")) if w]
    while palabras and (_sin_acentos(palabras[0]) in NO_NOMBRE and not (len(palabras) <= 2)):
        palabras.pop(0)
    while palabras and _sin_acentos(palabras[0]).strip(".") in NO_NOMBRE and len(palabras) > 2:
        palabras.pop(0)
    if not 2 <= len(palabras) <= 7:
        return "", pos
    if any(not re.fullmatch(r"[A-Za-zÁÉÍÓÚÑáéíóúñ'’]+\.?", w) for w in palabras):
        return "", pos
    if sum(_sin_acentos(w).strip(".") in NO_NOMBRE for w in palabras) > len(palabras) // 2:
        return "", pos
    nombre = " ".join(palabras)
    return nombre, pos - len(previo.rstrip(" ,.:;")) if previo.strip() else pos


def personas(texto):
    """Lista de textos «NOMBRE, cédula…, domicilio…» de cada persona con cédula o domicilio que aparezca en el parte,
    en el orden en que aparecen. Cada uno se puede leer con extractor_carab._infractor."""
    t = _plano(texto)
    ruts = [m.start() for m in re.finditer(RUT_RX, t)]
    out = []
    for m in MARCADOR.finditer(t):
        nombre, ini = _nombre_antes(t, m.start())
        if not nombre or (out and nombre == out[-1]["nombre"]):
            continue   # los marcadores siguientes de la misma persona (cédula, domicilio…) no tienen nombre propio delante
        cerca = t[m.start():m.start() + 260]
        if not (re.search(RUT_RX, cerca) or re.search(r"domicili", cerca, re.I)):
            continue   # sin cédula ni domicilio no es un infractor (p. ej. el denunciante)
        f = FIN_PERSONA.search(t, m.end())
        fin = min(f.start() if f else len(t), m.start() + 330)
        out.append({"ini": max(ini, 0), "nombre": nombre, "fin": fin, "marc": m.start()})
    textos = []
    for i, p in enumerate(out):
        fin = min(p["fin"], out[i + 1]["ini"]) if i + 1 < len(out) else p["fin"]
        textos.append((p["nombre"] + ", " + t[p["marc"]:fin].lstrip(" ,.")).strip())
    return textos


def vehiculo(texto):
    """Cláusula del vehículo («AUTOMOVIL, MARCA TOYOTA, MODELO …, PLACA PATENTE LL-25…») aunque no tenga rótulo.
    Devuelve '' si el parte no habla de un vehículo (p. ej. los de alcohol, cuya «marca» es la de la cerveza)."""
    t = _plano(texto)
    for m in re.finditer(r"\b(?:(?:" + TIPOS + r")\b[,\s]*)?marca\b", t, re.I):
        previo = t[max(0, m.start() - 45):m.start()]
        if re.search(r"CERVEZA|LATA|BOTELLA|VINO|PISCO|LICOR|ENVASE|BEBIDA", _sin_acentos(previo)):
            continue
        fin = len(t)
        f = re.compile(FIN_VEH, re.I).search(t, m.end())
        if f:
            fin = f.start()
        ini = m.start()
        atras = re.search(r"(?:(?:" + TIPOS + r")\b[^.;]{0,30}?)?(?:PLACA\s+PATENTE|PATENTE|PLACA|P\.?\s?P\.?\s?U\.?)\W{0,12}" + PLACA + r"\W{0,3}$",
                          t[max(0, m.start() - 70):m.start()].upper())
        if atras:
            ini = max(0, m.start() - 70) + atras.start()
        clausula = t[ini:min(fin, m.start() + 300)]
        tiene_tipo = re.match(r"(?:" + TIPOS + r")\b", clausula, re.I) is not None
        tiene_placa = re.search(r"(?:PLACA|PATENTE|P\.?\s?P\.?\s?U\.?)\W{0,12}" + PLACA, clausula.upper()) is not None
        if tiene_tipo or tiene_placa or ini != m.start():
            return clausula
    # vehículo sin «marca»: «STATION WAGON PATENTE YV-8892»
    m = re.search(r"\b(?:(?:" + TIPOS + r")\b[^.;]{0,30}?)?(?:PLACA\s+PATENTE|PATENTE|P\.?\s?P\.?\s?U\.?)\W{0,12}" + PLACA, t.upper())
    if m and not re.search(r"\bLEY\b|\bART", t.upper()[max(0, m.start() - 12):m.start()]):
        return t[m.start():m.end() + 2]
    return ""


LUGAR_RX = re.compile(
    r"\b(?:en|por|hasta|sorprendi\w*\s+en)\s+(?:la\s+)?((?:calle|avenida|avda\.?|av\.?|pasaje|pje\.?|camino|ruta|costanera|diagonal)\b"
    r"(?:[^.;]|(?<=\bnro)\.|(?<=\bavda)\.|(?<=\bav)\.|(?<=\bpje)\.|(?<=\bsgto)\.|(?<=\bn)\.){3,95}?)(?=,?\s+(?:de\s+esta\b|notific\w*|sorprendi\w*|la\s+siguiente|con\s+la\s+finalidad|personal\b|a\s+cargo|"
    r"donde|lugar\s+donde|mientras|se\s+)|(?<!\bnro)(?<!\bavda)(?<!\bav)(?<!\bpje)(?<!\bsgto)(?<!\bn)[.;]|$)", re.I)
MALO = re.compile(r"TRIBUNAL|JUZGADO|DEPENDENCIAS|DESTACAMENTO|TENENCIA|COMISAR|SUBOFICIAL|SARGENTO|\bCABO\b|DENUNCIANTE|"
                  r"TESTIGO|CARABINERO|JEFE|C[EÉ]DULA|DOMICILI", re.I)


def lugar(texto):
    """Primera referencia a una calle del parte («en calle Esmeralda frente al Nro. 622»), sin depender del orden."""
    t = _plano(texto)
    for m in LUGAR_RX.finditer(t):
        v = m.group(1)
        if MALO.search(v) or not re.search(r"\d|calle|avenida|avda|av\.|pasaje|camino|ruta", v, re.I):
            continue
        return v
    return ""


def lugar_narrativo(texto):
    """La calle que aparece justo antes de «…sorprendió / notificó la siguiente infracción»: es el lugar del hecho aunque
    el resto de la hoja venga en otro orden."""
    t = _plano(texto)
    v = re.search(r"\b(?:sorprendi\w*|notific\w*)\b", t, re.I)
    if not v:
        return ""
    ventana = t[max(0, v.start() - 220):v.start()]
    buenos = []
    for m in LUGAR_RX.finditer(ventana):
        c = m.group(1)
        if not MALO.search(c) and re.search(r"\d|calle|avenida|avda|av\.|pasaje|camino|ruta|costanera", c, re.I):
            buenos.append(c)
    if buenos:
        return buenos[-1]
    # «en Cerro Cordillera s/n», «en Los Alerces 120»: sin la palabra calle/avenida
    for m in re.finditer(r"\ben\s+((?:(?!(?:la|el|los|las|esta|ese|dependencias|momentos|servicio)\b)[A-Za-zÁÉÍÓÚÑáéíóúñ.]+\s+){1,5}"
                         r"(?:s/n|\d{1,5}))\b", ventana, re.I):
        if not MALO.search(m.group(1)):
            buenos.append(m.group(1))
    return buenos[-1] if buenos else ""
