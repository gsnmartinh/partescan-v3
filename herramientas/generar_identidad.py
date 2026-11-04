"""Genera los originales vectoriales y los iconos nativos de la familia ParteScan.

python herramientas/generar_identidad.py --raster
La exportación raster requiere Node con sharp y Pillow; PARTESCAN_NODE puede indicar Node.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import argparse
import base64
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'parte_scan/web/brand'
RES = ROOT / 'android/src/main/res'
PAPER = 'M184 132H280L336 188V356Q336 376 316 376H184Q164 376 164 356V152Q164 132 184 132Z'
FOLD = 'M280 132V172Q280 188 296 188H336Z'
FRAME = 'M160 112H128Q112 112 112 128V160M352 112H384Q400 112 400 128V160M400 352V384Q400 400 384 400H352M160 400H128Q112 400 112 384V352'
LINES = ['M200 224H300', 'M200 256H282', 'M200 288H246']
COLORS = {
    'windows': ('#3595EF', '#0F6CBD', '#2343A6'),
    'captura': ('#26C6C0', '#008C9F', '#006B91'),
}

def shape(d, fill='none', stroke=None, width=0, opacity=1):
    return dict(d=d, fill=fill, stroke=stroke, width=width, opacity=opacity)

def marks(kind):
    out = []
    if kind == 'windows':
        out.append(shape('M160 156L286 140Q304 138 306 156L332 358Q334 376 316 378L184 394Q166 396 164 378L142 178Q140 160 160 156Z', '#FFFFFF', opacity=.25))
    else:
        out.append(shape(FRAME, stroke='#FFFFFF', width=16, opacity=.95))
    out += [shape(PAPER, 'url(#paper)'), shape(FOLD, '#CDEBFA')]
    out += [shape(d, stroke='#0F6CBD' if kind == 'windows' else '#008C9F', width=14) for d in LINES]
    if kind == 'windows':
        out += [shape('M404 344A60 60 0 1 1 284 344A60 60 0 1 1 404 344Z', 'url(#badge)'),
                shape('M316 344L336 364L374 326', stroke='#FFFFFF', width=16)]
    return out

def svg(kind):
    start, middle, end = COLORS[kind]
    paths=[]
    for p in marks(kind):
        paths.append(f'<path d="{p["d"]}" fill="{p["fill"]}"'+
                     (f' stroke="{p["stroke"]}" stroke-width="{p["width"]}" stroke-linecap="round" stroke-linejoin="round"' if p['stroke'] else '')+
                     (f' opacity="{p["opacity"]}"' if p['opacity'] != 1 else '')+'/>')
    title='ParteScan · revisión e ingreso' if kind=='windows' else 'ParteScan Captura · escaneo de documentos'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="{title}">
<defs>
<linearGradient id="tile" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{start}"/><stop offset=".55" stop-color="{middle}"/><stop offset="1" stop-color="{end}"/></linearGradient>
<linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#FFFFFF"/><stop offset="1" stop-color="#E8F4FF"/></linearGradient>
<linearGradient id="badge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0A82CF"/><stop offset="1" stop-color="#1643A0"/></linearGradient>
</defs>
<rect width="512" height="512" rx="112" fill="url(#tile)"/>
{''.join(paths)}
</svg>
'''

def vector_path(p):
    attrs=[f'android:pathData="{p["d"]}"']
    if p['stroke']:
        attrs += [f'android:strokeColor="{p["stroke"]}"',f'android:strokeWidth="{p["width"]}"','android:strokeLineCap="round"','android:strokeLineJoin="round"']
        if p['opacity'] != 1: attrs.append(f'android:strokeAlpha="{p["opacity"]}"')
    if p['fill'].startswith('url('):
        ident=p['fill'][5:-1]
        if ident=='tile':
            start,middle,end=COLORS['captura']
            gradient=f'<gradient android:type="linear" android:startX="0" android:startY="0" android:endX="512" android:endY="512"><item android:offset="0" android:color="{start}"/><item android:offset=".55" android:color="{middle}"/><item android:offset="1" android:color="{end}"/></gradient>'
        else:
            gradient='<gradient android:type="linear" android:startX="0" android:startY="132" android:endX="0" android:endY="376" android:startColor="#FFFFFF" android:endColor="#E8F4FF"/>'
        return '<path '+' '.join(attrs)+'><aapt:attr name="android:fillColor">'+gradient+'</aapt:attr></path>'
    attrs += [f'android:fillColor="{p["fill"] if p["fill"]!="none" else "@android:color/transparent"}"']
    if p['opacity'] != 1 and p['fill'] != 'none': attrs.append(f'android:fillAlpha="{p["opacity"]}"')
    return '<path '+' '.join(attrs)+'/>'

def vector(paths, adaptive=False):
    content='\n'.join(vector_path(p) for p in paths)
    if adaptive: content='<group android:pivotX="256" android:pivotY="256" android:scaleX=".74" android:scaleY=".74">'+content+'</group>'
    return '<vector xmlns:android="http://schemas.android.com/apk/res/android" xmlns:aapt="http://schemas.android.com/aapt" android:width="108dp" android:height="108dp" android:viewportWidth="512" android:viewportHeight="512">\n'+content+'\n</vector>\n'

def save(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--raster',action='store_true'); args=parser.parse_args()
    save(WEB/'partescan.svg',svg('windows')); save(WEB/'captura.svg',svg('captura'))
    tile=shape('M112 0H400Q512 0 512 112V400Q512 512 400 512H112Q0 512 0 400V112Q0 0 112 0Z','url(#tile)')
    save(RES/'drawable/brand_capture.xml',vector([tile]+marks('captura')))
    save(RES/'drawable/ic_launcher_background.xml',vector([shape('M0 0H512V512H0Z','url(#tile)')]))
    save(RES/'drawable/ic_launcher_foreground.xml',vector(marks('captura'),True))
    # Alpha-only version for Android's themed icons, with document lines cut out.
    holes='M193 217H307V231H193Z M193 249H289V263H193Z M193 281H253V295H193Z'
    mono=vector([shape(PAPER+' '+holes,'#FFFFFF'),shape(FRAME,stroke='#FFFFFF',width=16)],True)
    mono=mono.replace('android:pathData="'+PAPER+' '+holes+'"','android:fillType="evenOdd" android:pathData="'+PAPER+' '+holes+'"')
    save(RES/'drawable/ic_launcher_monochrome.xml',mono)
    for version in (26,33):
        extra='<monochrome android:drawable="@drawable/ic_launcher_monochrome"/>' if version==33 else ''
        save(RES/f'mipmap-anydpi-v{version}/ic_launcher.xml','<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@drawable/ic_launcher_background"/><foreground android:drawable="@drawable/ic_launcher_foreground"/>'+extra+'</adaptive-icon>\n')
    left=base64.b64encode(svg('windows').encode()).decode(); right=base64.b64encode(svg('captura').encode()).decode()
    preview=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
<rect width="1200" height="760" fill="#F5F5F5"/>
<g font-family="Segoe UI,Arial,sans-serif" fill="#242424">
<text x="64" y="76" font-size="34" font-weight="600">ParteScan</text><text x="64" y="112" font-size="19" fill="#616161">Identidad visual · Windows 5.0 y Android 1.0</text>
<rect x="48" y="152" width="536" height="544" rx="24" fill="white" stroke="#E0E0E0"/>
<rect x="616" y="152" width="536" height="544" rx="24" fill="white" stroke="#E0E0E0"/>
<image x="188" y="204" width="256" height="256" href="data:image/svg+xml;base64,{left}"/>
<image x="756" y="204" width="256" height="256" href="data:image/svg+xml;base64,{right}"/>
<text x="316" y="522" text-anchor="middle" font-size="31" font-weight="600">ParteScan</text>
<text x="316" y="560" text-anchor="middle" font-size="20" fill="#616161">Revisión e ingreso de partes</text>
<text x="316" y="615" text-anchor="middle" font-size="18" fill="#0F6CBD">WINDOWS · 5.0</text>
<text x="884" y="522" text-anchor="middle" font-size="31" font-weight="600">ParteScan Captura</text>
<text x="884" y="560" text-anchor="middle" font-size="20" fill="#616161">Captura de partes y certificados</text>
<text x="884" y="615" text-anchor="middle" font-size="18" fill="#008C9F">ANDROID · 1.0</text>
</g></svg>'''
    save(ROOT/'assets/branding/identidad.svg',preview)
    if args.raster:
        node=os.environ.get('PARTESCAN_NODE') or shutil.which('node')
        if not node: raise SystemExit('Indica Node en PARTESCAN_NODE para exportar PNG e ICO.')
        subprocess.run([node,str(ROOT/'herramientas/exportar_identidad.cjs'),str(ROOT)],check=True)
        from PIL import Image
        with Image.open(ROOT/'assets/branding/partescan-windows-1024.png') as image:
            image.save(WEB/'partescan.ico',format='ICO',sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
    print('Identidad vectorial y recursos nativos generados.')

if __name__=='__main__': main()
