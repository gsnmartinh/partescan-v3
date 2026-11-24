// Comprobar la validación con las dos tandas reales; no contiene datos personales.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
new Function(script);
const source=`import json,sys,zipfile\nfrom parte_scan import catalogo\npartes=[]\nfor ruta in sys.argv[1:]:\n with zipfile.ZipFile(ruta) as z: partes+=json.loads(z.read('estado.json'))['partes']\nprint(json.dumps({'perfil':{'clasificacion_vehicular':catalogo.clasificacion_vehicular()},'partes':partes}))`;
assert.equal(process.argv.length,4,'Indica las sesiones reales del 23 y 24 de noviembre');
const result=spawnSync(process.env.PARTESCAN_PYTHON||'python',['-X','utf8','-c',source,...process.argv.slice(2)],{encoding:'utf8'});
assert.equal(result.status,0,result.stderr);
const data=JSON.parse(result.stdout);
const ctx=vm.createContext({PERFIL:data.perfil,P:data.partes,$:()=>({value:''}),ACT:{},TIPOS_VEHICULO:[],hoy:()=>'',esEmpadronado:()=>false});
vm.runInContext(script.slice(script.indexOf('function folioBase('),script.indexOf('function bakeEdits(')),ctx);
vm.runInContext(script.slice(script.indexOf('function infrVigentes('),script.indexOf('function mostrarFoto(')),ctx);
vm.runInContext(script.slice(script.indexOf('function formatoCampoValido('),script.indexOf('const pendientes=')),ctx);
ctx.compactarLugar=String;
ctx.valorActual=(p,k)=>p.ed?.[k]??'';
ctx.buscarInfr=()=>true;
let sin=0,con=0,multi=0;
const camposVehiculo=['Placa','Marca (certificado)','Modelo (certificado)','Año (certificado)','Tipo de vehículo (certificado)','Dígito de la placa'];
for(const p of data.partes){
 ctx.p=p;
 const codes=(p.items||[]).map((x,i)=>String(p.ed?.[`Infracción ${i+1} · código`]??x.cod));
 const classes=codes.map(c=>data.perfil.clasificacion_vehicular[c]);
 const necesita=vm.runInContext('requiereDatosVehiculo(p)',ctx);
 if(classes.includes('vehiculo')){
  assert.equal(necesita,true,`Vehículo: ${p.archivo} página ${p.pagina}`);con++;
  if(codes.length>1)multi++;
 }else if(classes.length&&classes.every(c=>c==='sin_vehiculo')){
  assert.equal(necesita,false,`Sin vehículo: ${p.archivo} página ${p.pagina}`);sin++;
  for(const k of camposVehiculo){
   ctx.f={k,st:'check'};
   assert.equal(vm.runInContext('estadoCampo(p,f,"")',ctx),'blank',k);
  }
  assert.equal(vm.runInContext('avisoVigente(p,"Falta el certificado del Registro Civil de este parte.")',ctx),false);
  const placa=vm.runInContext('campos(p)',ctx)[1].f[0];
  assert.equal(placa.st,'blank');
 }
}
assert.ok(sin>0&&con>0&&multi>0);
assert.equal(data.perfil.clasificacion_vehicular['67'],undefined,'67 depende del contexto');
console.log(`${data.partes.length} partes reales: ${sin} sin datos de vehículo, ${con} con vehículo (${multi} con varias infracciones); 67 conserva contexto.`);
