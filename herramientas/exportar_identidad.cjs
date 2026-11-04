const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
const root = process.argv[2];
(async () => {
  for (const [source, name] of [['partescan', 'partescan-windows'], ['captura', 'partescan-captura']]) {
    const svg = path.join(root, 'parte_scan/web/brand', source + '.svg');
    for (const size of [512, 1024]) await sharp(svg).resize(size, size).png().toFile(path.join(root, 'assets/branding', `${name}-${size}.png`));
  }
  for (const [density, size] of [['mdpi',48],['hdpi',72],['xhdpi',96],['xxhdpi',144],['xxxhdpi',192]]) {
    const dir=path.join(root, 'android/src/main/res', 'mipmap-'+density);
    fs.mkdirSync(dir,{recursive:true});
    await sharp(path.join(root,'parte_scan/web/brand/captura.svg')).resize(size,size).png().toFile(path.join(dir,'ic_launcher.png'));
  }
  await sharp(path.join(root, 'assets/branding/identidad.svg')).png().toFile(path.join(root, 'assets/branding/identidad.png'));
})().catch(error=>{console.error(error);process.exit(1)});
