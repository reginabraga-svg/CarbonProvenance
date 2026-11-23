"""E12: sensitivity of stock revision comparisons to a declared shared legend."""
from pathlib import Path
from collections import defaultdict
import csv,json,hashlib,math,sys
import pandas as pd
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent/'replication/code'))
import p3_brasil as P
protocol=json.loads((ROOT/'E12_protocol.json').read_text(encoding='utf-8'));assert hashlib.sha256((ROOT/'E12_protocol.json').read_text(encoding='utf-8').encode()).hexdigest()==(ROOT/'E12_protocol.sha256').read_text().strip()
frames={v:P.table(v).assign(stock=lambda d:d.media_t_C_ha*d.area_ha) for v in ['V1','V2']}
observed=sorted(set().union(*(set(d.classe.astype(int)) for d in frames.values())))
for name,mapping in protocol['mappings'].items():
 if name!='original_codes':assert {str(c) for c in observed}<=mapping.keys(),(name,observed)
# Independent parser and summation. It does not call P.table or any ledger operation.
independent={}
for version,frame in frames.items():
 buckets={name:defaultdict(list) for name in protocol['mappings']}
 with (P.D/P.FILES[version]).open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   year=int(row['ano']);mean=float(row['media_t_C_ha'] or 'nan');area=float(row['area_ha'] or 'nan')
   if year not in protocol['years'] or not math.isfinite(mean) or not area>0:continue
   value=mean*area;code=int(row['classe']);mid=row['id']
   for name,mapping in protocol['mappings'].items():
    group=str(code) if name=='original_codes' else mapping[str(code)]
    buckets[name][(mid,year,group)].append(value)
 independent[version]={name:{k:math.fsum(v) for k,v in groups.items()} for name,groups in buckets.items()}
 print('Parsed',version,'independently',flush=True)
report={'experiment':'E12','protocol_hash':(ROOT/'E12_protocol.sha256').read_text().strip(),'observed_codes':observed,'source_hashes':{v:hashlib.sha256((P.D/P.FILES[v]).read_bytes()).hexdigest() for v in frames},'scenarios':[],'checks':{},'limits':protocol['mapping_interpretation']};allrows=[];original=None;orig_country=None;checks=0;maxerr=0
for name,mapping in protocol['mappings'].items():
 grouped={}
 for version,d in frames.items():
  work=d.assign(group=d.classe.astype(int).map(lambda c:str(c) if name=='original_codes' else mapping[str(c)]))
  series=work.groupby(['id','ano','group']).stock.sum();grouped[version]=series
  reference=independent[version][name];assert set(series.index)==set(reference)
  for key,value in series.items():
   error=abs(value-reference[key]);maxerr=max(maxerr,error);checks+=1
   assert math.isclose(value,reference[key],rel_tol=1e-9,abs_tol=1e-4),(name,version,key,value,reference[key])
 aligned=pd.concat([grouped['V1'].rename('before'),grouped['V2'].rename('after')],axis=1).fillna(0);aligned['delta']=aligned.after-aligned.before
 stats=aligned.groupby(['id','ano']).agg(before=('before','sum'),after=('after','sum'),net=('delta','sum'),gross=('delta',lambda x:x.abs().sum()))
 assert len(stats)==27845
 if original is None:original=stats.copy()
 else:
  for field in ['before','after','net']:
   assert all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-4) for a,b in zip(stats[field],original[field])),(name,field)
  assert (stats.gross<=original.gross+1e-4).all()
 eligible=stats.before>0;stats=stats[eligible].copy();assert len(stats)==27840
 stats['net_percent']=stats.net.abs()/stats.before*100;stats['gross_percent']=stats.gross/stats.before*100
 stats['scenario']=name;allrows.append(stats.reset_index())
 thresholds=[]
 for t in protocol['thresholds_percent']:
  alert=stats.gross_percent>=t;tot=stats.net_percent>=t
  thresholds.append({'threshold_percent':t,'total_alerts':int(tot.sum()),'class_alerts':int(alert.sum()),'class_without_total':int((alert&~tot).sum()),'eligible':len(stats)})
 country=aligned.groupby(['ano','group']).delta.sum();years=[]
 for y in protocol['years']:
  g=stats.xs(y,level='ano');countrygross=float(country.loc[y].abs().sum()/1e6);countrybefore=float(g.before.sum()/1e6)
  years.append({'year':y,'national_net_TgC':float(country.loc[y].sum()/1e6),'national_gross_TgC':countrygross,'national_gross_percent':countrygross/countrybefore*100,'median_municipality_gross_percent':float(g.gross_percent.median()),'groups':{str(k):float(v/1e6) for k,v in country.loc[y].items()}})
 if name=='original_codes':orig_country={r['year']:r['national_gross_TgC'] for r in years}
 for row in years:row['national_gross_retained_fraction']=row['national_gross_TgC']/orig_country[row['year']]
 scenario={'name':name,'eligible':len(stats),'zero_baseline_exclusions':5,'threshold_results':thresholds,'by_year':years,'municipality_gross_sum_TgC':float(stats.gross.sum()/1e6),'median_gross_percent':float(stats.gross_percent.median())}
 report['scenarios'].append(scenario);print(name,thresholds,flush=True)
# Reproduce the previous E11 threshold results under the original code partition.
e11=json.loads((ROOT/'E11_results.json').read_text())
for a,b in zip(report['scenarios'][0]['threshold_results'],e11['threshold_results']):assert a['class_alerts']==b['class_alerts'] and a['total_alerts']==b['total_alerts']
report['checks']={'independent_group_checks':checks,'max_absolute_group_difference_tC':maxerr,'mass_preserved':True,'net_difference_preserved':True,'gross_nonincreasing':True,'E11_alerts_reproduced':True}
pd.concat(allrows,ignore_index=True).to_csv(ROOT/'E12_municipality_year.csv',index=False)
(ROOT/'E12_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('E12 complete',report['checks'])
