"""Regresiones de edición de tandas: HTTP, persistencia y reconocimiento móvil."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['PARTESCAN_PERFIL'] = tempfile.mkdtemp()
from PIL import Image
from parte_scan import exportar, servidor, tipos_vehiculo

CERT = '''REPUBLICA DE CHILE
EXTRACTO DE INSCRIPCION EN EL R.V.M.
Inscripción ABCD.12-3
DATOS DEL VEHICULO
Tipo Vehiculo CAMIONE TA Año : 2020
Marca TOYOTA
Modelo HILUX
DATOS DEL PROPIETARIO
Nombre PERSONA DE PRUEBA
R.U.N. 11.111.111-1
Domicilio CALLE PRUEBA 123
Comuna VALDIVIA
Fec. adquisición: 01-01-2020
'''

def parte(pid):
    return dict(id=pid, img_cert=0, placa='ABCD12', marca='', tipo_vehiculo='',
                cert={}, cert_avisos=['Falta certificado'], ed={'Lugar': 'CORREGIDO'},
                ok={}, done={}, fin=False, avisos=[], folio=str(pid))

class Edicion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = servidor.ThreadingHTTPServer(('127.0.0.1', 0), servidor.H)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join()

    def setUp(self):
        servidor.PARTES[:] = [parte(1), parte(2)]
        servidor.IMAGENES.clear()
        servidor.IMAGENES.update({i: Image.new('RGB', (10,10)) for i in (1,2,3)})
        servidor.TEXTOS.clear(); servidor.TEXTOS[2] = CERT
        servidor.ESTADO['pendientes'] = 0

    def post(self, parts, cert=None):
        request = Request('http://127.0.0.1:%d/api/tanda/editar' % self.http.server_port,
                          data=json.dumps(dict(partes=parts, certificado=cert)).encode())
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_reorder_delete_restore_and_session(self):
        original = copy.deepcopy(servidor.PARTES)
        self.assertEqual(self.post(original[::-1])[0], 200)
        self.assertEqual([p['id'] for p in servidor.PARTES], [2,1])
        self.assertEqual(self.post([original[0]])[0], 200)
        self.assertEqual(self.post(original)[0], 200)
        self.assertEqual(servidor.PARTES[0]['ed']['Lugar'], 'CORREGIDO')
        data = servidor.armar_sesion(dict(partes=servidor.PARTES))
        servidor.TEXTOS.clear()
        loaded = servidor.cargar_sesion(data)
        self.assertEqual(len(loaded['partes']), 2)
        self.assertEqual(servidor.TEXTOS[2], CERT)
        self.assertEqual(self.post([])[0], 200)
        self.assertEqual(self.post(original)[0], 200)

    def test_certificate_is_not_an_independent_part(self):
        status, result = self.post(servidor.PARTES, [2,1])
        self.assertEqual(status, 200, result)
        self.assertEqual(len(result['partes']), 1)
        receiver = result['partes'][0]
        self.assertEqual(receiver['img_cert'], 2)
        self.assertEqual(receiver['cert']['tipo_vehiculo'], 'CAMIONETA')
        third = parte(3)
        status, result = self.post([receiver, third], [1,3])
        self.assertEqual(status, 200, result)
        self.assertEqual(result['partes'][0]['img_cert'], 0)
        self.assertEqual(result['partes'][0]['cert'], {})
        self.assertEqual(result['partes'][1]['img_cert'], 2)

    def test_bad_edits_and_busy_are_rejected(self):
        for parts in ([parte(99)], [parte(1), parte(1)]):
            self.assertEqual(self.post(parts)[0], 400)
        servidor.ESTADO['pendientes'] = 1
        self.assertEqual(self.post([])[0], 400)
        servidor.ESTADO['pendientes'] = 0
        with patch.object(servidor.tecleador, 'corriendo', return_value=True):
            self.assertEqual(self.post([])[0], 400)
        self.assertEqual(len(servidor.PARTES), 2)

    def test_vehicle_types(self):
        for t in tipos_vehiculo.TIPOS:
            self.assertEqual(exportar.tipo_limpio(t), t)
        for text, expected in [('CAMIONE TA','CAMIONETA'), ('AUTOMÓVIL','AUTOMOVIL'),
                               ('STATION WAG0N','STATION WAGON'), ('TRACTOCAMIÓN','TRACTOCAMION'),
                               ('TIPO DESCONOCIDO','TIPO DESCONOCIDO')]:
            self.assertEqual(exportar.tipo_limpio(text), expected)

    def test_mobile_false_certificate_flag(self):
        # El certificado siguiente venía marcado false en los archivos afectados.
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'prueba.psocr'
            photo = io.BytesIO(); Image.new('RGB',(10,10)).save(photo,'JPEG')
            with zipfile.ZipFile(source,'w') as z:
                z.writestr('ocr.json',json.dumps([dict(texto='DENUNCIO N° 123456',certificado=False),dict(texto=CERT,certificado=False)]))
                for i in range(2): z.writestr('%d.jpg'%i,photo.getvalue())
            servidor.PARTES.clear(); servidor.IMAGENES.clear()
            with patch.object(servidor.motor,'leer_parte',return_value={}), patch.object(servidor,'armar',side_effect=lambda r,a,n,i: parte(i)):
                worker=threading.Thread(target=servidor.trabajador,daemon=True);worker.start()
                servidor.ESTADO['pendientes']=1
                servidor.COLA.put((str(source),'prueba.psocr'))
                import time
                deadline=time.monotonic()+5
                while servidor.ESTADO['pendientes'] and time.monotonic()<deadline: time.sleep(.02)
            self.assertEqual(servidor.ESTADO['pendientes'],0)
            self.assertEqual(len(servidor.PARTES),1)
            self.assertEqual(servidor.PARTES[0]['img_cert'],2)

if __name__ == '__main__': unittest.main()
