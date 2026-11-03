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
