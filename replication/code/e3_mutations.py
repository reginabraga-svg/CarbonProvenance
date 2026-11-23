"""E3: injected defects in source values, detected (or not) by three layers.

Each mutation is applied to one source value through the normal update path and then undone.
Layers
  structural   the value is present and numeric (what a schema check sees)
  contract     some value computed from it is blocked by an input or operation contract
  provenance   the ledger reports the change: a removed key (orphan) or a value changed under the same
               declared version (unannounced change)
Families
  invalid: unit_label (value converted, unit changed), period (year shifted), kind (stock<->flux), support
           (municipal value declared as state value), removed (key withdrawn), silent_scale (x1000, same
           version), silent_scale_versioned (x1000 under a new version label)
  controls: revision_versioned (value -2% under a new version label), equivalent_unit (/ a written as / yr)
"""
import json
import random
import sys

from engine import Meta

FAMILIES = ["unit_label", "period", "kind", "support", "removed", "silent_scale", "silent_scale_versioned",
            "revision_versioned", "equivalent_unit"]
INVALID = set(FAMILIES[:7])


def mutate(fam, key, v, m: Meta):
    if fam == "unit_label":
        return v * 1000, Meta(m.qkind, "kg" + m.unit[1:] if m.unit.startswith("t") else "1000 " + m.unit, m.period, m.support)
    if fam == "period":
        p, y = m.period.split(":") if ":" in m.period else (m.period, "")
        return v, Meta(m.qkind, m.unit, f"{p}:{int(y) - 1}" if y else "annual:2020", m.support)
    if fam == "kind":
        return v, Meta("flux" if m.qkind != "flux" else "stock", m.unit, m.period, m.support)
    if fam == "support":
        return v, Meta(m.qkind, m.unit, m.period, "state")
    if fam in ("silent_scale", "silent_scale_versioned"):
        return v * 1000, m
    if fam == "revision_versioned":
        return v * 0.98, m
    if fam == "equivalent_unit":
        return v, Meta(m.qkind, m.unit.replace("/ yr", "/ a") if "/ yr" in m.unit else m.unit, m.period, m.support)


def run(L, source, n, seed=7):
    rng = random.Random(seed)
    pool = sorted(k for k, x in L.d.items() if x.kind == "source" and x.source == source and L.down.get(k) and x.value)
    keys = rng.sample(pool, min(n, len(pool)))
    base_version = L.sources[source]["version"]
    rows = []
    for fam in FAMILIES:
        if fam == "equivalent_unit" and not any("/ yr" in L.d[k].meta.unit for k in keys):
            continue
        for k in keys:
            x = L.d[k]
            orig = {kk: (xx.value, xx.meta) for kk, xx in L.d.items() if xx.kind == "source" and xx.source == source}
            new = dict(orig)
            if fam == "removed":
                del new[k]
            else:
                new[k] = mutate(fam, k, x.value, x.meta)
            ver = base_version + "+m" if fam in ("silent_scale_versioned", "revision_versioned") else base_version
            before = {d: L.d[d].status for d in L.downstream([k])}
            res = L.apply_update(source, ver, new)
            after = {d: L.d[d].status for d in before}
            structural = fam == "removed"          # a missing key is visible to a completeness check
            contract = any(after[d] == "blocked" and before[d] != "blocked" for d in after)
            prov = bool(res["_diff"]["removed"]) or bool(res["_diff"]["unannounced"])
            rows.append(dict(family=fam, key=k, invalid=fam in INVALID, structural=structural, contract=contract,
                             provenance=prov, any=structural or contract or prov))
            L.apply_update(source, base_version, orig)     # undo
    return rows


def summarize(rows):
    out = {}
    for fam in FAMILIES:
        r = [x for x in rows if x["family"] == fam]
        if not r:
            continue
        out[fam] = {k: f"{sum(x[k] for x in r)}/{len(r)}" for k in ("structural", "contract", "provenance", "any")}
    inv = [x for x in rows if x["invalid"]]
    ctl = [x for x in rows if not x["invalid"]]
    out["invalid_total"] = {k: f"{sum(x[k] for x in inv)}/{len(inv)}" for k in ("structural", "contract", "provenance", "any")}
    out["controls_flagged"] = {k: f"{sum(x[k] for x in ctl)}/{len(ctl)}" for k in ("structural", "contract", "provenance", "any")}
    return out


if __name__ == "__main__":
    import p1_carbofarm as P1
    import p2_national as P2
    res = {}
    L1 = P1.build("V0")
    r1 = run(L1, "mapbiomas_soil_context", 30)
    res["P1 soil contexts"] = summarize(r1)
    L2 = P2.build()
    r2 = run(L2, "ipcc_factors", 30) + run(L2, "primap_hist", 30) + run(L2, "faostat_livestock", 30)
    res["P2 factors, PRIMAP, FAOSTAT"] = summarize(r2)
    res["all"] = summarize(r1 + r2)
    json.dump(res, open("../results/e3_mutations.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
