const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const script=fs.readFileSync('parte_scan/web/index.html','utf8').match(/<script>([\s\S]*)<\/script>/)[1];
const ctx=vm.createContext({});
vm.runInContext(script.slice(script.indexOf('function formatoCampoValido('),script.indexOf('function estadoCampo(')),ctx);
for(const [key,value,valid] of [['Fecha del parte','31/02/2026',false],['Fecha del parte','29/02/2024',true],['Hora de la infracción','25:00',false],['Hora de la infracción','23:59',true],['RUT (certificado)','11111111-1',true],['RUT (certificado)','11111111-2',false]]){
 assert.equal(vm.runInContext(`formatoCampoValido(${JSON.stringify(key)},${JSON.stringify(value)})`,ctx),valid);
}
console.log('Fechas, horas y dígito verificador RUT OK');
