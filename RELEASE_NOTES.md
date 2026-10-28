**ParteScan**: lee los partes escaneados y prepara los datos para que PartesTeclea los ingrese.
**PartesTeclea**: teclea esos partes en el sistema del Juzgado.

Descarga el zip de cada programa en *Assets*, descomprímelo completo y abre el `.exe`.
Si Windows muestra «Windows protegió su PC»: *Más información → Ejecutar de todas formas* (el programa no está firmado).

**Novedades v1.4.1**: encabezado de ParteScan ordenado en una sola fila (sesión agrupada, atajo F2 en la leyenda, «Continuar anterior» se oculta al haber partes).

**Novedades v1.4.0** (incluye lo preparado como v1.3.0)

*ParteScan*
- **Segundo lector de OCR (RapidOCR, local y sin internet)** que cotejan la boleta, la patente y el RUT: completa lo que el primero no leyó y avisa cuando los dos leen distinto (suma unos 80 MB al programa).
- Infracciones: línea amarilla, ciclovía y demás estacionamientos sin opción propia → 19; beber, ingerir o consumir alcohol (aunque venga mal escrito, ej. «ingringir») → 300; la descripción de la infracción ya no arrastra HORA/LUGAR y el lugar no trae «lugar donde» al final.
- Sesiones: guarda y abre el lote con tus correcciones e imágenes (archivo `.partescan`), con guardado automático para continuar sin releer los PDF.
- Lectura de partes de Carabineros más robusta: toma personas, vehículo y lugar por su significado, sin depender de rótulos ni del orden; mejor lectura del N° de parte, RUT, domicilio, hora y patentes de motos antiguas.
- Reconoce la unidad de Carabineros en encabezados como «R. ISLA TEJA» o «PRIMERA COM.».
- La boleta leída con poca seguridad se avisa para revisarla; el año de la fecha del parte siempre es el en curso (y avisa cuando lo corrige).
- Vehículo: si el parte no dice el tipo se usa AUTOMOVIL; la marca es opcional; la patente de motos va con 6 caracteres (TV880 → TV0880) y se vuelve a leer avisando si las lecturas difieren.
- Infracciones: estacionar sin opción propia → 19; alcohol → 300; no portar licencia → 66 (a confirmar); señal PARE de Carabineros más acera.

*PartesTeclea*: sin cambios respecto de la v1.2.0.

**Novedades v1.2.0**: ParteScan queda en un solo modo (sin «vías exclusivas»): el flujo es leer, revisar y guardar los datos para PartesTeclea.
