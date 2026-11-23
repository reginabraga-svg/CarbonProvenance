"""The ledger exported to PROV-O (RDF) and to a relational lineage table, with the same impact query in
SPARQL and in SQL. Used to check that the three implementations return the same affected set."""
import re
import sqlite3
import time

from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

PROV = Namespace("http://www.w3.org/ns/prov#")
GOV = Namespace("https://example.org/govprov#")
EX = Namespace("https://example.org/data/")


def _u(kind, key):
    return EX[f"{kind}/" + re.sub(r"[^A-Za-z0-9_.-]", "_", key)]


def to_prov(L):
    g = Graph()
    g.bind("prov", PROV); g.bind("gov", GOV); g.bind("ex", EX)
    for name, s in L.sources.items():
        sv = _u("src", f"{name}/{s['version']}")
        g.add((sv, RDF.type, PROV.Entity)); g.add((sv, RDF.type, GOV.SourceVersion))
        g.add((sv, PROV.specializationOf, _u("src", name))); g.add((sv, GOV.version, Literal(s["version"])))
    for k, x in L.d.items():
        u = _u("v", k)
        g.add((u, RDF.type, PROV.Entity)); g.add((u, GOV.key, Literal(k)))
        if x.value is not None:
            g.add((u, PROV.value, Literal(float(x.value), datatype=XSD.double)))
        m = x.meta
        g.add((u, GOV.quantityKind, Literal(m.qkind))); g.add((u, GOV.unit, Literal(m.unit)))
        g.add((u, GOV.period, Literal(m.period))); g.add((u, GOV.support, Literal(m.support)))
        g.add((u, GOV.status, Literal(x.status)))
        if x.kind == "source":
            if x.value is not None:       # a withdrawn value keeps no primary source
                g.add((u, PROV.hadPrimarySource, _u("src", f"{x.source}/{x.version}")))
        else:
            dv = L.der[k]
            a = _u("act", k)
            g.add((a, RDF.type, PROV.Activity)); g.add((a, GOV.operation, Literal(dv.op)))
            g.add((u, PROV.wasGeneratedBy, a))
            for i in dv.inputs:
                ui = _u("v", i)
                g.add((a, PROV.used, ui)); g.add((u, PROV.wasDerivedFrom, ui))
    return g


def impact_sparql(g, changed_keys):
    vals = " ".join(f"<{_u('v', k)}>" for k in changed_keys)
    q = f"""PREFIX prov: <http://www.w3.org/ns/prov#> PREFIX gov: <https://example.org/govprov#>
SELECT DISTINCT ?key WHERE {{ VALUES ?s {{ {vals} }} ?d prov:wasDerivedFrom+ ?s . ?d gov:key ?key }}"""
    t0 = time.perf_counter()
    out = {str(r[0]) for r in g.query(q)}
    return out, time.perf_counter() - t0


def to_sql(L, path=":memory:"):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE datum(key TEXT PRIMARY KEY, kind TEXT, source TEXT, version TEXT, value REAL, qkind TEXT, "
                "unit TEXT, period TEXT, support TEXT, status TEXT, reason TEXT)")
    con.execute("CREATE TABLE derivation(out TEXT PRIMARY KEY, op TEXT)")
    con.execute("CREATE TABLE uses(out TEXT, inp TEXT)")
    con.executemany("INSERT INTO datum VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [(k, x.kind, x.source, x.version, x.value, x.meta.qkind, x.meta.unit, x.meta.period,
                      x.meta.support, x.status, x.reason) for k, x in L.d.items()])
    con.executemany("INSERT INTO derivation VALUES (?,?)", [(k, dv.op) for k, dv in L.der.items()])
    con.executemany("INSERT INTO uses VALUES (?,?)", [(k, i) for k, dv in L.der.items() for i in dv.inputs])
    con.execute("CREATE INDEX ix_uses_inp ON uses(inp)")
    con.commit()
    return con


def impact_sql(con, changed_keys):
    con.execute("DROP TABLE IF EXISTS changed")
    con.execute("CREATE TEMP TABLE changed(k TEXT PRIMARY KEY)")
    con.executemany("INSERT INTO changed VALUES (?)", [(k,) for k in changed_keys])
    t0 = time.perf_counter()
    rows = con.execute("""WITH RECURSIVE dn(k) AS (
        SELECT u.out FROM uses u JOIN changed c ON u.inp = c.k
        UNION SELECT u.out FROM uses u JOIN dn ON u.inp = dn.k)
        SELECT k FROM dn""").fetchall()
    return {r[0] for r in rows}, time.perf_counter() - t0
