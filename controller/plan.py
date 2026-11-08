from functools import lru_cache

import numpy as np

from .ingest import DAY
from .stats import draws, norm, ptail, tv, ztest

AGES = ["18-30", "31-45", "46-60", "60+"]
FLOOR = 0.03
EXPLORE = 0.4
MIN_ARM = 150
PROBE = 0.05
RAMP = 300
LIFT = 0.02
SURE = 0.97
CAP = 0.25


@lru_cache(maxsize=None)
def feats(fk):
    lang, tier, age, val = fk.split("|")
    return {"lang": lang, "city_tier": tier, "age_band": age, "value_band": val}


def dist(cfg, key, dim):
    return (cfg["allocations"].get(key) or {}).get(dim) or cfg["allocations"]["default"][dim]


def cohort_of(cohorts, fk):
    if fk == "?":
        return "default"
    f = feats(fk)
    for c in cohorts:
        if all(f[k] in vs for k, vs in c["where"].items()):
            return c["id"]
    return "default"


def make_cohorts(db, wf):
    rows = db.execute("select fk, sum(leads) from camps where wf=? group by fk", (wf,)).fetchall()
    tot = sum(n for _, n in rows) or 1
    share = {}
    for fk, n in rows:
        f = feats(fk)
        k = (f["age_band"], f["lang"])
        share[k] = share.get(k, 0) + n / tot
    ages = sorted({a for a, _ in share}, key=lambda a: (AGES.index(a) if a in AGES else 9, a))
    langs = sorted({l for _, l in share}, key=lambda l: -sum(v for k, v in share.items() if k[1] == l))
    out = [{"id": f"{a}_{l}", "where": {"age_band": [a], "lang": [l]}}
           for a in ages for l in langs if share.get((a, l), 0) >= 0.02]
    out = out[:20 - len(ages)]
    return out + [{"id": a, "where": {"age_band": [a]}} for a in ages]


def by_cohort(cohorts, rows):
    out = {}
    for fk, *vals in rows:
        c = cohort_of(cohorts, fk)
        x = out.setdefault(c, [0] * len(vals))
        for i, v in enumerate(vals):
            x[i] += v or 0
    return out


def schedule(db, wf, cohorts, win, now):
    lo, hi = win
    rows = db.execute("select fk, hour, sum(dials), sum(conn), sum(eng) from hours where wf=? and day>=? "
                      "group by fk, hour", (wf, now // DAY - 21)).fetchall()
    ids = [c["id"] for c in cohorts]
    ix = {c: i for i, c in enumerate(ids)}
    Dm, Cm, Em = np.zeros((len(ids), 24)), np.zeros((len(ids), 24)), np.zeros(len(ids))
    for fk, h, d, c, e in rows:
        i = ix.get(cohort_of(cohorts, fk))
        if i is not None:
            Dm[i, h] += d
            Cm[i, h] += c
            Em[i] += e
    G = Cm.sum(0) / np.maximum(Dm.sum(0), 1)
    g = Cm.sum() / max(Dm.sum(), 1)
    prof, rates = {}, {}
    for i, cid in enumerate(ids):
        if Dm[i].sum() < 500 or not g:
            continue
        rc = Cm[i].sum() / Dm[i].sum()
        r = (Cm[i] + 100 * rc * G / g) / (Dm[i] + 100)
        prof[cid] = r[lo:hi] / rc
        rates[cid] = (r, Dm[i].sum(), Em[i] / max(Cm[i].sum(), 1))
    return prof, rates


def tables(prof, k, win):
    out = {}
    for cid, p in prof.items():
        w = p ** k
        w = np.clip(w / w.mean(), 0.05, 5)
        out[cid] = {str(h): round(float(x), 2) for h, x in zip(range(*win), w)}
    return out


def replay(tabs, rates, win):
    tot = sum(n for _, n, _ in rates.values()) or 1
    conn = eng = 0.0
    ps = []
    for h in range(*win):
        den = num = e_h = 0.0
        for cid, (r, n, e) in rates.items():
            t = tabs.get(cid) or tabs.get("default")
            w = t.get(str(h), 0.0) if t else 1.0
            den += n / tot * w
            num += n / tot * w * r[h]
            e_h += n / tot * w * r[h] * e
        if den:
            ps.append(num / den)
            conn += num / den
            eng += e_h / den
    return (float(np.mean(ps)) if ps else 0.0), (eng / conn if conn else 0.0)


def window(db, table, wf, now, hours, cols, key):
    return {r[0]: r[1:] for r in db.execute(
        f"select {key}, {cols} from {table} where wf=? and day*{DAY}+hour*60>=? group by {key}",
        (wf, now - hours * 60))}


def dids(db, wf, opts, now, banned=()):
    a6 = window(db, "dids", wf, now, 6, "sum(dials), sum(conn)", "d")
    a24 = window(db, "dids", wf, now, 24, "sum(dials), sum(conn)", "d")
    a72 = window(db, "dids", wf, now, 72, "sum(dials), sum(conn)", "d")
    if all(a6.get(d, (0, 0))[0] >= 150 for d in opts if a24.get(d, (0, 0))[0]):
        a24 = a6
    old = {r[0]: r[1:] for r in db.execute(
        f"select d, sum(dials), sum(conn) from dids where wf=? and day*{DAY}+hour*60>=? and day*{DAY}+hour*60<? "
        f"group by d", (wf, now - 96 * 60, now - 12 * 60))}
    live = [d for d in opts if d not in banned]
    seen = [d for d in live if a72.get(d, (0, 0))[0] >= 150]
    bad, ok, rate = [], [], {}
    for d in seen:
        n, c = a24.get(d, (0, 0))
        if n < 150:
            n, c = a72.get(d, (0, 0))
        rn = sum(a24.get(o, (0, 0))[0] for o in seen if o != d)
        rc = sum(a24.get(o, (0, 0))[1] for o in seen if o != d)
        rate[d] = c / n if n else None
        on, oc = old.get(d, (0, 0))
        worse = n >= 150 and rn and ztest(c, n, rc, rn) < -3
        if on >= 300:
            worse = worse and c / n < 0.75 * rc / rn and c / n < 0.75 * oc / on and ztest(c, n, oc, on) < -3
        else:
            worse = worse and c / n < 0.65 * rc / rn
        if not rn:
            ok.append(d)
        elif worse:
            bad.append(d)
        elif n >= 150 and c / n >= 0.9 * rc / rn:
            ok.append(d)
    probe = [d for d in live if d not in ok and d not in bad]
    if not ok:
        best = max(seen, key=lambda d: rate.get(d) or 0) if seen else None
        ok = [best] if best else []
        bad = [d for d in bad if d != best]
        probe = [d for d in probe if d != best]
    if not ok:
        return norm({d: 1 for d in live or opts}), bad, rate
    ps = min(PROBE, 0.3 / len(probe)) if probe else 0
    out = {d: ps for d in probe}
    out.update({d: (1 - ps * len(probe)) / len(ok) for d in ok})
    return norm(out), bad, rate


def target(pb, under):
    if not under:
        return norm({o: max(p, FLOOR) for o, p in pb.items()})
    out = {o: EXPLORE / len(under) for o in under}
    for o in pb:
        out[o] = (1 - EXPLORE) * max(pb[o], FLOOR)
    return norm(out)


def ramp(t, n):
    thin = [o for o in t if n.get(o, RAMP) < RAMP and t[o] > CAP]
    fat = [o for o in t if n.get(o, RAMP) >= RAMP]
    if not thin or not fat:
        return t
    spare = sum(t[o] - CAP for o in thin)
    out = {o: CAP if o in thin else v for o, v in t.items()}
    tot = sum(out[o] for o in fat)
    for o in fat:
        out[o] += spare * out[o] / tot
    return norm(out)


def choose(a, b, ks, under, cur):
    X = draws(a, b)
    pb = dict(zip(ks, np.bincount(X.argmax(0), minlength=len(ks)) / X.shape[1]))
    t = ramp(target(pb, under), {o: a[i] + b[i] - 2 for i, o in enumerate(ks)})
    if under:
        return t, pb, None
    s = sum(cur.get(o, 0) for o in ks) or 1
    tv_ = np.array([t.get(o, 0) for o in ks])
    cv = np.array([cur.get(o, 0) / s for o in ks])
    T, C = tv_ @ X, cv @ X
    return t, pb, float((T > C).mean()) if (T / C).mean() - 1 >= LIFT else 0.0


def arms(db, wf, opts, cohorts, now, cur, days=5, recent=None, half=1.5, fresh=()):
    today = now // DAY
    rows = [(fk, w, v, n * 0.5 ** ((today - d) / half), e * 0.5 ** ((today - d) / half)) for d, fk, w, v, n, e in
            db.execute("select day, fk, w, v, sum(conn), sum(eng) from arms where wf=? and day>=? "
                       "group by day, fk, w, v", (wf, today - days + 1))]
    out = {}
    for dim, j in (("welcome_message", 1), ("voice", 2)):
        own = {k for k, v in cur["allocations"].items() if k != "default" and dim in v}
        G, Cc = {o: [0, 0] for o in opts[dim]}, {}
        for r in rows:
            o = r[j]
            if o not in G:
                continue
            c = cohort_of(cohorts, r[0])
            if c not in own:
                G[o][0] += r[3]
                G[o][1] += r[4]
            x = Cc.setdefault(c, {}).setdefault(o, [0, 0])
            x[0] += r[3]
            x[1] += r[4]
        for o in (recent or {}).get(dim, []):
            G[o] = [v or 0 for v in db.execute(f"select sum(conn), sum(eng) from vh where wf=? and dim=? and o=? "
                                               f"and day*{DAY}+hour*60>=?", (wf, dim, o, now - DAY)).fetchone()]
        ks = list(G)
        n = sum(G[o][0] for o in ks)
        e = sum(G[o][1] for o in ks)
        base = e / n if n else 0.3
        tried = dict(db.execute(f"select {'w' if j == 1 else 'v'}, sum(conn) from arms where wf=? group by 1",
                                (wf,)).fetchall())
        under = [o for o in ks if (tried.get(o) or 0) < MIN_ARM
                 or dim in fresh and o not in (recent or {}).get(dim, []) and G[o][0] < MIN_ARM]
        samp = [o for o in ks if o not in under]
        top, pb, p = {o: 1 / len(ks) for o in ks}, {}, None
        if samp:
            top, pb, p = choose([1 + G[o][1] for o in samp], [1 + G[o][0] - G[o][1] for o in samp], samp, under,
                                dist(cur, "default", dim))
        lift = {o: (G[o][1] + 100 * base) / (G[o][0] + 100) / base if base else 1 for o in ks}
        mu = {"default": {o: base * lift[o] for o in ks}}
        res = {"default": (top, p)}
        for cid, cs in Cc.items():
            cn = sum(x[0] for x in cs.values())
            ce = sum(x[1] for x in cs.values())
            if cid == "default" or cn < 300:
                continue
            cb = ce / cn
            m = {o: min(0.95, cb * lift[o]) for o in ks}
            a = [200 * m[o] + cs.get(o, [0, 0])[1] for o in ks]
            b = [200 * (1 - m[o]) + cs.get(o, [0, 0])[0] - cs.get(o, [0, 0])[1] for o in ks]
            mu[cid] = {o: a[i] / (a[i] + b[i]) for i, o in enumerate(ks)}
            if under:
                continue
            t, _, pc = choose(a, b, ks, [], dist(cur, cid, dim))
            if tv(t, top) > 0.15:
                res[cid] = (t, pc)
        out[dim] = {"target": res, "global": G, "pbest": pb, "under": under, "mu": mu,
                    "decay": decay(db, wf, dim, now, dist(cur, "default", dim)),
                    "share": {c: sum(x[0] for x in cs.values()) for c, cs in Cc.items()}}
    return out


def decay(db, wf, dim, now, live):
    rows = db.execute(f"select o, day*{DAY}+hour*60>=?, sum(conn), sum(eng) from vh where wf=? and dim=? "
                      f"and day*{DAY}+hour*60>=? group by 1, 2", (now - DAY, wf, dim, now - 4 * DAY)).fetchall()
    s = {}
    for o, recent, n, e in rows:
        s.setdefault(o, [0, 0, 0, 0])[2 * recent: 2 * recent + 2] = [n, e]
    out = []
    for o, (n0, e0, n1, e1) in s.items():
        if live.get(o, 0) < 0.3:
            continue
        if n0 >= 300 and n1 >= 200 and e1 / n1 < 0.9 * e0 / n0 and ztest(e1, n1, e0, n0) < -3:
            out.append(o)
    return out


def halluc(db, wf, p, now, p0, hours=None):
    old = db.execute(f"select sum(conn), sum(flags) from prompts where wf=? and p=? and day*{DAY}+hour*60<?",
                     (wf, p, now - 24 * 60)).fetchone()
    on, ox = old[0] or 0, old[1] or 0
    known = on >= 2000
    if known:
        p0 = max(p0, ox / on)
    hours = hours or (24 if known else 12)
    r = window(db, "prompts", wf, now, hours, "sum(conn), sum(flags)", "p").get(p, (0, 0))
    n, x = (v or 0 for v in r)
    pv = ptail(x, n * p0) if n else 1.0
    lim, ratio, nmin = (1e-7, 2.0, 300) if known else (1e-3, 1.5, 100)
    hit = n >= nmin and x >= 6 and x / n >= ratio * p0 and pv < lim
    return hit, {"prompt": p, "connected": n, "flags": x, "flag_rate": round(x / n, 4) if n else None,
                 "baseline": round(p0, 4), "p_value": pv, "track_record": on, "window_h": hours}


def base_flags(db, wf):
    n, x = db.execute("select sum(conn), sum(flags) from prompts where wf=? and day<0", (wf,)).fetchone()
    return max((x or 0) / n, 0.003) if n else 0.01


def good_prompts(db, wf, p0):
    rows = db.execute("select p, sum(conn), sum(flags), sum(eng) from prompts where wf=? group by p", (wf,))
    ok = [(e / n, p) for p, n, x, e in rows if n >= 1000 and x / n <= 1.3 * p0]
    return [p for _, p in sorted(ok, reverse=True)]


def compare(db, wf, t):
    rows = db.execute(f"select day*{DAY}+hour*60, hour, sum(dials), sum(conn), sum(eng) from hours "
                      f"where wf=? and day*{DAY}+hour*60>=? group by 1", (wf, t - 2 * DAY)).fetchall()
    B, A = {}, {}
    for m, h, d, c, e in rows:
        x = (A if m >= t else B).setdefault(h, [0, 0, 0])
        x[0] += d
        x[1] += c
        x[2] += e
    ec = oc = ee = oe = 0.0
    for h, (d, c, e) in A.items():
        b = B.get(h)
        if not b or not b[0] or not b[1]:
            continue
        ec += d * b[1] / b[0]
        oc += c
        ee += c * b[2] / b[1]
        oe += e
    z = lambda o, x: (o - x) / max(x, 1) ** 0.5
    return {"connected": int(oc), "pickup_ratio": oc / ec if ec else None, "pickup_z": z(oc, ec),
            "engage_ratio": oe / ee if ee else None, "engage_z": z(oe, ee)}


def active_leads(db, wf, now, cadence, cohorts=None, keep=None):
    rows = db.execute("select fk, sum(leads - eng) from camps where wf=? and day>? group by fk",
                      (wf, now // DAY - len(cadence))).fetchall()
    if keep is None:
        return int(sum(n for _, n in rows))
    return int(sum(n for fk, n in rows if cohort_of(cohorts, fk) in keep))
