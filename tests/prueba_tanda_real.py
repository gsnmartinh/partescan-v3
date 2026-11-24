"""Regresión contra correcciones reales del usuario. No contiene documentos ni datos personales."""
import argparse,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from parte_scan import catalogo,extractor_mtt,extractor_carab

def comprobar(sesion, ocr=None):
    with zipfile.ZipFile(sesion) as paquete:
        partes=json.loads(paquete.read('estado.json'))['partes']
        textos=json.loads(paquete.read('textos.json'))
    if ocr:
        with zipfile.ZipFile(ocr) as paquete:
            hojas=json.loads(paquete.read('ocr.json'))
        textos={str(p['id']):hojas[p['pagina']-1]['texto'] for p in partes}
    resultados=[]
    for pagina in (p["pagina"] for p in partes):
        parte=next(p for p in partes if p['pagina']==pagina)
        assert parte['archivo']=='ParteScan-20261123-121740.psocr', 'La sesión no es la tanda de referencia'
        items=parte['items'] or [{}]
        esperados=[str(parte.get('ed',{}).get(f'Infracción {i+1} · código',item.get('cod',''))) for i,item in enumerate(items)]
        if pagina==21:
            # Confirmación posterior del usuario: la tercera luz de freno corresponde al 59.
            esperados=['59']
        datos=extractor_mtt.parte(textos[str(parte['id'])]) if parte['origen']=='mtt' else {'infracciones':[extractor_carab.parte(textos[str(parte['id'])])['infraccion_texto']]}
        obtenidos=[]
        for bloque in datos['infracciones']:
            for item in catalogo.resolver_o_comodin(bloque)[1]:
                if str(item['cod']) not in obtenidos:obtenidos.append(str(item['cod']))
        resultados.append({'pagina':pagina,'esperados_corregidos_por_usuario':esperados,'obtenidos':obtenidos,'acierto':set(esperados)==set(obtenidos),'referencia':'confirmación posterior del usuario' if pagina==21 else 'sesión corregida'})
    from parte_scan import servidor
    escolar=next(p for p in partes if p['pagina']==17)
    lectura=extractor_mtt.parte(textos[str(escolar['id'])])
    armado=servidor.armar_mtt(lectura,escolar['archivo'],17,17)
    assert [i['cod'] for i in armado['items']]==['67']
    assert all(catalogo._literal(bloque) in armado['causa'] for bloque in lectura['infracciones']), 'La descripción debe conservar ambos hechos'
    parte=next(p for p in partes if p['pagina']==26)
    referencia=parte['infractores'][0]
    datos=extractor_carab.parte(textos[str(parte['id'])])
    # El usuario confirmó que esta causa corresponde al primer infractor de la sesión.
    resultados.append({'pagina':26,'esperados_corregidos_por_usuario':['un infractor: el confirmado por el usuario'],
                       'obtenidos':[len(datos['infractores'])],
                       'acierto':len(datos['infractores'])==1 and datos['infractores'][0]['rut']==referencia['rut']})
    return resultados

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sesion',required=True);parser.add_argument('--informe');parser.add_argument('--ocr')
    args=parser.parse_args();resultados=comprobar(args.sesion,args.ocr)
    if args.informe:Path(args.informe).write_text(json.dumps(resultados,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in resultados:print('Página',r['pagina'],'correcto' if r['acierto'] else 'FALLO',r['obtenidos'],'esperado',r['esperados_corregidos_por_usuario'])
    sys.exit(0 if all(r['acierto'] for r in resultados) else 1)
