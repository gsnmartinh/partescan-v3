# ParteScan + PartesTeclea

Herramientas gratuitas para Windows para ingresar partes en el sistema de un Juzgado de Policía Local
(hecho para el 2° Juzgado de Valdivia; configurable para otros).

| Programa | Para qué sirve |
|---|---|
| **ParteScan** (`parte_scan/`) | Lee partes escaneados (Carabineros, MTT, Inspección) y sus certificados, los deja listos para revisar y genera el archivo para PartesTeclea. |
| **PartesTeclea** (`teclea/`) | Teclea en el sistema los partes ya revisados, campo por campo, mirando la pantalla. |
| **Herramientas** (`herramientas/`) | Scripts de solo lectura para estudiar el sistema si cambia: grabar un ingreso, ver ventanas y exportar listas «Busca…». |

## Descargar
**Releases** → última versión → `ParteScan-Windows` y `PartesTeclea-Windows` (zip). Se descomprime y se abre el `.exe`; no necesita instalación.

## Otros juzgados
Los códigos de infracciones y oficinas, las actuarias y otros datos propios de cada juzgado se configuran en un perfil
(botón **⚙ Juzgado** en ParteScan, **Ajustes** en PartesTeclea). Sin configurar, usa los del 2° Juzgado de Valdivia.

## Para quien mantiene el proyecto
- Nueva versión: **Actions** → «Compilar ParteScan…» y «Compilar PartesTeclea…» → *Run workflow* con el mismo número (ej. `v1.2.0`).
- Pruebas: `python tests/prueba_perfil.py`.
- `RELEASE_NOTES.md` es el texto de cada Release.

> El archivo `.json` de tecleo trae RUT, nombres y direcciones: guardarlo solo en carpetas del Juzgado y borrarlo al terminar.
