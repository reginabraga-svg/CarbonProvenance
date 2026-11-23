import json
from collections import Counter
import p2_national as P
from evaluate import score_step
# (a) the same PRIMAP update with units written canonically (/a == /yr)
L=P.build(canon_units=True)
new={k:(v,P.Meta(m.qkind,P.canonical_unit(m.unit),m.period,m.support)) for k,(v,m) in P.primap("v2.7").items()}
r,L=score_step("PRIMAP-hist v2.6->v2.7, canonical units","primap_hist",L,"v2.7",lambda t: new,lambda t: P.build({"primap":"v2.7"},canon_units=True))
print(json.dumps({k:v for k,v in r.items() if k!="mismatches"}))
# (b) what a pipeline without lineage does with 2019 factors and the 2006 regions: a missing factor read as 0
cfg={"primap":"v2.7","gwp":"AR6","factors":"2019"}
bad=P.build(cfg); good=P.build(dict(cfg,scheme="2019"))
ef=P.factors("2019",None)
miss=Counter(); lost={}
for k,dv in bad.der.items():
    if k.startswith("enteric_ch4|") and "|total|" not in k:
        if dv.inputs[1] not in ef:
            iso,a,y=k.split("|")[1:]
            if y=="2020":
                miss[a]+=1; lost[iso]=lost.get(iso,0)+(good.d[k].value or 0)
tot2020=sum((good.d[k].value or 0) for k in good.d if k.startswith("enteric_ch4|") and k.endswith("|total|2020"))
print("value-lookups without a 2019 factor under 2006 regions (2020):",dict(miss))
print("countries affected:",len(lost),"enteric CH4 that would be silently dropped in 2020 (Gg):",round(sum(lost.values()),1),
      "of world total",round(tot2020,1),"=",round(100*sum(lost.values())/tot2020,1),"%")
print("largest:",sorted(lost.items(),key=lambda x:-x[1])[:6])
