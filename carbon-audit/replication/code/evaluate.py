"""E1 and E2: replay real source evolutions on a pipeline and score the impact analysis.

For each version step the ledger built on the old version is updated incrementally, and a second ledger
is built from scratch on the new version (ground truth). Reported per step:
  truly_changed  derived values whose value or status differs between the old state and the ground truth
  flagged        values the impact analysis marks (stale + orphan + resolvable)
  recall/precision of flagged against truly_changed; equality of the incremental result and the ground truth
  table-level baseline: every derived value that depends on the updated source table
  no-lineage baseline: nothing flagged; truly_changed values stay silently out of date
  cost: evaluations and seconds, incremental against full rebuild
"""
import json
import time

from engine import same


def _st(s):
    # a rebuild from scratch cannot know that a value once had an origin: orphan and unresolved compare equal
    return "unresolved" if s == "orphan" else s


def score_step(name, source, old_L, new_tag, loader, builder):
    before = old_L.snapshot()
    deps = {k for k in old_L.order if source in old_L.sources_of(k)} if len(old_L.order) < 400000 else None
    new = loader(new_tag)
    res = old_L.apply_update(source, new_tag, new)
    t0 = time.perf_counter()
    gt = builder(new_tag)
    t_full = time.perf_counter() - t0
    truth = gt.snapshot()
    keys = set(truth) | set(before)
    truly = {k for k in keys if k in truth and k in before and
             (not same(before[k][0], truth[k][0]) or _st(before[k][1]) != _st(truth[k][1]))}
    imp = res["_impact"]
    flagged = imp["stale"] | imp["orphan"] | imp["resolvable"]
    after = old_L.snapshot()
    mismatch = [k for k in truth if k not in after or not same(after[k][0], truth[k][0]) or _st(after[k][1]) != _st(truth[k][1])]
    st_counts = {}
    for k in truth:
        st_counts[truth[k][1]] = st_counts.get(truth[k][1], 0) + 1
    out = dict(
        step=name, source=source, new_version=new_tag, derived_values=len(truth),
        source_diff=res["diff"], impact=res["impact"],
        truly_changed=len(truly), flagged=len(flagged),
        recall=round(len(truly & flagged) / len(truly), 4) if truly else None,
        precision=round(len(truly & flagged) / len(flagged), 4) if flagged else None,
        incremental_equals_full_rebuild=(len(mismatch) == 0), mismatches=mismatch[:5],
        table_level_flagged=(len(deps) if deps is not None else None),
        table_level_precision=(round(len(truly & deps) / len(deps), 4) if deps else None),
        no_lineage_silently_stale=len(truly),
        evaluations_incremental=res["recomputed"], evaluations_full=len(gt.order),
        seconds_impact_analysis=round(res["seconds_analysis"], 4),
        seconds_incremental_recompute=round(res["seconds_recompute"], 4),
        seconds_full_rebuild=round(t_full, 3),
        status_counts_after=st_counts)
    return out, old_L


def run(pipeline, steps, out_json):
    results = []
    L = pipeline.build(steps[0][1])
    for (name, tag, source) in steps[1:]:
        r, L = score_step(name, source, L, tag, pipeline.LOADERS[source], pipeline.build)
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "mismatches"}, ensure_ascii=False))
    json.dump(results, open(out_json, "w"), indent=1, ensure_ascii=False)
    return L, results
