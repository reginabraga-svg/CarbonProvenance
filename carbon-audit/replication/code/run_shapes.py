import pandas as pd
import json
import p1_carbofarm as P1
from stores import to_prov
from shapes import check
cf=P1.farm_records(); cf=cf[cf.city_cod.isin([2312908,3142106])]
# sample: farm areas of the two contexts with lineage problems plus 300 others, fixed seed
special=cf[((cf.city_cod==2312908)&(cf.area_cod==12))|((cf.city_cod==3142106)&(cf.area_cod==4))]
cf=pd.concat([special.sample(min(len(special),150),random_state=1), cf.drop(special.index).sample(300,random_state=1)])
L=P1.build("V0",cf=cf); L.apply_update("mapbiomas_soil_context","V2",P1.soil_version("V2"))
g=to_prov(L); res,t=check(g)
from stores import _u
key={str(_u("v",k)):k for k in L.d}
sh={s:{key[f] for f,ss,v in res if ss==s} for s in ("S1","S2","S3")}
eng_S1={k for k,x in L.d.items() if x.kind=="derived" and x.status=="blocked" and not x.reason.startswith("inherits") and x.reason.startswith(("diff","sum"))}
eng_S2={k for k,x in L.d.items() if x.kind=="derived" and x.reason.startswith("value of")}
eng_S3={k for k,x in L.d.items() if x.kind=="derived" and x.status in ("unresolved","orphan")}
unres={k for k,x in L.d.items() if x.status in ("unresolved","orphan")}
def cmp(a,b): return dict(shacl=len(a),ledger=len(b),ledger_subset_of_shacl=b<=a,extra_all_unresolved=(a-b)<=unres,extra=len(a-b))
out=dict(records=len(cf), triples=len(g), seconds_shacl=round(t,1),
         S1=cmp(sh["S1"],eng_S1), S2=cmp(sh["S2"],eng_S2),
         S3=dict(shacl=len(sh["S3"]),ledger=len(eng_S3),equal=sh["S3"]==eng_S3))
print(json.dumps(out)); json.dump(out,open("../results/shacl_equivalence.json","w"),indent=1)
if not out["S3"]["equal"]: print(list(sh["S3"]-eng_S3)[:3], list(eng_S3-sh["S3"])[:3])
