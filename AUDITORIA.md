# Auditoría de mantenimiento — 2 de noviembre de 2026

Base revisada: `2b288bbe04d70dcb511786d0d713f4b89401f314` (`main`).

## Limpieza aplicada

- Retirar del índice 12 archivos `__pycache__/*.pyc` de Python 3.14. Son
  bytecode regenerable; los fuentes `.py` correspondientes existen.
- Ampliar `.gitignore` para entornos, cachés, salidas de compilación y
  nombres concretos de diagnósticos/grabaciones generados por las herramientas.
- Documentar todas las pruebas de mantenimiento en el README.

No se cambia código de ejecución, catálogos, perfiles ni flujos de compilación.
No se reescribe el historial ni se eliminan ramas.

## Estructura y duplicados conservados

- `parte_scan/`: reconocimiento, servidor, perfil, actualización y tecleo integrado.
- `teclea/`: aplicación independiente; comparte módulos de `parte_scan`.
- `herramientas/`: utilidades de diagnóstico y exportación.
- `instalador/` y `.github/workflows/`: empaquetado y publicación Windows.
- `tests/`: tres scripts de pruebas; no usan el descubrimiento de pytest.
- `parte_scan/index.html` y `parte_scan/web/index.html` son idénticos por
  SHA-256. El servidor (`WEB`) y PyInstaller usan la copia en `web/`.
  Se conserva la otra por compatibilidad con usos externos no verificables.
  Por ahora cualquier cambio de interfaz debe mantener ambas sincronizadas.
- Las dos copias de `comunas_sistema.txt` son idénticas. Se conservan porque
  cada distribución empaqueta su propia copia; `prueba_tecleador.py` comprueba
  su igualdad.
- No se ignoran globalmente JSON, CSV, TXT, ZIP ni PDF: pueden ser recursos
  legítimos. Las exportaciones de `exportar_lista.py` tienen nombres dinámicos;
  revisar su contenido antes de agregarlas. Sesiones, partes, certificados y
  exportaciones con datos personales deben guardarse fuera del repositorio.

## PR y ramas

Los PR #2, #3 y #4 están cerrados e integrados en `main`: múltiples
infracciones, valores editados como fuente del tecleo y autocompletado.
No había PR abiertos al consultar GitHub.

Ramas cuyo extremo ya es ancestro de `main`:

- `feature/infraccion-autocomplete`
- `fix/edited-fields-source-of-truth`
- `fix/restore-buttons-js-syntax`
- `fix/tecleo-multiple-infractions`

Son candidatas a eliminación posterior. Se conservan durante esta limpieza.
`fix/tecleo-use-edited-office` tiene un commit no integrado por ascendencia
(`db3ce6b`), que cambia solo la oficina municipal en el HTML antiguo.
`main` ya aplica `V(p,'Oficina emisora')` a todos los orígenes en ambos HTML,
por lo que contiene una solución más amplia. No fusionar esa rama antigua
sin revisar; se conserva como referencia.

## Validación y límites

Las tres pruebas existentes pasaron antes de la limpieza. Se vuelven a
ejecutar después, junto con revisión del diff, sintaxis de los scripts HTML,
igualdad de duplicados y comprobación de exclusiones de Git.
Los archivos de ejecución permanecen sin cambios.

Los workflows actuales prueban y compilan al enviar cambios a `main`, pero
no se disparan para pull requests. La compilación completa con OCR,
instalador y automatización de ventanas requiere el entorno Windows del
workflow. El tecleo real de varias infracciones necesita prueba supervisada
en el sistema del Juzgado; las pruebas locales usan un sistema falso.
