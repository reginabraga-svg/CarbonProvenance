"""E5: verification questions answered by query, in SQL over the lineage tables and SPARQL over PROV-O.

Q1 which sources and versions does a reported value rest on?
Q2 which reported values rest on a given source version (here IPCC factors 2006)?
Q3 which values combine quantities of different kinds or units?
Q4 which values rest on a value assigned from a coarser spatial support?
Q5 which values have lineage that does not reach a primary source?
Q6 which values would change if one factor were revised (Latin America dairy cattle)?
"""
import json
import time

import p2_national as P
from stores import _u, impact_sql, to_prov, to_sql

L = P.build({"factors": "2019", "gwp": "AR6", "primap": "v2.7"})       # 2019 factors, 2006 regions: some orphans
con = to_sql(L)
target = "livestock_t1_co2e|BRA|2020"
SQL = {
    "Q1": f"""WITH RECURSIVE up(k) AS (SELECT '{target}' UNION SELECT u.inp FROM uses u JOIN up ON u.out = up.k)
             SELECT DISTINCT d.source, d.version FROM up JOIN datum d ON d.key = up.k WHERE d.kind = 'source'""",
    "Q2": """WITH RECURSIVE dn(k) AS (SELECT u.out FROM uses u JOIN datum d ON u.inp = d.key
             WHERE d.source = 'ipcc_factors' UNION SELECT u.out FROM uses u JOIN dn ON u.inp = dn.k) SELECT count(*) FROM dn""",
    "Q3": """SELECT count(*) FROM datum WHERE kind = 'derived' AND status = 'blocked' AND reason NOT LIKE 'inherits%'""",
    "Q4": """SELECT count(*) FROM datum WHERE kind = 'derived' AND status = 'contextual'""",
    "Q5": """SELECT count(*) FROM datum WHERE kind = 'derived' AND status IN ('unresolved', 'orphan')""",
    "Q6": """WITH RECURSIVE dn(k) AS (SELECT out FROM uses WHERE inp = 'ef|enteric|dairy|Latin America'
             UNION SELECT u.out FROM uses u JOIN dn ON u.inp = dn.k) SELECT count(*) FROM dn""",
}
out = {"values": len(L.d), "derived": len(L.order)}
for q, s in SQL.items():
    t0 = time.perf_counter()
    r = con.execute(s).fetchall()
    out[q] = dict(sql_answer=r if q == "Q1" else r[0][0], sql_seconds=round(time.perf_counter() - t0, 4))

g = to_prov(L)
PFX = "PREFIX prov: <http://www.w3.org/ns/prov#> PREFIX gov: <https://example.org/govprov#>\n"
SPARQL = {
    "Q1": f"SELECT DISTINCT ?src WHERE {{ <{_u('v', target)}> prov:wasDerivedFrom* ?x . ?x prov:hadPrimarySource ?src }}",
    "Q6": f"SELECT (COUNT(DISTINCT ?d) AS ?n) WHERE {{ ?d prov:wasDerivedFrom+ <{_u('v', 'ef|enteric|dairy|Latin America')}> }}",
    "Q5": "SELECT (COUNT(DISTINCT ?d) AS ?n) WHERE { ?d gov:status ?s ; prov:wasGeneratedBy ?a . FILTER(?s IN (\"unresolved\",\"orphan\")) }",
}
for q, s in SPARQL.items():
    t0 = time.perf_counter()
    r = [tuple(str(c) for c in row) for row in g.query(PFX + s)]
    out[q].update(sparql_answer=(sorted(x[0].split("/src/")[-1] for x in r) if q == "Q1" else int(r[0][0])),
                  sparql_seconds=round(time.perf_counter() - t0, 3))
out["triples"] = len(g)
json.dump(out, open("../results/e5_questions.json", "w"), indent=1)
print(json.dumps(out, indent=1))
