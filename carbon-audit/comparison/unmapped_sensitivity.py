from pathlib import Path
import json,hashlib,csv,math
from collections import defaultdict
import pandas as pd
r=Path(__file__).resolve().parent
p={'analysis':'E12 S1','purpose':'Check that code 0 does not account for the common level 1 alert counts. Defined after E12 results were known.','rule':'Retain the total stock denominator and total difference. Remove abs(delta for code 0) only from the gross class numerator. Keep records and report counts side by side. This is a labelled sensitivity check, not a revision of the primary E12 test.'};s=json.dumps(p,indent=2);(r/'E12_S1_protocol.json').write_text(s);(r/'E12_S1_protocol.sha256').write_text(hashlib.sha256(s.encode()).hexdigest())
root=r.parent/'replication/data/mapbiomas_brasil';files={'V1':'brasil_solo_B_col3_cob71.csv','V2':'brasil_solo_C_col3_cob10.csv'};unknown={}
for version,file in files.items():
 groups=defaultdict(list)
 with (root/file).open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   if int(row['classe'])!=0 or int(row['ano']) not in range(2017,2022):continue
   mean=float(row['media_t_C_ha'] or 'nan');area=float(row['area_ha'] or 'nan')
   if math.isfinite(mean) and area>0:groups[(row['id'],int(row['ano']))].append(mean*area)
 unknown[version]={k:math.fsum(v) for k,v in groups.items()}
d=pd.read_csv(r/'E12_municipality_year.csv',dtype={'id':str});d=d[d.scenario.eq('level1')].copy();d['unknown_delta']=[unknown['V2'].get((row.id,row.ano),0)-unknown['V1'].get((row.id,row.ano),0) for row in d.itertuples()];d['known_gross']=(d.gross-d.unknown_delta.abs()).clip(lower=0);d['known_gross_percent']=100*d.known_gross/d.before
rows=[]
for t in [0.1,1,5,10]:rows.append({'threshold_percent':t,'including_code0':int((d.gross_percent>=t).sum()),'excluding_code0_from_numerator':int((d.known_gross_percent>=t).sum()),'total_alerts':int((d.net_percent>=t).sum())})
byyear=[]
primary=json.loads((r/'E12_results.json').read_text());l1=next(s for s in primary['scenarios'] if s['name']=='level1')
for y,g in d.groupby('ano'):
 national=next(s for s in l1['by_year'] if s['year']==int(y));local=float(g.gross.sum()/1e6)
 byyear.append({'year':int(y),'sum_municipality_gross_TgC':local,'national_gross_TgC':national['national_gross_TgC'],'spatial_cancellation_fraction':1-national['national_gross_TgC']/local})
report={'analysis':'E12 S1','thresholds':rows,'by_year':byyear,'interpretation':'Excluding code 0 from the gross numerator is a sensitivity check. National aggregation can cancel differences between municipalities. Neither quantity establishes a source error or carbon transport.'};(r/'E12_S1_results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
