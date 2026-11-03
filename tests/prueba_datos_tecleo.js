const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
(async()=>{
for(const path of ['parte_scan/web/index.html']){
 const script=fs.readFileSync(path,'utf8').match(/<script>([\s\S]*)<\/script>/)[1];
 const calls=[],p={nombre:'Nombre OCR NACIONALIDAD',ed:{'Nombre (certificado)':'NOMBRE CORREGIDO'}};
 const elements={tAviso:{},tAuto:{checked:true},tAct:{value:''}};
 let fail=false;
 const ctx=vm.createContext({P:[p],$:id=>elements[id],valorActual:(p,k)=>p.ed[k]??'',hoy:()=>'',infrVigentes:()=>[],placa6:String,
 fetch:async(url,opt)=>{calls.push({url,body:JSON.parse(opt.body)});return {json:async()=>fail?{error:'En curso'}:{ok:true}}},alert(){},tecSondear(){}});
 vm.runInContext(script.slice(script.indexOf('function V(p,k)'),script.indexOf("$('btnTecleo').onclick=")),ctx);
 vm.runInContext("let tMarcando=false;",ctx);
 vm.runInContext(script.slice(script.indexOf('async function tecPost('),script.indexOf('function tecPintar(')),ctx);
 vm.runInContext(script.slice(script.indexOf('async function tecIniciar('),script.indexOf("$('tTabla').onclick=")),ctx);
 await vm.runInContext('tecIniciar(null)',ctx);
 assert.equal(calls[0].url,'/api/tecleo/cargar');
 assert.equal(calls[0].body.partes[0].nombre,'NOMBRE CORREGIDO');
 assert.equal(calls[1].url,'/api/tecleo/iniciar');
 assert.equal(calls[1].body.auto,true);
 calls.length=0;fail=true;
 await vm.runInContext('tecIniciar(null)',ctx);
 assert.equal(calls.length,1);assert.equal(elements.tAviso.textContent,'En curso');
 console.log(path+': reenvía el nombre corregido antes de iniciar y no inicia si falla la carga');
}
})().catch(e=>{console.error(e);process.exitCode=1});
