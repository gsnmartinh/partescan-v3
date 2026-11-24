const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
new Function(script);
const storage=new Map();
const INFR=[['92','VEHICULO SIN SEGURO OBLIGATORIO'],['37','VEHICULO SIN PERMISO CIRCULACION VIGENTE'],['33','VEHICULO SIN REVISION TECNICA VIGENTE'],['19','ESTACIONAR SITIO PROHIBIDO Y SEÑALIZADO']];
const ctx=vm.createContext({INFR,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},toast(){},confirm:()=>true,
 V:(p,k)=>p.ed?.[k]??(k==='Oficina emisora'?p.oficina:k==='Descripción de la causa'?p.causa:p.items[Number(k.match(/\d+/)?.[0])-1]?.cod),
 infrVigentes:p=>p.items.map((x,i)=>p.ed?.[`Infracción ${i+1} — código`]??x.cod).filter(Boolean)});
vm.runInContext(script.slice(script.indexOf('function bakeEdits('),script.indexOf('function refrescarConScroll(')),ctx);
vm.runInContext(script.slice(script.indexOf('function buscarInfr('),script.indexOf('function barraInfracciones(')),ctx);
const run=s=>vm.runInContext(s,ctx);
// El selector funciona sin datalist y el clic confirma un código, no el texto de búsqueda.
ctx.Event=class{constructor(type){this.type=type}};
ctx.document={createElement:()=>({childNodes:[],setAttribute(){},replaceChildren(){this.childNodes=[]},append(x){this.childNodes.push(x)}})};
const listeners={};let selected,results;
ctx.el={value:'revision',removeAttribute(){},addEventListener:(k,f)=>listeners[k]=f,after:x=>results=x,
 dispatchEvent:e=>{selected=ctx.el.value;listeners[e.type]?.()}};
run('agregarSelectorInfracciones(el)');listeners.input();
assert.equal(results.childNodes[0].textContent,'33 — VEHICULO SIN REVISION TECNICA VIGENTE');
results.childNodes[0].onclick();assert.equal(selected,'33');assert.equal(results.childNodes.length,0);
assert.equal(run(`sugerirInfracciones('revision tecnica')[0][0]`),'33');
assert.equal(run(`sugerirInfracciones('señalizado')[0][0]`),'19');
assert.equal(run(`sugerirInfracciones('37')[0][0]`),'37');
assert.equal(run(`buscarInfr('37 — VEHICULO SIN PERMISO CIRCULACION VIGENTE')[0]`),'37');
run(`var p={origen:'carab',oficina:'CORRAL',infraccion_texto:'permiso, seguro y revisión técnica vencidos',items:[{cod:'92'},{cod:'37'},{cod:'33'}],ed:{},done:{},ok:{}};sincronizarDescripcion(p)`);
assert.equal(run('p.causa'),'CONDUCIR CON LA TOTALIDAD DE LA DOCUMENTACION VENCIDA');
run(`p.infraccion_texto='sin permiso de circulación, seguro y revisión técnica';sincronizarDescripcion(p)`);
assert.equal(run('p.causa'),'CONDUCIR SIN LA TOTALIDAD DE LA DOCUMENTACION');
run(`p.infraccion_texto='sin seguro, revisión técnica vencida y permiso vencido';sincronizarDescripcion(p)`);
assert.match(run('p.causa'),/ \/ /);
run(`p.infraccion_texto='seguro vigente, revisión técnica y permiso vencidos';sincronizarDescripcion(p)`);
assert.match(run('p.causa'),/ \/ /);
assert.equal(run('recordarInterpretacion(p)'),true);
assert.equal(run('sugerirInterpretacion(p).codigos.length'),3);
assert.equal(run(`sugerirInterpretacion({...p,oficina:'VALDIVIA'})`),undefined);
assert.equal(run(`sugerirInterpretacion({...p,infraccion_texto:'otro texto'})`),undefined);
run(`p.ed['Infracción 1 — código']='19';p.ok['Infracción 1 — código']=true;aplicarInterpretacion(p,sugerirInterpretacion(p))`);
assert.equal(run(`p.items[0].cod`),'92');
assert.equal(run(`p.items[0].estado`),'check');
assert.equal(run(`p.ok['Infracción 1 — código']`),undefined);
run(`INFR[0][1]='CODIGO MODIFICADO'`);
assert.equal(run('sugerirInterpretacion(p)'),undefined);
console.log('Infracciones: búsqueda, resumen, estados mixtos, memoria por oficina, revisión e invalidación de catálogo OK');
