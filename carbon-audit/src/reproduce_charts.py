from pathlib import Path
import sys,json,hashlib,csv,io
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'replication/code'))
import p3_brasil as P
from e7_explain import CLASS
out={'schema_version':1,'cases':[],'sources':[]}
for tag,file in P.FILES.items():
 p=P.D/file
 out['sources'].append({'version':tag,'file':file,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
tables={v:P.table(v).assign(stock=lambda d:d.media_t_C_ha*d.area_ha) for v in P.FILES}
for case,a,b,dim,unit,title,default in [('soil','V0','V1','uf','%','Soil carbon stock change by state',2020),('cover','V1','V2','classe','Tg C','Stock change by land cover class',2021)]:
 c={'id':case,'title':title,'source':'MapBiomas CSV extracts in S1_artC.zip','versions':{'V0':'Soil beta 2.1 / land cover 7.1','V1':'Soil collection 3 / land cover 7.1','V2':'Soil collection 3 / land cover 10'},'before_version':a,'after_version':b,'unit':unit,'default_year':default,'years':P.YEARS,'data':{},'scope':'Stock is the sum of soil mean times valid mapped area. A change of mapped contexts is included. This is a version comparison, not a measured environmental trend.'}
 for year in P.YEARS:
  groups={v:tables[v][tables[v].ano.eq(year)].groupby(dim).stock.sum() for v in [a,b]}
  rows=[]
  for key in sorted(set(groups[a].index)|set(groups[b].index)):
   old=float(groups[a].get(key,0));new=float(groups[b].get(key,0))
   delta=(new/old-1)*100 if unit=='%' and old else (None if unit=='%' else (new-old)/1e6)
   rows.append({'key':str(key),'label':CLASS.get(int(key),str(key)) if dim=='classe' else str(key),'before':old/1e6,'after':new/1e6,'value':delta,'status':'available' if delta is not None else 'unresolved','unit':unit})
  c['data'][str(year)]=rows
 out['cases'].append(c)
plan=json.loads((ROOT/'external/plans/noaa_baseline_plan.json').read_text())
noaa={'id':'noaa','title':'Monthly atmospheric CO2 concentration','source':'NOAA Global Monitoring Laboratory','before_version':'downloaded-snapshot','after_version':'downloaded-snapshot','unit':'ppm','years':list(range(2015,2024)),'default_year':2020,'data':{},'scope':'Downloaded source records. The two series have different spatial supports. These lines do not represent publisher revision history.'}
for y in noaa['years']:
 rows=[]
 for source in plan['sources']:
  for row in csv.DictReader(io.StringIO(source['csv'])):
   parts=row['key'].split('|')
   if int(parts[1])==y:rows.append({'key':row['key'],'label':parts[2],'series':'Mauna Loa' if parts[0]=='mlo' else 'Global marine surface','value':float(row['value']),'status':'available','unit':'ppm'})
 noaa['data'][str(y)]=rows
out['cases'].append(noaa)
out['noaa_sources']={k:v for k,v in json.loads((ROOT/'external/source_manifest.json').read_text()).items() if k.startswith('noaa')}
(ROOT.parent/'carbon-provenance-lab/dist/chart-data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print('Chart data prepared:',[(c['id'],len(c['data'][str(c['default_year'])])) for c in out['cases']])
# Check national stock comparison against published E7 rounded results.
e=json.loads((ROOT/'replication/results/e7_explain.json').read_text())
for cid,ref in [('soil','X2_brazil_2020_soil_revision'),('cover','X4_brazil_2021_land_cover_revision')]:
 c=next(c for c in out['cases'] if c['id']==cid);rows=c['data'][str(c['default_year'])]
 delta=sum(r['after']-r['before'] for r in rows)
 assert abs(delta-e[ref]['change_TgC'])<.01,(cid,delta)
 print(cid,'national change checked',delta)
