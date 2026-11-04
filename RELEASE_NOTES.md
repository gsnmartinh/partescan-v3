# ParteScan 5.0 · ParteScan Captura 1.0

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
