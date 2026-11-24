const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
const ctx=vm.createContext({});
vm.runInContext(script.slice(script.indexOf('function compactarLugar('),script.indexOf('function textoMemoria(')),ctx);
vm.runInContext(script.slice(script.indexOf('function formatoCampoValido('),script.indexOf('function estadoCampo(')),ctx);
const source="import json,sys,zipfile\nwith zipfile.ZipFile(sys.argv[1]) as z: partes=json.loads(z.read('estado.json'))['partes']\nprint(json.dumps([p.get('lugar','') for p in partes]))";
const p=spawnSync(process.env.PARTESCAN_PYTHON||'python',['-X','utf8','-c',source,process.argv[2]],{encoding:'utf8'});
assert.equal(p.status,0,p.stderr);
let largos=0;
for(const original of JSON.parse(p.stdout)){
 const compacto=vm.runInContext('compactarLugar('+JSON.stringify(original)+')',ctx);
 if(compacto.length>30){
  largos++;
  assert.equal(vm.runInContext('formatoCampoValido("Lugar",'+JSON.stringify(compacto)+')',ctx),true);
 }
}
assert.ok(largos>0,'La sesión debe contener lugares reales de más de 30 caracteres');
console.log(largos+' lugares reales de más de 30 caracteres aceptados por la validación.');
