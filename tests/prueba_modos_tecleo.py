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

class PruebasBoton(unittest.TestCase):
    def activar(self, foco=40, texto='&Aceptar', habilitado=True):
        sis=T.Sistema.__new__(T.Sistema)
        sis.ids={40:40}
        sis.asegurar_primer_plano=MagicMock()
        sis.chequear_avisos=MagicMock()
        sis.tecla=MagicMock()
        api=MagicMock()
        api.IsWindow.return_value=True
        api.IsWindowEnabled.return_value=habilitado
        api.IsWindowVisible.return_value=True
        with patch.object(T,'user32',api), patch.object(T,'revisar_teclas'), \
             patch.object(T,'rect',return_value=(1,1,80,30)), \
             patch.object(T,'clase',return_value='ThunderRT6CommandButton'), \
             patch.object(T,'leer',return_value=texto), patch.object(T,'dar_foco') as enfocar, \
             patch.object(T,'pausa'), patch.object(T,'foco_actual',return_value=foco):
            try:
                sis.aceptar()
            except T.Detener:
                sis.tecla.assert_not_called()
                raise
        enfocar.assert_called_once_with(40)
        sis.tecla.assert_called_once_with('{SPACE}')
        api.PostMessageW.assert_not_called()
    def test_enfocar_y_activar_una_vez(self): self.activar()
    def test_foco_incorrecto_no_activa(self):
        with self.assertRaises(T.Detener): self.activar(foco=38)
    def test_boton_incorrecto_no_activa(self):
        with self.assertRaises(T.Detener): self.activar(texto='Cancelar')
    def test_boton_inhabilitado_no_activa(self):
        with self.assertRaises(T.Detener): self.activar(habilitado=False)

if __name__=='__main__': unittest.main()
