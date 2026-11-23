import json, time
import p2_national as P, p1_carbofarm as P1
from stores import to_prov, impact_sparql, to_sql, impact_sql
out=[]
def check(name, L, changed):
    eng=L.downstream(changed)
    t=time.perf_counter(); g=to_prov(L); tg=time.perf_counter()-t
    sp,ts=impact_sparql(g,changed)
    t=time.perf_counter(); con=to_sql(L); tq=time.perf_counter()-t
    sq,tsq=impact_sql(con,changed)
    r=dict(case=name, changed_sources=len(changed), affected_engine=len(eng), sparql_equal=(sp==eng), sql_equal=(sq==eng),
           triples=len(g), seconds_build_rdf=round(tg,1), seconds_sparql=round(ts,2), seconds_build_sql=round(tq,1), seconds_sql=round(tsq,3))
    print(json.dumps(r)); out.append(r)
L=P.build()
check("GWP AR5->AR6 (P2)", L, list(P.gwp("AR6")))
d=L.diff_source("ipcc_factors", P.factors("2019",None)); check("IPCC factors 2006->2019 (P2)", L, d["changed"]+d["removed"])
L1=P1.build("V0"); d=L1.diff_source("mapbiomas_soil_context", P1.soil_version("V2"))
check("MapBiomas V0->V2 (P1)", L1, d["changed"]+d["removed"])
json.dump(out,open("../results/stores_equivalence.json","w"),indent=1)
