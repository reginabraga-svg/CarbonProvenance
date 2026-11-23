"""E13 descriptive sensitivity on E12 level 1 records. Does not use the dashboard."""
from pathlib import Path
from hashlib import sha256
import json,csv,math
import pandas as pd
ROOT=Path(__file__).resolve().parent
raw=(ROOT/'E13_protocol.json').read_bytes();p=json.loads(raw)
assert sha256(raw).hexdigest()==(ROOT/'E13_protocol.sha256').read_text().strip()
assert sha256((ROOT/p['input']).read_bytes()).hexdigest()==p['input_sha256']
d=pd.read_csv(ROOT/p['input'],dtype={'id':str});d=d[d.scenario==p['partition']].copy()
assert len(d)==27840 and (d.before>0).all() and (d.after>=0).all()
assert d.groupby('id').ano.nunique().eq(5).all()
assert d.groupby(['id','ano']).size().eq(1).all()
denoms={'previous':d.before,'symmetric':(d.before+d.after)/2,'maximum':d[['before','after']].max(axis=1)}
counts=[]
for name,den in denoms.items():
 for t in p['thresholds_percent']:
  a=d.gross/den*100>=t;n=d.net.abs()/den*100>=t
  counts.append(dict(denominator=name,threshold_percent=t,eligible=len(d),class_alerts=int(a.sum()),total_alerts=int(n.sum()),class_without_total=int((a&~n).sum())))
e12=json.loads((ROOT/'E12_results.json').read_text());expected=next(s for s in e12['scenarios'] if s['name']=='level1')['threshold_results']
for got,ref in zip(counts[:4],expected):
 assert got['class_alerts']==ref['class_alerts'] and got['total_alerts']==ref['total_alerts']
d['alert']=(d.gross/d.before*100>=1)&(d.net.abs()/d.before*100<1)
yearrows=[];groups=[]
for y,g in d.groupby('ano',sort=True):
 g=g.sort_values(['before','id']).copy();g['stock_group']=[min(4,i*4//len(g)+1) for i in range(len(g))]
 total=float(g.before.sum())
 yearrows.append(dict(year=int(y),eligible=len(g),alerts=int(g.alert.sum()),alert_percent=float(g.alert.mean()*100),previous_stock_in_alerts_percent=float(g.loc[g.alert,'before'].sum()/total*100),gross_sum_TgC=float(g.gross.sum()/1e6),weighted_gross_percent=float(g.gross.sum()/total*100),median_gross_percent=float(g.gross_percent.median())))
 for rank,s in g.groupby('stock_group'):
  groups.append(dict(year=int(y),group=int(rank),eligible=len(s),previous_stock_min_tC=float(s.before.min()),previous_stock_max_tC=float(s.before.max()),alerts=int(s.alert.sum()),alert_percent=float(s.alert.mean()*100),median_gross_percent=float(s.gross_percent.median())))
persistent=d.groupby('id').alert.sum().value_counts().reindex(range(6),fill_value=0)
omissions=[]
for y in p['years']:
 g=d[d.ano!=y];omissions.append(dict(omitted_year=y,eligible=len(g),alerts=int(g.alert.sum()),alert_percent=float(g.alert.mean()*100)))
# Independent summary of the same E12 records, not independent validation of their source maps.
ind=[]
with (ROOT/p['input']).open(newline='',encoding='utf-8') as f:
 for r in csv.DictReader(f):
  if r['scenario']=='level1':ind.append({k:(r[k] if k=='id' else int(r[k]) if k=='ano' else float(r[k])) for k in ['id','ano','before','after','net','gross']})
checks=0
for rec in counts:
 a=n=b=0
 for r in ind:
  den={'previous':r['before'],'symmetric':(r['before']+r['after'])/2,'maximum':max(r['before'],r['after'])}[rec['denominator']]
  ca=r['gross']/den*100>=rec['threshold_percent'];ta=abs(r['net'])/den*100>=rec['threshold_percent']
  a+=ca;n+=ta;b+=ca and not ta
 assert (a,n,b)==(rec['class_alerts'],rec['total_alerts'],rec['class_without_total']);checks+=1
for rec in yearrows:
 g=[r for r in ind if r['ano']==rec['year']];a=[r for r in g if r['gross']/r['before']*100>=1 and abs(r['net'])/r['before']*100<1]
 assert len(a)==rec['alerts']
 weighted=math.fsum(r['gross'] for r in g)/math.fsum(r['before'] for r in g)*100
 assert math.isclose(weighted,rec['weighted_gross_percent'],rel_tol=1e-12)
 assert math.isclose(math.fsum(r['before'] for r in a)/math.fsum(r['before'] for r in g)*100,rec['previous_stock_in_alerts_percent'],rel_tol=1e-12);checks+=3
out=dict(experiment='E13',protocol_sha256=sha256(raw).hexdigest(),denominator_counts=counts,by_year=yearrows,by_stock_group=groups,municipality_years_with_alert={str(k):int(v) for k,v in persistent.items()},year_omissions=omissions,checks=dict(E12_counts_reproduced=True,independent_summary_checks=checks),limits=p['limits'])
(ROOT/'E13_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
for name,rows in [('E13_by_year.csv',yearrows),('E13_stock_groups.csv',groups),('E13_denominators.csv',counts),('E13_year_omissions.csv',omissions)]:pd.DataFrame(rows).to_csv(ROOT/name,index=False)
print(json.dumps({'years':yearrows,'persistence':out['municipality_years_with_alert'],'denominators':counts,'checks':out['checks']},indent=2))
