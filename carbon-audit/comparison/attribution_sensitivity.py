"""E16 source-factor allocation sensitivity, independent of the ledger and UI."""
from pathlib import Path
from hashlib import sha256
from collections import defaultdict
import json,csv,math
import pandas as pd
ROOT=Path(__file__).resolve().parent;raw=(ROOT/'E16_protocol.json').read_bytes();p=json.loads(raw)
assert sha256(raw).hexdigest()==(ROOT/'E16_protocol.sha256').read_text().strip()
D=ROOT.parent/'replication/data/mapbiomas_brasil';frames=[];source=[]
for n in p['sources']:
 assert sha256((D/n).read_bytes()).hexdigest()==p['sources'][n]
 d=pd.read_csv(D/n,dtype={'id':str});d=d[d.ano.isin(p['years'])&d.media_t_C_ha.notna()&(d.area_ha>0)]
 assert not d.duplicated(['id','ano','classe']).any()
 frames.append(d.set_index(['id','ano','classe'])[['media_t_C_ha','area_ha']])
 records={}
 with (D/n).open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f):
   year=int(r['ano']);s=float(r['media_t_C_ha'] or 'nan');a=float(r['area_ha'] or 'nan')
   if year in p['years'] and math.isfinite(s) and a>0:records[(r['id'],year,int(r['classe']))]=(s,a)
 source.append(records)
x=frames[0].rename(columns={'media_t_C_ha':'s0','area_ha':'a0'}).join(frames[1].rename(columns={'media_t_C_ha':'s1','area_ha':'a1'}),how='outer')
both=x.s0.notna()&x.s1.notna();added=x.s0.isna();withdrawn=x.s1.isna()
x=x.fillna(0);x['before']=x.s0*x.a0;x['after']=x.s1*x.a1
tot=x.groupby(['id','ano'])[['before','after']].sum().unstack('ano');old=tot['before'][2021]-tot['before'][2020];new=tot['after'][2021]-tot['after'][2020]
flips=(old!=0)&(new!=0)&((old>0)!=(new>0));assert int(flips.sum())==1669
allrows=[];summary=[];dominance=[];maxerr=0;checks=0
for mode in p['allocations']:
 y=x[['before','after']].copy()
 if mode=='midpoint':soil=(x.s1-x.s0)*(x.a0+x.a1)/2;area=(x.a1-x.a0)*(x.s0+x.s1)/2
 elif mode=='soil_first':soil=(x.s1-x.s0)*x.a0;area=(x.a1-x.a0)*x.s1
 else:soil=(x.s1-x.s0)*x.a1;area=(x.a1-x.a0)*x.s0
 y['soil']=soil.where(both,0);y['area']=area.where(both,0);y['added']=(x.s1*x.a1).where(added,0);y['withdrawn']=(-x.s0*x.a0).where(withdrawn,0)
 g=y.groupby(['id','ano']).sum();g['closure']=g[['soil','area','added','withdrawn']].sum(axis=1)-(g.after-g.before)
 assert g.closure.abs().max()<1e-4;maxerr=max(maxerr,float(g.closure.abs().max()))
 annual=g.unstack('ano');out=pd.DataFrame({c:annual[c][2021]-annual[c][2020] for c in ['soil','area','added','withdrawn']})
 out['revision_effect']=new-old;out['old_annual_difference']=old;out['new_annual_difference']=new;out['sign_reversal']=flips
 out['soil_dominates']=out.soil.abs()>out[['area','added','withdrawn']].abs().sum(axis=1)
 assert (out[['soil','area','added','withdrawn']].sum(axis=1)-out.revision_effect).abs().max()<1e-4
 # Separate source parser and math.fsum implementation.
 buckets=defaultdict(lambda:defaultdict(list))
 for key in set(source[0])|set(source[1]):
  mid,year,cl=key;s0,a0=source[0].get(key,(0.,0.));s1,a1=source[1].get(key,(0.,0.));sign=1 if year==2021 else -1
  if key not in source[0]:terms={'added':s1*a1}
  elif key not in source[1]:terms={'withdrawn':-s0*a0}
  elif mode=='midpoint':terms={'soil':(s1-s0)*(a0+a1)/2,'area':(a1-a0)*(s0+s1)/2}
  elif mode=='soil_first':terms={'soil':(s1-s0)*a0,'area':(a1-a0)*s1}
  else:terms={'soil':(s1-s0)*a1,'area':(a1-a0)*s0}
  for c,v in terms.items():buckets[mid][c].append(sign*v)
 for mid,row in out.iterrows():
  for c in ['soil','area','added','withdrawn']:
   assert math.isclose(row[c],math.fsum(buckets[mid][c]),rel_tol=1e-9,abs_tol=1e-4);checks+=1
 subset=out[flips];dominance.append(subset.soil_dominates.rename(mode));out['allocation']=mode;allrows.append(out.reset_index())
 summary.append(dict(allocation=mode,sign_reversals=len(subset),positive_to_negative=int((subset.old_annual_difference>0).sum()),soil_dominates=int(subset.soil_dominates.sum()),absolute_soil_TgC=float(subset.soil.abs().sum()/1e6),absolute_area_TgC=float(subset.area.abs().sum()/1e6),absolute_added_TgC=float(subset.added.abs().sum()/1e6),absolute_withdrawn_TgC=float(subset.withdrawn.abs().sum()/1e6)))
dom=pd.concat(dominance,axis=1);robust=int(dom.all(axis=1).sum())
arch=json.loads((ROOT.parent/'replication/results/e7_explain.json').read_text())['X3_sign_flips_2020_2021']
assert summary[0]['soil_dominates']==arch['soil_dominates']
report=dict(experiment='E16',protocol_sha256=sha256(raw).hexdigest(),summary=summary,soil_dominates_under_all_conventions=robust,dominance_changes_between_conventions=int((dom.nunique(axis=1)>1).sum()),checks=dict(independent_contribution_checks=checks,max_municipality_year_closure_error_tC=maxerr,E7_midpoint_count_reproduced=True),limits=p['limits'])
pd.concat(allrows,ignore_index=True).to_csv(ROOT/'E16_municipality_attribution.csv',index=False)
(ROOT/'E16_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
