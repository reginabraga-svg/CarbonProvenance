"""E15: effect of source version on reported class stocks and shares."""
from pathlib import Path
from hashlib import sha256
from collections import defaultdict
import csv,json,math
import pandas as pd
ROOT=Path(__file__).resolve().parent
raw=(ROOT/'E15_protocol.json').read_bytes();p=json.loads(raw)
assert sha256(raw).hexdigest()==(ROOT/'E15_protocol.sha256').read_text().strip()
mapping=json.loads((ROOT/'E12_protocol.json').read_text())['mappings']['level1']
D=ROOT.parent/'replication/data/mapbiomas_brasil';frames={};ind={};checks=0
for version,name in zip(['V1','V2'],p['sources']):
 assert sha256((D/name).read_bytes()).hexdigest()==p['sources'][name]
 d=pd.read_csv(D/name,dtype={'id':str});d=d[d.ano.isin(p['years'])&d.media_t_C_ha.notna()&(d.area_ha>0)].copy()
 d['stock']=d.media_t_C_ha*d.area_ha;d['group']=d.classe.astype(str).map(mapping);assert d.group.notna().all()
 frames[version]=d.groupby(['id','ano','group']).stock.sum()
 buckets=defaultdict(list)
 with (D/name).open(newline='',encoding='utf-8-sig') as f:
  for row in csv.DictReader(f):
   y=int(row['ano']);s=float(row['media_t_C_ha'] or 'nan');a=float(row['area_ha'] or 'nan')
   if y in p['years'] and math.isfinite(s) and a>0:buckets[(row['id'],y,mapping[row['classe']])].append(s*a)
 ind[version]={key:math.fsum(v) for key,v in buckets.items()}
 assert set(frames[version].index)==set(ind[version])
 for key,v in frames[version].items():assert math.isclose(v,ind[version][key],rel_tol=1e-9,abs_tol=1e-4);checks+=1
 print('Checked source',version,flush=True)
a=pd.concat([frames['V1'].rename('before'),frames['V2'].rename('after')],axis=1).fillna(0)
tot=a.groupby(['id','ano'])[['before','after']].sum();eligible=tot[(tot.before>0)&(tot.after>0)]
assert len(eligible)==27840
outrows=[];summary=[];e12=next(s for s in json.loads((ROOT/'E12_results.json').read_text())['scenarios'] if s['name']=='level1')
for group in p['groups']:
 sub=a.xs(group,level='group').reindex(eligible.index,fill_value=0).copy()
 sub['delta']=sub.after-sub.before;sub['share_before']=sub.before/eligible.before*100;sub['share_after']=sub.after/eligible.after*100;sub['share_delta_pp']=sub.share_after-sub.share_before
 sub['stock_relative_percent']=sub.delta/sub.before.where(sub.before>0)*100
 sub['group']=group;outrows.append(sub.reset_index())
 for y,g in sub.groupby(level='ano'):
  net=float(g.delta.sum()/1e6);ref=next(z for z in e12['by_year'] if z['year']==y)['groups'][group]
  assert math.isclose(net,ref,rel_tol=1e-9,abs_tol=1e-4)
  summary.append(dict(group=group,year=int(y),eligible=len(g),before_TgC=float(g.before.sum()/1e6),after_TgC=float(g.after.sum()/1e6),delta_TgC=net,absolute_municipality_delta_sum_TgC=float(g.delta.abs().sum()/1e6),share_change_ge_1pp=int((g.share_delta_pp.abs()>=1).sum()),share_change_ge_5pp=int((g.share_delta_pp.abs()>=5).sum()),median_abs_share_change_pp=float(g.share_delta_pp.abs().median()),positive_old_group=int((g.before>0).sum()),group_stock_change_ge_10percent=int((g.stock_relative_percent.abs()>=10).sum())))
# Check reported shares against independently summed source records.
indtotal={}
for version,records in ind.items():
 buckets=defaultdict(list)
 for (mid,y,group),v in records.items():buckets[(mid,y)].append(v)
 indtotal[version]={k:math.fsum(v) for k,v in buckets.items()}
rows=pd.concat(outrows,ignore_index=True)
for row in rows.itertuples():
 key=(row.id,row.ano);old=ind['V1'].get((*key,row.group),0);new=ind['V2'].get((*key,row.group),0)
 delta_pp=100*(new/indtotal['V2'][key]-old/indtotal['V1'][key])
 assert math.isclose(row.share_delta_pp,delta_pp,rel_tol=1e-9,abs_tol=1e-9);checks+=1
rows.to_csv(ROOT/'E15_reporting_outputs.csv',index=False)
pd.DataFrame(summary).to_csv(ROOT/'E15_by_group_year.csv',index=False)
out=dict(experiment='E15',protocol_sha256=sha256(raw).hexdigest(),summary=summary,checks=dict(source_group_and_share_checks=checks,E12_national_group_deltas_reproduced=True),limits=p['limits'])
(ROOT/'E15_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
