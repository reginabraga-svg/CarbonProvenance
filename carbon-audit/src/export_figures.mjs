import path from 'node:path';import {fileURLToPath} from 'node:url';import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')+'/';const dir=root+'carbon-provenance-lab/dist/';
const ctx=vm.createContext({state:{charts:JSON.parse(fs.readFileSync(dir+'chart-data.json')),evidence:JSON.parse(fs.readFileSync(dir+'evidence.json'))},esc:x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))});
vm.runInContext(fs.readFileSync(dir+'charts.js','utf8'),ctx);
fs.mkdirSync(root+'research_outputs/exports',{recursive:true});
for(const [id,year,n] of [['soil',2020,4],['cover',2021,5]]){
 vm.runInContext(`chartState.id='${id}';chartState.year=${year};`,ctx);
 const c=vm.runInContext('selectedChart()',ctx);assert.equal(c.year,year);assert.equal(c.rows.length,id==='soil'?27:8);
 const stem=root+'research_outputs/exports/Figure_'+n;
 fs.writeFileSync(stem+'.svg',vm.runInContext('plotSVG(selectedChart())',ctx));fs.writeFileSync(stem+'.csv',vm.runInContext('chartCSV(selectedChart())',ctx));fs.writeFileSync(stem+'.json',JSON.stringify(c,null,2));
}
const e=ctx.state.evidence.attribution;const soil=ctx.state.charts.cases.find(c=>c.id==='soil'),cover=ctx.state.charts.cases.find(c=>c.id==='cover');
assert.ok(Math.abs(soil.data['2020'].find(r=>r.label==='Rondonia').value-e.X1_rondonia_2020_soil_revision.change_pct)<.05);
for(const [label,v] of Object.entries(e.X4_brazil_2021_land_cover_revision.by_class_TgC))assert.ok(Math.abs(cover.data['2021'].find(r=>r.label===label).value-v)<.0051,label);
for(const c of ctx.state.charts.cases)for(const rows of Object.values(c.data))for(const r of rows)assert.ok(r.value===null||Number.isFinite(r.value));
vm.runInContext("chartState.id='revision-counts'",ctx);assert.equal(vm.runInContext('selectedChart().rows.length',ctx),24);
console.log('Checks passed: 27 states, 8 published class changes, 24 revision count records, finite values, SVG and CSV exports.');
