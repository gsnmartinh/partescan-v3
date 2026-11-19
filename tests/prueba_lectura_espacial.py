"""Regresiones de coordenadas OCR, calidad y fechas."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
from parte_scan import lectura, extractor, motor

class Lectura(unittest.TestCase):
    def test_importa_coordenadas_y_archivos_anteriores(self):
        import io, json, tempfile, zipfile
        from parte_scan import servidor
        image = Image.new('RGB', (100, 100), 'white')
        photo = io.BytesIO()
        image.save(photo, 'JPEG')
        for metadata in ([], [{'texto': 'DOY CUENTA', 'caja': [.1,.2,.8,.3]}]):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'prueba.psocr'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('ocr.json', json.dumps([{'texto':'DOY CUENTA', 'certificado':False, 'lineas':metadata}]))
                    archive.writestr('0.jpg', photo.getvalue())
                pages = list(servidor.paginas_ocr_movil(str(path)))
                self.assertEqual(len(pages), 1)
                self.assertEqual(pages[0][0].info['ocr_lineas'], metadata)
                self.assertEqual(pages[0][1], 'DOY CUENTA')

    def test_datos_presentes_pero_invalidos(self):
        self.assertFalse(lectura.valido('fecha_parte', '31/02/2026'))
        self.assertFalse(lectura.valido('nombre', 'DATOS DEL PROPIETARIO'))
        self.assertFalse(lectura.valido('placa', 'BCEF12'))
        self.assertTrue(lectura.valido('nombre', 'MARIA PEREZ'))
        self.assertEqual(extractor.fecha_de('31 DE FEBRERO DE 2026'), '')
        self.assertEqual(extractor.hora_de('a las 9:30'), '09:30')

    def test_filas_con_rotulos_y_valores_separados(self):
        lines = lectura.lineas_espaciales([
            {'texto':'01 DE OCTUBRE DE 2026', 'caja':[.4,.51,.8,.55]},
            {'texto':'Doy cuenta a US.', 'caja':[.1,.5,.35,.55]},
            {'texto':'CITACION', 'caja':[.1,.85,.4,.9]},
            {'texto':'inválida', 'caja':[-1,0,1,1]}])
        text = lectura.ordenar_lineas(lines)
        self.assertTrue(text.startswith('Doy cuenta a US. 01 DE OCTUBRE DE 2026'))
        image = Image.new('L', (1000, 1000))
        image.info['ocr_lineas'] = lines
        zone = motor.zona_por_etiqueta(image, r'Doy\s+cuenta')
        self.assertLess(zone.height, 300)
        self.assertEqual(motor.preparar(image).info['ocr_lineas'], lines)

    def test_no_premia_ruido_repetido(self):
        good = 'DATOS DEL PROPIETARIO Nombre MARIA PEREZ DOMICILIO LOS ROBLES 123'
        self.assertGreater(lectura.puntaje(good), lectura.puntaje('BASURA '*1000))

if __name__ == '__main__': unittest.main()
