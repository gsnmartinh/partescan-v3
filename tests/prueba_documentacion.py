"""Regresión de descripción agrupada; conserva los tres códigos de ingreso."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
with tempfile.TemporaryDirectory() as tmp:
    os.environ['PARTESCAN_PERFIL'] = tmp
    from parte_scan import catalogo

    for texto, estado in [
        ('SIN PERMISO DE CIRCULACION, SEGURO OBLIGATORIO Y REVISION TECNICA', 'SIN LA TOTALIDAD'),
        ('PERMISO DE CIRCULACION, SOAP Y REVISION TECNICA VENCIDOS', 'CON LA TOTALIDAD'),
        ('sin permiso, seguro y revisión', 'SIN LA TOTALIDAD'),
        ('permiso, seguro y revisión vencidos', 'CON LA TOTALIDAD'),
        ('revisión técnica, seguro y permiso de circulación caducados', 'CON LA TOTALIDAD'),
        ('SIN PERMISO DE\nCIRCULACION, SEGURO Y REVISION\nTECNICA', 'SIN LA TOTALIDAD'),
    ]:
        descripcion, items = catalogo.resolver(texto)
        assert estado in descripcion, (texto, descripcion)
        assert {i['cod'] for i in items} == {'92', '37', '33'}, (texto, items)
    descripcion, items = catalogo.resolver('SIN SEGURO, PERMISO DE CIRCULACION Y REVISION TECNICA VENCIDOS')
    assert 'TOTALIDAD' not in descripcion
    descripcion, _ = catalogo.resolver('SEGURO VIGENTE, PERMISO DE CIRCULACION Y REVISION TECNICA VENCIDOS')
    assert 'TOTALIDAD' not in descripcion
    assert catalogo.resumen_documentacion('DOCUMENTOS VENCIDOS', items)
    assert not catalogo.resumen_documentacion('DOCUMENTOS VENCIDOS', items + [{'cod': '19'}])
print('Documentación: sin, vencida, abreviada, saltos de línea y estados mixtos OK')
