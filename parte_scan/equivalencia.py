"""Busca, en la lista de infracciones de CUALQUIER juzgado, el código que corresponde a cada concepto del catálogo.

Cada concepto del catálogo cuenta con múltiples frases clave alternativas (regex sobre la descripción sin tildes 
y en mayúsculas) para atrapar todas las variantes posibles de redacción de los partes de Carabineros e inspectores.
"""
import re

from . import perfil

# Diccionario masivo HINTS con todos los códigos del sistema y sus variantes de redacción
HINTS = {
    # --- ESTACIONAMIENTOS Y DETENCIONES ---
    "11":  [r"COSTADO IZQUIERDO", r"LADO IZQUIERDO"],
    "13":  [r"CONTRA SENTIDO", r"SENTIDO CONTRARIO"],
    "17":  [r"DOBLE FILA", r"ESTACIONAR.*DOBLE FILA"],
    "19":  [r"SITIO PROHIBIDO", r"PROHIBIDO Y SEÑALIZADO"],
    "20":  [r"MINUSVALID", r"DISCAPACIT"],
    "21":  [r"SITIO RESERVADO SEÑALIZADO"],
    "27":  [r"TOMAR PASAJERO EN SEGUNDA FILA", r"DEJAR.*PASAJERO.*SEGUNDA FILA"],
    "39":  [r"DETENERSE SOBRE PASO PEATONAL", r"SOBRE PASO PEATONAL"],
    "42":  [r"ESTACIONAR EN CURVA"],
    "43":  [r"MENOS.*10.*ESQUINA", r"10 MTS.*ESQUINA", r"MENOS DE 10 METROS.*ESQUINA"],
    "46":  [r"DENTRO DE CRUCE", r"ESTACIONAR.*CRUCE"],
    "48":  [r"ESTACIONAR SOBRE ACERA", r"SOBRE ACERA", r"EN LA ACERA"],
    "49":  [r"ESTACIONAR SOBRE PASO PEATONAL", r"SOBRE PASO PEATONAL"],
    "52":  [r"MENOS.*10.*PARE", r"10 MTS.*SIGNO PARE"],
    "53":  [r"MENOS.*20.*PARADERO", r"20 MTS.*PARADERO"],
    "483": [r"ENTRADA Y SALIDA", r"CASA PARTICULAR", r"OBSTRUIR.*ENTRADA"],
    "492": [r"MENOS.*5.*GRIFO", r"5 MTS.*GRIFO"],
    "494": [r"MENOS.*10.*CEDA EL PASO"],
    "499": [r"AREA VERDE", r"SOBRE AREA VERDE"],
    "615": [r"ESTACIONAR.*PUENTES", r"ESTACIONAR.*TUNELES"],
    "616": [r"ESTACIONAR.*CALZADAS O BERMAS"],

    # --- MOVIMIENTO, ADELANTAMIENTOS Y SENTIDOS ---
    "1":   [r"VEHICULO ABANDONADO", r"ABANDONADO.*VIA PUBLICA"],
    "2":   [r"ADELANTAR EN LINEA CONTINUA", r"LINEA CONTINUA"],
    "3":   [r"ADELANTAR EN CRUCE"],
    "4":   [r"ADELANTAR EN CURVA"],
    "6":   [r"ADELANTAR EN PUENTE"],
    "15":  [r"CONDUCIR CONTRA SENTIDO", r"CONTRA SENTIDO DEL TRANSITO"],
    "16":  [r"SIN.*HABER OBTENIDO.*LICENCIA", r"NO HABER OBTENIDO LICENCIA"],
    "23":  [r"CAMBIAR PISTA SORPRESIVAMENTE", r"OBTRUYENDO OTRA"],
    "26":  [r"PASO PREFERENTE PEATON", r"NO RESPETAR.*PEATON"],
    "38":  [r"DESOBEDECER SEÑAL.*CARABINEROS", r"CARABINEROS", r"SEÑAL.*CARABINEROS"],
    "40":  [r"CARGA SOBREPASA ANCHO", r"ANCHO Y LARGO"],
    "41":  [r"CARGA MAL ESTIBADA"],
    "47":  [r"VIRAJE INDEBIDO EN U", r"VIRAR EN U"],
    "51":  [r"CARRERA DE AUTOS", r"CARRERAS CLANDESTINAS"],
    "63":  [r"ATENTO A LAS CONDICIONES", r"NO ESTAR ATENTO"],
    "67":  [r"NO RESPETAR SEÑALES"],
    "69":  [r"LUZ AMARILLA", r"NO RESPETAR.*AMARILLA"],
    "91":  [r"LUZ ROJA", r"SEMAFORO.*ROJA", r"NO RESPETAR.*ROJA"],
    "505": [r"VIRAR A LA IZQUIERDA.*SITIO PROHIBIDO"],
    "608": [r"SOBREPASAR.*POR LA BERMA"],
    "613": [r"PISTA IZQUIERDA.*DOS SENTIDOS"],
    "614": [r"DERECHO DE PASO"],
    "617": [r"INFRINGIR NORMAS SOBRE VIRAJE"],
    "631": [r"CRUZAR.*VIA FERREA.*NO AUTORIZADO"],
    "635": [r"MITAD IZQUIERDA DE LA CALZADA"],
    "645": [r"VIAS EXCLUSIVAS"],

    # --- VELOCIDAD ---
    "18":  [r"EXCESO VELOCIDAD ZONA URBANA", r"EXCESO.*URBANA"],
    "28":  [r"VELOCIDAD NO RAZONABLE", r"NO RAZONABLE NI PRUDENTE"],
    "29":  [r"ZONA ESCUELA", r"MAYOR VELOCIDAD.*ESCUELA"],
    "36":  [r"DISPOSITIVO VELOCIDAD.*MAL ESTADO"],
    "94":  [r"EXCESO DE VELOCIDAD", r"CONDUCIR EXCESO"],

    # --- LICENCIAS Y DOCUMENTACIÓN ---
    "7":   [r"SIN CAMBIO DOMICILIO.*LICENCIA"],
    "10":  [r"SIN PLACA PATENTE", r"FALTA PLACA PATENTE", r"SIN PPU"],
    "22":  [r"SIN LENTES", r"CONDUCIR SIN LENTES"],
    "24":  [r"BOLETA CITACION VENCIDA"],
    "32":  [r"LICENCIA DISTINTA"],
    "33":  [r"REVISION TECNICA", r"SIN REVISION TECNICA", r"VEHICULO SIN REVISION TECNICA", r"CIRCULAR SIN REVISION TECNICA"],
    "37":  [r"PERMISO CIRCULACION", r"SIN PERMISO CIRCULACION", r"VEHICULO SIN PERMISO CIRCULACION", r"CIRCULAR SIN PERMISO DE CIRCULACION"],
    "60":  [r"FECHA CONTROL VENCIDA", r"CONTROL VENCIDA", r"LICENCIA.*VENCIDA"],
    "602": [r"PERMISO PROVISORIO VENCIDO"],
    "66":  [r"CONDUCIR SIN LICENCIA", r"SIN PORTAR LICENCIA"],
    "92":  [r"SEGURO OBLIGATORIO", r"SEGURO.*VENCIDO", r"VEHICULO CON SEGURO OBLIGATORIO VENCIDO", r"VEHICULO SIN SEGURO OBLIGATORIO VIGENTE"],
    "606": [r"PLACA PATENTE OCULTA", r"OCULTAR.*PATENTE"],
    "669": [r"SIN LA PLACA PATENTE"],
    "670": [r"PATENTE OCULTA"],
    "671": [r"PPU.*GRABADA"],

    # --- ALCOHOL Y LEY DE ALCOHOLES ---
    "12":  [r"CONSUMIR ALCOHOL DENTRO VEHICULO", r"BEBER DENTRO"],
    "14":  [r"BAJO INFLUENCIA ALCOHOL", r"HASTA 0[,.]5"],
    "300": [r"BEBER.*VIA PUBLICA", r"INGERIR ALCOHOL", r"CONSUMIR ALCOHOL"],
    "301": [r"^TRANSITAR EBRIO", r"ESTADO DE EBRIEDAD", r"EBRIO EN VIA PUBLICA"],
    "86":  [r"TRANSPORTAR PERSONAS EN ESTADO DE EBRIEDAD"],
    "302": [r"ROTULO EXIGIDO POR LEY"],
    "303": [r"MENORES.*LOCAL DE ALCOHOLES"],
    "304": [r"PERSONA EBRIA.*LOCAL ALCOHOLES"],
    "305": [r"CARTEL LEY ALCOHOLES"],
    "307": [r"EXPENDER BEBIDAS ALCOHOLICAS"],
    "484": [r"CONEXION CON CASA PARTICULAR"],
    "643": [r"SIN PATENTE LOCAL ALCOHOLES"],
    "647": [r"PATENTE DISTINA A LA REQUERIDA"],
    "648": [r"VENTA CLANDESTINA.*ALCOHOL"],

    # --- CONDICIONES TÉCNICAS Y MECÁNICAS ---
    "25":  [r"MENOR 8 AÑOS.*ASIENTO DELANTERO"],
    "30":  [r"BICICLETA SOBRE ACERA"],
    "31":  [r"CONDUCIR SOBRE LA ACERA", r"TRANSITAR.*ACERA"],
    "34":  [r"SIN MALLA PROTECTORA"],
    "50":  [r"SIN EXTINTOR"],
    "58":  [r"LUCES ANTIREGLAMENTARIAS", r"^LUCES"],
    "59":  [r"LUCES DE FRENOS"],
    "61":  [r"LUCES QUE INDUCEN A ERROR", r"FOCOS NEBLINEROS"],
    "64":  [r"NEUMATICOS EN MAL ESTADO"],
    "68":  [r"RUEDA DE REPUESTO", r"SIN REPUESTO"],
    "72":  [r"BOTIQUIN REGLAMENTARIO"],
    "75":  [r"PARABRISAS", r"PARABRISAS TRIZADO"],
    "76":  [r"PARABRISAS TRASERO POLARIZADO"],
    "77":  [r"RUEDA DE REPUESTO.*MAL ESTADO"],
    "78":  [r"TRABAJOS MECANICOS EN VIA PUBLICA"],
    "79":  [r"SIN LUCES"],
    "80":  [r"SIN CASCO"],
    "81":  [r"SIN TACOGRAFO"],
    "82":  [r"SIN TUBO DE ESCAPE", r"SIN SILENCIADOR"],
    "83":  [r"SIN RUEDA DE REPUESTO"],
    "84":  [r"TAXIMETRO.*SIN FUNCIONAR"],
    "89":  [r"USO DE BOCINA INDEBIDAMENTE"],
    "97":  [r"TUBO ESCAPE ANTIRREGLAMENTARIO"],
    "482": [r"PARACHOQUE ANTIRREGLAMENTARIO"],
    "496": [r"EMISIONES DE GASES"],
    "507": [r"VENTANA EN MAL ESTADO"],
    "600": [r"ASIENTO EN MAL ESTADO"],
    "601": [r"VIDEO DE SEGURIDAD"],
    "618": [r"SISTEMA DE DIRECCION DEFICIENTE"],
    "619": [r"SISTEMA DE FRENOS DEFICIENTES"],
    "620": [r"NO BAJAR LA LUZ"],
    "622": [r"CIERROS EN MAL ESTADO"],
    "623": [r"LINEA FERREA"],
    "625": [r"TAXIMETRO SIN SELLO"],
    "626": [r"TAXIMETRO ACONDICIONADO"],
    "627": [r"PROVEER COMBUSTIBLE.*PASAJEROS"],
    "628": [r"TACOGRAFO EN MAL ESTADO"],
    "630": [r"EXCEDIENDO LOS PESOS MAXIMOS", r"EXCESO DE CARGA", r"CONDUCIR UN VEHICULO EXCEDIENDO"],
    "632": [r"PUERTAS ABIERTAS", r"PUERTAS ABIERTAS.*MOVIMIENTO"],
    "633": [r"PISADERAS"],
    "636": [r"EVADIR LA FISCALIZACION"],
    "640": [r"CINTURON DE SEGURIDAD.*BUSES"],
    "641": [r"PPU GRABADA.*VIDRIOS"],

    # --- PASAJEROS, TRANSPORTE Y OTROS ---
    "5":   [r"ABANDONAR EL RECORRIDO"],
    "8":   [r"USAR CINTURON DE SEGURIDAD", r"NO USAR CINTURON"],
    "54":  [r"HABLANDO POR CELULAR", r"TELEFONO MOVIL", r"^CELULAR"],
    "55":  [r"JUGAR EN LA VIA PUBLICA"],
    "62":  [r"ANIMALES SUELTOS", r"^ANIMALES"],
    "65":  [r"TRANSPORTE PASAJERO NO AUTORIZADO", r"MINISTRATEL"],
    "70":  [r"NEGARSE A TRASLADAR PASAJEROS"],
    "71":  [r"NO LLEVAR A CARABINERO"],
    "85":  [r"SUSTANCIAS PELIGROSAS"],
    "87":  [r"TOMAR PASAJEROS EN CRUCE"],
    "88":  [r"CARGA PELIGROSA SIN ROTULO"],
    "90":  [r"SIN HOJA DE RUTA"],
    "93":  [r"EXCESO DE CARGA", r"SOBREPESO"],
    "95":  [r"DAÑOS EN VOLCAMIENTO"],
    "96":  [r"OFRECER HOSPEDAJE"],
    "485": [r"PASAJEROS DE PIE"],
    "486": [r"PEATON NO RESPETA"],
    "487": [r"PERSONAS EN ZONA DE CARGA"],
    "488": [r"CARGA/DESCARGA EN HORARIO NO AUTORIZADO"],
    "503": [r"COMERCIO AMBULANTE", r"AMBULANTE"],
    "508": [r"TARJETA DE IDENTIFICACION"],
    "509": [r"NOMINA PASAJEROS"],
    "609": [r"ENTREGAR VEHÍCULO A PERSONA SIN REQUISITOS"],
    "629": [r"TRANSPORTE DE PASAJEROS O CARGA"],
    "634": [r"JUNTO A LA ACERA AL TOMAR O DEJAR"],
    "637": [r"ARROJAR.*CIGARRILLOS"],
    "638": [r"DISPOSITIVOS ESPECIALES.*EMERGENCIA"],
    "649": [r"FACILITAR VEHICULO A QUIEN NO POSEE"],

    # --- ACCIDENTES, DAÑOS Y OTROS ---
    "56":  [r"LESIONES LEVES EN ATROPELLO"],
    "57":  [r"DAÑOS EN COLISION", r"COLISION"],
    "500": [r"DAÑOS EN CHOQUE", r"CHOQUE"],
    "639": [r"CAUSA PRINCIPAL DE UN ACCIDENTE"],
    
    # --- LEYES ESPECIALES Y MUNICIPALES ---
    "350": [r"RUIDOS? MOLESTOS?"],
    "400": [r"DS\.? 93", r"VIGILANCIA PRIVADA"],
    "420": [r"LEY 19\.?496", r"CONSUMIDOR"],
    "450": [r"LEY DE BOSQUES", r"20\.?283", r"CONAF"],
    "461": [r"ESPECIES ABANDONADAS"],
    "470": [r"RECLAMACION", r"RECLAMACIONES"],
    "480": [r"LOCAL SIN PATENTE", r"SIN PATENTE MUNICIPAL"],
    "481": [r"ESCOMBROS EN LA VIA PUBLICA"],
    "489": [r"AFICHE EN LA VIA PUBLICA"],
    "490": [r"INDEMNIZACION DE PERJUCIO"],
    "491": [r"ORDEN DE ALLANAMIENTO"],
    "493": [r"MEDIO AMBIENTE", r"ORDENANZA LOCAL"],
    "495": [r"HORARIO DE VEDA"],
    "497": [r"CONSTRUCCION AMPLIACION SIN PERMISO"],
    "498": [r"FOLLETERIA"],
    "501": [r"QUEMA SIN AUTORIZACION"],
    "502": [r"LEY 18\.?700", r"PROPAGANDA ELECTORAL"],
    "504": [r"PATENTE A LA VISTA"],
    "506": [r"PEGATINA AFICHES"],
    "603": [r"LEY DEL TABACO"],
    "604": [r"ESPACIO NO AUTORIZADO EN B\.?N\.?U\.?P"],
    "605": [r"AGUAS LLUVIAS"],
    "610": [r"INSPECTOR FISCAL"],
    "611": [r"TOMARSE LOS CONDUCTORES DE MOTOCICLETAS"],
    "642": [r"ELECTOR QUE NO SUFRAGO"],
    "644": [r"DEMANDA LEY 20009"],
    "646": [r"LEY CHOLITO"],
    "667": [r"VOCAL MESA"],
    "668": [r"COLEGIO ESCRUTADOR"],

    # --- PREFIXES MIGR / OTROS ---
    "Mig1":  [r"FALTAS AL CODIGO PENAL"],
    "Mig2":  [r"INF\.? LEY DE TRANSITO"],
    "Mig3":  [r"ORDENANZAS MUNICIPALES"],
    "Mig5":  [r"SERV\.? NAC\.? CONSUMIDOR"],
    "Mig6":  [r"LEY DE ALCOHOLES"],
    "Mig7":  [r"LEY ELECTORAL"],
    "Mig8":  [r"RENTAS MUNICIPALES"],
}


def _toks(s):
    return {w[:5] for w in re.findall(r"[A-Z0-9]+", perfil.sin_tildes(s)) if len(w) >= 3}


def _afinidad(a, b):
    A, B = _toks(a), _toks(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def candidatos(abrev, texto_concepto, lista=None):
    """[(codigo, descripcion, puntaje, hit)] ordenados de mejor a peor para un concepto del catálogo."""
    lista = lista if lista is not None else perfil.infracciones()
    
    patterns = HINTS.get(abrev, [])
    if isinstance(patterns, str):
        patterns = [patterns]
        
    out = []
    for c, d in lista.items():
        dn = " ".join(perfil.sin_tildes(d).split())
        hit = any(bool(re.search(pat, dn, re.I)) for pat in patterns) if patterns else False
        puntaje = _afinidad(texto_concepto, d) + (2.0 if hit else 0.0)
        out.append((c, d, puntaje, hit))
        
    out.sort(key=lambda z: -z[2])
    return [(c, d, round(s, 2), hit) for c, d, s, hit in out[:6]]


def sugerir(abrev, texto_concepto, lista=None):
    """(codigo, estado, nota, [candidatos]) · Estado «ok» cuando hay un hit claro en la lista dada."""
    lista = lista if lista is not None else perfil.infracciones()
    cand = candidatos(abrev, texto_concepto, lista)
    con_frase = [z for z in cand if z[3]]
    
    if con_frase:
        c, d, s, _ = con_frase[0]
        return c, "ok", "%s · %s" % (c, d), cand
    elif cand and cand[0][2] >= 0.3:
        c, d, s, _ = cand[0]
        return c, "ok", "%s · %s" % (c, d), cand
        
    if len(con_frase) > 1:
        c, d, s, _ = con_frase[0]
        otros = " · ".join("%s %s" % (z[0], z[1]) for z in con_frase[1:3])
        return c, "ok", "Hay varias parecidas: elegí %s · %s. También: %s" % (c, d, otros), cand
        
    return cand[0][0] if cand else "", "check", "Revisar opciones", cand
