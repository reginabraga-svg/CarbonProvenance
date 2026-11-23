"""Reconcile E14 cached pair sums. No Google credentials are required."""
from pathlib import Path
from collections import defaultdict
import csv,json,math,hashlib,statistics
R=Path(__file__).resolve().parent
p=json.loads((R/'E14_protocol.json').read_text())
m=json.loads((R/'E12_protocol.json').read_text())['mappings']['level1']
def dumpcsv(name,rows):
 with (R/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
original={}
with (R/'E12_municipality_year.csv').open(newline='',encoding='utf-8') as f:
 for r in csv.DictReader(f):
  if r['scenario']=='level1':original[(r['id'],int(r['ano']))]=r
rows=[];transitions=[];hashes={};checks=0
for case in p['sample']:
 for year in p['years']:
  for grid in ['cover71','cover10']:
   file=R/'E14_map_summaries'/f"{case['id']}_{year}_{grid}.json"
   a=json.loads(file.read_text());hashes[file.name]=hashlib.sha256(file.read_bytes()).hexdigest()
   pairs=a['result']['pairs']['groups'];masks=a['result']['masks']['groups']
   stock=math.fsum(z['stock_tC'] for z in pairs);area=math.fsum(z['area_ha'] for z in pairs)
   common=next(z for z in masks if z['mask_membership']==3)
   assert math.isclose(stock,common['stock_tC'],rel_tol=1e-8,abs_tol=1e-3)
   assert math.isclose(area,common['area_ha'],rel_tol=1e-8,abs_tol=1e-3)
   old=defaultdict(list);new=defaultdict(list);cross=[];changed=[];matrix=defaultdict(list)
   for z in pairs:
    c1,c2=divmod(z['pair'],1000)
    assert str(c1) in m and str(c2) in m,(c1,c2)
    g1,g2=m[str(c1)],m[str(c2)];v=z['stock_tC'];old[g1].append(v);new[g2].append(v)
    matrix[(g1,g2)].append(v)
    if c1!=c2:changed.append(v)
    if g1!=g2:cross.append(v)
   gross=math.fsum(abs(math.fsum(new[g])-math.fsum(old[g])) for g in set(old)|set(new))
   net=math.fsum(math.fsum(new[g])-math.fsum(old[g]) for g in set(old)|set(new))
   between=math.fsum(cross);assert gross<=2*between+1e-4
   assert abs(net)<1e-4
   ref=original[(case['id'],year)]
   rows.append(dict(municipality_id=case['id'],municipality=case['municipio'],year=year,grid=grid,common_stock_tC=stock,common_area_ha=area,code_disagreement_stock_percent=100*math.fsum(changed)/stock,between_group_stock_percent=100*between/stock,level1_gross_percent=100*gross/stock,level1_gross_tC=gross,level1_net_tC=net,exclusive_mask_area_ha=math.fsum(z['area_ha'] for z in masks if z['mask_membership'] in [1,2]),neither_mask_area_ha=math.fsum(z['area_ha'] for z in masks if z['mask_membership']==0),E12_level1_gross_percent=float(ref['gross_percent']),stock_pair_mask_difference_tC=stock-common['stock_tC'],area_pair_mask_difference_ha=area-common['area_ha']))
   for (g1,g2),values in sorted(matrix.items()):transitions.append(dict(municipality_id=case['id'],year=year,grid=grid,from_group=g1,to_group=g2,stock_tC=math.fsum(values)))
   checks+=4
primary=[r for r in rows if r['grid']=='cover71'];other={(r['municipality_id'],r['year']):r for r in rows if r['grid']=='cover10'}
changes=[abs(r['level1_gross_percent']-other[r['municipality_id'],r['year']]['level1_gross_percent']) for r in primary]
summary={}
for year in p['years']:
 s=[r for r in primary if r['year']==year]
 summary[str(year)]={field:{'min':min(r[field] for r in s),'median':statistics.median(r[field] for r in s),'max':max(r[field] for r in s)} for field in ['between_group_stock_percent','level1_gross_percent','E12_level1_gross_percent']}
 summary[str(year)]['class_alerts_at_1_percent']=sum(r['level1_gross_percent']>=1 for r in s)
report=dict(experiment='E14',status='complete',municipalities=12,years=p['years'],grid_cases=len(rows),reconciliation_checks=checks,source_hashes=hashes,summary_by_year=summary,max_grid_gross_difference_percentage_points=max(changes),max_pair_mask_stock_difference_tC=max(abs(r['stock_pair_mask_difference_tC']) for r in rows),max_exclusive_mask_area_ha=max(r['exclusive_mask_area_ha'] for r in rows),limits=['Purposive cases selected after E13, not a probability sample.','Map disagreement between versions at the same year is not observed environmental change or map accuracy.','Common support and one soil field force equal totals by construction.','E12 uses archived class mean times area, while E14 sums pixel stock on common support. Differences are not exact replications.','Gross class differences count both allocation margins. Between-group stock counts each disagreeing pixel once.'])
dumpcsv('E14_pixel_diagnostics.csv',rows);dumpcsv('E14_group_transitions.csv',transitions)
(R/'E14_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'E14_execution_status.json').write_text(json.dumps({'experiment':'E14','status':'complete','results':'E14_results.json','queries':len(rows)},indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))
