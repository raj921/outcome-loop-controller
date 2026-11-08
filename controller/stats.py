import math

import numpy as np


def draws(a, b, n=4000, seed=7):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.random.default_rng(seed).beta(a[:, None], b[:, None], (len(a), n))


def pbest(a, b, n=4000, seed=7):
    return np.bincount(draws(a, b, n, seed).argmax(0), minlength=len(a)) / n


def ztest(x1, n1, x2, n2):
    if not n1 or not n2:
        return 0.0
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (x1 / n1 - x2 / n2) / se


def ptail(x, lam):
    if x <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    s = sum(math.exp(k * math.log(lam) - lam - math.lgamma(k + 1)) for k in range(x))
    return max(0.0, 1 - s)


def tv(a, b):
    sa, sb = sum(a.values()) or 1, sum(b.values()) or 1
    return 0.5 * sum(abs(a.get(k, 0) / sa - b.get(k, 0) / sb) for k in set(a) | set(b))


def norm(d, unit=1024):
    s = sum(d.values())
    raw = {k: v / s * unit for k, v in d.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: out[k] - raw[k])[:unit - sum(out.values())]:
        out[k] += 1
    return {k: v / unit for k, v in sorted(out.items()) if v}
