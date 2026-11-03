const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
(async()=>{
for(const path of ['parte_scan/web/index.html']){
 const html=fs.readFileSync(path,'utf8'),script=html.match(/<script>([\s\S]*)<\/script>/)[1];
 new Function(script);
 const elements={};const $=id=>elements[id]??=( {textContent:'',options:[{},{}],querySelectorAll:()=>[],value:'',checked:false});
 let rows=[{uid:0,estado:'interrumpido',n_parte:'1',errores:[],avisos:[],aviso:'guardado no detectado'}],saved=[],reject=false,pollResolve;
 const ctx=vm.createContext({$,P:[{fin:false}],pend:0,subiendo:0,ultimoAuto:'',Promise,Error,Option:function(){},esc:String,pintarTira(){},mostrar(){},alert(msg){ctx.alerts.push(msg)},alerts:[],estadoSesion:()=>JSON.stringify({partes:ctx.P}),fetch:async(url,opt)=>{
  if(url.includes('/sesion/auto')){saved.push(JSON.parse(opt.body));return {ok:true,json:async()=>({ok:true})}}
  if(url.endsWith('/marcar')){if(reject)return {json:async()=>({error:'En curso'})};rows[0].estado=JSON.parse(opt.body).estado;return {json:async()=>({ok:true})}}
  if(pollResolve===null)return new Promise(resolve=>pollResolve=()=>resolve({json:async()=>snapshot('interrumpido')}));
  return {json:async()=>snapshot(rows[0].estado)};
 }});
 function snapshot(estado){return {partes:[{...rows[0],estado}],log:[],nlog:0,actuarios:[],disponible:true,corriendo:false}}
 vm.runInContext(script.slice(script.indexOf('let colaAuto='),script.indexOf('setInterval(()=>{autoguardar')),ctx);
 vm.runInContext(script.slice(script.indexOf('const TXT_EST='),script.indexOf("$('tTabla').onclick=")),ctx);
 vm.runInContext('tecPintar('+JSON.stringify(snapshot('interrumpido'))+')',ctx);
 assert.match($('tTabla').innerHTML,/Confirmar ingreso/);
 pollResolve=null;const stale=vm.runInContext('tecSondear()',ctx);
 await vm.runInContext("tecMarcar(0,'ingresado')",ctx);pollResolve();await stale;
 assert.equal(ctx.P[0].fin,true);assert.equal(saved.at(-1).partes[0].fin,true);
 assert.match($('tResumen').textContent,/1 de 1 ingresados · 0 pendientes/);
 assert.match($('tTabla').innerHTML,/Volver a pendiente/);
 assert.match($('tTabla').innerHTML,/data-uno="0" disabled/);
 await vm.runInContext("tecMarcar(0,'pendiente')",ctx);
 assert.equal(ctx.P[0].fin,false);assert.equal(saved.at(-1).partes[0].fin,false);
 assert.match($('tResumen').textContent,/0 de 1 ingresados · 1 pendientes/);
 reject=true;await vm.runInContext("tecMarcar(0,'ingresado')",ctx);
 assert.equal(ctx.P[0].fin,false);assert.equal(ctx.alerts.at(-1),'En curso');
 console.log(path+': confirmación, reversión, contadores, autoguardado, respuesta obsoleta y rechazo OK');
}
})().catch(e=>{console.error(e);process.exitCode=1});
