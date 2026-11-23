import fs from 'node:fs';import path from 'node:path';import {pathToFileURL,fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));const runtime=process.env.PROVSQL_RUNTIME||path.resolve(root,'vendor/runtime');
const {PGlite}=await import(pathToFileURL(runtime+'/pglite/index.js'));const {uuid_ossp}=await import(pathToFileURL(runtime+'/pglite/contrib/uuid_ossp.js'));
const provsql={name:'provsql',setup:async(_pg,o)=>({emscriptenOpts:o,bundlePath:pathToFileURL(runtime+'/provsql.tar.gz')})};
const pg=await PGlite.create({extensions:{uuid_ossp,provsql}});await pg.exec('CREATE EXTENSION provsql CASCADE; SET search_path=public,provsql; SET provsql.update_provenance=on; SET join_collapse_limit=1; SET from_collapse_limit=1; SET statement_timeout=10000;');
const metadata={postgres:(await pg.query('SELECT version()')).rows,provsql:(await pg.query("SELECT extversion FROM pg_extension WHERE extname='provsql'")).rows,protocol_hash:fs.readFileSync(root+'/protocol.sha256','utf8').trim(),timing_scope:'No cross-runtime timing comparison',adapter_scope:'Plain SQL contract and history views classify outputs. Native ProvSQL queries execute the unrolled arithmetic and retain provenance tokens. Classification is supplied by the SQL adapter, not claimed as built-in ProvSQL labels.',asset_manifest:JSON.parse(fs.readFileSync(runtime+'/download_manifest.json','utf8'))};
const input=JSON.parse(fs.readFileSync(root+'/provsql_cases.json','utf8'));const results=[];
for(const [index,test] of input.cases.entries()){
 if(test.rejected_by_declaration_adapter){results.push({id:test.id,adapter_rejection:test.rejected_by_declaration_adapter,failures:[],scope:'The declaration adapter rejected the operation. This is not a ProvSQL feature limitation.'});continue}
 const rec={id:test.id,snapshots:[],failures:[]};let lastSQL='';
 try{
  await pg.exec(`CREATE SCHEMA case_${index}; SET search_path=case_${index},public,provsql;`);
  for(const sql of input.schema){lastSQL=sql;await pg.exec(sql)}
  await pg.exec(input.schema[0].replace('CREATE TABLE facts','CREATE TABLE plain_facts'));await pg.query("SELECT add_provenance('facts')");let priorViews=[];
  for(const stage of test.stages){
   for(const sql of stage.commands){lastSQL=sql;await pg.exec(sql)}
   const sourceRows=(await pg.query('SELECT key,value,qkind,unit,period,support,source,present(provenance()) AS active FROM facts')).rows.filter(r=>r.active);
   await pg.exec('DELETE FROM plain_facts');
   for(const r of sourceRows)await pg.query('INSERT INTO plain_facts VALUES ($1,$2,$3,$4,$5,$6,$7)',[r.key,r.value,r.qkind,r.unit,r.period,r.support,r.source]);
   for(const name of priorViews.reverse())await pg.exec('DROP VIEW '+name+' CASCADE');priorViews=[];
   for(const sql of stage.views){lastSQL=sql.replace('FROM facts WHERE present(provenance())','FROM plain_facts');await pg.exec(lastSQL);priorViews.push(sql.match(/^CREATE VIEW (\w+)/)[1])}
   const values={},native={};let tokens=0,checked=0;
   for(const [key,view] of Object.entries(stage.outputs)){
    lastSQL=`SELECT value,status FROM ${view}`;
    const rows=(await pg.query(lastSQL)).rows;
    if(rows.length!==1)throw Error(key+': expected one policy row, got '+rows.length);
    const r=rows[0];values[key]={value:r.value===null?null:Number(r.value),status:r.status};
    lastSQL=stage.native_queries[key].sql;
    const actual=(await pg.query(lastSQL)).rows.filter(r=>r.active===true);
    native[key]={source_keys:stage.native_queries[key].source_keys,actual_rows:actual.map(r=>({value:r.value,token:r.token}))};
    if(actual.some(r=>r.token))tokens++;
    if(r.status==='ok'||r.status==='contextual'){
     if(actual.length!==1||actual[0].value===null||Math.abs(Number(actual[0].value)-Number(r.value))>Math.max(1e-9,1e-9*Math.abs(Number(r.value))))throw Error(key+': native arithmetic disagrees with SQL policy');
    }
    if(++checked%50===0)console.log(test.id,stage.name,checked+' outputs');
   }
   rec.snapshots.push({name:stage.name,values,outputs_with_token:tokens,native});
  }
  const values=rec.snapshots.at(-1).values;
  for(const [key,e] of Object.entries(test.expected)){
   const a=values[key];if(!a||a.status!==e.status||(a.value===null)!==(e.value===null)||(a.value!==null&&Math.abs(a.value-e.value)>Math.max(1e-9,1e-9*Math.max(Math.abs(a.value),Math.abs(e.value)))))rec.failures.push({key,expected:e,actual:a});
  }
  rec.modification_log=(await pg.query('SELECT query_type,query FROM update_provenance')).rows.map(({query_type,query})=>({query_type,query}));
 }catch(e){rec.error=e.message;rec.failed_sql=lastSQL;rec.failures.push({exception:e.message})}
 results.push(rec);console.log(test.id,'failures',rec.failures.length,rec.error||'');
 fs.writeFileSync(root+'/provsql_results.json',JSON.stringify({metadata,results},null,2));
}
metadata.functions=(await pg.query("SELECT proname,pg_get_function_identity_arguments(p.oid) AS args FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='provsql' AND proname IN ('where_provenance','sub_circuit_for_where','get_gate_type','get_children','provenance_evaluate')")).rows;
fs.writeFileSync(root+'/provsql_results.json',JSON.stringify({metadata,results},null,2));await pg.close();

