const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
new Function(script);
const storage=new Map();
const ctx=vm.createContext({localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
  valorActual:(p,k)=>p[k]||'',toast(){}});
vm.runInContext(script.slice(script.indexOf('const CLAVE_MEMORIA='),script.indexOf('function pintarMemoria(')),ctx);
const run=s=>vm.runInContext(s,ctx);
for(const value of ["0´higgins 123", "O’HIGGINS 123", "O'HIGGINS 123",'0 HIGGINS 123']){
  assert.equal(run(`normalizarDireccion(${JSON.stringify(value)})`),'OHIGGINS 123');
}
assert.equal(run('normalizarDireccion("LOS HIGGINS 123")'),'LOS HIGGINS 123');
run(`var p={origen:'carab','Oficina emisora':'TENENCIA CORRAL','Comuna (certificado)':'CORRAL'};`);
assert.equal(run(`recordarCalle(p,'Lugar','CALIE MATTA 12','CALLE MATTA 12')`),true);
assert.equal(run(`sugerenciasMemoria(p,'Lugar','CALIE MATTA 12').length`),1);
assert.equal(run(`sugerenciasMemoria(p,'Lugar','CALIE MATTA 13').length`),0);
assert.equal(run(`sugerenciasMemoria({...p,'Comuna (certificado)':'VALDIVIA'},'Lugar','CALIE MATTA 12').length`),0);
assert.equal(run(`sugerenciasMemoria(p,'Dirección (certificado)','CALIE MATTA 12').length`),0);
assert.equal(run(`recordarCalle(p,'RUT (certificado)','123','456')`),false);
run(`var datos=leerMemoria();datos[0].activa=false;guardarMemoria(datos)`);
assert.equal(run(`sugerenciasMemoria(p,'Lugar','CALIE MATTA 12').length`),0);
run(`guardarMemoria([])`);assert.equal(run('leerMemoria().length'),0);
console.log('OHIGGINS y memoria: coincidencia exacta, contexto, campos permitidos, desactivar y olvidar OK');
