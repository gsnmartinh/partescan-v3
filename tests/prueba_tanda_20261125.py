"""Reproduce la importación local de la tanda sin ediciones del 25/11."""
import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from parte_scan import certificado, extractor_carab, motor, servidor


def comprobar(sesion,ocr,tesseract,informe):
    exe=Path(tesseract).resolve()
    motor.pytesseract.pytesseract.tesseract_cmd=str(exe)
    os.environ['TESSDATA_PREFIX']=str(exe.parent/'tessdata')
    with zipfile.ZipFile(sesion) as z:
        estado=json.loads(z.read('estado.json'))
    previos=estado['partes'];assert len(previos)==15 and not any(p.get('ed') for p in previos)
    nuevos=[]
    for pg,(imagen,texto,es_cert) in enumerate(servidor.paginas_ocr_movil(ocr),1):
        if es_cert:
            c=motor.leer_certificado(None,texto,imagen=imagen)
            servidor.aplicar_certificado(nuevos[-1],c,pg)
        elif motor.tipo_pagina(texto)=='carab':
            r=motor.leer_carab(None,texto,imagen=imagen)
            nuevos.append(servidor.armar_carab(r,Path(ocr).name,pg,pg))
        else:
            r=motor.leer_parte(imagen,texto,None,solo_texto=True)
            nuevos.append(servidor.armar(r,Path(ocr).name,pg,pg))
        print('Hoja',pg,'certificado' if es_cert else 'parte','leída',flush=True)
    assert len(nuevos)==15
    por_pagina={p['pagina']:p for p in nuevos}
    for a,b in zip(previos,nuevos):
        assert a['pagina']==b['pagina']
        assert (a.get('n_parte_carab') or a['folio'])==(b.get('n_parte_carab') or b['folio'])
        for k in ('fecha_parte','fecha_infraccion','hora_infraccion','fecha_citacion'):
            assert a[k]==b[k],f'{k} página {a["pagina"]}'
        if a['img_cert']:
            assert a['cert']['rut']==b['cert']['rut'],f'Conservar el RUN de página {a["pagina"]}'
    assert por_pagina[15]['placa']=='LSKC35'
    for pg,tipo in ((7,'AUTOMOVIL'),(9,'STATION WAGON'),(19,'STATION WAGON'),(21,'CAMIONETA')):
        assert por_pagina[pg]['cert']['tipo_vehiculo']==tipo
        assert not any('No pude leer el tipo' in a for a in por_pagina[pg]['cert_avisos'])
    assert por_pagina[5]['cert']['comuna']=='SANTIAGO'
    assert por_pagina[11]['cert']['marca']=='PEUGEOT'
    for pg in (1,2,3,4):assert por_pagina[pg]['hora_citacion']=='10:00'
    for pg in (2,4):
        assert por_pagina[pg]['cert']['direccion']=='LAS NUTRIAS 754'
        assert not certificado.rut_ok(por_pagina[pg]['cert']['rut'])
        assert any('dígito verificador' in a for a in por_pagina[pg]['cert_avisos'])
    assert por_pagina[3]['empadronado']
    assert por_pagina[3]['cert']['nombre']=='MOTO KFX017'
    assert [i['cod'] for i in por_pagina[3]['items']]==['38']
    for pg in (7,21):
        assert por_pagina[pg]['items'][0]['estado']=='check'
        assert 'fotografía' in por_pagina[pg]['items'][0]['nota']
    for pg,campo in ((5,'nombre'),(19,'direccion')):
        p=por_pagina[pg]
        if certificado.campo_dudoso(campo,p['cert'][campo]):
            assert campo in p['cert_campos_revisar'],'Los datos sospechosos no deben quedar como correctos'
            etiqueta={'nombre':'Nombre (certificado)','direccion':'Dirección (certificado)'}[campo]
            opciones=p['lecturas'][etiqueta]
            assert opciones[0][0]==p['cert'][campo]
            assert len(opciones)==2 and not certificado.campo_dudoso(campo,opciones[1][0])
    resultado={'referencia':'Imágenes verificadas y criterios del usuario; sesión original sin cambios.',
               'estado':dict(estado,partes=nuevos),'antes':previos}
    Path(informe).write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding='utf-8')
    print('15 partes y 10 certificados importados: patentes, tipos, modalidad, horas, avisos y criterios verificados.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sesion',required=True);p.add_argument('--ocr',required=True)
    p.add_argument('--tesseract',required=True);p.add_argument('--informe',required=True)
    a=p.parse_args();comprobar(a.sesion,a.ocr,a.tesseract,a.informe)
