"""E14 public map diagnostics. Requires Earth Engine authentication and a project.

Usage: python comparison/pixel_comparison.py --project PROJECT --prepare-only
Then: python comparison/pixel_comparison.py --project PROJECT
No credentials are copied into this directory. No batch exports are submitted.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import argparse,json,sys,time
ap=argparse.ArgumentParser();ap.add_argument('--project',required=True);ap.add_argument('--deps');ap.add_argument('--credential-file');ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
if args.deps:sys.path.insert(0,str(Path(args.deps).resolve()))
import ee
if args.credential_file:ee.oauth.get_credentials_path=lambda:str(Path(args.credential_file).resolve())
ROOT=Path(__file__).resolve().parent;P=json.loads((ROOT/'E14_protocol.json').read_bytes())
assert sha256((ROOT/'E14_protocol.json').read_bytes()).hexdigest()==(ROOT/'E14_protocol.sha256').read_text().strip()
ee.Initialize(project=args.project);ee.data.setDeadline(240000)
cache=ROOT/'E14_map_summaries';cache.mkdir(exist_ok=True)
def resolve(folder,word):
 assets=ee.data.listAssets({'parent':folder}).get('assets',[])
 candidates=[a['name'] if 'name' in a else a['id'] for a in assets if a['type']=='IMAGE' and word in a.get('id',a.get('name','')).lower()]
 good=[]
 for asset in candidates:
  bands=ee.Image(asset).bandNames().getInfo()
  if all('classification_'+str(y) in bands for y in P['years']):good.append(asset)
 assert len(good)==1,{'folder':folder,'matching_candidates':good,'all_candidates':candidates}
 return good[0]
manifest_path=ROOT/'E14_assets.json'
if manifest_path.exists():
 M=json.loads(manifest_path.read_text());assert M['protocol_sha256']==sha256((ROOT/'E14_protocol.json').read_bytes()).hexdigest()
else:
 ids={'cover71':resolve(P['assets']['cover71_folder'],'integration'),'cover10':resolve(P['assets']['cover10_folder'],'coverage'),'soil':P['assets']['soil'],'municipalities':P['assets']['municipalities']}
 M={'protocol_sha256':sha256((ROOT/'E14_protocol.json').read_bytes()).hexdigest(),'retrieved_utc':datetime.now(timezone.utc).isoformat(),'assets':ids,'metadata':{k:ee.data.getAsset(v) for k,v in ids.items()},'grids':{}}
 for name in ['cover71','cover10']:
  M['grids'][name]={str(y):ee.Image(ids[name]).select('classification_'+str(y)).projection().getInfo() for y in P['years']}
 manifest_path.write_text(json.dumps(M,ensure_ascii=False,indent=2),encoding='utf-8')
print('Resolved assets and grids',json.dumps({'assets':M['assets'],'grids':M['grids']}),flush=True)
if args.prepare_only:sys.exit(0)
cover71=ee.Image(M['assets']['cover71']);cover10=ee.Image(M['assets']['cover10']);soil=ee.Image(M['assets']['soil'])
mun=ee.FeatureCollection(M['assets']['municipalities']).filter(ee.Filter.eq('shapeGroup','BRA'))
sum2=ee.Reducer.sum().setOutputs(['stock_tC']).combine(ee.Reducer.sum().setOutputs(['area_ha']),sharedInputs=False)
for case in P['sample']:
 feature=mun.filter(ee.Filter.eq('shapeID',case['id']));assert feature.size().getInfo()==1,case['id']
 geometry=feature.geometry()
 for year in P['years']:
  s=soil.select('carbon_'+str(year));c1=cover71.select('classification_'+str(year));c2=cover10.select('classification_'+str(year))
  validsoil=s.mask().reduce(ee.Reducer.min()).gt(0).And(s.gte(0))
  v1=c1.mask().reduce(ee.Reducer.min()).unmask(0).gt(0);v2=c2.mask().reduce(ee.Reducer.min()).unmask(0).gt(0)
  area=ee.Image.pixelArea().divide(10000);stock=s.multiply(area)
  common=validsoil.And(v1).And(v2)
  pair=c1.multiply(1000).add(c2).toInt().rename('pair')
  transition=stock.rename('stock_tC').addBands(area.rename('area_ha')).addBands(pair).updateMask(common)
  membership=v1.toInt().add(v2.toInt().multiply(2)).rename('mask_membership')
  masks=stock.rename('stock_tC').addBands(area.rename('area_ha')).addBands(membership).updateMask(validsoil)
  grids=['cover71']
  if M['grids']['cover71'][str(year)]!=M['grids']['cover10'][str(year)]:grids.append('cover10')
  for grid in grids:
   target=cache/f"{case['id']}_{year}_{grid}.json"
   if target.exists():print('Cached',target.name,flush=True);continue
   projection=M['grids'][grid][str(year)];start=time.monotonic()
   kwargs=dict(geometry=geometry,crs=projection['crs'],crsTransform=projection['transform'],bestEffort=False,maxPixels=100000000,tileScale=4)
   query=ee.Dictionary({'pairs':transition.reduceRegion(sum2.group(groupField=2,groupName='pair'),**kwargs),'masks':masks.reduceRegion(sum2.group(groupField=2,groupName='mask_membership'),**kwargs)})
   print('Computing',case['municipio'],year,grid,flush=True)
   try:
    result=query.getInfo()
   except Exception as error:
    attempt={'municipality_id':case['id'],'year':year,'grid':grid,'error':str(error),'utc':datetime.now(timezone.utc).isoformat()}
    (cache/f"{case['id']}_{year}_{grid}_attempt.json").write_text(json.dumps(attempt,indent=2),encoding='utf-8')
    raise
   record={'municipality_id':case['id'],'municipality':case['municipio'],'year':year,'grid':grid,'projection':projection,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-start,'result':result}
   target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
   print('Saved',target.name,'seconds',round(record['elapsed_seconds'],1),flush=True)
print('E14 extraction complete. Summaries require reconciliation before manuscript use.',flush=True)
