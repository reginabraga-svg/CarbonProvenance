import time, json
import p1_carbofarm as P
from evaluate import run
t=time.perf_counter(); L0=P.build("V0"); print("build V0", round(time.perf_counter()-t,2),"s", len(L0.d),"datums", len(L0.order),"derived")
from collections import Counter; print(Counter(x.status for x in L0.d.values() if x.kind=="derived"))
print("\n".join(L0.explain("bal_ha|1")))
steps=[("start","V0",None),("soil beta2.1->col3","V1","mapbiomas_soil_context"),("landcover 7.1->10","V2","mapbiomas_soil_context")]
L,res=run(P,steps,"../results/e1_p1.json")
EXPL=[k for k,x in L.d.items() if x.kind=="derived" and x.status=="orphan"][:1]
print("\n".join(L.explain(EXPL[0])) if EXPL else "no orphan")
