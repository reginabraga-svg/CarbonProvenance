"""Independent SQL reconstruction from source snapshots and operation declarations.
No import of audit.py, engine.py or their encoded states.
"""
import csv,io,copy,json,sqlite3,math
from pathlib import Path
FIELDS=['qkind','unit','period','support']
def lit(x):
 if x is None:return 'NULL'
 if isinstance(x,(int,float)):return repr(x)
 return "'"+str(x).replace("'","''")+"'"
def source_rows(spec,text):
 rows=[];seen=set()
 for r in csv.DictReader(io.StringIO(text)):
  key=r['key']
  if key in seen:raise ValueError('duplicate source key')
  seen.add(key);value=float(r['value'])
  if not math.isfinite(value):raise ValueError('non-finite source value')
  rows.append([key,value,*[r.get(f) or spec.get('contract',{}).get(f) for f in FIELDS],spec['name']])
 return rows
SCHEMA=['CREATE TABLE facts(key TEXT NOT NULL,value DOUBLE PRECISION,qkind TEXT,unit TEXT,period TEXT,support TEXT,source TEXT)','CREATE TABLE history(key TEXT PRIMARY KEY)','CREATE TABLE edges(output_key TEXT,input_key TEXT)']
def node_order(nodes):
 pending=list(nodes);done=[]
 while pending:
  remaining={n['key'] for n in pending};ready=[n for n in pending if not(set(n['inputs'])&remaining)]
  if not ready:raise ValueError('dependency cycle')
  for n in ready:
   if n['op'] not in ['sum','diff','mul','scale','lin','ratio','broadcast']:raise ValueError('unsupported operation')
   done.append(n);pending.remove(n)
 return done

def views(nodes,known_keys,contracts=True,history=True,postgres=False,present_keys=None):
 ordered=node_order(nodes);mapping={};statements=[]
 all_source_keys=sorted(set(known_keys)|{k for n in ordered for k in n['inputs'] if k not in {x['key'] for x in ordered}})
 active='facts' if not postgres else '(SELECT key,value,qkind,unit,period,support,source FROM facts WHERE present(provenance()))'
 for i,key in enumerate(all_source_keys):
  name='source_'+str(i);mapping[key]=name
  missing="CASE WHEN EXISTS(SELECT 1 FROM history h WHERE h.key="+lit(key)+") THEN 'orphan' ELSE 'unresolved' END" if history else "'unresolved'"
  if present_keys is not None and key in present_keys:
   statements.append(f"CREATE VIEW {name} AS SELECT f.value,f.qkind,f.unit,f.period,f.support,'ok' AS status FROM {active} f WHERE f.key={lit(key)}")
   continue
  statements.append(f'CREATE VIEW {name} AS SELECT f.value,f.qkind,f.unit,f.period,f.support,CASE WHEN f.key IS NOT NULL THEN \'ok\' ELSE {missing} END AS status FROM (SELECT 1 AS seed) seed LEFT JOIN {active} f ON f.key={lit(key)}')
 for i,n in enumerate(ordered):
  name='output_'+str(i);op=n['op'];ins=n['inputs'];params=n.get('params',{});v=[f'i{j}.value' for j in range(len(ins))]
  joins=' '.join(f'CROSS JOIN {mapping[k]} i{j}' for j,k in enumerate(ins))
  bad=[]
  canon=lambda expr:f"replace({expr},'/ a','/ yr')"
  if contracts:
   for j,e in enumerate(params.get('expect',[])):
    if e is None:continue
    for f,want in zip(FIELDS,e):
     if f in ['period','support'] and not want:continue
     left=f'i{j}.{f}';right=lit(want)
     if f=='unit':left=canon(left);right=canon(right)
     bad.append(f'{left}<>{right}')
   if op in ['sum','diff','ratio'] and len(ins)>1:
    for j in range(1,len(ins)):
     bad += [f'i{j}.qkind<>i0.qkind',f'{canon(f"i{j}.unit")}<>{canon("i0.unit")}']
     # Sums require the same period. Differences allow different dates of the same period type.
     if op in ['sum','ratio']:bad.append(f'i{j}.period<>i0.period')
     else:bad.append(f"substr(i{j}.period,1,instr(i{j}.period,':')-1)<>substr(i0.period,1,instr(i0.period,':')-1)" if not postgres else f"split_part(i{j}.period,':',1)<>split_part(i0.period,':',1)")
  statuses=[]
  for s in ['orphan','unresolved','blocked']:
   if ins:statuses.append('WHEN '+ ' OR '.join(f"i{j}.status={lit(s)}" for j in range(len(ins)))+' THEN '+lit(s))
  if bad:statuses.append('WHEN '+' OR '.join('('+x+')' for x in bad)+" THEN 'blocked'")
  if op=='ratio':statuses.append("WHEN i1.value=0 THEN 'unresolved'")
  contextual=[f"i{j}.status='contextual'" for j in range(len(ins))]
  if contracts and op=='broadcast':contextual.append('i0.support<>'+lit(n['contract']['support']))
  if contextual:statuses.append('WHEN '+' OR '.join(contextual)+" THEN 'contextual'")
  status='CASE '+' '.join(statuses)+" ELSE 'ok' END" if statuses else "'ok'"
  k=lit(params.get('k',1))
  if op=='sum':value=' + '.join(v) or '0'
  elif op=='mul':value=' * '.join(v)+f' * {k}'
  elif op=='diff':value=f'{v[0]} - {v[1]}'
  elif op=='ratio':value=f'{v[0]} / NULLIF({v[1]},0) * {k}'
  elif op=='broadcast':value=v[0]
  elif op=='scale':value=f'{v[0]} * {k}'
  elif op=='lin':value=' + '.join(f'({lit(w)} * {x})' for w,x in zip(params['w'],v))
  inner=f'SELECT ({value}) AS computed,{status} AS status FROM (SELECT 1 AS seed) seed {joins}'
  meta=','.join(lit(n['contract'][f])+' AS '+f for f in FIELDS)
  statements.append(f"CREATE VIEW {name} AS SELECT CASE WHEN status IN ('ok','contextual') THEN computed ELSE NULL END AS value,{meta},status FROM ({inner}) calculation")
  mapping[n['key']]=name
 return statements,{n['key']:mapping[n['key']] for n in ordered}

def stages(plan):
 current={};known=set();initial=[]
 for spec in plan['sources']:
  for row in source_rows(spec,spec['csv']):
   if row[0] in current:raise ValueError('duplicate key across sources')
   current[row[0]]=row;known.add(row[0]);initial.append('INSERT INTO facts VALUES ('+','.join(map(lit,row))+')');initial.append('INSERT INTO history VALUES ('+lit(row[0])+')')
 nodes=copy.deepcopy(plan['nodes']);out=[dict(name='baseline',commands=initial,nodes=copy.deepcopy(nodes),known=sorted(known),present=sorted(current))]
 for revision in plan.get('revisions',[]):
  commands=[]
  for update in revision.get('updates',[]):
   spec=next(s for s in plan['sources'] if s['name']==update['source']);new={r[0]:r for r in source_rows(spec,update['csv'])};old={k:r for k,r in current.items() if r[-1]==spec['name']}
   for key in old.keys()-new.keys():commands.append('DELETE FROM facts WHERE key='+lit(key));current.pop(key)
   for key,row in new.items():
    if key in old:
     if row!=old[key]:commands.append('UPDATE facts SET '+','.join(f'{f}={lit(x)}' for f,x in zip(['key','value',*FIELDS,'source'],row))+' WHERE key='+lit(key))
    else:commands.append('INSERT INTO facts VALUES ('+','.join(map(lit,row))+')')
    if key not in known:commands.append('INSERT INTO history VALUES ('+lit(key)+')');known.add(key)
    current[key]=row
  nodes.extend(copy.deepcopy(revision.get('add_nodes',[])))
  for n in nodes:
   if n['key'] in revision.get('rewire',{}):n['inputs']=revision['rewire'][n['key']]
  out.append(dict(name=revision['name'],commands=commands,nodes=copy.deepcopy(nodes),known=sorted(known),present=sorted(current)))
 return out

def evaluate(plan,contracts=True,history=True):
 con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
 for sql in SCHEMA:con.execute(sql)
 snapshots=[]
 for stage in stages(plan):
  for sql in stage['commands']:con.execute(sql)
  old=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view'")]
  for name in reversed(old):con.execute('DROP VIEW '+name)
  statements,outputs=views(stage['nodes'],stage['known'],contracts,history,present_keys=stage['present'])
  for sql in statements:con.execute(sql)
  snapshots.append({key:dict(con.execute('SELECT value,status FROM '+name).fetchone()) for key,name in outputs.items()})
 con.close();return snapshots


def native_queries(nodes):
    ordered=node_order(nodes);by_key={n['key']:n for n in ordered};out={}
    for node in ordered:
        leaves=[]
        def expression(key):
            if key not in by_key:
                if key not in leaves:leaves.append(key)
                return 'f'+str(leaves.index(key))+'.value'
            n=by_key[key];op=n['op'];p=n.get('params',{});xs=[expression(k) for k in n['inputs']];k=lit(p.get('k',1))
            if op=='sum':return '('+(' + '.join(xs) or '0')+')'
            if op=='mul':return '('+' * '.join(xs)+' * '+k+')'
            if op=='diff':return '('+xs[0]+' - '+xs[1]+')'
            if op=='ratio':return '('+xs[0]+' / NULLIF('+xs[1]+',0) * '+k+')'
            if op=='scale':return '('+xs[0]+' * '+k+')'
            if op=='broadcast':return xs[0]
            if op=='lin':return '('+' + '.join('('+lit(w)+' * '+x+')' for w,x in zip(p['w'],xs))+')'
            raise ValueError(op)
        expr=expression(node['key']);tables=' CROSS JOIN '.join('facts f'+str(i) for i in range(len(leaves)));where=' AND '.join('f'+str(i)+'.key='+lit(key) for i,key in enumerate(leaves))
        out[node['key']]={'sql':'SELECT '+expr+' AS value,provenance() AS token,present(provenance()) AS active FROM '+tables+' WHERE '+where,'source_keys':leaves}
    return out
