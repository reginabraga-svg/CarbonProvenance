"""E2: cost against size. P2 over longer year spans; update = IPCC factors 2006->2019 (2006 regions)."""
import json, time
import p2_national as P
from stores import to_sql, impact_sql
out=[]
for y0 in (2015, 2003, 1990, 1961):
    P.YEARS=list(range(y0,2023))
    t=time.perf_counter(); L=P.build(); tb=time.perf_counter()-t
    con=to_sql(L); d=L.diff_source("ipcc_factors",P.factors("2019",None))
    _,tsq=impact_sql(con,d["changed"]+d["removed"])
    r=L.apply_update("ipcc_factors","2019",P.factors("2019",None))
    t=time.perf_counter(); P.build({"factors":"2019"}); tf=time.perf_counter()-t
    row=dict(years=len(P.YEARS), values=len(L.d), derived=len(L.order), seconds_build=round(tb,2),
             flagged=sum(r["impact"].values()), seconds_impact=round(r["seconds_analysis"],3), seconds_incremental=round(r["seconds_recompute"],3),
             seconds_full_rebuild=round(tf,2), seconds_impact_sql=round(tsq,3))
    print(json.dumps(row)); out.append(row)
json.dump(out,open("../results/e2_scale.json","w"),indent=1)
