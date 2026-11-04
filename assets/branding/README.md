# Identidad de ParteScan

Las dos aplicaciones comparten una hoja con esquina doblada y tres líneas de texto.

- **ParteScan, Windows:** azul, documentos y una marca de revisión. Representa la revisión y el ingreso de partes.
- **ParteScan Captura, Android:** turquesa y un marco de escaneo. Representa la captura de partes y certificados.

Los originales editables están en `parte_scan/web/brand/partescan.svg` y `captura.svg`. Esta carpeta contiene sus exportaciones PNG de 512 y 1024 píxeles y la presentación conjunta.

El ICO de Windows está en `parte_scan/web/brand/partescan.ico`. Android incluye iconos adaptativos para las máscaras del fabricante, una versión monocroma para iconos temáticos y PNG de respaldo.

Para regenerar los recursos: `python herramientas/generar_identidad.py --raster`. Requiere Pillow y Node con sharp. Se puede indicar el ejecutable de Node mediante `PARTESCAN_NODE`.
