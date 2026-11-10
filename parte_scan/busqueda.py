"""Segunda lectura local de un campo, con el recorte usado como evidencia."""
import base64
import io
import re
from collections import defaultdict

from . import catalogo, certificado, extractor, extractor_carab, extractor_mtt, exportar, motor

IDENTIDAD = {"rut", "nombre", "direccion", "comuna"}
CAMPOS = IDENTIDAD | {"placa", "fecha_parte", "fecha_infraccion", "hora_infraccion", "descripcion"}


def sugerir_infracciones(texto, origen):
    if origen == "carab":
        datos = extractor_carab.parte(texto)
    elif origen == "mtt":
        datos = extractor_mtt.parte(texto)
    elif origen == "dom":
        datos = extractor.parte_dom(texto)
    elif extractor.es_os10(texto):
        datos = extractor.parte_os10(texto)
    else:
        datos = extractor.parte(extractor.completar_lineas_movil(texto))
    principal = datos.get("infraccion_texto", "")
    bloques = datos.get("infracciones") or [principal, *datos.get("bloques_infraccion", [])]
    sugerencias = {}
    for bloque in bloques:
        if not bloque:
            continue
        _, items = catalogo.resolver(bloque)
        for item in items:
            codigo = str(item["cod"])
            if codigo.isdigit():
                sugerencias.setdefault(codigo, {"codigo": codigo, "texto": bloque})
    return {"texto": principal, "codigos": list(sugerencias.values())}


def releer_descripcion(origen, fuentes):
    for _, imagen, texto in fuentes:
        if imagen is not None:
            nuevo = sugerir_infracciones(motor.releer_franja(motor.preparar(imagen), 0, 1), origen)
            if nuevo["texto"] or nuevo["codigos"]:
                return dict(nuevo, fuente="Segunda lectura del parte")
        return dict(sugerir_infracciones(texto, origen), fuente="Lectura original del parte")
    return {"texto": "", "codigos": [], "fuente": ""}


def extraer(texto, campo, origen, es_certificado):
    if not texto.strip():
        return ""
    if es_certificado:
        valor = certificado.leer(texto).get(campo, "")
    elif origen == "mtt":
        dato = "infractor_" + campo if campo in IDENTIDAD else campo
        valor = extractor_mtt.parte(texto).get(dato, "")
    elif origen == "carab":
        dato = "infractor_" + campo if campo in IDENTIDAD else campo
        valor = (extractor_carab.parte(texto) or {}).get(dato, "")
    elif campo == "fecha_parte":
        valor = extractor.fecha_documento(texto)
    elif campo in {"fecha_infraccion", "hora_infraccion"}:
        fecha, hora = extractor.momento_infraccion(texto.splitlines())
        valor = fecha if campo == "fecha_infraccion" else hora
    else:
        if origen == "dom":
            datos = extractor.parte_dom(texto)
        elif extractor.es_os10(texto):
            datos = extractor.parte_os10(texto)
        else:
            datos = extractor.parte(texto)
        valor = datos.get("persona", {}).get(campo, "") if campo in IDENTIDAD else datos.get(campo, "")
    valor = str(valor or "").strip().upper()
    if campo == "rut":
        valor = valor.replace(".", "").replace(" ", "")
        return valor if certificado.rut_ok(valor) else ""
    if campo == "placa":
        valor = exportar.placa6(valor)
        return valor if extractor.placa_ok(valor) else ""
    if campo == "hora_infraccion" and ":" in valor:
        valor = valor.zfill(5)
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", valor):
            return ""
    return valor


def recorte_del_valor(zona, valor, campo):
    """Ubica una coincidencia única; si es ambigua, deja visible la zona."""
    ocr = motor.pytesseract
    try:
        datos = ocr.image_to_data(zona, lang="spa", config="--psm 6", output_type=ocr.Output.DICT, timeout=15)
    except (ocr.TesseractNotFoundError, ocr.TesseractError, RuntimeError):
        return zona, False
    lineas = defaultdict(list)
    for i, palabra in enumerate(datos["text"]):
        if palabra.strip():
            clave = tuple(datos[k][i] for k in ("block_num", "par_num", "line_num"))
            lineas[clave].append(i)

    def clave(texto):
        return re.sub(r"[^A-Z0-9]", "", catalogo.sin_tildes(texto.upper()))

    buscado = clave(valor)
    if campo == "hora_infraccion":
        buscado = buscado.lstrip("0")
    coincidencias = [
        indices for indices in lineas.values()
        if buscado and buscado in clave(" ".join(datos["text"][i] for i in indices))
    ]
    if len(coincidencias) != 1:
        return zona, False
    indices = coincidencias[0]
    arriba = min(datos["top"][i] for i in indices)
    abajo = max(datos["top"][i] + datos["height"][i] for i in indices)
    margen = max(12, abajo - arriba)
    return zona.crop((0, max(0, arriba - margen), zona.width, min(zona.height, abajo + margen))), True


def buscar(campo, origen, fuentes):
    resultados = {}
    for fuente, imagen, texto in fuentes:
        es_certificado = fuente == "Certificado"
        if imagen is not None:
            gris = motor.preparar(imagen)
            if campo == "fecha_parte":
                inicio, fin = 0, 0.32
            elif campo in {"fecha_infraccion", "hora_infraccion"}:
                inicio, fin = (0.18, 0.48) if origen == "inspeccion" else (0, 0.64)
            else:
                inicio, fin = 0, 1
            lectura = motor.releer_franja(gris, inicio, fin)
            valor = extraer(lectura, campo, origen, es_certificado)
            if valor:
                recorte = gris.crop((0, int(gris.height * inicio), gris.width, int(gris.height * fin)))
                recorte, preciso = recorte_del_valor(recorte, valor, campo)
                recorte.thumbnail((1200, 1200))
                salida = io.BytesIO()
                recorte.save(salida, "JPEG", quality=85)
                resultados.setdefault((valor, fuente), {
                    "valor": valor, "fuente": fuente,
                    "imagen": base64.b64encode(salida.getvalue()).decode("ascii"),
                    "zona": "Línea leída" if preciso else "Zona releída",
                })
        valor = extraer(texto, campo, origen, es_certificado)
        if valor:
            resultados.setdefault((valor, fuente), {"valor": valor, "fuente": fuente})
    return list(resultados.values())
