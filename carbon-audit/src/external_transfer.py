"""Transfer tests with new source series and controlled changes to test copies."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from datetime import datetime,timezone
import csv,io,json,sys,hashlib,math,sqlite3
from audit import run_bundle,ROOT

EXT=ROOT/'external'
YEARS=list(range(2015,2024))
COUNTRIES=['BRA','USA','CHN','IND','DEU','ZAF','CAN','AUS','IDN','FRA','ARG','JPN']

def contract(kind,unit,period,support):
    return dict(qkind=kind,unit=unit,period=period,support=support)
def csv_text(rows):
    stream=io.StringIO();w=csv.writer(stream,lineterminator='\n')
    w.writerow(['key','value','qkind','unit','period','support'])
    for key,(value,meta) in sorted(rows.items()):w.writerow([key,str(value),*[meta[k] for k in ['qkind','unit','period','support']]])
    return stream.getvalue()
def node(key,op,inputs,meta,**params):
    return dict(key=key,op=op,inputs=inputs,contract=meta,params=params)
def expected(meta):return [meta[k] for k in ['qkind','unit','period','support']]
def source(name,rows):
    return dict(name=name,version='downloaded-snapshot',csv=csv_text(rows))
def write_json(name,data):
    p=EXT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def noaa_series(filename,prefix,support):
    raw=(EXT/'raw'/filename).read_text(encoding='utf-8-sig')
    lines=[s for s in raw.splitlines() if s and not s.startswith('#')]
    rows={};excluded=[]
    for r in csv.DictReader(lines):
        year,month=int(r['year']),int(r['month'])
        if year not in YEARS+[2024]:continue
        value=Decimal(r['average'])
        if value<0:excluded.append((year,month));continue
        key=f'{prefix}|{year}|{month:02}'
        rows[key]=(value,contract('concentration','ppm',f'monthly:{year}-{month:02}',support))
    return rows,excluded

def noaa_nodes(years,series):
    out=[]
    for year in years:
        for month in range(1,13):
            a,b=f'mlo|{year}|{month:02}',f'global|{year}|{month:02}'
            # Explicit expectations use declared semantics, including different spatial supports.
            ma=contract('concentration','ppm',f'monthly:{year}-{month:02}','station_series')
            mb=contract('concentration','ppm',f'monthly:{year}-{month:02}','global_marine_surface')
            out.append(node(f'concentration_difference|{year}|{month:02}','diff',[a,b],
                            contract('concentration','ppm',f'monthly:{year}-{month:02}','station_vs_global'),expect=[expected(ma),expected(mb)]))
        for prefix,support in [('mlo','station_series'),('global','global_marine_surface')]:
            keys=[f'{prefix}|{year}|{month:02}' for month in range(1,13)]
            out.append(node(f'monthly_record_mean|{prefix}|{year}','lin',keys,
                            contract('concentration','ppm',f'annual:{year}',support),w=[1/12]*12,
                            expect=[expected(contract('concentration','ppm',f'monthly:{year}-{m:02}',support)) for m in range(1,13)]))
        out.append(node(f'annual_mean_difference|{year}','diff',
                        [f'monthly_record_mean|mlo|{year}',f'monthly_record_mean|global|{year}'],
                        contract('concentration','ppm',f'annual:{year}','station_vs_global')))
    return out

def noaa_reference(series,years):
    out={}
    for year in years:
        for month in range(1,13):
            out[f'concentration_difference|{year}|{month:02}']=series['mlo'][f'mlo|{year}|{month:02}'][0]-series['global'][f'global|{year}|{month:02}'][0]
        for prefix in ['mlo','global']:
            out[f'monthly_record_mean|{prefix}|{year}']=sum(series[prefix][f'{prefix}|{year}|{m:02}'][0] for m in range(1,13))/Decimal(12)
        out[f'annual_mean_difference|{year}']=out[f'monthly_record_mean|mlo|{year}']-out[f'monthly_record_mean|global|{year}']
    return out

def wdi_series(filename,prefix):
    payload=json.loads((EXT/'raw'/filename).read_text(encoding='utf-8'),parse_float=Decimal)
    if not isinstance(payload,list) or len(payload)!=2:raise ValueError('World Bank response is not a data page')
    if int(payload[0]['pages'])!=1:raise ValueError('World Bank response requires pagination')
    rows={};missing=[]
    for r in payload[1]:
        country=r['countryiso3code'];year=int(r['date'])
        if country not in COUNTRIES+['NZL'] or year not in YEARS:continue
        if r['value'] is None:missing.append([country,year]);continue
        rows[f'{prefix}|{country}|{year}']=(Decimal(str(r['value'])),contract('area','km2',f'instant:{year}','country'))
    return rows,missing,payload[0]

def wdi_nodes(countries,years):
    out=[]
    for year in years:
        for country in countries:
            meta=contract('area','km2',f'instant:{year}','country')
            out.append(node(f'forest_share|{country}|{year}','ratio',[f'forest|{country}|{year}',f'land|{country}|{year}'],
                            contract('share','percent',f'instant:{year}','country'),k=100,expect=[expected(meta),expected(meta)]))
        for prefix in ['forest','land']:
            out.append(node(f'selected_country_total|{prefix}|{year}','sum',[f'{prefix}|{c}|{year}' for c in countries],
                            contract('area','km2',f'instant:{year}','selected_countries')))
        out.append(node(f'selected_country_forest_share|{year}','ratio',
                        [f'selected_country_total|forest|{year}',f'selected_country_total|land|{year}'],
                        contract('share','percent',f'instant:{year}','selected_countries'),k=100))
    return out

def wdi_reference(series,countries,years):
    # SQL is independent of the ledger operations and declaration graph.
    con=sqlite3.connect(':memory:')
    con.execute('create table areas(kind text,country text,year integer,value real)')
    for kind,rows in series.items():
        con.executemany('insert into areas values(?,?,?,?)',[(kind,key.split('|')[1],int(key.split('|')[2]),float(value)) for key,(value,meta) in rows.items() if key.split('|')[1] in countries and int(key.split('|')[2]) in years])
    out={}
    for country,year,share in con.execute("select f.country,f.year,100.0*f.value/l.value from areas f join areas l on f.country=l.country and f.year=l.year where f.kind='forest' and l.kind='land'"):
        out[f'forest_share|{country}|{year}']=share
    for kind,year,total in con.execute('select kind,year,sum(value) from areas group by kind,year'):
        out[f'selected_country_total|{kind}|{year}']=total
    for year in years:out[f'selected_country_forest_share|{year}']=100*out[f'selected_country_total|forest|{year}']/out[f'selected_country_total|land|{year}']
    con.close()
    return out

def check_reference(result,reference):
    values={v['key']:v for v in result['values'] if v['kind']=='derived'}
    failures=[];error=0
    for key,value in reference.items():
        actual=values.get(key)
        if actual is None or actual['value'] is None or actual['status']!='ok':failures.append(dict(key=key,reason='missing or non-ok output'));continue
        error=max(error,abs(actual['value']-float(value)))
        if not math.isclose(actual['value'],float(value),rel_tol=1e-10,abs_tol=1e-9):failures.append(dict(key=key,actual=actual['value'],expected=float(value)))
    if values.keys()!=reference.keys():failures.append(dict(reason='derived key sets differ'))
    return dict(comparisons=len(reference),max_absolute_error=error,failures=failures)

def controlled_case(base,label,updates=None,add_nodes=None,rewire=None):
    plan=deepcopy(base)
    plan['title']=base['title']+' / controlled test: '+label
    revision=dict(name='Controlled test: '+label,updates=updates or [])
    if add_nodes:revision['add_nodes']=add_nodes
    if rewire:revision['rewire']=rewire
    plan['revisions']=[revision]
    result=run_bundle(plan)
    return plan,result

def tests_for_dataset(name,base,series,reference,changed_source,key,expected_dependents):
    report=dict(dataset=name,baseline_source_values=sum(len(s) for s in series.values()),baseline_outputs=len(reference),
                baseline=check_reference(run_bundle(base),reference),cases=[])
    def record(label,result,expected_status=None,expected_keys=None):
        revision=result['revisions'][0]
        changed={k for k in revision['after'] if k in revision['before'] and (revision['before'][k]['value']!=revision['after'][k]['value'] or revision['before'][k]['status']!=revision['after'][k]['status']) and revision['after'][k]['kind']=='derived'}
        keys=expected_keys or expected_dependents
        failures=[]
        if changed!=set(keys):failures.append(dict(reason='changed output set differs',expected=sorted(keys),actual=sorted(changed)))
        if expected_status:
            for k in keys:
                d=revision['after'][k]
                if d['status']!=expected_status or (expected_status in ['orphan','blocked','unresolved'] and d['value'] is not None):failures.append(dict(key=k,reason='unexpected status or numeric value'))
        flagged=set(revision['flagged'])
        if not set(keys)<=flagged:failures.append(dict(reason='expected affected output not flagged'))
        report['cases'].append(dict(name=label,expected_affected=len(keys),metrics=revision['metrics'],failures=failures))
        write_json(f'results/{name}_{label}.json',result)
        return failures
    rows=deepcopy(series[changed_source]);v,m=rows[key];rows[key]=(v*Decimal('1.05'),m)
    plan,r=controlled_case(base,'numeric_change',[dict(source=changed_source,version='controlled-change',csv=csv_text(rows))])
    record('numeric_change',r,'ok')
    ref_series=deepcopy(series);ref_series[changed_source]=rows
    revised_ref=noaa_reference(ref_series,YEARS) if name=='noaa' else wdi_reference(ref_series,COUNTRIES,YEARS)
    report['numeric_reference']=check_reference(r,revised_ref)
    rows=deepcopy(series[changed_source]);del rows[key]
    plan,r=controlled_case(base,'key_withdrawal',[dict(source=changed_source,version='controlled-withdrawal',csv=csv_text(rows))])
    record('key_withdrawal',r,'orphan')
    write_json(f'plans/{name}_withdrawal_plan.json',plan)
    rows=deepcopy(series[changed_source]);v,m=rows[key];m=dict(m,unit='ppb' if name=='noaa' else 'ha');rows[key]=(v*Decimal(1000 if name=='noaa' else 100),m)
    plan,r=controlled_case(base,'unit_mismatch',[dict(source=changed_source,version='controlled-unit',csv=csv_text(rows))])
    record('unit_mismatch',r,'blocked')
    duplicate=deepcopy(base);first=duplicate['sources'][0];first['csv']+=first['csv'].splitlines()[1]+'\n'
    try:run_bundle(duplicate);duplicate_pass=False
    except ValueError as exc:duplicate_pass='duplicate' in str(exc).lower()
    report['cases'].append(dict(name='duplicate_key_rejection',failures=[] if duplicate_pass else ['duplicate key accepted']))
    unsupported=deepcopy(base);unsupported['nodes'][0]['op']='median'
    try:run_bundle(unsupported);unsupported_pass=False
    except ValueError as exc:unsupported_pass='unsupported operation' in str(exc)
    report['cases'].append(dict(name='unsupported_operation_rejection',failures=[] if unsupported_pass else ['unsupported operation accepted']))
    return report

def run_all():
    manifest=json.loads((EXT/'source_manifest.json').read_text(encoding='utf-8'))
    report=dict(executed_at=datetime.now(timezone.utc).isoformat(),source_manifest=manifest,
                controlled_changes_are_publisher_revisions=False,datasets=[],limitations=[])
    mlo,excluded_mlo=noaa_series('noaa_mlo.csv','mlo','station_series')
    global_series,excluded_global=noaa_series('noaa_global.csv','global','global_marine_surface')
    full={'mlo':mlo,'global':global_series}
    series={name:{k:v for k,v in rows.items() if int(k.split('|')[1]) in YEARS} for name,rows in full.items()}
    base=dict(schema_version=1,title='NOAA monthly CO2 comparison',sources=[source(n,r) for n,r in series.items()],nodes=noaa_nodes(YEARS,series))
    ref=noaa_reference(series,YEARS)
    dependents={'concentration_difference|2020|01','monthly_record_mean|mlo|2020','annual_mean_difference|2020'}
    noaa=tests_for_dataset('noaa',base,series,ref,'mlo','mlo|2020|01',dependents)
    additions=noaa_nodes([2024],full)
    extended={name:{k:v for k,v in rows.items() if int(k.split('|')[1]) in YEARS+[2024]} for name,rows in full.items()}
    plan,result=controlled_case(base,'year_extension',[dict(source=n,version='controlled-context-extension',csv=csv_text(r)) for n,r in extended.items()],add_nodes=additions)
    noaa['context_addition']=check_reference(result,noaa_reference(extended,YEARS+[2024]))
    noaa['context_addition']['new_outputs']=result['revisions'][0]['metrics']['new_outputs']
    noaa['excluded_average_values']=excluded_mlo+excluded_global
    write_json('plans/noaa_baseline_plan.json',base);write_json('plans/noaa_year_extension_plan.json',plan);write_json('results/noaa_year_extension.json',result)
    report['datasets'].append(noaa)
    if (EXT/'raw/wdi_forest.json').exists() and (EXT/'raw/wdi_land.json').exists():
        forest,missing_forest,meta_forest=wdi_series('wdi_forest.json','forest')
        land,missing_land,meta_land=wdi_series('wdi_land.json','land')
        full={'forest':forest,'land':land}
        series={n:{k:v for k,v in rows.items() if k.split('|')[1] in COUNTRIES} for n,rows in full.items()}
        base=dict(schema_version=1,title='World Bank forest area assessment',sources=[source(n,r) for n,r in series.items()],nodes=wdi_nodes(COUNTRIES,YEARS))
        reference=wdi_reference(series,COUNTRIES,YEARS)
        dependents={'forest_share|BRA|2020','selected_country_total|forest|2020','selected_country_forest_share|2020'}
        wdi=tests_for_dataset('wdi',base,series,reference,'forest','forest|BRA|2020',dependents)
        extended={n:dict(rows,**{k:v for k,v in full[n].items() if k=='%s|NZL|2020'%n}) for n,rows in series.items()}
        new=wdi_nodes(['NZL'],[2020])[0]
        rewire={f'selected_country_total|{n}|2020':[f'{n}|{c}|2020' for c in COUNTRIES+['NZL']] for n in series}
        plan,result=controlled_case(base,'country_extension',[dict(source=n,version='controlled-context-extension',csv=csv_text(rows)) for n,rows in extended.items()],add_nodes=[new],rewire=rewire)
        # SQL references for original years and the extended country set only in 2020.
        extended_ref=wdi_reference(series,COUNTRIES,YEARS)
        extended_ref.update(wdi_reference(extended,COUNTRIES+['NZL'],[2020]))
        wdi['context_addition']=check_reference(result,extended_ref)
        wdi['context_addition']['new_outputs']=result['revisions'][0]['metrics']['new_outputs']
        zero=deepcopy(series['land']);v,m=zero['land|BRA|2020'];zero['land|BRA|2020']=(Decimal(0),m)
        plan_zero,zero_result=controlled_case(base,'zero_denominator',[dict(source='land',version='controlled-zero',csv=csv_text(zero))])
        d=next(v for v in zero_result['values'] if v['key']=='forest_share|BRA|2020')
        wdi['zero_denominator']=dict(status=d['status'],value=d['value'],failures=[] if d['status']=='unresolved' and d['value'] is None else ['zero denominator not handled'])
        wdi['missing_source_values']=missing_forest+missing_land
        wdi['publisher_metadata']={'forest':meta_forest,'land':meta_land}
        write_json('plans/wdi_baseline_plan.json',base);write_json('plans/wdi_country_extension_plan.json',plan);write_json('results/wdi_country_extension.json',result);write_json('results/wdi_zero_denominator.json',zero_result)
        report['datasets'].append(wdi)
    else:report['limitations'].append('World Bank acquisition did not complete. No World Bank transfer result is claimed.')
    frozen=json.loads((EXT/'frozen_before_test.json').read_text(encoding='utf-8'))
    # Frozen records retain their original labels. Resolve sibling projects
    # relative to this extracted package rather than the author's workspace.
    workspace=ROOT.parent
    def frozen_file(name):
        parts=name.replace('\\','/').split('/')
        if parts[0]=='outputs':parts=parts[1:]
        path=workspace.joinpath(*parts).resolve()
        if not path.is_relative_to(workspace.resolve()):
            raise ValueError('Frozen file is outside the replication package')
        return path
    report['frozen_hash_check']={name:hashlib.sha256(frozen_file(name).read_bytes()).hexdigest()==digest for name,digest in frozen.items()}
    report['engine_changes_required']=not all(v for k,v in report['frozen_hash_check'].items() if k.endswith('audit.py') or k.endswith('engine.py'))
    report['limitations']+=['Test-copy changes are controlled perturbations, not historical publisher revisions.',
                           'Source adapters and semantic declarations were written for these cases.',
                           'NOAA concentrations are not emissions inventories. Means use the twelve reported monthly values.',
                           'No participant study or proof of generality for arbitrary datasets follows from these tests.']
    failures=[]
    for d in report['datasets']:
        for group in ['baseline','numeric_reference','context_addition','zero_denominator']:
            failures.extend(d.get(group,{}).get('failures',[]))
        for c in d['cases']:failures.extend(c['failures'])
    report['all_assertions_passed']=not failures
    report['failures']=failures
    write_json('transfer_test_report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=='__main__':
    result=run_all()
    if not result['all_assertions_passed']:sys.exit(1)
