"""E6: what current practice reports, on the same revisions and defects.

Two tools that a data team would use today, run on the same sources:

  Lineage service    the pipelines' lineage written as OpenLineage run events with the column-lineage facet
                     (one dataset per value family, one field per value column), and impact computed by
                     traversal of that graph, as a lineage service such as Marquez does.
  Data validation    Great Expectations suites profiled from the previous version of each source, the usual
                     way such suites are bootstrapped: values not null and inside the reference range of their
                     family, unit, quantity kind, period and support inside the reference sets, keys unique and
                     containing every reference key.

Reported
  revisions   (E1) values the lineage service flags; whether validation raises an alarm on a legitimate revision
  defects     (E3) the same 840 invalid changes and 120 controls, detected by validation
  release     (E4) the CarboFarm release table against a suite written from its documentation
"""
import json
import random
import warnings
from collections import defaultdict, deque

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd
from openlineage.client.event_v2 import InputDataset, Job, OutputDataset, Run, RunEvent, RunState
from openlineage.client.facet_v2 import column_lineage_dataset

import e3_mutations as E3
import p1_carbofarm as P1
import p2_national as P2

warnings.filterwarnings("ignore")
NS = "carbon-inventory"


# ------------------------------------------------------------------ lineage service (OpenLineage column lineage)
def fam(key):
    return key.split("|")[0]


def openlineage_events(L):
    """One run event per derived value family, with the column-lineage facet of its value field."""
    inputs_of = defaultdict(set)
    for k, dv in L.der.items():
        for i in dv.inputs:
            src = L.d[i].source if i in L.d and L.d[i].kind == "source" else None
            inputs_of[fam(k)].add(src or fam(i))
    events = []
    for out, ins in sorted(inputs_of.items()):
        facet = column_lineage_dataset.ColumnLineageDatasetFacet(fields={
            "value": column_lineage_dataset.Fields(inputFields=[
                column_lineage_dataset.InputField(namespace=NS, name=i, field="value") for i in sorted(ins)],
                transformationType="", transformationDescription="")})
        events.append(RunEvent(eventType=RunState.COMPLETE, eventTime="2026-10-22T00:00:00Z",
                               run=Run(runId="00000000-0000-0000-0000-000000000000"),
                               job=Job(namespace=NS, name=f"derive_{out}"), producer="e6_practice",
                               inputs=[InputDataset(namespace=NS, name=i) for i in sorted(ins)],
                               outputs=[OutputDataset(namespace=NS, name=out, facets={"columnLineage": facet})]))
    return events


def lineage_impact(events, source):
    """datasets downstream of a source in the column-lineage graph"""
    down = defaultdict(set)
    for e in events:
        for o in e.outputs:
            for f in o.facets["columnLineage"].fields["value"].inputFields:
                down[f.name].add(o.name)
    seen, q = set(), deque([source])
    while q:
        for o in down[q.popleft()]:
            if o not in seen:
                seen.add(o)
                q.append(o)
    return seen


def lineage_flagged(L, events, source):
    fams = lineage_impact(events, source)
    return sum(1 for k in L.order if fam(k) in fams)


# ------------------------------------------------------------------ data validation (Great Expectations)
CTX = gx.get_context(mode="ephemeral")
DS = CTX.data_sources.add_pandas("sources")
ASSET = DS.add_dataframe_asset("source_table")
BATCH = ASSET.add_batch_definition_whole_dataframe("whole")


def table(src: dict):
    return pd.DataFrame([dict(key=k, family=fam(k), value=v, unit=m.unit, qkind=m.qkind, period=m.period,
                              support=m.support) for k, (v, m) in src.items()])


def profile(ref: pd.DataFrame, name):
    s = gx.ExpectationSuite(name=name)
    s.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="value"))
    for f, g in ref.groupby("family"):
        s.add_expectation(gxe.ExpectColumnValuesToBeBetween(
            column="value", min_value=float(g.value.min()), max_value=float(g.value.max()),
            row_condition=f'family=="{f}"', condition_parser="pandas"))
    for c in ["unit", "qkind", "period", "support"]:
        s.add_expectation(gxe.ExpectColumnValuesToBeInSet(column=c, value_set=sorted(ref[c].unique())))
    s.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="key"))
    s.add_expectation(gxe.ExpectColumnDistinctValuesToContainSet(column="key", value_set=sorted(ref.key)))
    return s


def validate(df, suite):
    r = BATCH.get_batch(batch_parameters={"dataframe": df}).validate(suite)
    return [x.expectation_config.type for x in r.results if not x.success]


def source_values(L, name):
    return {k: (x.value, x.meta) for k, x in L.d.items() if x.kind == "source" and x.source == name and x.value is not None}


# ------------------------------------------------------------------ E1 revisions
def revisions():
    out = []
    L = P1.build("V0")
    ev = openlineage_events(L)
    for name, tag in [("Soil beta 2.1 -> collection 3 (P1)", "V1"), ("Land cover 7.1 -> 10 (P1)", "V2")]:
        old = source_values(L, "mapbiomas_soil_context")
        new = P1.soil_version(tag)
        fails = validate(table(new), profile(table(old), "ref"))
        out.append(dict(revision=name, lineage_flagged=lineage_flagged(L, ev, "mapbiomas_soil_context"),
                        lineage_orphans_reported=0, validation_alarm=bool(fails), failed=sorted(set(fails))))
        L.apply_update("mapbiomas_soil_context", tag, new)
    L = P2.build()
    ev = openlineage_events(L)
    cfgs = [("PRIMAP-hist v2.6 -> v2.7 (P2)", "primap_hist", lambda: P2.primap("v2.7"), "v2.7"),
            ("GWP AR5 -> AR6 (P2)", "gwp", lambda: P2.gwp("AR6"), "AR6"),
            ("IPCC factors 2006 -> 2019, 2006 regions (P2)", "ipcc_factors", lambda: P2.factors("2019", None), "2019")]
    for name, src, load, tag in cfgs:
        old, new = source_values(L, src), load()
        fails = validate(table(new), profile(table(old), "ref"))
        out.append(dict(revision=name, lineage_flagged=lineage_flagged(L, ev, src), lineage_orphans_reported=0,
                        validation_alarm=bool(fails), failed=sorted(set(fails))))
        L.apply_update(src, tag, new)
    return out, ev


# ------------------------------------------------------------------ E3 defects
def defects():
    rows = []
    for L, srcs in [(P1.build("V0"), ["mapbiomas_soil_context"]),
                    (P2.build(), ["ipcc_factors", "primap_hist", "faostat_livestock"])]:
        for source in srcs:
            rng = random.Random(7)
            pool = sorted(k for k, x in L.d.items() if x.kind == "source" and x.source == source and L.down.get(k) and x.value)
            keys = rng.sample(pool, min(30, len(pool)))
            ref = source_values(L, source)
            suite = profile(table(ref), source)
            for f in E3.FAMILIES:
                if f == "equivalent_unit":
                    continue
                for k in keys:
                    new = dict(ref)
                    if f == "removed":
                        del new[k]
                    else:
                        new[k] = E3.mutate(f, k, *ref[k])
                    fails = validate(table(new), suite)
                    rows.append(dict(source=source, family=f, key=k, invalid=f in E3.INVALID, flagged=bool(fails),
                                     failed=sorted(set(fails))))
    summ = {}
    for f in E3.FAMILIES[:-1]:
        r = [x for x in rows if x["family"] == f]
        summ[f] = f"{sum(x['flagged'] for x in r)}/{len(r)}"
    inv, ctl = [x for x in rows if x["invalid"]], [x for x in rows if not x["invalid"]]
    summ["invalid_total"] = f"{sum(x['flagged'] for x in inv)}/{len(inv)}"
    summ["controls_flagged"] = f"{sum(x['flagged'] for x in ctl)}/{len(ctl)}"
    # union with the ledger (E3 layers), joined on source, family and key
    led = {}
    for L, srcs in [(P1.build("V0"), ["mapbiomas_soil_context"]),
                    (P2.build(), ["ipcc_factors", "primap_hist", "faostat_livestock"])]:
        for source in srcs:
            for r in E3.run(L, source, 30):
                led[(source, r["family"], r["key"])] = r["any"]
    both = {}
    for f in E3.FAMILIES[:-1]:
        r = [x for x in rows if x["family"] == f]
        both[f] = f"{sum(x['flagged'] or led[(x['source'], f, x['key'])] for x in r)}/{len(r)}"
    inv = [x for x in rows if x["invalid"]]
    both["invalid_total"] = f"{sum(x['flagged'] or led[(x['source'], x['family'], x['key'])] for x in inv)}/{len(inv)}"
    ctl = [x for x in rows if not x["invalid"]]
    both["controls_flagged"] = f"{sum(x['flagged'] or led[(x['source'], x['family'], x['key'])] for x in ctl)}/{len(ctl)}"
    summ["union_with_ledger"] = both
    return summ


# ------------------------------------------------------------------ E4 release
def release():
    cf = P1.farm_records()
    s = gx.ExpectationSuite(name="carbofarm_release")
    for c in ["CO2_stock_ha", "CO2_emission_ha", "balance_CO2_ha", "area_size", "city_cod", "area_cod"]:
        s.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=c))
    s.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="CO2_stock_ha", min_value=0, max_value=1000))
    s.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="CO2_emission_ha", min_value=-100, max_value=100))
    s.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="area_size", min_value=0, strict_min=True))
    s.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="index"))
    s.add_expectation(gxe.ExpectColumnValuesToBeInSet(column="year", value_set=[2021]))
    fails = validate(cf, s)
    return dict(expectations=len(s.expectations), failed=sorted(set(fails)),
                problems_flagged="0/5" if not fails else f"see failed ({len(set(fails))} expectation types)")


if __name__ == "__main__":
    rev, ev = revisions()
    out = dict(revisions=rev, defects=defects(), release=release(),
               openlineage_events=len(ev))
    json.dump(out, open("../results/e6_practice.json", "w"), indent=1)
    json.dump([json.loads(json.dumps(e, default=lambda o: o.__dict__)) for e in ev[:3]],
              open("../results/e6_openlineage_sample_events.json", "w"), indent=1, default=str)
    print(json.dumps(out, indent=1))
