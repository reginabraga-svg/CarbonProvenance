"""Attribution of the change of a derived value to the source values it was derived from.

The change of a value between two states of the ledger is pushed down its derivation links
(prov:wasDerivedFrom, with the operation recorded on the generating activity):
  sum, diff, scale, lin, broadcast   the change is passed to the inputs with their coefficients
  mul (two inputs)                   d(xy) = dx * mean(y) + mean(x) * dy, which is exact
  an input wired in only one state   its whole value enters as a context added or withdrawn
The contributions of the source values add up exactly to the change of the target.
"""
import heapq
from collections import defaultdict

LINEAR = {"sum", "diff", "scale", "lin", "broadcast"}


def capture(L):
    """the part of a ledger state that attribution needs: every value and the inputs of every derivation"""
    return {k: x.value for k, x in L.d.items()}, {k: list(dv.inputs) for k, dv in L.der.items()}


def attribute(L, old, target, nv=None, pos=None):
    """L: ledger in the new state. old: capture() of the old state. Returns {(kind, key): contribution},
    kind in source | added | withdrawn."""
    ov, oin = old
    nv = nv if nv is not None else {k: x.value for k, x in L.d.items()}
    pos = pos if pos is not None else {k: i for i, k in enumerate(L.order)}
    w = defaultdict(float)
    w[target] = 1.0
    heap = [(-pos[target], target)]
    seen = {target}
    out = defaultdict(float)

    def push(k, x):
        w[k] += x
        if k in pos and k not in seen:
            seen.add(k)
            heapq.heappush(heap, (-pos[k], k))

    while heap:
        _, k = heapq.heappop(heap)
        wk = w[k]
        if wk == 0:
            continue
        dv = L.der[k]
        new_in, old_in = dv.inputs, oin.get(k, dv.inputs)
        p = dv.params
        if dv.op == "sum":
            both = set(new_in) & set(old_in)
            for i in new_in:
                if i in both:
                    push(i, wk)
                elif nv.get(i) is not None:
                    out[("added", i)] += wk * nv[i]
            for i in old_in:
                if i not in both and ov.get(i) is not None:
                    out[("withdrawn", i)] -= wk * ov[i]
        elif dv.op == "diff":
            push(new_in[0], wk)
            push(new_in[1], -wk)
        elif dv.op in ("scale",):
            push(new_in[0], wk * p["k"])
        elif dv.op == "broadcast":
            push(new_in[0], wk)
        elif dv.op == "lin":
            for c, i in zip(p["w"], new_in):
                push(i, wk * c)
        elif dv.op == "mul" and len(new_in) == 2:
            x, y = new_in
            vals = [ov.get(x), nv.get(x), ov.get(y), nv.get(y)]
            if None in vals:
                if nv.get(k) is not None and ov.get(k) is None:
                    out[("added", k)] += wk * nv[k]
                elif ov.get(k) is not None and nv.get(k) is None:
                    out[("withdrawn", k)] -= wk * ov[k]
                continue
            kk = p.get("k", 1.0)
            push(x, wk * kk * (vals[2] + vals[3]) / 2)
            push(y, wk * kk * (vals[0] + vals[1]) / 2)
        else:
            raise ValueError(f"no attribution rule for {dv.op} with {len(new_in)} inputs ({k})")
    for k, x in w.items():
        if k not in pos and x != 0:
            a, b = ov.get(k), nv.get(k)
            if a is not None and b is not None and a != b:
                out[("source", k)] += x * (b - a)
    return dict(out)
