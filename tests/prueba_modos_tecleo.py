"""Prueba el motor real de lotes sin tocar ventanas ni enviar teclas."""
import ctypes
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'teclea'))
if sys.platform != 'win32':
    ctypes.windll = MagicMock()
    if not hasattr(ctypes, 'WINFUNCTYPE'):
        ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
import teclea_contextual as T

class SistemaFalso:
    def __init__(self, fallo=False):
        self.avisos = []
        self.rol_usado = '100'
        self.clicks = 0
        self.esperas = []
        self.tecleados = []
        self.fallo = fallo
    def conectar(self): pass
    def esperar_vacio(self, mensaje, vigilar=False):
        self.esperas.append(vigilar)
        if vigilar and self.fallo:
            raise T.Detener('No se confirmó el guardado')
    def teclear_parte(self, p):
        self.tecleados.append(p['n_parte'])
        self.avisos = ['Aviso de revisión']
    def chequear_avisos(self): pass
    def aceptar(self): self.clicks += 1
    def leer_id(self, i): return '101'

class Pruebas(unittest.TestCase):
    def ejecutar(self, auto, fallo=False):
        sis=SistemaFalso(fallo)
        estados=[]
        with patch.object(T, 'ESPERA_INICIO', 0), patch.object(T, 'revisar_teclas'):
            try:
                T.procesar_lote(sis,[{'n_parte':'1'},{'n_parte':'2'}],[0,1],
                               on_estado=lambda *e: estados.append(e),aceptar_auto=auto)
            except T.Detener:
                if not fallo: raise
        return sis,estados
    def test_manual(self):
        sis,estados=self.ejecutar(False)
        self.assertEqual(sis.clicks,0)
        self.assertEqual(sis.tecleados,['1','2'])
        self.assertEqual([e[1] for e in estados].count('ingresado'),2)
    def test_automatico_con_avisos(self):
        sis,estados=self.ejecutar(True)
        self.assertEqual(sis.clicks,2)
        self.assertEqual(sis.esperas,[False,True,True])
        self.assertEqual([e[1] for e in estados].count('ingresado'),2)
    def test_sin_confirmacion_no_avanza(self):
        sis,estados=self.ejecutar(True,True)
        self.assertEqual(sis.tecleados,['1'])
        self.assertEqual(estados[-1],(0,'interrumpido','No se confirmó el guardado'))
        self.assertFalse(any(e[1]=='ingresado' for e in estados))

if __name__=='__main__': unittest.main()
