"""Formato breve del lugar del hecho; conserva cruces y numeración."""
import re

LIMITE_LUGAR = 30


def compactar_lugar(valor):
    texto = re.sub(r'\s+', ' ', str(valor or '')).strip(' ,.;').upper()
    texto = re.sub(r"\b[O0]\s*['’‘´`ʼ]?\s*HIGGINS\b", 'OHIGGINS', texto)
    texto = re.sub(r'\bHERNANDE\s+Z\b', 'HERNANDEZ', texto)
    texto = re.sub(r'\bESQ(?:UINA)?\.?\s*(?:CON\s+)?|\bINTERSECCI[ÓO]N\s+(?:CON\s+)?', 'CON ', texto)
    texto = re.sub(r'\s+/\s+', ' CON ', texto)
    texto = re.sub(r'\s*,?\s+CON\s+', ' CON ', texto)
    texto = re.sub(r'\b(?:NRO\.?|N[°º]|N[ÚU]MERO|NO\.)\s*(?=\d)', '', texto)
    texto = re.sub(r',?\s+(?:DE\s+(?:LA\s+)?(?:CIUDAD|COMUNA)\s+DE\s+|COMUNA\s+DE\s+)?VALDIVIA[ ,.;]*$', '', texto)
    # En un cruce ya identificado, el sector es información secundaria.
    if ' CON ' in texto:
        texto = re.split(r',\s*(?:SECTOR\b|DE LA COMU)', texto)[0]
    tramos = []
    for tramo in texto.split(' CON '):
        tramo = tramo.strip(' ,.;')
        avenida_alemania = bool(re.match(r'^(?:AVENIDA|AVDA\.?|AV\.?)\s+ALEMANIA\b', tramo))
        tramo = re.sub(r'^(?:(?:CALLE|AVENIDA|AVDA\.?|AV\.?)\s+)+', '', tramo)
        tramo = re.sub(r'^ARTURO\s+PRATT?\b', 'PRAT', tramo)
        if avenida_alemania:
            tramo = 'AV ' + tramo
        tramos.append(tramo)
    resultado = ' CON '.join(tramos).strip()
    if len(resultado) > LIMITE_LUGAR:
        # Iniciales de nombres presentes en la tanda real, conservando el apellido.
        iniciales = {'ERNESTO RIQUELME': 'E RIQUELME', 'CAMILO HENRÍQUEZ': 'C HENRÍQUEZ',
                     'CAMILO HENRIQUEZ': 'C HENRIQUEZ', 'CLEMENTE ESCOBAR': 'C ESCOBAR',
                     'TORIBIO MEDINA': 'T MEDINA'}
        for nombre, breve in iniciales.items():
            resultado = re.sub(r'\b' + re.escape(nombre) + r'\b', breve, resultado)
    return re.sub(r'\s+', ' ', resultado).strip(' ,.;')
