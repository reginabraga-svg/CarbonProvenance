"""E7: explaining a revision through the derivation links (P3, all Brazilian municipalities).

Questions a user of an integrated carbon dataset asks after a new release, answered from the record:
  X1 why did a state's stock change, and which land-cover classes and municipalities account for it?
  X2 which states and classes account for the change of the national stock?
  X3 why did the sign of a municipality's 2020-2021 stock change flip?
  X4 the land-cover revision left totals almost unchanged; what moved underneath?
Each attribution is checked for closure (contributions add up to the observed change) and X1 against an
independent computation from the source tables. The same questions are put to the OpenLineage
column-lineage graph of P3.
"""
import json
import time
from collections import defaultdict

import pandas as pd

import p3_brasil as P
from attribution import attribute, capture
from engine import same

CLASS = {0: "not mapped", 3: "Forest formation", 4: "Savanna formation", 5: "Mangrove", 6: "Floodable forest",
         9: "Forest plantation", 11: "Wetland", 12: "Grassland", 13: "Other non-forest formation", 15: "Pasture",
         20: "Sugar cane", 21: "Mosaic of uses", 23: "Beach and dune", 24: "Urban area", 25: "Other non-vegetated",
         29: "Rocky outcrop", 30: "Mining", 31: "Aquaculture", 32: "Hypersaline tidal flat", 33: "River and lake",
         35: "Oil palm", 39: "Soybean", 40: "Rice", 41: "Other temporary crops", 46: "Coffee", 47: "Citrus",
         48: "Other perennial crops", 49: "Wooded sandbank vegetation", 50: "Herbaceous sandbank vegetation",
         62: "Cotton", 75: "Photovoltaic power plant"}


def parts(key):
    f = key.split("|")
    return f[0], f[1], int(f[2]), int(f[3])          # family, municipality, class, year


def group(contrib, by):
    g = defaultdict(float)
    for (kind, key), c in contrib.items():
        fam, m, cl, y = parts(key)
        what = {"source": "soil" if fam == "soil" else "area", "added": "context added", "withdrawn": "context withdrawn"}[kind]
        g[by(what, m, cl, y)] += c
    return dict(g)


def step(L, tag):
    L.apply_update("mapbiomas_soil", tag, P.soil(tag))
    L.apply_update("mapbiomas_lulc_area", tag, P.area(tag))
    P.rewire_to(L, tag)


def tg(x):
    return round(x / 1e6, 2)                         # t C -> Tg C


if __name__ == "__main__":
    muns = P.municipalities()
    names = dict(zip(P.table("V0").id, P.table("V0").municipio))
    L = P.build("V0")
    pos = {k: i for i, k in enumerate(L.order)}
    res = {}

    # ---------------------------------------------------------------- V0 -> V1, soil beta 2.1 -> collection 3
    old = capture(L)
    step(L, "V1")
    nv = {k: x.value for k, x in L.d.items()}
    ov = old[0]
    t0 = time.perf_counter()
    a = attribute(L, old, "stock_uf|Rondonia|2020", nv, pos)
    t_state = time.perf_counter() - t0
    d = nv["stock_uf|Rondonia|2020"] - ov["stock_uf|Rondonia|2020"]
    by_class = group(a, lambda w, m, c, y: CLASS.get(c, str(c)))
    by_kind = group(a, lambda w, m, c, y: w)
    by_mun = group(a, lambda w, m, c, y: m)
    top = sorted(by_mun.items(), key=lambda x: -x[1])
    # independent check: per-class change of soil x area joined from the two source tables
    t0_, t1_ = P.table("V0"), P.table("V1")
    j = []
    for t in (t0_, t1_):
        x = t[(t.uf == "Rondonia") & (t.ano == 2020)]
        j.append((x.media_t_C_ha * x.area_ha).groupby(x.classe).sum())
    indep = (j[1].reindex(j[0].index.union(j[1].index), fill_value=0) - j[0].reindex(j[0].index.union(j[1].index), fill_value=0))
    max_dev = max(abs(by_class.get(CLASS.get(c, str(c)), 0) - v) for c, v in indep.items())
    res["X1_rondonia_2020_soil_revision"] = dict(
        stock_old_TgC=tg(ov["stock_uf|Rondonia|2020"]), stock_new_TgC=tg(nv["stock_uf|Rondonia|2020"]),
        change_pct=round(d / ov["stock_uf|Rondonia|2020"] * 100, 1), change_TgC=tg(d),
        closure_error_tC=abs(sum(a.values()) - d), source_values_reached=len(a), seconds=round(t_state, 2),
        by_kind_TgC={k: tg(v) for k, v in by_kind.items()},
        by_class_TgC={k: tg(v) for k, v in sorted(by_class.items(), key=lambda x: -abs(x[1]))[:6]},
        by_class_share={k: round(v / d, 3) for k, v in sorted(by_class.items(), key=lambda x: -abs(x[1]))[:4]},
        municipalities=len(by_mun), top10_share=round(sum(v for _, v in top[:10]) / d, 3),
        top3=[(names[m], tg(v)) for m, v in top[:3]],
        independent_join_max_deviation_tC=float(max_dev))

    t0 = time.perf_counter()
    a = attribute(L, old, "stock_br|2020", nv, pos)
    t_nat = time.perf_counter() - t0
    d = nv["stock_br|2020"] - ov["stock_br|2020"]
    by_state = group(a, lambda w, m, c, y: muns[m])
    by_class = group(a, lambda w, m, c, y: CLASS.get(c, str(c)))
    res["X2_brazil_2020_soil_revision"] = dict(
        change_TgC=tg(d), change_pct=round(d / ov["stock_br|2020"] * 100, 2), closure_error_tC=abs(sum(a.values()) - d),
        source_values_reached=len(a), seconds=round(t_nat, 2),
        by_state_TgC={k: tg(v) for k, v in sorted(by_state.items(), key=lambda x: -abs(x[1]))[:8]},
        by_class_TgC={k: tg(v) for k, v in sorted(by_class.items(), key=lambda x: -abs(x[1]))[:6]},
        gross_up_TgC=tg(sum(v for v in by_state.values() if v > 0)), gross_down_TgC=tg(sum(v for v in by_state.values() if v < 0)))

    # X3: sign flips of the 2020-2021 municipal change
    flips, soil_led, pos_to_neg, closure = 0, 0, 0, 0.0
    tot = defaultdict(float)
    for m in sorted(muns):
        k = f"dstock_mun|{m}|2021"
        x, y = ov.get(k), nv.get(k)
        if x and y and (x > 0) != (y > 0):
            a = attribute(L, old, k, nv, pos)
            closure = max(closure, abs(sum(a.values()) - (y - x)))
            g = group(a, lambda w, mm, c, yy: w)
            for w_, v in g.items():
                tot[w_] += abs(v)
            flips += 1
            pos_to_neg += x > 0
            soil_led += abs(g.get("soil", 0)) > sum(abs(v) for w_, v in g.items() if w_ != "soil")
    res["X3_sign_flips_2020_2021"] = dict(municipalities=flips, positive_to_negative=pos_to_neg,
                                          soil_dominates=soil_led, abs_contribution_TgC={k: tg(v) for k, v in tot.items()},
                                          max_closure_error_tC=closure)

    # ---------------------------------------------------------------- V1 -> V2, land cover 7.1 -> 10
    old = capture(L)
    step(L, "V2")
    nv = {k: x.value for k, x in L.d.items()}
    ov = old[0]
    a = attribute(L, old, "stock_br|2021", nv, pos)
    d = nv["stock_br|2021"] - ov["stock_br|2021"]
    by_kind = group(a, lambda w, m, c, y: w)
    by_class = group(a, lambda w, m, c, y: CLASS.get(c, str(c)))
    mun_abs = []
    for m in sorted(muns):
        k = f"stock_mun|{m}|2021"
        if ov.get(k):
            mun_abs.append(abs(nv[k] - ov[k]) / ov[k])
    res["X4_brazil_2021_land_cover_revision"] = dict(
        change_TgC=tg(d), change_pct=round(d / ov["stock_br|2021"] * 100, 4), closure_error_tC=abs(sum(a.values()) - d),
        by_kind_TgC={k: tg(v) for k, v in by_kind.items()},
        gross_class_flows_TgC=tg(sum(abs(v) for v in by_class.values())),
        by_class_TgC={k: tg(v) for k, v in sorted(by_class.items(), key=lambda x: -abs(x[1]))[:8]},
        max_municipal_change_pct=round(max(mun_abs) * 100, 4))

    json.dump(res, open("../results/e7_explain.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))
