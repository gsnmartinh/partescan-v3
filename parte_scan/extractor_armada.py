"""Informes de Capitanía de Puerto: separar denunciado, patrulla y citación."""
import datetime
import re

from . import extractor, extractor_carab as EC, perfil


def es_armada(texto):
    return bool(re.search(r"CAPITAN[IÍ]A\s+DE\s+PUERTO", texto or "", re.I)
                and re.search(r"ORDINARIO\s+N|POLIC[IÍ]A\s+MAR[IÍ]TIMA", texto or "", re.I))


def numero_oficio(texto):
    """Regla del juzgado: tres primeros dígitos + dos primeros tras la barra."""
    m = re.search(r"ORDINARIO\s+N[°ºo.*]?\s*([\d.]+)\s*/\s*(\d{2,3})\s*/\s*JPL\b", texto or "", re.I)
    if not m:
        return ""
    prefijo = re.sub(r"\D", "", m[1])
    return prefijo[:3] + m[2][:2] if len(prefijo) >= 3 else ""


def parte(texto):
    t = re.sub(r"\s+", " ", texto)
    r = extractor.parte("")
    avisos = []
    numero = numero_oficio(t)
    if not numero:
        avisos.append("No pude leer el N° de parte de la Armada: verifica el encabezado en la imagen.")
    # El denunciado aparece después de la constatación; la patrulla queda fuera.
    persona = re.search(r"\bla\s+Sra\.?\s*\(ita\)\s*(.+?)(?=,?\s*se\s+encontraba)", t, re.I)
    n, rut, d, c, aviso, leido = EC._infractor(persona[1] if persona else "")
    if aviso:
        avisos.append(aviso)
    if not n or not rut:
        avisos.append("Revisa la identidad de la persona denunciada en el informe de la Armada.")
    bol = re.search(r"citaci[oó]n\s+N[°º.]?\s*(\d{4,7})", t, re.I)
    citacion = re.search(r"para\s+el\s+d[ií]a\s+(.+?\bhrs?\.)", t, re.I)
    cit = citacion[1] if citacion else ""
    hc = re.search(r"a\s+las\s+(\d{1,2}:\d{2})", cit, re.I)
    hh = re.search(r"alrededor\s+de\s+las\s+(\d{1,2}:\d{2})", t, re.I)
    lugar = re.search(r'en\s+el\s+sector\s+de\s+uso\s+p[uú]blico\s+["“]([^"”]+)', t, re.I)
    cab = re.search(r"VALDIVIA,\s*[il|]?(\d{1,2})\s+([A-Z]{3})\s+(20\d{2})\b", t, re.I)
    fecha = ""
    meses = {"ENE":1,"FEB":2,"MAR":3,"ABR":4,"MAY":5,"JUN":6,"JUL":7,"AGO":8,"SEP":9,"OCT":10,"NOV":11,"DIC":12}
    if cab:
        try:
            fecha = datetime.date(int(cab[3]), meses[cab[2].upper()], int(cab[1])).strftime("%d/%m/%Y")
        except (ValueError, KeyError):
            pass
    if not fecha:
        avisos.append("Revisa la fecha del informe en el encabezado de la Armada.")
    hecho = re.search(r"patrullaje\s+efectuado\s+el\s+d[ií]a\s+(.+?),", t, re.I)
    fecha_hecho = ""
    if hecho:
        anio = re.search(r"\b20\d{2}\b", t)
        fecha_hecho = EC._fecha_texto(re.sub(r"del\s+presente\s+a[ñn]o", "de " + (anio[0] if anio else ""), hecho[1], flags=re.I))
    if fecha and fecha_hecho and datetime.datetime.strptime(fecha, "%d/%m/%Y") < datetime.datetime.strptime(fecha_hecho, "%d/%m/%Y"):
        avisos.append("La fecha del informe resulta anterior al patrullaje: revisa el encabezado en la imagen.")
    infr = re.search(r"realizando\s+(venta\s+de\s+bebida[s]?\s+alcoh[oó]lica[s]?\s+en\s+la\s+v[ií]a\s+p[uú]blica)", t, re.I)
    r.update(departamento="ARMADA", oficina=perfil.oficinas().get("40", ""), numero_armada=numero,
             n_parte_final=bol[1] if bol else "", parte_escrito=True,
             persona={"rut":rut or leido,"nombre":n,"direccion":d,"comuna":c},
             fecha_parte=fecha, fecha_infraccion=fecha_hecho, hora_infraccion=hh[1] if hh else "",
             fecha_citacion=EC._fecha_texto(cit), hora_citacion=hc[1] if hc else "",
             lugar=lugar[1].upper() if lugar else "", infraccion_texto=infr[1].upper() if infr else "",
             avisos=avisos)
    return r
