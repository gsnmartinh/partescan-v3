const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
new Function(script);
const ctx=vm.createContext({});
vm.runInContext(script.slice(script.indexOf('function compactarLugar('),script.indexOf('function textoMemoria(')),ctx);
const python=process.env.PARTESCAN_PYTHON||'python';
const source=`import json,sys,zipfile\nfrom parte_scan.lugares import compactar_lugar\nwith zipfile.ZipFile(sys.argv[1]) as z: partes=json.loads(z.read('estado.json'))['partes']\nrows=[{'pagina':p['pagina'],'original':p.get('ed',{}).get('Lugar',p.get('lugar',''))} for p in partes]\nfor r in rows:r['compacto']=compactar_lugar(r['original'])\nprint(json.dumps(rows,ensure_ascii=False))`;
const result=spawnSync(python,['-X','utf8','-c',source,process.argv[2]],{encoding:'utf8'});
assert.equal(result.status,0,result.stderr);
const rows=JSON.parse(result.stdout);
const compact=s=>vm.runInContext('compactarLugar('+JSON.stringify(s)+')',ctx);
for(const row of rows){
 assert.equal(compact(row.original),row.compacto,'Paridad escritorio/tecleo página '+row.pagina);
 assert.ok(row.compacto.length<=30,'Longitud página '+row.pagina);
 assert.deepEqual(row.compacto.match(/\d+/g)||[],row.original.match(/\d+/g)||[],'Numeración página '+row.pagina);
 assert.equal(compact(row.compacto),row.compacto,'Formato estable página '+row.pagina);
}
assert.equal(compact('av arturo prat esquina con av alemania'),'PRAT CON AV ALEMANIA');
assert.equal(rows.find(r=>r.pagina===37).compacto,'BOMBERO HERNANDEZ CON SEDEÑO');
assert.equal(rows.find(r=>r.pagina===6).compacto,'LOS ROBLES CON OETTINGER');
console.log(rows.length+' lugares reales: misma abreviación en pantalla y tecleo, hasta 30 caracteres y numeración conservada.');
