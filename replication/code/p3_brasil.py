"""P3: soil carbon stocks of every Brazilian municipality, 2017-2021, on the ledger.

Sources (one version per MapBiomas soil x land-cover pair, extracted with gee/brasil_solo_versoes.js)
  mapbiomas_soil        mean 0-30 cm soil organic carbon stock (t C/ha) per municipality x land-cover class x year
  mapbiomas_lulc_area   area (ha) of each municipality x class x year with a valid soil value
Derived
  stock|m|c|y      = soil x area                          (t C, municipality x class)
  stock_mun|m|y    = sum of stock|m|c|y over the classes the version maps in m and y
  stock_uf|u|y, stock_br|y = sums upward
  dstock_*|y       = stock at y minus stock at y-1, for municipalities, states and Brazil

The plan declares a stock value for every municipality x class x year context that any of the three versions
maps. Which contexts a municipal total sums is part of the plan and changes with the land-cover collection;
that change is applied as a rewiring (Section 3.3), as for the regional mapping of P2.
"""
from collections import defaultdict
from pathlib import Path

import pandas as pd

from engine import AREA, STOCK, Ledger, Meta

D = Path(__file__).resolve().parent.parent / "data" / "mapbiomas_brasil"
FILES = {"V0": "brasil_solo_A_beta21_cob71.csv", "V1": "brasil_solo_B_col3_cob71.csv", "V2": "brasil_solo_C_col3_cob10.csv"}
YEARS = [2017, 2018, 2019, 2020, 2021]

# geoBoundaries spells two states differently; 32 coastal municipalities have their centroid at sea
UF_FIX = {"Rio Granda do Norte": "Rio Grande do Norte", "Rio de Jeneiro": "Rio de Janeiro"}
SEM_UF = {"Apicum-Açu": "Maranhao", "Cajapió": "Maranhao", "Paço do Lumiar": "Maranhao", "Raposa": "Maranhao",
          "Cajueiro da Praia": "Piaui", "Ilha Grande": "Piaui", "Barroquinha": "Ceara", "Cruz": "Ceara",
          "Paracuru": "Ceara", "Senador Georgino Avelino": "Rio Grande do Norte", "Santa Rosa de Lima": "Sergipe",
          "Aracruz": "Espirito Santo", "João Neiva": "Espirito Santo", "Vitória": "Espirito Santo",
          "Angra dos Reis": "Rio de Janeiro", "Armação dos Búzios": "Rio de Janeiro", "Mangaratiba": "Rio de Janeiro",
          "Paraty": "Rio de Janeiro", "Belém": "Para", "Quatipuru": "Para", "Salinópolis": "Para",
          "Balneário Camboriú": "Santa Catarina", "Barra Velha": "Santa Catarina", "Bombinhas": "Santa Catarina",
          "Garopaba": "Santa Catarina", "Itapoá": "Santa Catarina", "Laguna": "Santa Catarina",
          "Navegantes": "Santa Catarina", "Penha": "Santa Catarina", "Balneário Piçarras": "Santa Catarina",
          "Balneário Rincão": "Santa Catarina", "São José do Norte": "Rio Grande do Sul"}

_cache = {}


def table(tag):
    if tag not in _cache:
        d = pd.read_csv(D / FILES[tag])
        d["uf"] = d.uf.replace(UF_FIX)
        m = d.uf == "sem_uf"
        d.loc[m, "uf"] = d.loc[m, "municipio"].map(SEM_UF)
        assert d.uf.notna().all()
        d = d[d.ano.isin(YEARS) & d.media_t_C_ha.notna() & (d.area_ha > 0)]
        _cache[tag] = d
    return _cache[tag]


def m_soil(y):
    return Meta(STOCK, "t C/ha", f"instant:{y}", "municipality_class")


def m_area(y):
    return Meta(AREA, "ha", f"instant:{y}", "municipality_class")


def soil(tag):
    return {f"soil|{r.id}|{r.classe}|{r.ano}": (float(r.media_t_C_ha), m_soil(r.ano)) for r in table(tag).itertuples()}


def area(tag):
    return {f"area|{r.id}|{r.classe}|{r.ano}": (float(r.area_ha), m_area(r.ano)) for r in table(tag).itertuples()}


def contexts(tag):
    return set(zip(table(tag).id, table(tag).classe, table(tag).ano))


def municipalities():
    t = pd.concat([table(v)[["id", "uf"]] for v in FILES]).drop_duplicates("id")
    return dict(zip(t.id, t.uf))


def mun_inputs(tag):
    """the plan part that depends on the land-cover collection: which contexts each municipal total sums"""
    out = defaultdict(list)
    for m, c, y in sorted(contexts(tag)):
        out[f"stock_mun|{m}|{y}"].append(f"stock|{m}|{c}|{y}")
    return out


def build(tag="V0", plan_versions=("V0", "V1", "V2")):
    L = Ledger()
    L.register_source("mapbiomas_soil", tag, note=FILES[tag])
    for k, (v, m) in soil(tag).items():
        L.put(k, v, m, "mapbiomas_soil", tag)
    L.register_source("mapbiomas_lulc_area", tag, note=FILES[tag])
    for k, (v, m) in area(tag).items():
        L.put(k, v, m, "mapbiomas_lulc_area", tag)
    plan = sorted(set().union(*(contexts(v) for v in plan_versions)))
    for m, c, y in plan:
        L.derive(f"stock|{m}|{c}|{y}", "mul", [f"soil|{m}|{c}|{y}", f"area|{m}|{c}|{y}"],
                 Meta(STOCK, "t C", f"instant:{y}", "municipality_class"),
                 expect=[(STOCK, "t C/ha", f"instant:{y}", "municipality_class"), (AREA, "ha", f"instant:{y}", "municipality_class")])
    inputs = mun_inputs(tag)
    muns = municipalities()
    by_uf = defaultdict(list)
    for m, uf in sorted(muns.items()):
        for y in YEARS:
            L.derive(f"stock_mun|{m}|{y}", "sum", inputs.get(f"stock_mun|{m}|{y}", []),
                     Meta(STOCK, "t C", f"instant:{y}", "municipality"))
        by_uf[uf].append(m)
    for uf, ms in sorted(by_uf.items()):
        for y in YEARS:
            L.derive(f"stock_uf|{uf}|{y}", "sum", [f"stock_mun|{m}|{y}" for m in ms], Meta(STOCK, "t C", f"instant:{y}", "state"))
    for y in YEARS:
        L.derive(f"stock_br|{y}", "sum", [f"stock_uf|{uf}|{y}" for uf in sorted(by_uf)], Meta(STOCK, "t C", f"instant:{y}", "country"))
    for y in YEARS[1:]:
        for m in sorted(muns):
            L.derive(f"dstock_mun|{m}|{y}", "diff", [f"stock_mun|{m}|{y}", f"stock_mun|{m}|{y - 1}"],
                     Meta(STOCK, "t C", f"change:{y - 1}-{y}", "municipality"))
        for uf in sorted(by_uf):
            L.derive(f"dstock_uf|{uf}|{y}", "diff", [f"stock_uf|{uf}|{y}", f"stock_uf|{uf}|{y - 1}"],
                     Meta(STOCK, "t C", f"change:{y - 1}-{y}", "state"))
        L.derive(f"dstock_br|{y}", "diff", [f"stock_br|{y}", f"stock_br|{y - 1}"], Meta(STOCK, "t C", f"change:{y - 1}-{y}", "country"))
    return L


def rewire_to(L, tag):
    """point every municipal total at the contexts the new land-cover collection maps"""
    new = mun_inputs(tag)
    ch = {}
    for k in L.order:
        if k.startswith("stock_mun|"):
            want = new.get(k, [])
            if L.der[k].inputs != want:
                ch[k] = want
    return L.rewire(ch)


LOADERS = {"mapbiomas_soil": soil, "mapbiomas_lulc_area": area}
