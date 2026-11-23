import json, time
from collections import Counter
import p2_national as P
from evaluate import score_step, _st
from engine import same

def cnt(L): return Counter(x.status for x in L.d.values() if x.kind=="derived")
t=time.perf_counter(); L=P.build(); print("build S0", round(time.perf_counter()-t,1),"s", len(L.d),"datums", len(L.order),"derived", cnt(L))
res=[]
steps=[("PRIMAP-hist v2.6->v2.7","primap_hist","v2.7",lambda t: P.primap(t), {"primap":"v2.7"}),
       ("GWP AR5->AR6","gwp","AR6",lambda t: P.gwp(t), {"primap":"v2.7","gwp":"AR6"}),
       ("IPCC factors 2006->2019 (2006 regions kept)","ipcc_factors","2019",lambda t: P.factors(t,None), {"primap":"v2.7","gwp":"AR6","factors":"2019"})]
for name,src,tag,loader,cfg in steps:
    r,L=score_step(name,src,L,tag,loader,lambda _t,cfg=cfg: P.build(cfg)); res.append(r)
    print(json.dumps({k:v for k,v in r.items() if k!="mismatches"},ensure_ascii=False)); print("   mismatches:",r["mismatches"][:3])
# S4: regional scheme 2006 -> 2019 (structural change)
before=L.snapshot()
rw=P.rewire_for_scheme(L,"2019")
gt=P.build({"primap":"v2.7","gwp":"AR6","factors":"2019","scheme":"2019"}); truth=gt.snapshot(); after=L.snapshot()
truly={k for k in truth if k in before and (not same(before[k][0],truth[k][0]) or _st(before[k][1])!=_st(truth[k][1]))}
mism=[k for k in truth if not same(after[k][0],truth[k][0]) or _st(after[k][1])!=_st(truth[k][1])]
r=dict(step="regional scheme 2006->2019 (rewire)", rewired=rw["rewired"], affected=rw["affected"], truly_changed=len(truly),
       recall=round(len(truly&rw["_affected"])/len(truly),4) if truly else None, precision=round(len(truly&rw["_affected"])/rw["affected"],4),
       incremental_equals_full_rebuild=not mism, mismatches=mism[:5], recomputed=rw["recomputed"], evaluations_full=len(gt.order),
       seconds=round(rw["seconds"],3), status_counts_after=dict(Counter(v[1] for v in truth.values())))
res.append(r); print(json.dumps({k:v for k,v in r.items()},ensure_ascii=False))
json.dump(res,open("../results/e1_p2.json","w"),indent=1,ensure_ascii=False)
for k in ["enteric_ch4|USA|buffalo|2020","tier1_vs_primap_ch4|BRA|2020","enteric_ch4|NGA|other_cattle|2020"]:
    print("\n".join(L.explain(k)) if k in L.d else k+" absent")
