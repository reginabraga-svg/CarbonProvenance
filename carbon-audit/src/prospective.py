"""P3 test without the future context union used by the original experiment."""
import gc
import json
import math
import time
from collections import defaultdict, Counter
from pathlib import Path
from audit import AuditLedger, Meta, ROOT, add_nodes
import p3_brasil as P


def nodes(tag):
    # Only this release is inspected. No municipality list from a future release.
    table = P.table(tag)
    definitions = []
    def node(key, op, inputs, support, year, **params):
        definitions.append(dict(key=key, op=op, inputs=inputs,
                                contract=dict(qkind='stock', unit='t C', period=f'instant:{year}', support=support),
                                params=params))
    ctx = defaultdict(list)
    for m, c, y in sorted(P.contexts(tag)):
        key = f'stock|{m}|{c}|{y}'
        node(key, 'mul', [f'soil|{m}|{c}|{y}', f'area|{m}|{c}|{y}'], 'municipality_class', y,
             expect=[['stock', 't C/ha', f'instant:{y}', 'municipality_class'], ['area', 'ha', f'instant:{y}', 'municipality_class']])
        ctx[m, y].append(key)
    muns = dict(zip(table.id, table.uf))
    by_uf = defaultdict(list)
    for m, uf in sorted(muns.items()):
        by_uf[uf].append(m)
        for y in P.YEARS:
            node(f'stock_mun|{m}|{y}', 'sum', ctx[m, y], 'municipality', y)
    for uf, ms in sorted(by_uf.items()):
        for y in P.YEARS:
            node(f'stock_uf|{uf}|{y}', 'sum', [f'stock_mun|{m}|{y}' for m in ms], 'state', y)
    for y in P.YEARS:
        node(f'stock_br|{y}', 'sum', [f'stock_uf|{uf}|{y}' for uf in sorted(by_uf)], 'country', y)
    return definitions


def build(tag, definitions):
    L = AuditLedger()
    for source, loader in [('mapbiomas_soil', P.soil), ('mapbiomas_lulc_area', P.area)]:
        L.register_source(source, tag)
        for k, (value, meta) in loader(tag).items():
            L.put(k, value, meta, source, tag)
    # Definitions already follow dependency order. Avoid quadratic generic insertion for national data.
    for n in definitions:
        L.derive(n['key'], n['op'], n['inputs'], Meta(**n['contract']), **n['params'])
    return L


def run():
    definitions = nodes('V0')
    L = build('V0', definitions)
    report = dict(origin='executed_this_session', experiment='P3 prospective contexts',
                  scope='stocks by class, municipality, state and country for 2017 to 2021',
                  excludes='annual stock differences and attribution', steps=[])
    for tag in ['V1', 'V2']:
        start = time.perf_counter()
        previous_keys = set(L.der)
        before = L.snapshot()
        for source, loader in [('mapbiomas_soil', P.soil), ('mapbiomas_lulc_area', P.area)]:
            L.apply_update(source, tag, loader(tag))
        definitions = nodes(tag)
        new_nodes = [n for n in definitions if n['key'] not in L.der]
        for n in new_nodes:
            L.derive(n['key'], n['op'], n['inputs'], Meta(**n['contract']), **n['params'])
        changes = {n['key']: n['inputs'] for n in definitions if n['op'] == 'sum' and L.der[n['key']].inputs != n['inputs']}
        L.rewire(changes)
        incremental_seconds = time.perf_counter() - start
        gt = build(tag, definitions)
        mismatch = [k for k in gt.order if L.d[k].status != gt.d[k].status or
                    not math.isclose(L.d[k].value, gt.d[k].value, rel_tol=1e-9, abs_tol=1e-7)]
        # Independent arithmetic: pandas works straight from the extraction, no ledger operations.
        t = P.table(tag).copy()
        t['stock'] = t.media_t_C_ha * t.area_ha
        expected = t.groupby(['id', 'ano'])['stock'].sum()
        deviations = [abs(L.d[f'stock_mun|{m}|{y}'].value - float(v)) for (m, y), v in expected.items()]
        independent_fail = sum(not math.isclose(L.d[f'stock_mun|{m}|{y}'].value, float(v), rel_tol=1e-9, abs_tol=1e-7)
                               for (m, y), v in expected.items())
        report['steps'].append(dict(version=tag, new_context_outputs=len(new_nodes), rewired_sums=len(changes),
                                   active_outputs=len(gt.order), retained_outputs=len(L.order),
                                   rebuild_mismatches=len(mismatch), independent_checks=len(expected),
                                   independent_failures=independent_fail, max_absolute_deviation_tC=max(deviations),
                                   incremental_seconds=round(incremental_seconds, 3)))
        print(json.dumps(report['steps'][-1]), flush=True)
        assert not mismatch and not independent_fail
        del gt, t, before
        gc.collect()
    target = ROOT / 'validation' / 'prospective.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report

if __name__ == '__main__':
    run()
