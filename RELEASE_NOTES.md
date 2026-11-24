# ParteScan 5.1.20

- Corrige los pendientes falsos del semáforo: el contador, el formulario y el filtro de revisión utilizan el mismo valor normalizado, incluido el RUT sin puntos y con guion.
- Conserva las correcciones y revisiones guardadas en la sesión. Los datos que realmente faltan o no cumplen el formato siguen pidiendo revisión.
- Al pasar el puntero sobre un parte pendiente, muestra los campos que todavía necesitan revisión.

Validación con 111 partes reales de las tandas del 23 y 24/11. Se reprodujeron y corrigieron cuatro pendientes falsos en los partes comerciales, incluido el 117862. Las pruebas también comprueban que los RUT impresos inválidos mantengan su revisión. Captura Android conserva la versión 1.1.7.

# ParteScan 5.1.19

- Recupera RUT presentes en el texto del parte aunque las etiquetas o los dígitos estén separados por el OCR. Conserva para revisión los RUT impresos que no cumplen el dígito verificador.
- Añade una segunda lectura local de nombres y domicilios dudosos. Confirma el mismo RUT antes de recuperar apellidos partidos o líneas mezcladas y separa el domicilio del relato, la licencia y los datos del vehículo.
- Distingue el lugar del hecho del domicilio del denunciado y la hora del hecho de la citación en los modelos de Carabineros revisados.
- Reconoce los informes de Capitanía de Puerto, separa la identidad de la denunciada de los funcionarios de la patrulla y aplica la numeración confirmada del juzgado. Los números manuscritos que no se leen siguen pidiendo revisión.
- Conserva por separado la fecha del informe y la fecha del hecho: en los informes revisados, 16/11 y 09/11 respectivamente. La fecha de infracción corresponde al hecho, según el criterio confirmado por el usuario.
- Recupera el RUN de certificados cuando el OCR confunde el número 1 con la letra l, únicamente junto al rótulo y con dígito verificador válido.
- Clasifica las causas con y sin datos de vehículo según los códigos corregidos. Las causas sin vehículo no piden patente, tipo ni certificado; las combinadas mantienen la revisión vehicular si corresponde. El comodín 67 conserva el contexto.
- Restablece la lista desplegable de infracciones y mantiene el catálogo completo al corregir un código reconocido.
- Propone 48 como aproximación, con revisión, para estacionar en medio de la calzada impidiendo el tránsito. Conserva los códigos 16 y 33 en el caso combinado revisado.
- Los 30 caracteres de Lugar son un aviso. Si el sistema del Juzgado efectivamente recorta el texto, el tecleo se detiene para revisar la causa.
- Armoniza los campos, botones, listas y sugerencias con Fluent 2; mejora las etiquetas accesibles y la distribución en pantalla completa, media pantalla y temas claro y oscuro.

Validación local con las tandas reales del 23 y 24/11: pruebas de clasificación sobre 111 partes, regresión de códigos de los 58 partes de referencia, recuperación de 16 RUT presentes en el OCR y segunda lectura efectiva de nueve imágenes seleccionadas. También se cotejaron 20 certificados y se comprobó la interfaz en navegador aislado. Esto no representa un porcentaje global de reconocimiento ni reemplaza la revisión del documento. La aplicación Android conserva la versión Captura 1.1.7; estas mejoras corresponden al escritorio.

# ParteScan 5.1.18

- Abrevia el lugar del hecho conservando calles, cruces y numeración. Usa CON y elimina rótulos como CALLE o AVENIDA. Muestra el original y un contador de 30 caracteres.
- Comprueba el límite del campo al teclear y detiene el ingreso si el lugar queda recortado. El límite de referencia de 30 caracteres proviene del caso observado y requiere comprobación en el sistema real.
- Corrige la lectura de infracciones con rótulos repetidos o dañados y conserva las cinco infracciones combinadas del caso real revisado.
- Reconoce luces de freno en mal estado (59), neumáticos en mal estado (64) y transporte sin inscripción (65).
- Aplica el criterio confirmado del juzgado para facilitar vehículo sin licencia: 67 y descripción del hecho.
- Conserva todos los hechos en la descripción cuando comparten el código comodín 67.
- Evita tomar como segundo infractor a una persona mencionada en la sección del vehículo cuando el denunciado está identificado en su propia sección.
- Mejora la búsqueda de infracciones, la descripción conjunta de documentación y la memoria local de interpretaciones confirmadas.

Validación local sobre la tanda real del 23/11: coincidencia del conjunto de códigos en los 58 partes con la referencia corregida y la confirmación posterior del código 59. Los 58 lugares quedan dentro de 30 caracteres conservando la numeración. Esto no mide el acierto de los demás campos ni sustituye la revisión del documento. Los partes de varias hojas se revisarán en otra sesión con ejemplos reales.

# ParteScan 5.1.17 · ParteScan Captura 1.1.7

- Relee datos sospechosos, valida fechas y utiliza etiquetas del documento para localizar campos.
- Android conserva las coordenadas de las líneas en nuevas lecturas y las exporta para mejorar la reconstrucción de filas en escritorio.
- Compara la calidad del texto recuperado y añade una lectura con contraste. Los PDF se procesan página por página.
- Antes de Aceptar comprueba rol, número y fecha del parte. Un rol posterior vacío, antiguo o con salto inesperado interrumpe el lote y deja el ingreso sin confirmar.
- Evita heredar el estado y rol de otra causa al reutilizar identificadores de tanda.
- Mejora la edición de infracciones y el reconocimiento de correcciones válidas.
- Agrega denunciado por domicilio, con dirección como nombre y SR como RUT, y limpia la identificación al cambiar modalidad.
- Reconoce la disposición de ficha empresarial con cuadro único para la razón social. Requiere comprobación en el sistema real del Juzgado.

Pendientes detectados en pruebas sintéticas: asociación de hojas de continuación, generación automática de copias por infractor y boleta, asociación de boletas citadas en orden inverso y reconocimiento completo de algunas infracciones combinadas. Revisa estos casos antes de teclear.

# ParteScan 5.1.16 · ParteScan Captura 1.1.6

- Escritorio distingue los datos detectados, modificados y revisados, y valida fechas, horas y el dígito verificador del RUT.
- Al cambiar infracciones permite actualizar la descripción con los códigos seleccionados.
- Guarda el historial de correcciones de la tanda y permite consultar los valores anteriores y nuevos.
- Las búsquedas por campo se procesan en cola. Cancelar descarta el resultado de una lectura que ya comenzó.
- Conserva las páginas que fallaron durante el reconocimiento para reintentarlas y continúa leyendo las demás.
- Android permite reintentar el OCR desde cada foto y abrir las fotos señaladas para revisión.
- Incorpora avisos orientativos de poca iluminación, exceso de luz, poco detalle y texto junto al borde. Conviene comprobar el encuadre y la legibilidad en la imagen ampliada.

# ParteScan 5.1.15 · ParteScan Captura 1.1.5

- Escritorio normaliza las variantes de O’Higgins como OHIGGINS, sin apóstrofo, al mostrar, copiar y preparar el tecleo.
- Permite recordar correcciones de calles y direcciones en este equipo y ofrecerlas como sugerencias ante coincidencias exactas del texto y contexto. No modifica automáticamente otros partes.
- Correcciones locales permite consultar, desactivar y olvidar las reglas guardadas.
- Android distingue las páginas procesadas, pendientes y con poco texto para revisar. El aviso usa caracteres, no bytes, de forma consistente con la exportación.
- Al guardar, Android muestra el avance de las lecturas pendientes y confirma que la copia fue verificada.

# ParteScan 5.1.14 · ParteScan Captura 1.1.4

- Windows conserva los datos reconocidos y relee las fotos de una tanda cuando faltan campos clave.
- Android vuelve a leer fotos con poco texto antes de exportar e indica cuántas quedaron con una lectura corta.
- El README describe el flujo actual de captura, revisión y tecleo integrado.

# ParteScan 5.1.13

- Agrega el modo compacto en Windows para trabajar con ParteScan y el sistema del Juzgado lado a lado.
- En ventanas estrechas, permite elegir el parte desde un desplegable, alternar entre datos y documentos y mantener visible el boton de tecleo.

# ParteScan 5.1.12

- Teclea SR en los partes empadronados que lo usan y elimina el aviso de RUT no reconocible.
- Completa y acepta la ficha nueva del Juzgado cuando el RUT es valido, fue confirmado en ParteScan y estan disponibles el nombre, la direccion y la comuna.

# ParteScan 5.1.11

- Relee campos con OCR local y muestra alternativas con su fuente y, cuando es posible, el recorte donde aparecen.
- Abre una ventana para releer la descripción de la causa y seleccionar los códigos de infracción que quieres agregar.
- Filtra los pendientes por campo y cuenta las correcciones localmente por tipo de parte.
- Conserva CON o ESQUINA en el lugar de los hechos y omite VALDIVIA al final, salvo en partes de Tenencia Corral.

En Windows, vuelve a abrir ParteScan y pulsa **Actualizar a v5.1.11**.

# ParteScan 5.1.1 · ParteScan Captura 1.1.0

- Carga las tandas grandes por bloques y avisa si el archivo está dañado o la transferencia quedó incompleta.
- Reconoce «POR ESCRITO» con letras juntas o separadas. En partes empadronados, forma el nombre con el tipo de vehículo y la patente y deja vacío el RUT.
- Mejora la extracción de folios e infracciones de Carabineros e incorpora las correcciones de códigos verificadas con la tanda.

En Windows, cierra y abre ParteScan y pulsa **Actualizar a v5.1.1**.

## Novedades de 5.1.0

- Windows reconoce los informes OS10 con oficina 33 e infracción 400 y extrae los datos de la empresa denunciada.
- Mejora la lectura del rótulo de infracción en los partes de Carabineros.
- Listado impreso compacto con boleta u oficio, ROL, oficina e infracción.
- Barra de edición de la tanda con botones y selector alineados.
- Android permite ampliar y recorrer las fotos con dos dedos y ajustar con doble toque.
- Android busca nuevas versiones al abrir y ofrece descargarlas. La instalación se confirma en el teléfono. Instala este APK una vez para activar esa función.


ParteScan 5.0.1 corrige la apertura de tandas .psocr con fotos de más de 40 megapíxeles. Reduce las imágenes durante la decodificación y conserva el texto OCR del teléfono.

Los usuarios con ParteScan instalado pueden cerrar y abrir la aplicación y pulsar **Actualizar a v5.0.1**.

Las dos aplicaciones estrenan una identidad visual complementaria:

- **Windows:** documento azul con marca de revisión, en el programa, el instalador, los accesos directos y la cabecera.
- **Android:** documento turquesa con marco de escaneo, con iconos adaptativos y versión monocroma para iconos temáticos.

## ParteScan 5.0

Consolida el diseño Fluent 2, el tecleo integrado, la revisión junto a las imágenes, la eliminación y reordenación con deshacer, la reasignación de certificados y la normalización de tipos de vehículo. Conserva las sesiones y las actualizaciones diferenciales.

## ParteScan Captura 1.0

Consolida la navegación entre **Tanda**, **Escanear** y **Guardar**, la revisión de partes y certificados, la repetición y giro de fotos, la eliminación con deshacer, la apertura de tandas .psocr y la recuperación local. Incluye la apertura de cámara corregida, la exportación a .psocr y PDF y la navegación Atrás de Android reciente.

## Descargas

- **Windows:** `ParteScan-Instalador-v5.0.0.exe` o el ZIP portátil.
- **Android:** `ParteScan-Captura-1.0.0.apk`.
- **Logos:** originales SVG, exportaciones PNG e icono ICO en `ParteScan-Logos-v5.0.0.zip`.

El APK conserva la firma de las versiones oficiales 0.9 y 0.10: se instala como actualización. Se conservan los identificadores de las aplicaciones y los formatos de archivos y sesiones.

## Historial de versiones

**ParteScan v4.1.0**

- Consolida el nuevo diseño de revisión y las mejoras de reconocimiento usadas en el trabajo diario.
- Permite eliminar partes, cambiar su orden y deshacer esos cambios conservando las correcciones y las imágenes.
- Permite asociar una hoja reconocida como parte a su verdadero parte como certificado, o reasignar un certificado existente.
- Reconoce certificados en tandas móviles aunque se hayan marcado como partes al escanear.
- Ajusta los tipos de vehículo a la lista del sistema y marca para revisión los valores desconocidos.
- Conserva el tecleo integrado, el guardado de sesiones y las actualizaciones diferenciales.

**ParteScan Captura Android 0.9**

- Revisión de todos los partes capturados, con imágenes ampliables y posibilidad de repetir las fotografías.
- Eliminación de partes con opción de deshacer.
- Apertura de tandas .psocr guardadas para seguir modificándolas.
- Recuperación local de la tanda al volver a abrir la aplicación.
- Conserva el diseño nuevo, la orientación de las fotos y la exportación a .psocr o PDF.

El APK 0.9 usa una firma estable para las próximas actualizaciones. Si Android rechaza la instalación sobre una versión de prueba anterior, guarda primero la tanda como .psocr, desinstala esa versión e instala el APK nuevo. Después puedes volver a abrir la tanda guardada.

**ParteScan v4.0.5** corrige el bloqueo de la aceptación automática. ParteScan verifica el botón Aceptar y su foco antes de activarlo.

**ParteScan v4.0.4** unifica la revisión y el guardado de los campos compartidos entre formularios. Las versiones se distribuyen como una sola aplicación con el tecleo integrado.

**Novedades de v4.0.3**

- Reintenta la lectura cuando falta la comuna y reconoce más variantes de la patente en los certificados del Registro Civil.
- Mejora la detección de los formularios municipales que corresponden a la oficina 32.
- Asigna el código 493 a botar basura en la vía pública o en un bien nacional de uso público.
- Pide revisar el original si falta el número del parte de Carabineros, aunque la boleta sea legible.

**Instalación (recomendada):** descarga `ParteScan-Instalador-…exe` en *Assets*, ejecútalo y sigue el asistente. No pide permisos de administrador y crea el acceso directo.
Si Windows muestra «Windows protegió su PC»: *Más información → Ejecutar de todas formas* (el programa no está firmado).
También hay un `.zip` portátil (se descomprime completo y se abre `ParteScan.exe`).

**Actualizaciones diferenciales.** Si tienes v4.0.0 o posterior instalada en la ubicación predeterminada, abre ParteScan y pulsa **Actualizar a v4.0.5**. La aplicación descarga los archivos modificados, verifica sus huellas y reinicia. El perfil y las sesiones se conservan.

**Novedades de v4.0.2.** Formato de RUT sin puntos y con guion antes del dígito verificador. El botón de actualización queda junto al título.

**Novedades de v4.0.1.** Mejora la lectura de nombre, RUT, domicilio y comuna en certificados del Registro Civil. Cuando un campo falta o falla la validación, vuelve a leer el certificado con otro modo de OCR.

**Novedades de v4.0.0**

- Reconoce el formulario DOM con oficina 31 y código 497 para ejecución de obra sin permiso.
- Completa el denunciado desde los partes escritos por actividad comercial sin patente y asigna el código 480.
- Solicita verificar la fotografía cuando un parte de estacionamiento apunta a varios códigos.
- Actualiza el domicilio cuando el del parte difiere del autocompletado por el RUT.
- Imprime el listado final de boletas u oficios con su ROL.

**Novedades v3.0.3**
- Botón **✓ Confirmar** junto a «Copiar» en cada campo marcado «Revisar», y **✓ Ya revisé todo** en el recuadro de avisos: al confirmar, el campo queda en verde y el parte cambia de color.
- Los avisos «No pude leer la marca / el tipo de vehículo / la comuna…» desaparecen solos cuando el campo ya tiene valor.

**Novedades v3.0.2**
- Botón **🧹 Nueva tanda**: limpia el lote y el tecleo para empezar de cero sin cerrar el programa.
- Partes municipales: la **oficina emisora** se completa sola según el encabezado (Inspección General y Seguridad Ciudadana → «Departamento Inspeccion General»; se cambia en ⚙ Juzgado).
- Certificados del Registro Civil: se ignora el ruido que deja el borde del escáner («I», «1», «!», «|» al final de nombre, dirección y comuna) y la comuna se ajusta a la lista del sistema (MÁFIL A → MÁFIL).
- Si el nombre, la dirección o la comuna no se leen por el rótulo, se toman por su posición en «Datos del propietario».
- El **RUT** del certificado, cuando no se lee, se vuelve a leer ampliando solo esa línea.
- El N° de denuncia se corrige con el de la citación adjunta cuando el OCR agrega un dígito (9111187 → 111187).

**Novedades v3.0.1**: la dirección del infractor ya no arrastra la «Disposición infringida» aunque el OCR la lea con errores, y «sin Nro.» queda como S/N.

**Novedades v3.0.0**
- Ventana de escritorio propia (sin navegador ni consola negra).
- Teclear en el sistema directamente desde ParteScan: se corrige un dato y se sigue, sin empezar de nuevo.
- Infracción que no calza con la lista: se ingresa con el código comodín **67** y la descripción lleva lo que dice el parte.
- Comuna escrita exactamente como la lista del sistema (con tilde); se conserva la Ñ en el resto de los campos.
- Aviso si la comuna del parte no existe en la lista; la comuna del infractor ya no arrastra la «Disposición infringida».
