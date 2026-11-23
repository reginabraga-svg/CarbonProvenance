"""P2: national Tier 1 livestock estimates for inventory support, linked to PRIMAP-hist.

Sources (all public, versioned)
  faostat_livestock   FAOSTAT Livestock Manure: stocks (head) and N left on pasture (kg N), 2015-2022
  ipcc_factors        Tier 1 factors: enteric CH4 (Tables 10.10, 10.11) and EF3PRP (Table 11.1), 2006 or 2019 Refinement
  gwp                 100-year global warming potentials, AR5 or AR6
  primap_hist         PRIMAP-hist HISTCR, CH4 and KYOTOGHG (AR5GWP100) for M.0.EL, M.AG and 3.A, v2.6 or v2.7
  region mapping      country -> IPCC regional characteristics (2006 or 2019 scheme), a declared parameter

Derived per country and year: enteric CH4 by animal and total, N2O from pasture by animal and total,
CO2e of both, the ratio of Tier 1 enteric CH4 to PRIMAP 3.A CH4, the agriculture share of national emissions
and the livestock share of agriculture.
"""
from pathlib import Path

import country_converter as coco
import pandas as pd

from engine import COUNT, FACTOR, FLUX, NFLOW, SHARE, Ledger, Meta

HERE = Path(__file__).resolve().parent
D = HERE.parent / "data"
EMN = D / "faostat/Environment_LivestockManure_E_All_Data_(Normalized).csv"
PRIMAP = {"v2.6": D / "primap/Guetschow_et_al_2024a-PRIMAP-hist_v2_6_final_13-Sep-2024.csv",
          "v2.7": D / "primap/Guetschow_et_al_2025a-PRIMAP-hist_v2_7_final_22-Aug-2025.csv"}
YEARS = list(range(2015, 2023))
CACHE = D / "faostat/emn_cache.csv"

ANIMALS = {"Cattle, dairy": "dairy", "Cattle, non-dairy": "other_cattle", "Buffalo": "buffalo", "Sheep": "sheep",
           "Goats": "goats", "Swine": "swine", "Horses": "horses", "Asses": "asses", "Mules and hinnies": "mules",
           "Camels": "camels", "Chickens": "chickens"}
ENTERIC = ["dairy", "other_cattle", "buffalo", "sheep", "goats", "swine", "horses", "asses", "mules", "camels"]
CPP = {"dairy", "other_cattle", "buffalo", "swine", "chickens"}       # EF3PRP,CPP; the rest use EF3PRP,SO

# ---------------------------------------------------------------- factors, transcribed from the guidelines
# 2006 IPCC Guidelines Vol. 4 Table 10.11 (cattle) and Table 10.10 (developed / developing)
CATTLE_2006 = {"North America": (128, 53), "Western Europe": (117, 57), "Eastern Europe": (99, 58),
               "Oceania": (100, 60), "Latin America": (72, 56), "Asia": (68, 47),
               "Africa and Middle East": (46, 31), "Indian Subcontinent": (58, 27)}
OTHER_2006 = {"buffalo": (55, 55), "sheep": (8, 5), "goats": (5, 5), "camels": (46, 46), "horses": (18, 18),
              "asses": (10, 10), "mules": (10, 10), "swine": (1.5, 1.0)}
DEVELOPED_2006 = {"North America", "Western Europe", "Eastern Europe", "Oceania"}
# 2019 Refinement Vol. 4 Table 10.11 (updated; Tier 1 rows) and Table 10.10 (updated; high / low productivity)
CATTLE_2019 = {"North America": (138, 64), "Western Europe": (126, 52), "Eastern Europe": (93, 58),
               "Oceania": (93, 63), "Latin America": (87, 56), "Asia": (78, 54), "Africa": (76, 52),
               "Middle East": (76, 60), "Indian Subcontinent": (73, 46)}
BUFFALO_2019 = {"Western Europe": 78, "Eastern Europe": 68, "Latin America": 68, "Asia": 68, "Africa": 81,
                "Middle East": 67, "Indian Subcontinent": 85}      # none given for North America and Oceania
OTHER_2019 = {"sheep": (9, 5), "goats": (9, 5), "swine": (1.5, 1.0), "camels": (46, 46), "horses": (18, 18),
              "asses": (10, 10), "mules": (10, 10)}
HIGH_PROD_2019 = {"North America", "Western Europe", "Eastern Europe", "Oceania"}   # Table 10.10 footnote 1
EF3 = {"2006": {"CPP": 0.02, "SO": 0.01}, "2019": {"CPP": 0.004, "SO": 0.003}}       # Table 11.1, aggregated
GWP = {"AR5": {"CH4": 28.0, "N2O": 265.0}, "AR6": {"CH4": 27.0, "N2O": 273.0}}       # AR6: non-fossil CH4

# ---------------------------------------------------------------- region mapping (declared parameter)
SUB2REG = {"Northern America": "North America", "Western Europe": "Western Europe", "Northern Europe": "Western Europe",
           "Southern Europe": "Western Europe", "Eastern Europe": "Eastern Europe",
           "Australia and New Zealand": "Oceania", "Melanesia": "Asia", "Micronesia": "Asia", "Polynesia": "Asia",
           "Caribbean": "Latin America", "Central America": "Latin America", "South America": "Latin America",
           "Eastern Asia": "Asia", "South-eastern Asia": "Asia", "Central Asia": "Asia",
           "Southern Asia": "Indian Subcontinent", "Western Asia": "Middle East",
           "Northern Africa": "Africa", "Eastern Africa": "Africa", "Middle Africa": "Africa",
           "Southern Africa": "Africa", "Western Africa": "Africa"}


def region(iso3, sub, scheme):
    r = SUB2REG.get(sub)
    if r is None:
        return None
    if iso3 in ("IRN", "AFG"):
        r = "Middle East"
    if scheme == "2006" and r in ("Africa", "Middle East"):
        r = "Africa and Middle East"
    return r


# ---------------------------------------------------------------- loaders
def emn():
    cache = CACHE if YEARS == list(range(2015, 2023)) else CACHE.with_name(f"emn_cache_{YEARS[0]}_{YEARS[-1]}.csv")
    if cache.exists():
        return pd.read_csv(cache)
    e = pd.read_csv(EMN, encoding="latin1", usecols=["Area Code", "Area Code (M49)", "Area", "Item", "Element", "Year", "Value"])
    e = e[(e["Area Code"] < 5000) & e.Year.isin(YEARS) & e.Item.isin(ANIMALS) &
          e.Element.isin(["Stocks", "Manure left on pasture (N content)"])]
    m49 = e["Area Code (M49)"].astype(str).str.lstrip("'").str.lstrip("0")
    codes = sorted(m49.unique())
    iso = dict(zip(codes, coco.convert(codes, src="UNcode", to="ISO3", not_found=None)))
    sub = dict(zip(codes, coco.convert(codes, src="UNcode", to="UNregion", not_found=None)))
    e["iso3"], e["sub"] = m49.map(iso), m49.map(sub)
    e = e[e.iso3.notna() & (e.iso3 != "None") & e.Value.notna()]
    e.to_csv(cache, index=False)
    return e


def factors(version, scheme_regions):
    """ipcc_factors source datums. Keys are scheme-independent where the guideline is."""
    out = {}
    mf = lambda u: Meta(FACTOR, u, "none", "region")
    if version == "2006":
        for r, (d, o) in CATTLE_2006.items():
            out[f"ef|enteric|dairy|{r}"] = (d, mf("kg CH4/head/yr"))
            out[f"ef|enteric|other_cattle|{r}"] = (o, mf("kg CH4/head/yr"))
        for a, (dev, dvg) in OTHER_2006.items():
            out[f"ef|enteric|{a}|high"] = (dev, mf("kg CH4/head/yr"))
            out[f"ef|enteric|{a}|low"] = (dvg, mf("kg CH4/head/yr"))
    else:
        for r, (d, o) in CATTLE_2019.items():
            out[f"ef|enteric|dairy|{r}"] = (d, mf("kg CH4/head/yr"))
            out[f"ef|enteric|other_cattle|{r}"] = (o, mf("kg CH4/head/yr"))
        for r, b in BUFFALO_2019.items():
            out[f"ef|enteric|buffalo|{r}"] = (b, mf("kg CH4/head/yr"))
        for a, (hi, lo) in OTHER_2019.items():
            out[f"ef|enteric|{a}|high"] = (hi, mf("kg CH4/head/yr"))
            out[f"ef|enteric|{a}|low"] = (lo, mf("kg CH4/head/yr"))
    for g, v in EF3[version].items():
        out[f"ef|prp|{g}"] = (v, mf("kg N2O-N/kg N"))
    return out


def gwp(version):
    return {f"gwp|{g}": (v, Meta(FACTOR, "t CO2e/t", "none", "global")) for g, v in GWP[version].items()}


def primap(version):
    d = pd.read_csv(PRIMAP[version], usecols=lambda c: not c.isdigit() or int(c) in YEARS)
    d = d[(d["scenario (PRIMAP-hist)"] == "HISTCR") &
          d["category (IPCC2006_PRIMAP)"].isin(["M.0.EL", "M.AG", "3.A"]) &
          d.entity.isin(["CH4", "KYOTOGHG (AR5GWP100)"])]
    out = {}
    for r in d.itertuples(index=False):
        area, ent, unit, cat = r[3], r[4], r[5], r[6]
        # unit written "CH4 * gigagram / a" in v2.6 and "/ yr" in v2.7: declared as given
        for y, v in zip(YEARS, r[7:7 + len(YEARS)]):
            if pd.notna(v):
                e = "KYOTO_AR5" if ent.startswith("KYOTO") else ent
                u = unit if e == "CH4" else unit + " (AR5GWP100)"
                out[f"primap|{area}|{e}|{cat}|{y}"] = (float(v), Meta(FLUX, u, f"annual:{y}", "country"))
    return out


def canonical_unit(u):
    return u.replace("/ a", "/ yr")


# ---------------------------------------------------------------- pipeline
CONFIG = {"factors": "2006", "scheme": "2006", "gwp": "AR5", "primap": "v2.6"}


def ef_key(a, reg, scheme):
    if a in ("dairy", "other_cattle"):
        return f"ef|enteric|{a}|{reg}"
    if a == "buffalo" and scheme == "2019":
        return f"ef|enteric|buffalo|{reg}"
    hi = reg in (DEVELOPED_2006 if scheme == "2006" else HIGH_PROD_2019)
    return f"ef|enteric|{a}|{'high' if hi else 'low'}"


def build(cfg=None, canon_units=False):
    cfg = dict(CONFIG, **(cfg or {}))
    e = emn()
    L = Ledger()
    L.register_source("faostat_livestock", "FAOSTAT EMN 2025-09")
    countries = e.groupby("iso3")["sub"].first().to_dict()
    for r in e.itertuples():
        a = ANIMALS[r.Item]
        if r.Element == "Stocks":
            L.put(f"heads|{r.iso3}|{a}|{r.Year}", float(r.Value), Meta(COUNT, "head", f"instant:{r.Year}", "country"),
                  "faostat_livestock", "FAOSTAT EMN 2025-09")
        else:
            L.put(f"npast|{r.iso3}|{a}|{r.Year}", float(r.Value), Meta(NFLOW, "kg N/yr", f"annual:{r.Year}", "country"),
                  "faostat_livestock", "FAOSTAT EMN 2025-09")
    L.register_source("ipcc_factors", cfg["factors"])
    for k, (v, m) in factors(cfg["factors"], None).items():
        L.put(k, v, m, "ipcc_factors", cfg["factors"])
    L.register_source("gwp", cfg["gwp"])
    for k, (v, m) in gwp(cfg["gwp"]).items():
        L.put(k, v, m, "gwp", cfg["gwp"])
    L.register_source("primap_hist", cfg["primap"])
    for k, (v, m) in primap(cfg["primap"]).items():
        if canon_units:
            m = Meta(m.qkind, canonical_unit(m.unit), m.period, m.support)
        L.put(k, v, m, "primap_hist", cfg["primap"])

    have = set(L.d)
    ch4u = "CH4 * gigagram / a" if not canon_units else "CH4 * gigagram / yr"
    for iso, sub in sorted(countries.items()):
        reg = region(iso, sub, cfg["scheme"])
        if reg is None:
            continue
        for y in YEARS:
            ch4_parts, n2o_parts = [], []
            for a in ANIMALS.values():
                hk = f"heads|{iso}|{a}|{y}"
                if a in ENTERIC and hk in have:
                    k = f"enteric_ch4|{iso}|{a}|{y}"
                    L.derive(k, "mul", [hk, ef_key(a, reg, cfg["scheme"])],
                             Meta(FLUX, ch4u, f"annual:{y}", "country"), k=1e-6,
                             expect=[(COUNT, "head", f"instant:{y}", "country"), (FACTOR, "kg CH4/head/yr", None, "region")])
                    ch4_parts.append(k)
                nk = f"npast|{iso}|{a}|{y}"
                if nk in have:
                    k = f"prp_n2o|{iso}|{a}|{y}"
                    L.derive(k, "mul", [nk, f"ef|prp|{'CPP' if a in CPP else 'SO'}"],
                             Meta(FLUX, "N2O * gigagram / yr", f"annual:{y}", "country"), k=1e-6 * 44 / 28,
                             expect=[(NFLOW, "kg N/yr", f"annual:{y}", "country"), (FACTOR, "kg N2O-N/kg N", None, "region")])
                    n2o_parts.append(k)
            if ch4_parts:
                L.derive(f"enteric_ch4|{iso}|total|{y}", "sum", ch4_parts, Meta(FLUX, ch4u, f"annual:{y}", "country"))
                L.derive(f"enteric_co2e|{iso}|{y}", "mul", [f"enteric_ch4|{iso}|total|{y}", "gwp|CH4"],
                         Meta(FLUX, "CO2e * gigagram / yr", f"annual:{y}", "country"),
                         expect=[None, (FACTOR, "t CO2e/t", None, "global")])
                pk = f"primap|{iso}|CH4|3.A|{y}"
                L.derive(f"tier1_vs_primap_ch4|{iso}|{y}", "ratio", [f"enteric_ch4|{iso}|total|{y}", pk],
                         Meta(SHARE, "1", f"annual:{y}", "country"),
                         expect=[None, (FLUX, "CH4 * gigagram / yr", f"annual:{y}", "country")])
            if n2o_parts:
                L.derive(f"prp_n2o|{iso}|total|{y}", "sum", n2o_parts, Meta(FLUX, "N2O * gigagram / yr", f"annual:{y}", "country"))
                L.derive(f"prp_co2e|{iso}|{y}", "mul", [f"prp_n2o|{iso}|total|{y}", "gwp|N2O"],
                         Meta(FLUX, "CO2e * gigagram / yr", f"annual:{y}", "country"),
                         expect=[None, (FACTOR, "t CO2e/t", None, "global")])
            if ch4_parts and n2o_parts:
                L.derive(f"livestock_t1_co2e|{iso}|{y}", "sum", [f"enteric_co2e|{iso}|{y}", f"prp_co2e|{iso}|{y}"],
                         Meta(FLUX, "CO2e * gigagram / yr", f"annual:{y}", "country"))
            ag, tot, la = (f"primap|{iso}|KYOTO_AR5|{c}|{y}" for c in ("M.AG", "M.0.EL", "3.A"))
            # declared plan: these indicators are wanted for every country, whether or not PRIMAP covers it today
            if True:
                L.derive(f"ag_share|{iso}|{y}", "ratio", [ag, tot], Meta(SHARE, "1", f"annual:{y}", "country"),
                         expect=[(FLUX, "CO2 * gigagram / yr (AR5GWP100)", f"annual:{y}", "country")] * 2)
                L.derive(f"livestock_share_ag|{iso}|{y}", "ratio", [la, ag], Meta(SHARE, "1", f"annual:{y}", "country"),
                         expect=[(FLUX, "CO2 * gigagram / yr (AR5GWP100)", f"annual:{y}", "country")] * 2)
    L.countries = countries
    return L


def rewire_for_scheme(L, scheme):
    """the structural change a maintainer makes when the regional scheme changes: enteric derivations of
    the affected countries read the factor of their new region."""
    changes = {}
    for iso, sub in L.countries.items():
        reg = region(iso, sub, scheme)
        if reg is None:
            continue
        for y in YEARS:
            for a in ENTERIC:
                k = f"enteric_ch4|{iso}|{a}|{y}"
                if k in L.der:
                    new = [f"heads|{iso}|{a}|{y}", ef_key(a, reg, scheme)]
                    if new != L.der[k].inputs:
                        changes[k] = new
    return L.rewire(changes)
