"""E1 and E2 on P3 (all Brazilian municipalities, 2017-2021): two real MapBiomas revisions at national scale.

Each step updates both sources (soil means and mapped areas) and then rewires the municipal totals to the
contexts the new land-cover collection maps; the result is compared with a ledger built from scratch.
"""
import json
import time
from collections import Counter

import p3_brasil as P
from engine import same
from evaluate import _st


def step(L, tag):
    before = L.snapshot()
    t0 = time.perf_counter()
    r1 = L.apply_update("mapbiomas_soil", tag, P.soil(tag))
    r2 = L.apply_update("mapbiomas_lulc_area", tag, P.area(tag))
    rw = P.rewire_to(L, tag)
    t_inc = time.perf_counter() - t0
    flagged = set()
    for r in (r1, r2):
        flagged |= r["_impact"]["stale"] | r["_impact"]["orphan"] | r["_impact"]["resolvable"]
    flagged |= rw["_affected"]
    t0 = time.perf_counter()
    gt = P.build(tag)
    t_full = time.perf_counter() - t0
    truth, after = gt.snapshot(), L.snapshot()
    truly = {k for k in truth if k in before and (not same(before[k][0], truth[k][0]) or _st(before[k][1]) != _st(truth[k][1]))}
    mism = [k for k in truth if k not in after or not same(after[k][0], truth[k][0]) or _st(after[k][1]) != _st(truth[k][1])]
    return dict(new_version=tag, values=len(L.d), derived=len(L.order),
                soil_diff=r1["diff"], area_diff=r2["diff"], rewired=rw["rewired"],
                truly_changed=len(truly), flagged=len(flagged),
                recall=round(len(truly & flagged) / len(truly), 4), precision=round(len(truly & flagged) / len(flagged), 4),
                orphans_after=sum(1 for k in L.order if L.d[k].status == "orphan"),
                table_level_flagged=len(L.order),
                incremental_equals_full_rebuild=not mism, mismatches=mism[:5],
                seconds_incremental=round(t_inc, 2), seconds_full_rebuild=round(t_full, 2),
                evaluations_incremental=r1["recomputed"] + r2["recomputed"] + rw["recomputed"], evaluations_full=len(gt.order),
                status_counts=dict(Counter(v[1] for v in truth.values()))), before, truth


def headline(snaps):
    """national, state and municipal consequences of the two revisions (2021 unless stated)"""
    out = {}
    v = lambda s, k: s[k][0] if k in s and s[k][0] is not None else None
    for tag, s in snaps.items():
        out[f"stock_br_2021_PgC_{tag}"] = round(v(s, "stock_br|2021") / 1e9, 3)
        out[f"dstock_br_2020_2021_TgC_{tag}"] = round(v(s, "dstock_br|2021") / 1e6, 2)
    muns = sorted({k.split("|")[1] for k in snaps["V0"] if k.startswith("stock_mun|")})
    for a, b in [("V0", "V1"), ("V1", "V2")]:
        rel = []
        flips = 0
        n_d = 0
        for m in muns:
            x, y = v(snaps[a], f"stock_mun|{m}|2021"), v(snaps[b], f"stock_mun|{m}|2021")
            if x and y is not None:
                rel.append((y - x) / x)
            dx, dy = v(snaps[a], f"dstock_mun|{m}|2021"), v(snaps[b], f"dstock_mun|{m}|2021")
            if dx is not None and dy is not None and abs(dx) > 0 and abs(dy) > 0:
                n_d += 1
                flips += (dx > 0) != (dy > 0)
        s = pd_series(rel)
        out[f"{a}->{b}"] = dict(municipalities=len(rel), median_change=round(float(s.median()), 4),
                               p05=round(float(s.quantile(.05)), 4), p95=round(float(s.quantile(.95)), 4),
                               over_10pct=int((s.abs() > .10).sum()), over_25pct=int((s.abs() > .25).sum()),
                               annual_change_2020_2021_sign_flips=f"{flips}/{n_d}")
        ufs = sorted({k.split("|")[1] for k in snaps[a] if k.startswith("stock_uf|")})
        out[f"{a}->{b}_by_state"] = {u: round((v(snaps[b], f"stock_uf|{u}|2021") / v(snaps[a], f"stock_uf|{u}|2021") - 1) * 100, 2) for u in ufs}
    return out


def pd_series(x):
    import pandas as pd
    return pd.Series(x)


if __name__ == "__main__":
    t0 = time.perf_counter()
    L = P.build("V0")
    res = dict(build_seconds=round(time.perf_counter() - t0, 1), values=len(L.d), derived=len(L.order),
               status_V0=dict(Counter(L.d[k].status for k in L.order)))
    print(json.dumps(res))
    snaps = {"V0": L.snapshot()}
    steps = []
    for tag in ["V1", "V2"]:
        r, before, truth = step(L, tag)
        steps.append(r)
        snaps[tag] = truth
        print(json.dumps({k: x for k, x in r.items() if k != "mismatches"}))
    res["steps"] = steps
    res["headline"] = headline(snaps)
    ex = [k for k in L.order if L.d[k].status == "orphan"][:1]
    res["orphan_example"] = L.explain(ex[0], maxdepth=2) if ex else None
    json.dump(res, open("../results/e1_p3.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res["headline"], indent=1, ensure_ascii=False))
