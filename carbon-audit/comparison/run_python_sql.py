from pathlib import Path
import sys,json,math,hashlib,platform
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'src'))
from audit import run_bundle
from sql_reference import evaluate,stages,views,SCHEMA,native_queries
protocol=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
assert hashlib.sha256((root/'protocol.json').read_text(encoding='utf-8').encode()).hexdigest()==(root/'protocol.sha256').read_text().strip()
def compare(expected,actual):
 failures=[]
 for key,e in expected.items():
  a=actual.get(key)
  if a is None or a['status']!=e['status'] or ((a['value'] is None)!=(e['value'] is None)) or (a['value'] is not None and not math.isclose(float(a['value']),float(e['value']),rel_tol=1e-9,abs_tol=1e-9)):
   failures.append({'key':key,'expected':e,'actual':a})
 if actual.keys()!=expected.keys():failures.append({'unexpected_keys':sorted(actual.keys()-expected.keys())})
 return failures
results=[];pgcases=[]
for case in protocol['cases']:
 record={'id':case['id'],'outputs':len(case['expected']) if 'error' not in case['expected'] else 0,'approaches':{}}
 for approach in ['ledger','sql_full','sql_no_contracts','sql_no_history']:
  try:
   if approach=='ledger':
    raw=run_bundle(case['plan']);actual={v['key']:{'value':v['value'],'status':v['status']} for v in raw['values'] if v['kind']=='derived'}
   else:actual=evaluate(case['plan'],contracts=approach!='sql_no_contracts',history=approach!='sql_no_history')[-1]
   failures=[{'expected_error':True}] if 'error' in case['expected'] else compare(case['expected'],actual)
   record['approaches'][approach]={'failures':failures,'actual':actual}
  except Exception as e:
   record['approaches'][approach]={'error':str(e),'failures':[] if 'error' in case['expected'] else [{'exception':str(e)}]}
  print(case['id'],approach,len(record['approaches'][approach]['failures']),flush=True)
 try:
  compiled=[]
  for stage in stages(case['plan']):
   sql,outputs=views(stage['nodes'],stage['known'],postgres=True,present_keys=stage['present'])
   compiled.append({'name':stage['name'],'commands':stage['commands'],'views':sql,'outputs':outputs,'native_queries':native_queries(stage['nodes'])})
  pgcases.append({'id':case['id'],'stages':compiled,'expected':case['expected']})
 except ValueError as e:pgcases.append({'id':case['id'],'rejected_by_declaration_adapter':str(e),'expected':case['expected']})
 results.append(record)
(root/'python_sql_results.json').write_text(json.dumps({'protocol_hash':(root/'protocol.sha256').read_text(),'environment':platform.platform(),'results':results},indent=2),encoding='utf-8')
(root/'provsql_cases.json').write_text(json.dumps({'schema':SCHEMA,'cases':pgcases},indent=2),encoding='utf-8')
print('Saved comparative results and PostgreSQL queries')
