// Semáforo y formulario deben validar los mismos valores de las sesiones reales.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
const source="import json,sys,zipfile\nfrom parte_scan import servidor,perfil\nwith zipfile.ZipFile(sys.argv[1]) as z:estado=json.loads(z.read('estado.json'))\nprint(json.dumps({'estado':estado,'perfil':servidor.estado_perfil(),'infracciones':list(perfil.infracciones().items())}))";
const result=spawnSync(process.env.PARTESCAN_PYTHON||'python',['-X','utf8','-c',source,process.argv[2]],{encoding:'utf8'});
assert.equal(result.status,0,result.stderr);
const data=JSON.parse(result.stdout),estado=data.estado,perfil=data.perfil;
const ACT={};for(let d=0;d<10;d++){const nombre=perfil.rol_actuario[String(d)];ACT[d]=nombre?[nombre,perfil.actuarios[nombre]]:null}
const ctx=vm.createContext({PERFIL:perfil,P:estado.partes,INFR:data.infracciones,ACT,
 $:id=>({value:id==='rol'?estado.rol||'':id==='cit'?estado.cit||'':''}),hoy:()=> '24/11/2026'});
vm.runInContext(script.match(/const TIPOS_VEHICULO=.*?;/)[0],ctx);
const cargar=(a,b)=>vm.runInContext(script.slice(script.indexOf(a),script.indexOf(b)),ctx);
cargar('function folioBase(','function bakeEdits(');
cargar('function buscarInfr(','function normalizarInfraccion(');
cargar('function infrVigentes(','function mostrarFoto(');
cargar('function compactarLugar(','function textoMemoria(');
cargar('function formatoRut(','function copiarCampo(');
cargar('function V(p,k)',"$('btnTecleo').onclick=");
cargar('function campoPendiente(','function siguientePendiente(');
let inconsistencias=0;
for(const p of estado.partes){
 ctx.p=p;
 const visibles=vm.runInContext("campos(p).flatMap(s=>s.f).filter(f=>!(p.origen==='carab'&&esEmpadronado(p)&&f.k==='Comuna (certificado)')).filter(f=>estadoCampo(p,f,valorActual(p,f.k))==='check').map(f=>f.k)",ctx);
 const semaforo=vm.runInContext('pendientes(p)',ctx);
 if(semaforo!==visibles.length){console.log('Diferencia',p.pagina,'contador',semaforo,'visibles',visibles.length,visibles);inconsistencias++}
 for(const key of visibles){ctx.key=key;if(!p.fin)assert.equal(vm.runInContext('campoPendiente(p,key)',ctx),true)}
 if(p.folio==='117862'){
  console.log('117862: pendientes visibles',visibles,'contador',semaforo);
  assert.equal(visibles.length,0,'El parte real tiene su identificación y dirección completas');
 }
 if(estado.partes.length===53&&[26,37].includes(p.pagina)){
  // El RUT impreso inválido sí necesita revisión, aunque luego fuera corregido.
  assert.equal(vm.runInContext("estadoCampo(p,campos(p).flatMap(s=>s.f).find(f=>f.k==='RUT (certificado)'),formatoRut(p.cert.rut))",ctx),'check');
 }
}
assert.equal(inconsistencias,0,'El semáforo debe coincidir con los campos que pide revisar el formulario');
console.log(estado.partes.length+' partes reales: formulario, filtro y semáforo consistentes.');
