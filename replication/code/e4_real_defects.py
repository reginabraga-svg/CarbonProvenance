"""E4: the documented problems of the CarboFarm release, as the governance layer reports them.

The release is loaded as a source with the meaning it declares (column names and ontology properties say CO2),
next to the reconstruction from its public sources. Reported, with the number of values involved:
  D1 unit       the stock column declared as CO2 reproduces MapBiomas carbon values (t C): a unit contract violation
  D2 kind       balance = stock (instant) minus emission (annual flux): blocked
  D3 support    municipal x class means assigned to farm areas: contextual
  D4 origin     records whose stock has no counterpart in the source (Miradouro class 4): unresolved, though the
                release gives them a value
  D5 component  the emission rate is the BRLUC crop rate plus a municipal constant whose source is not documented
"""
import json
from collections import Counter

import pandas as pd

import p1_carbofarm as P1
from engine import AREA, FACTOR, FLUX, SHARE, STOCK, Meta

L = P1.build("V0")
cf = P1.farm_records()
out = {}

# D1: declared release values against the reconstruction, with the release's own unit
L.register_source("carbofarm_release", "carbofarm-2023", note="columns as declared: CO2_stock_ha")
for (c, a), v in cf.groupby(["city_cod", "area_cod"]).CO2_stock_ha.first().items():
    L.put(f"release_stock|{c}|{a}", float(v), Meta(STOCK, "t CO2/ha", "instant:2021", "municipality_class"),
          "carbofarm_release", "carbofarm-2023")
    L.derive(f"repro_ratio|{c}|{a}", "ratio", [f"release_stock|{c}|{a}", f"soil|{c}|{a}|2021"], Meta(SHARE, "1", "none", "municipality_class"))
r = [L.d[k] for k in L.d if k.startswith("repro_ratio|")]
vals = [x for x in r if x.value is not None]
out["D1_unit"] = dict(contexts=len(r), blocked=sum(x.status == "blocked" for x in r),
                      ratio_median=float(pd.Series([x.value for x in vals]).median()) if vals else None,
                      ratio_if_really_CO2=round(44 / 12, 4),
                      example=L.explain(r[0].key)[:3])

st = Counter((k.split("|")[0], x.status) for k, x in L.d.items() if x.kind == "derived")
out["D2_kind"] = dict(balance_values_blocked=st[("bal_ha", "blocked")] + st[("bal_area", "blocked")],
                      example=L.explain("bal_ha|1")[0])
out["D3_support"] = dict(contextual_values=sum(v for (n, s), v in st.items() if s == "contextual"),
                         example=L.explain("stock_ha|1")[0])
unres = [k for k, x in L.d.items() if k.startswith("stock_ha|") and x.status == "unresolved"]
rel = cf.set_index("index")
out["D4_origin"] = dict(records_without_source=len(unres),
                        release_values_for_them=sorted({float(rel.loc[int(k.split('|')[1]), "CO2_stock_ha"]) for k in unres}),
                        example=L.explain(unres[0])[:2] if unres else None)

# D5: decomposition of the emission rate with the BRLUC rate table (Crop_Emission_Rate.xls)
rt = pd.read_excel(P1.D / "crop_emission_rate.xls", sheet_name="Emissao").set_index("Codigo Municipal IBGE")
g = cf.groupby(["city_cod", "area_cod"]).agg(emi=("CO2_emission_ha", "first"), n=("index", "size")).reset_index()
g["brluc"] = [rt.loc[x.city_cod, x.area_cod] for x in g.itertuples()]
g["residual"] = (g.emi - g.brluc).round(6)
res_by_mun = g[g.brluc > 0].groupby("city_cod").residual.agg(["min", "max"])
out["D5_component"] = dict(contexts=len(g), contexts_with_residual=int((g.residual.abs() > 1e-6).sum()),
                           records_with_residual=int(g[g.residual.abs() > 1e-6].n.sum()),
                           residual_constant_within_municipality=bool((res_by_mun["max"] - res_by_mun["min"]).abs().max() < 1e-6),
                           residual_by_municipality=res_by_mun["min"].round(4).to_dict(),
                           rule="residual added only where the BRLUC rate is positive")
json.dump(out, open("../results/e4_real_defects.json", "w"), indent=1, ensure_ascii=False, default=str)
print(json.dumps(out, indent=1, ensure_ascii=False, default=str))
