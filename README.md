# ParteScan + PartesTeclea

Herramientas gratuitas para Windows para ingresar partes en el sistema de un Juzgado de Policía Local
(hecho para el 2° Juzgado de Valdivia; configurable para otros).

| Programa | Para qué sirve |
|---|---|
| **ParteScan** (`parte_scan/`) | Lee y permite revisar partes de Carabineros, MTT, Inspección y DOM. Desde la misma ventana teclea los datos revisados en el sistema del Juzgado. |
| **Herramientas** (`herramientas/`) | Scripts de solo lectura para estudiar el sistema si cambia: grabar un ingreso, ver ventanas y exportar listas «Busca…». |

## Descargar
En **Releases**, descarga `ParteScan-Instalador` e instala en la ubicación predeterminada para recibir actualizaciones desde la app. Si usas la edición portátil `ParteScan-Windows`, descomprime toda la carpeta y abre `ParteScan.exe`.

## Otros juzgados
Los códigos de infracciones y oficinas, las actuarias y otros datos propios de cada juzgado se configuran en un perfil
(botón **⚙ Juzgado** en ParteScan). Sin configurar, usa los del 2° Juzgado de Valdivia.

## Para quien mantiene el proyecto
- Para publicar una versión, sube una etiqueta `vX.Y.Z` al commit correspondiente. GitHub Actions compila ParteScan y publica el instalador, el ZIP portátil y los archivos de actualización.
- Pruebas (desde la raíz): `python tests/prueba_perfil.py`,
  `python tests/prueba_tecleador.py` y `python tests/prueba_actualizador.py`.
  Ejecutar las tres; la del actualizador usa un servidor local sin internet.
- Estructura, duplicados conservados y revisión de ramas: [AUDITORIA.md](AUDITORIA.md).
- `RELEASE_NOTES.md` es el texto de cada Release.

> El archivo `.json` de tecleo trae RUT, nombres y direcciones: guardarlo solo en carpetas del Juzgado y borrarlo al terminar.
