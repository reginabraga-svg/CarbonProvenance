"""Value-level provenance ledger for integrated carbon inventory data.

Every value in the integration is a datum with a key, a value and a contract (quantity kind, unit,
period type, spatial support). Source datums come from a versioned source; derived datums record the
operation and the input keys that produced them. From this record the ledger answers three questions
when a source changes version: which values are stale, which have lost their origin (orphans), and
which unresolved values can now be computed. It also recomputes only what is affected and explains
any value back to its sources.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------------- contracts
# quantity kinds used here
STOCK, FLUX, AREA, COUNT, FACTOR, NFLOW, SHARE = "stock", "flux", "area", "count", "factor", "n_flow", "share"


@dataclass
class Meta:
    qkind: str              # stock (at a date), flux (per period), area, count, factor, n_flow, share
    unit: str
    period: str             # instant:YYYY | annual:YYYY | none
    support: str            # spatial support of the value: farm_area, municipality_class, municipality, country...

    def as_tuple(self):
        return (self.qkind, self.unit, self.period, self.support)


@dataclass
class Datum:
    key: str
    kind: str               # source | derived
    meta: Meta
    value: float | None = None
    source: str | None = None        # source name (for source datums)
    version: str | None = None       # source version (for source datums)
    status: str = "ok"               # ok | contextual | blocked | unresolved | orphan
    reason: str = ""


@dataclass
class Derivation:
    out: str
    op: str
    inputs: list
    params: dict = field(default_factory=dict)


CANON = [("/ a", "/ yr")]          # unit spellings declared equivalent


def canon(u):
    for a, b in CANON:
        u = u.replace(a, b)
    return u


def _check(op, ins: list, out: Meta, expect=None):
    """Contract of each operation. Returns (status, reason)."""
    ms = [d.meta for d in ins]
    if expect:
        # input contract declared by the pipeline: what each operation expects to receive
        for i, (m, e) in enumerate(zip(ms, expect)):
            if e is None:
                continue
            eq, eu, ep, es = e
            if m.qkind != eq or canon(m.unit) != canon(eu) or (ep and m.period != ep) or (es and m.support != es):
                return "blocked", f"input {ins[i].key} violates the expected contract {e}: got {m.as_tuple()}"
    if op == "ratio":
        if ms[0].qkind != ms[1].qkind or canon(ms[0].unit) != canon(ms[1].unit) or ms[0].period != ms[1].period:
            return "blocked", f"ratio of incompatible values: {ms[0].as_tuple()} / {ms[1].as_tuple()}"
    if op in ("sum", "diff"):
        kinds = {m.qkind for m in ms}
        units = {canon(m.unit) for m in ms}
        periods = {m.period.split(":")[0] for m in ms}
        if len(kinds) > 1:
            return "blocked", f"{op} of different quantity kinds: {sorted(kinds)}"
        if len(units) > 1:
            return "blocked", f"{op} of different units: {sorted(units)}"
        if len(periods) > 1:
            return "blocked", f"{op} of different period types: {sorted(periods)}"
    if op == "broadcast":
        # a context value copied to a finer support is usable but not an observation of that unit
        if ms[0].support != out.support:
            return "contextual", f"value of {ms[0].support} assigned to {out.support}"
    return "ok", ""


OPS = {
    "broadcast": lambda v, p: v[0],
    "scale": lambda v, p: v[0] * p["k"],
    "mul": lambda v, p: math.prod(v) * p.get("k", 1.0),
    "sum": lambda v, p: sum(v),
    "diff": lambda v, p: v[0] - v[1],
    "lin": lambda v, p: sum(w * x for w, x in zip(p["w"], v)),
    "ratio": lambda v, p: (v[0] / v[1] if v[1] else float("nan")) * p.get("k", 1.0),
}
RANK = {"ok": 0, "contextual": 1, "blocked": 2, "unresolved": 3, "orphan": 4}


# --------------------------------------------------------------------------------------------- ledger
class Ledger:
    def __init__(self):
        self.d: dict[str, Datum] = {}
        self.der: dict[str, Derivation] = {}
        self.order: list[str] = []                  # derived keys in creation (topological) order
        self.down: dict[str, set] = defaultdict(set)  # input key -> derived keys that use it
        self.sources: dict[str, dict] = {}          # source name -> {version, sha256, published, note}
        self.n_evals = 0

    # ---- sources
    def register_source(self, name, version, sha256="", published="", note=""):
        self.sources[name] = dict(version=version, sha256=sha256, published=published, note=note)

    def put(self, key, value, meta: Meta, source, version):
        self.d[key] = Datum(key, "source", meta, value, source, version)

    # ---- derivations
    def derive(self, key, op, inputs, meta: Meta, **params):
        dv = Derivation(key, op, list(inputs), params)
        self.der[key] = dv
        self.order.append(key)
        for i in inputs:
            self.down[i].add(key)
        self.d[key] = Datum(key, "derived", meta)
        self._eval(key)
        return self.d[key]

    def _eval(self, key):
        dv, out = self.der[key], self.d[key]
        self.n_evals += 1
        ins = [self.d.get(i) for i in dv.inputs]
        missing = [i for i, x in zip(dv.inputs, ins) if x is None or x.status == "orphan"]
        if missing:
            orph = [i for i in missing if i in self.d and self.d[i].status == "orphan"]
            out.value = None
            out.status = "orphan" if orph else "unresolved"
            out.reason = ("input lost its origin: " if orph else "missing input: ") + ", ".join(missing[:3])
            return
        unres = [x for x in ins if x.status == "unresolved"]
        if unres:
            out.value, out.status, out.reason = None, "unresolved", "input unresolved: " + unres[0].key
            return
        out.value = OPS[dv.op]([x.value for x in ins], dv.params)
        if out.value is not None and math.isnan(out.value):
            out.value, out.status, out.reason = None, "unresolved", "undefined result (division by zero)"
            return
        st, why = _check(dv.op, ins, out.meta, dv.params.get("expect"))
        inherited = max((x.status for x in ins), key=lambda s: RANK[s])
        if RANK[inherited] > RANK[st]:
            st, why = inherited, "inherits " + inherited + " from input"
        out.status, out.reason = st, why

    # ---- lineage
    def downstream(self, keys):
        seen, q = set(), deque(keys)
        while q:
            k = q.popleft()
            for o in self.down.get(k, ()):
                if o not in seen:
                    seen.add(o)
                    q.append(o)
        return seen

    def sources_of(self, key):
        """source names a derived value depends on (table-level lineage)."""
        out, seen, q = set(), set(), deque([key])
        while q:
            k = q.popleft()
            if k in seen:
                continue
            seen.add(k)
            dt = self.d.get(k)
            if dt is not None and dt.kind == "source":
                out.add(dt.source)
            elif k in self.der:
                q.extend(self.der[k].inputs)
            else:
                out.add("(missing)")
        return out

    def explain(self, key, depth=0, maxdepth=8):
        dt = self.d.get(key)
        pad = "  " * depth
        if dt is None:
            return [f"{pad}{key}: MISSING"]
        val = "—" if dt.value is None else f"{dt.value:.6g}"
        m = dt.meta
        line = f"{pad}{key} = {val} [{m.qkind}, {m.unit}, {m.period}, {m.support}] status={dt.status}"
        if dt.reason:
            line += f" ({dt.reason})"
        if dt.kind == "source":
            v = self.sources.get(dt.source, {})
            return [line + f" <- source {dt.source} version {dt.version} sha256 {v.get('sha256', '')[:12]}"]
        dv = self.der[key]
        lines = [line + f" <- {dv.op}" + (f" {dv.params}" if dv.params else "")]
        if depth < maxdepth:
            for i in dv.inputs:
                lines += self.explain(i, depth + 1, maxdepth)
        return lines

    # ---- source update with impact analysis
    def diff_source(self, name, new: dict, rtol=0.0):
        """new: key -> (value, Meta). Returns dict changed / removed / added / contract_changed."""
        old = {k: x for k, x in self.d.items() if x.kind == "source" and x.source == name and x.value is not None}
        changed, removed, added, cchanged = [], [], [], []
        for k, x in old.items():
            if k not in new:
                removed.append(k)
                continue
            v, m = new[k]
            if (m.qkind, canon(m.unit), m.period, m.support) != (x.meta.qkind, canon(x.meta.unit), x.meta.period, x.meta.support):
                cchanged.append(k)
            if v != x.value and not (abs(v - x.value) <= rtol * max(1.0, abs(x.value))):
                changed.append(k)
        added = [k for k in new if k not in old]
        return dict(changed=changed, removed=removed, added=added, contract_changed=cchanged)

    def impact(self, diff):
        """stale: downstream of changed values or changed contracts; orphan: downstream of removed;
        resolvable: unresolved values whose missing input is now added."""
        orphan = self.downstream(diff["removed"])
        stale = self.downstream(diff["changed"] + diff["contract_changed"]) - orphan
        resolvable = set()
        for k in diff["added"]:
            resolvable |= {o for o in self.down.get(k, ())}
        resolvable = (resolvable | self.downstream(list(resolvable))) - orphan
        return dict(stale=stale, orphan=orphan, resolvable=resolvable)

    def apply_update(self, name, version, new: dict, sha256="", incremental=True):
        """Swap a source to a new version. Incremental: recompute only affected values."""
        t0 = time.perf_counter()
        diff = self.diff_source(name, new)
        imp = self.impact(diff)
        prev = self.sources.get(name, {}).get("version")
        # values that change while the declared version stays the same: an unannounced change
        diff["unannounced"] = list(diff["changed"]) if (prev == version and diff["changed"]) else []
        t1 = time.perf_counter()
        for k in diff["removed"]:
            self.d[k].status, self.d[k].value = "orphan", None
            self.d[k].reason = f"{name} {version} no longer provides this key"
            self.d[k].version = version
        for k, (v, m) in new.items():
            if k in self.d:
                self.d[k].value, self.d[k].meta, self.d[k].version = v, m, version
                self.d[k].status, self.d[k].reason = "ok", ""
            else:
                self.d[k] = Datum(k, "source", m, v, name, version)
        self.sources[name] = dict(self.sources.get(name, {}), version=version, sha256=sha256)
        n0 = self.n_evals
        todo = imp["stale"] | imp["orphan"] | imp["resolvable"] if incremental else set(self.order)
        for k in self.order:
            if k in todo:
                self._eval(k)
        t2 = time.perf_counter()
        return dict(diff={k: len(v) for k, v in diff.items()}, impact={k: len(v) for k, v in imp.items()},
                    recomputed=self.n_evals - n0, seconds_analysis=t1 - t0, seconds_recompute=t2 - t1,
                    _diff=diff, _impact=imp)

    # ---- structural change: a derivation now reads other inputs (e.g. a new category mapping)
    def rewire(self, changes: dict):
        """changes: derived key -> new input list. Returns the affected set (rewired + downstream)."""
        t0 = time.perf_counter()
        for k, new_inputs in changes.items():
            for i in self.der[k].inputs:
                self.down[i].discard(k)
            self.der[k].inputs = list(new_inputs)
            for i in new_inputs:
                self.down[i].add(k)
        affected = set(changes) | self.downstream(list(changes))
        n0 = self.n_evals
        for k in self.order:
            if k in affected:
                self._eval(k)
        return dict(rewired=len(changes), affected=len(affected), recomputed=self.n_evals - n0,
                    seconds=time.perf_counter() - t0, _affected=affected)

    # ---- snapshots
    def snapshot(self):
        return {k: (x.value, x.status) for k, x in self.d.items() if x.kind == "derived"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def same(a, b, rtol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= rtol * max(1.0, abs(a), abs(b))
