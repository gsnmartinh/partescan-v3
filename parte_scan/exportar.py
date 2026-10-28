"""Limpieza de datos del vehículo (placa, marca, tipo) para ingresarlos en el sistema."""
import re
import unicodedata

def sin_tildes(v):
    """Sin acentos, pero conserva la eñe (el sistema la acepta): CONCEPCIÓN -> CONCEPCION, PIÑA -> PIÑA."""
    v = unicodedata.normalize("NFD", str(v or "").replace("ñ", "\x01").replace("Ñ", "\x02"))
    v = "".join(ch for ch in v if unicodedata.category(ch) != "Mn")
    v = "".join(ch for ch in v if ord(ch) < 128 or ch == "°").replace("\x01", "ñ").replace("\x02", "Ñ")   # comillas curvas, guiones largos, etc. se descartan
    return v


def _txt(v):
    v = re.sub(r"[|\r\n\t]", " ", sin_tildes(v))
    return re.sub(r"\s+", " ", v).strip().upper()


def placa6(placa):
    """Motos: 3 letras + 2 dígitos (JHB47) o 2 letras + 3 dígitos (TV880) se escriben con 6 caracteres, agregando un 0 (JHB047, TV0880)."""
    x = re.sub(r"[^A-Z0-9]", "", str(placa or "").upper())
    m = re.fullmatch(r"([A-Z]{3})(\d{2})", x) or re.fullmatch(r"([A-Z]{2})(\d{3})", x)
    return m.group(1) + "0" + m.group(2) if m else x


DOBLES = ("MERCEDES BENZ", "LAND ROVER", "ALFA ROMEO", "GREAT WALL", "RANGE ROVER", "ASTON MARTIN", "SSANG YONG",
          "MINI COOPER", "DAIHATSU TERIOS")


def marca_limpia(m):
    """Solo la marca (TOYOTA, HONDA, NISSAN…): sin modelo, sin restos del OCR («SOTA — CITROEN» -> CITROEN)."""
    m = re.sub(r"[^A-ZÁÉÍÓÚÑ0-9 \-—–/,]", " ", _txt(m).upper())
    trozos = [t.strip() for t in re.split(r"\s*[—–/,]\s*|\s+-\s+", m) if t.strip()]
    if not trozos:
        return ""
    m = trozos[-1] if len(trozos) > 1 else trozos[0]
    for d in DOBLES:
        if m.startswith(d):
            return d
    m = m.split()[0] if m.split() else ""
    return {"REANULT": "RENAULT", "RENAUL": "RENAULT", "CITROUN": "CITROEN", "CITROEM": "CITROEN", "CHEVROLER": "CHEVROLET"}.get(m, m)


def tipo_limpio(t):
    """Lleva el tipo de vehículo a la descripción exacta de la lista del sistema (BuscaTipoVeh). Lo que el sistema no
    tiene (CAMIONETA, CAMIÓN, FURGÓN…) queda con la palabra limpia, sin restos del OCR."""
    import unicodedata
    x = unicodedata.normalize("NFD", _txt(t).upper())
    x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
    x = re.sub(r"\bP\W?P\W?U.*$", "", x)               # «MOTOCICLETA P:P:U: JHB-47»
    x = re.sub(r"[^A-Z ]", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    if not x:
        return ""
    if re.fullmatch(r"VEHICULOS?( MOTORIZADOS?)?", x):   # el parte no dice el tipo: «VEHICULO» no existe en el sistema
        return "AUTOMOVIL"
    esc, tur, par = "ESCOLAR" in x, "TURISMO" in x, "PARTICULAR" in x or "PATICULAR" in x
    if re.search(r"ST\w*\s*WAGO|STAT\w*ION|WAGON|WAGO\b", x):
        return "ST. WAGON ESCOLAR" if esc else ("STATION WAGON TURISMO" if tur else "STATION WAGON")
    if "TAXIBUS" in x:
        return "TAXIBUS PATICULAR" if par else "TAXIBUS"
    if "TAXI" in x:
        return "TAXI TURISMO" if tur else "TAXI BASICO"
    if "MICROBUS" in x:
        return "MICROBUS"
    if re.search(r"MINI\s*BUS", x):
        return "MINI BUS ESCOLAR" if esc else ("MINI BUS TURISMO" if tur else ("MINIBUS PARTICULAR" if par else "MINIBUS"))
    if re.search(r"\bBUS\b", x):
        return "BUS ESCOLAR" if esc else ("BUS RURAL" if "RURAL" in x else ("BUS PARTICULAR" if par else "BUS"))
    if "FURGON" in x and esc:
        return "FURGON ESCOLAR"
    if "SEDAN" in x:
        return "SEDÁN"
    if "AUTOM" in x:
        return "AUTOMÓVIL"
    if "CAMIONETA" in x:
        return "CAMIONETA"
    if "TRACTO" in x:
        return "TRACTOCAMIÓN"
    if "CAMION" in x:
        return "CAMIÓN"
    if "FURGON" in x:
        return "FURGÓN"
    if "MOTO" in x:
        return "MOTOS"
    if re.search(r"\bSUV\b|JEEP|TODO\s*TERRENO", x):
        return "SUV"
    if "SEMI" in x:
        return "SEMIRREMOLQUE"
    if re.search(r"CARRO|REMOLQUE|ARRASTRE", x):
        return "CARRO ARRASTRE"
    if "CASA" in x and "RODANTE" in x:
        return "CASA RODANTE"
    if "TRICICLO" in x:
        return "TRICICLOS LENTOS" if "LENTO" in x else "TRICICLO RAPIDOS"
    return x
