**ParteScan v3**: lee los partes escaneados (OCR local, sin internet) y los **teclea en el sistema del Juzgado**, todo en una sola aplicación de escritorio.

**Instalación (recomendada):** descarga `ParteScan-Instalador-…exe` en *Assets*, ejecútalo y sigue el asistente. No pide permisos de administrador y crea el acceso directo.
Si Windows muestra «Windows protegió su PC»: *Más información → Ejecutar de todas formas* (el programa no está firmado).
También hay un `.zip` portátil (se descomprime completo y se abre `ParteScan.exe`).

**Actualizaciones automáticas:** si hay internet, al abrir el programa avisa cuando hay una versión nueva y se actualiza con un botón, conservando tu perfil y tus sesiones. Sin internet funciona igual.

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
