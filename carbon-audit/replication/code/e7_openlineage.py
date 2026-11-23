"""E7, lineage service side: what the OpenLineage column-lineage graph of P3 can say about the questions of E7."""
import json
from collections import defaultdict

import p3_brasil as P
from e6_practice import fam, openlineage_events

L = P.build("V0")
ev = openlineage_events(L)
up = defaultdict(set)
for e in ev:
    for o in e.outputs:
        for f in o.facets["columnLineage"].fields["value"].inputFields:
            up[o.name].add(f.name)


def upstream(ds):
    seen, todo = [], [ds]
    while todo:
        for i in sorted(up[todo.pop()]):
            if i not in seen:
                seen.append(i)
                todo.append(i)
    return seen


res = dict(events=len(ev), datasets=sorted({o.name for e in ev for o in e.outputs}),
           stock_uf_upstream=upstream("stock_uf"), stock_br_upstream=upstream("stock_br"),
           dstock_mun_upstream=upstream("dstock_mun"),
           note="the graph is the same for every state, municipality and year; it holds no values and no operations")
json.dump(res, open("../results/e7_openlineage.json", "w"), indent=1)
print(json.dumps(res, indent=1))
