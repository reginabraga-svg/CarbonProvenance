"""E11 descriptive comparison of total and class differences across source versions."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root.parent/'replication/code'))
import p3_brasil as P
protocol=json.loads((root/'E11_protocol.json').read_text());assert hashlib.sha256((root/'E11_protocol.json').read_text().encode()).hexdigest()==(root/'E11_protocol.sha256').read_text().strip()
data={v:P.table(v).assign(stock=lambda d:d.media_t_C_ha*d.area_ha) for v in ['V1','V2']}
a=data['V1'].groupby(['id','ano','classe']).stock.sum();b=data['V2'].groupby(['id','ano','classe']).stock.sum();aligned=pd.concat([a.rename('before'),b.rename('after')],axis=1).fillna(0);aligned['delta']=aligned.after-aligned.before
summary=aligned.groupby(['id','ano']).agg(before=('before','sum'),after=('after','sum'),net=('delta','sum'),gross=('delta',lambda x:x.abs().sum()))
assert len(summary)==27845
excluded=summary[summary.before<=0].copy();summary=summary[summary.before>0].copy()
summary['net_percent']=summary.net.abs()/summary.before*100;summary['gross_class_percent']=summary.gross/summary.before*100;summary['offsetting_percent']=(summary.gross-summary.net.abs()).clip(lower=0)/(2*summary.before)*100
rows=[]
for threshold in protocol['thresholds_percent']:
 total=summary.net_percent>=threshold;classes=summary.gross_class_percent>=threshold
 rows.append(dict(threshold_percent=threshold,total_alerts=int(total.sum()),class_alerts=int(classes.sum()),class_alerts_without_total_alert=int((classes&~total).sum()),comparisons=len(summary)))
# Check against the archived E7 result before interpreting the new counts.
e7=json.loads((root.parent/'replication/results/e7_explain.json').read_text())['X4_brazil_2021_land_cover_revision'];national=aligned.groupby(['ano','classe']).delta.sum();net2021=float(national.loc[2021].sum()/1e6)
assert abs(net2021-e7['change_TgC'])<.0051
from e7_explain import CLASS
for label,value in e7['by_class_TgC'].items():
 code=next(k for k,v in CLASS.items() if v==label);assert abs(float(national.loc[(2021,code)]/1e6)-value)<.0051
by_year=[]
for year,group in summary.groupby(level='ano'):
 by_year.append(dict(year=int(year),comparisons=len(group),max_net_percent=float(group.net_percent.max()),median_gross_class_percent=float(group.gross_class_percent.median()),median_offsetting_percent=float(group.offsetting_percent.median())))
report={'experiment':'E11','protocol_hash':(root/'E11_protocol.sha256').read_text().strip(),'comparison_units':len(summary),'zero_baseline_exclusions':len(excluded),'source_comparison_units':len(summary)+len(excluded),'threshold_results':rows,'by_year':by_year,'national_2021_net_TgC':net2021,'checks':'National total and the eight largest class changes agree with archived E7 to its rounding precision.','interpretation':protocol['interpretation'],'scope':protocol['scope']}
summary.to_csv(root/'E11_municipality_year.csv');(root/'E11_results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
