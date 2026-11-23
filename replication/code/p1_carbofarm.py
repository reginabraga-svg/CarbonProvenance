"""P1: the CarboFarm farm-area integration rebuilt on the ledger.

Sources
  mapbiomas_soil_context   soil organic carbon stock 0-30 cm, mean by municipality x land-cover class, 2021
                           (one version per MapBiomas Soil x MapBiomas land-cover collection pair, from Earth Engine)
  carbofarm_emission_rate  emission rate by municipality x class from the CarboFarm release (its SEEG version and
                           the intermediate rate table are not available, so it stays fixed)
  car_farm_areas           area of each farm area record (Rural Environmental Registry), with its municipality and class
Derived, per farm area record: stock_ha, stock_area, emission_ha, emission_area, balance_ha, balance_area;
per municipality x class and per municipality: total stock and total emission.
"""
from pathlib import Path

import pandas as pd

from engine import AREA, FLUX, STOCK, Ledger, Meta

HERE = Path(__file__).resolve().parent
D = HERE.parent / "data"
CF = D / "carbofarm/data_integration_all_areas_final.csv"
GEE = D / "gee_solo_2021_versoes.csv"
VERSIONS = {"V0": ("beta_2_1", "col_7_1"), "V1": ("col_3", "col_7_1"), "V2": ("col_3", "col_10")}

M_SOIL = Meta(STOCK, "t C/ha", "instant:2021", "municipality_class")
M_EMI = Meta(FLUX, "t CO2e/ha/yr", "annual:2021", "municipality_class")
M_AREA = Meta(AREA, "ha", "instant:2021", "farm_area")


def farm_records():
    cf = pd.read_csv(CF, encoding="utf-8-sig")
    return cf


def soil_version(tag):
    g = pd.read_csv(GEE)
    vs, vc = VERSIONS[tag]
    g = g[(g.versao_solo == vs) & (g.versao_cobertura == vc) & g.media_t_C_ha.notna()]
    return {f"soil|{r.cod}|{r.classe}|2021": (float(r.media_t_C_ha), M_SOIL) for r in g.itertuples()}


def build(tag="V0", cf=None):
    cf = farm_records() if cf is None else cf
    L = Ledger()
    L.register_source("mapbiomas_soil_context", tag, note=str(VERSIONS[tag]))
    for k, (v, m) in soil_version(tag).items():
        L.put(k, v, m, "mapbiomas_soil_context", tag)
    L.register_source("carbofarm_emission_rate", "carbofarm-2023", note="SEEG version unknown")
    for (c, a), v in cf.groupby(["city_cod", "area_cod"]).CO2_emission_ha.first().items():
        L.put(f"emi|{c}|{a}", float(v), M_EMI, "carbofarm_emission_rate", "carbofarm-2023")
    L.register_source("car_farm_areas", "carbofarm-2023")
    for r in cf.itertuples():
        L.put(f"area|{r.index}", float(r.area_size), M_AREA, "car_farm_areas", "carbofarm-2023")

    by_ctx = {}
    for r in cf.itertuples():
        i, c, a = r.index, r.city_cod, r.area_cod
        L.derive(f"stock_ha|{i}", "broadcast", [f"soil|{c}|{a}|2021"], Meta(STOCK, "t C/ha", "instant:2021", "farm_area"),
                 expect=[(STOCK, "t C/ha", "instant:2021", "municipality_class")])
        L.derive(f"stock_area|{i}", "mul", [f"stock_ha|{i}", f"area|{i}"], Meta(STOCK, "t C", "instant:2021", "farm_area"),
                 expect=[None, (AREA, "ha", "instant:2021", "farm_area")])
        L.derive(f"emi_ha|{i}", "broadcast", [f"emi|{c}|{a}"], Meta(FLUX, "t CO2e/ha/yr", "annual:2021", "farm_area"),
                 expect=[(FLUX, "t CO2e/ha/yr", "annual:2021", "municipality_class")])
        L.derive(f"emi_area|{i}", "mul", [f"emi_ha|{i}", f"area|{i}"], Meta(FLUX, "t CO2e/yr", "annual:2021", "farm_area"))
        # the historical CarboFarm balance: stock minus annual emission
        L.derive(f"bal_ha|{i}", "diff", [f"stock_ha|{i}", f"emi_ha|{i}"], Meta(FLUX, "t CO2e/ha/yr", "annual:2021", "farm_area"))
        L.derive(f"bal_area|{i}", "mul", [f"bal_ha|{i}", f"area|{i}"], Meta(FLUX, "t CO2e/yr", "annual:2021", "farm_area"))
        by_ctx.setdefault((c, a), []).append(i)
    by_mun = {}
    for (c, a), ids in by_ctx.items():
        L.derive(f"stock_total|{c}|{a}", "sum", [f"stock_area|{i}" for i in ids],
                 Meta(STOCK, "t C", "instant:2021", "municipality_class"))
        L.derive(f"emi_total|{c}|{a}", "sum", [f"emi_area|{i}" for i in ids],
                 Meta(FLUX, "t CO2e/yr", "annual:2021", "municipality_class"))
        by_mun.setdefault(c, []).append(a)
    for c, cls in by_mun.items():
        L.derive(f"stock_total|{c}", "sum", [f"stock_total|{c}|{a}" for a in cls], Meta(STOCK, "t C", "instant:2021", "municipality"))
        L.derive(f"emi_total|{c}", "sum", [f"emi_total|{c}|{a}" for a in cls], Meta(FLUX, "t CO2e/yr", "annual:2021", "municipality"))
    return L


LOADERS = {"mapbiomas_soil_context": soil_version}
