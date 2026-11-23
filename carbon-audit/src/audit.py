"""Declarative audit interface. The replication engine stays unchanged."""
from __future__ import annotations
import copy
import csv
import hashlib
import io
import json
import math
import sys
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'replication' / 'code'))
from engine import Ledger, Meta, Datum, OPS, _check, canon


class AuditLedger(Ledger):
    """Null blocked outputs and enforce a DAG before rewiring."""
    def _eval(self, key):
        self.n_evals += 1
        dv, out = self.der[key], self.d[key]
        ins = [self.d.get(k) for k in dv.inputs]
        missing = [k for k, d in zip(dv.inputs, ins) if d is None]
        orphan = [d.key for d in ins if d and d.status == 'orphan']
        unresolved = [d.key for d in ins if d and d.status == 'unresolved']
        blocked = [d.key for d in ins if d and d.status == 'blocked']
        for status, keys in [('orphan', orphan), ('unresolved', missing + unresolved), ('blocked', blocked)]:
            if keys:
                out.value, out.status, out.reason = None, status, status + ': ' + ', '.join(keys[:5])
                return
        st, why = _check(dv.op, ins, out.meta, dv.params.get('expect'))
        if dv.op == 'sum' and len({d.meta.period for d in ins}) > 1:
            st, why = 'blocked', 'the sum contains different periods'
        if st == 'blocked':
            out.value, out.status, out.reason = None, st, why
            return
        value = OPS[dv.op]([d.value for d in ins], dv.params)
        if not math.isfinite(value):
            out.value, out.status, out.reason = None, 'unresolved', 'undefined result'
            return
        contextual = any(d.status == 'contextual' for d in ins)
        out.value = value
        out.status = 'contextual' if contextual else st
        out.reason = 'inherits context from an input' if contextual else why

    def derive(self, key, op, inputs, meta, **params):
        if key in self.d or key in self.der:
            raise ValueError('duplicate key: ' + key)
        if op not in OPS:
            raise ValueError('unsupported operation: ' + op)
        return super().derive(key, op, inputs, meta, **params)

    def topological_order(self, changes=None):
        changes = changes or {}
        indeg = {k: 0 for k in self.der}
        down = {k: set() for k in self.der}
        for k, dv in self.der.items():
            for i in set(changes.get(k, dv.inputs)):
                if i in self.der:
                    indeg[k] += 1
                    down[i].add(k)
        q = deque(k for k in self.order if indeg[k] == 0)
        out = []
        while q:
            k = q.popleft()
            out.append(k)
            for o in sorted(down[k]):
                indeg[o] -= 1
                if indeg[o] == 0:
                    q.append(o)
        if len(out) != len(self.der):
            raise ValueError('the plan contains a dependency cycle')
        return out

    def rewire(self, changes):
        if any(k not in self.der for k in changes):
            raise ValueError('the change refers to a derivation that does not exist')
        order = self.topological_order(changes)
        # Validation precedes mutation. New nodes may follow their consumers in creation order.
        self.order = order
        return super().rewire(changes)


def read_csv_source(spec, text):
    required = {'key', 'value'}
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('the CSV requires key and value columns')
    rows = {}
    for row in reader:
        key = row['key'].strip()
        if not key or key in rows:
            raise ValueError('missing or duplicate CSV key: ' + key)
        value = float(row['value'])
        if not math.isfinite(value):
            raise ValueError('the value must be finite: ' + key)
        fields = {f: row.get(f) or spec.get('contract', {}).get(f) for f in ['qkind', 'unit', 'period', 'support']}
        if not all(isinstance(v, str) and v for v in fields.values()):
            raise ValueError('the contract requires qkind, unit, period and support: ' + key)
        rows[key] = (value, Meta(**fields))
    return rows, hashlib.sha256(text.encode('utf-8')).hexdigest()


def add_nodes(ledger, nodes):
    pending = list(nodes)
    keys = [n['key'] for n in pending]
    if len(keys) != len(set(keys)) or any(k in ledger.d for k in keys):
        raise ValueError('duplicate key in the plan')
    # Resolve dependencies among new nodes, while allowing genuinely missing source inputs.
    while pending:
        pending_keys = {n['key'] for n in pending}
        ready = [n for n in pending if not set(n['inputs']) & pending_keys]
        if not ready:
            raise ValueError('the plan contains a dependency cycle')
        for n in ready:
            op, inputs, params = n['op'], n['inputs'], n.get('params', {})
            arity = {'broadcast': 1, 'scale': 1, 'diff': 2, 'ratio': 2}
            if op in arity and len(inputs) != arity[op]:
                raise ValueError('incorrect input count: ' + n['key'])
            if op == 'lin' and len(params.get('w', [])) != len(inputs):
                raise ValueError('weight count does not match input count: ' + n['key'])
            if op == 'scale' and 'k' not in params:
                raise ValueError('scale requires parameter k')
            if 'expect' in params and len(params['expect']) != len(inputs):
                raise ValueError('expect requires one contract per input')
            ledger.derive(n['key'], op, inputs, Meta(**n['contract']), **params)
            pending.remove(n)


def encode_value(ledger, key):
    d = ledger.d[key]
    dv = ledger.der.get(key)
    return dict(key=key, value=d.value, status=d.status, reason=d.reason,
                contract=vars(d.meta), kind=d.kind, source=d.source, version=d.version,
                operation=dv.op if dv else None, inputs=dv.inputs if dv else [])


def compare_snapshots(before, after, flagged):
    changed = set()
    for k in before.keys() | after.keys():
        if k not in before or k not in after:
            changed.add(k)
            continue
        a, sa = before[k]
        b, sb = after[k]
        if sa != sb or (a is None) != (b is None) or (a is not None and not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)):
            changed.add(k)
    return dict(changed=len(changed), flagged=len(flagged),
                recall=len(changed & flagged) / len(changed) if changed else None,
                precision=len(changed & flagged) / len(flagged) if flagged else None,
                new_outputs=len(after.keys() - before.keys()),
                removed_outputs=len(before.keys() - after.keys()))


def run_bundle(bundle):
    """Accept JSON plus inline CSV, never arbitrary executable code or server file paths."""
    ledger = AuditLedger()
    sources = bundle['sources']
    names = [s['name'] for s in sources]
    if len(names) != len(set(names)):
        raise ValueError('duplicate source')
    for spec in sources:
        rows, digest = read_csv_source(spec, spec['csv'])
        ledger.register_source(spec['name'], spec['version'], digest)
        for key, (value, meta) in rows.items():
            if key in ledger.d:
                raise ValueError('the key belongs to more than one source: ' + key)
            ledger.put(key, value, meta, spec['name'], spec['version'])
    add_nodes(ledger, bundle.get('nodes', []))
    history = []
    for revision in bundle.get('revisions', []):
        before = ledger.snapshot()
        before_values = {k: encode_value(ledger, k) for k in ledger.d}
        flagged = set()
        events = []
        # All changes occur in a disposable ledger for this run, never the frozen replication data.
        for update in revision.get('updates', []):
            if update['source'] not in names:
                raise ValueError('source not registered: ' + update['source'])
            spec = next(s for s in sources if s['name'] == update['source'])
            rows, digest = read_csv_source(spec, update['csv'])
            if any(k in ledger.d and ledger.d[k].source != spec['name'] for k in rows):
                raise ValueError('the update attempts to replace a key from another source')
            result = ledger.apply_update(spec['name'], update['version'], rows, digest)
            for keys in result['_impact'].values():
                flagged |= keys
            events.append(dict(source=spec['name'], version=update['version'], diff=result['diff'], impact=result['impact']))
        additions = revision.get('add_nodes', [])
        add_nodes(ledger, additions)
        flagged |= {n['key'] for n in additions}
        if revision.get('rewire'):
            changes = revision['rewire']
            for k, ins in changes.items():
                dv = ledger.der.get(k)
                if dv is None or dv.op != 'sum':
                    raise ValueError('rewire supports sum operations in this interface')
                if 'expect' in dv.params:
                    raise ValueError('rewire requires a new declaration of input contracts')
            flagged |= ledger.rewire(changes)['_affected']
        after = ledger.snapshot()
        history.append(dict(name=revision['name'], metrics=compare_snapshots(before, after, flagged),
                            events=events, before=before_values,
                            after={k: encode_value(ledger, k) for k in ledger.d},
                            flagged=sorted(flagged)))
    return dict(schema_version=1, origin='local_execution', title=bundle.get('title', 'Data audit'),
                source_count=len(sources), value_count=len(ledger.d),
                status_counts=dict(Counter(ledger.d[k].status for k in ledger.order)),
                values=[encode_value(ledger, k) for k in ledger.d],
                sources=ledger.sources, revisions=history,
                limits=['Contracts and dependencies require a declaration.',
                        'A version comparison does not determine whether a numeric revision contains an error.',
                        'Change attribution requires a rule for each operation.'])


if __name__ == '__main__':
    bundle = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    result = run_bundle(bundle)
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(payload, encoding='utf-8')
    else:
        print(payload)
