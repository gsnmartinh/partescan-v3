# ParteScan

ParteScan ayuda a revisar e ingresar partes en el sistema del Juzgado de Policía Local. **ParteScan para Windows** lee y organiza los documentos. **ParteScan Captura para Android** fotografía los partes y sus certificados y prepara la tanda para llevarla al computador.

Descarga el instalador de Windows y el APK firmado de Android en [Versiones de ParteScan](https://github.com/gsnmartinh/partescan-v3/releases/latest).

## Flujo de trabajo

1. En Android, fotografía cada parte y su certificado si corresponde. La app reconoce texto en segundo plano y permite revisar, ampliar o repetir las fotos antes de exportar.
2. Guarda la tanda como `.psocr`. Puedes dividir una tanda grande en bloques. La app verifica la copia guardada e indica si quedaron fotos con poco texto legible.
3. En Windows, abre los archivos `.psocr`, PDF o imágenes. ParteScan usa el texto disponible y relee las fotos cuando faltan campos clave.
4. Revisa los datos junto a la imagen original. Usa **Revisar por campo** para ir a los pendientes. **Buscar en el documento** ofrece lecturas alternativas y **Releer y sugerir códigos** permite confirmar infracciones antes de agregarlas.
5. Pulsa **Teclear en el sistema** para enviar la tanda al sistema del Juzgado. Al trabajar con ambas ventanas lado a lado, ParteScan muestra el modo compacto. También puedes exportar los datos a JSON y generar el listado de ingresos con los roles asignados.

## Qué reconoce

- Partes municipales, Carabineros, MTT, DOM e informes OS10.
- Folio, oficina emisora, fechas, hora, lugar, patente e infracciones según el formato del documento.
- Datos del denunciado desde el parte o el certificado, según la modalidad. En MTT, usa el folio para una notificación personal y el Registro Civil para una denuncia empadronada.
- Una o varias infracciones por parte. Los datos dudosos y las diferencias entre lecturas quedan disponibles para revisar.

El reconocimiento se hace en el teléfono o en el computador. Las actualizaciones se consultan en GitHub desde cada aplicación.

## Desarrollo

- `parte_scan/` contiene el reconocimiento, la interfaz de Windows y el motor de tecleo.
- `android/` contiene ParteScan Captura.
- `tests/` contiene las pruebas de reconocimiento, revisión, tecleo y actualización.
- `herramientas/` contiene utilidades de desarrollo y diagnóstico.

Para ejecutar Windows desde el código, instala las dependencias de `requirements.txt` y Tesseract con español. Luego ejecuta `python partescan.py`. GitHub Actions compila los paquetes oficiales al publicar una etiqueta de versión.
