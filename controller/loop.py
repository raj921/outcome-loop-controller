import copy
import json

from . import plan
from .gov import OPEN, log
from .ingest import DAY, meta, put
from .plan import dist
from .stats import norm, tv

AGENT = ("welcome_message", "voice", "caller_id")
FACING = ("welcome_message", "voice", "prompt_version")
VERIFY = ("cohorts", "schedule", "caller_id")


def when(m):
    d, r = divmod(m, DAY)
    return f"D{d} {r // 60:02d}:{r % 60:02d}"


def fmt(d):
    return " ".join(f"{k} {v:.0%}" for k, v in sorted(d.items()))


class Flow:
    def __init__(self, db, api, gov, w):
        self.db, self.api, self.gov, self.w = db, api, gov, w
        self.id = w["workflow_id"]
        self.g = w["governance"]
        self.obj = w["objective"]
        aa = self.g["auto_apply"]
        self.auto = set(aa["allowed_dims"]) if aa.get("enabled") else set()
        self.shift = aa.get("max_shift", 0)
        self.win = w["dialling_window"]
        self.opts = w["options"]

    def tick(self, now):
        self.now = now
        self.gov.sync(self.id, now)
        self.load()
        self.frozen = self.supervisor()
        self.hallucination()
        self.verify()
        self.optimise()

    def load(self):
        c = self.api.get(f"/workflows/{self.id}/config")
        self.ver, self.cfg = c["version"], c["config"]
        k = f"cfg:{self.id}:{self.ver}"
        if meta(self.db, k) is None:
            put(self.db, k, {"actor": c["actor"], "applied_at": c["applied_at"], "config": self.cfg})
        put(self.db, f"cfg:{self.id}", self.ver)

    def note(self, kind, msg, data=None):
        log(self.db, self.now, self.id, kind, msg, data)

    def credits(self, r):
        if r.status_code == 200:
            put(self.db, "credits", r.json()["credits_remaining"])

    def cohorts(self):
        k = f"cohorts:{self.id}"
        c = meta(self.db, k)
        if c is None:
            c = plan.make_cohorts(self.db, self.id)
            put(self.db, k, c)
            self.note("cohorts", f"{len(c)} shared cohorts fixed from history", c)
        return c

    def supervisor(self):
        k = f"sup_seen:{self.id}"
        seen = meta(self.db, k, 0)
        out = set()
        for r in self.db.execute("select event_id, at, body from misc where wf=? and type='config_changed' "
                                 "and at>=? order by event_id", (self.id, self.now - 2 * DAY)):
            e = json.loads(r["body"])
            if e["actor"] != "supervisor":
                continue
            out |= set(e["changed_dims"])
            if r["event_id"] > seen:
                seen = r["event_id"]
                self.note("supervisor_edit", f"supervisor changed {e['changed_dims']} -> v{e['version']}; "
                          f"those dims are left alone for 48h", e)
        put(self.db, k, seen)
        return out

    def incident(self, kind):
        return self.db.execute("select * from incidents where wf=? and kind=? and status not in ('closed', 'stuck') "
                               "order by id desc", (self.id, kind)).fetchone()

    def hallucination(self):
        p0 = plan.base_flags(self.db, self.id)
        inc = self.incident("halluc")
        if inc is None:
            hit, ev = plan.halluc(self.db, self.id, self.cfg["prompt_version"], self.now, p0)
            if not hit:
                return
            self.db.execute("insert into incidents(wf, kind, status, opened, data) values(?,?,?,?,?)",
                            (self.id, "halluc", "open", self.now,
                             json.dumps({"bad": ev["prompt"], "tried": [], "val": {}, "detect": ev, "llm": 0})))
            self.note("incident", f"hallucination flags {ev['flag_rate']:.1%} on {ev['prompt']} vs "
                      f"{ev['baseline']:.1%} baseline (n={ev['connected']}, p={ev['p_value']:.1e})", ev)
            inc = self.incident("halluc")
        d = json.loads(inc["data"])
        st = inc["status"]
        cur = self.cfg["prompt_version"]
        if cur not in (d["bad"], d.get("fix")):
            hit, ev = plan.halluc(self.db, self.id, cur, self.now, p0)
            if not hit:
                self.close(inc, d, "closed", f"prompt moved to {cur} outside this incident; {cur} looks normal")
                return
        if st == "open":
            c = [p for p in plan.good_prompts(self.db, self.id, p0) if p != d["bad"] and p not in d["tried"]]
            if not c and d["llm"] < 2 and (meta(self.db, "credits", 999) or 0) >= 3:
                r = self.api.post("/llm/suggest-fixes", {"workflow_id": self.id, "problem":
                                  f"hallucination flag rate {d['detect']['flag_rate']:.1%} on prompt {d['bad']}, "
                                  f"baseline {d['detect']['baseline']:.1%}"})
                self.credits(r)
                d["llm"] += 1
                if r.status_code == 200:
                    s = r.json()["suggestions"]
                    d["suggestions"] = s
                    c = [x["prompt_version"] for x in s if x["prompt_version"] not in d["tried"] + [d["bad"]]]
                    self.note("llm", f"LLM suggested {[x['prompt_version'] for x in s]}", s)
            if not c:
                return self.close(inc, d, "stuck", "no candidate prompt left to try; needs a human")
            d["cands"] = c
            st = "validate"
        if st == "validate":
            for p in d["cands"]:
                if p not in d["val"]:
                    r = self.api.post("/validation/runs", {"workflow_id": self.id, "prompt_version": p, "n": 300})
                    self.credits(r)
                    if r.status_code != 200:
                        self.note("alert", f"validation call failed {r.status_code}: {r.text[:200]}")
                        return self.save(inc, d, st)
                    v = r.json()
                    d["val"][p] = {"id": v["validation_run_id"], "pass_rate": v["pass_rate"], "n": v["n"]}
                    self.note("validation", f"{p}: pass rate {v['pass_rate']:.3f} on {v['n']} runs", v)
                if d["val"][p]["pass_rate"] >= self.g["min_validation_pass_rate"]:
                    d["fix"] = p
                    st = "propose"
                    break
            else:
                d["tried"] += d["cands"]
                st = "open"
        if st == "propose":
            if cur == d["fix"]:
                d["at"] = self.now
                st = "verify"
            elif not any(r["tag"] == "incident" for r in self.gov.rows(self.id, *OPEN)) \
                    and self.gov.sent24(self.id, self.now) < self.g["max_requests_per_24h"]:
                new = copy.deepcopy(self.cfg)
                new["prompt_version"] = d["fix"]
                n, x, e = self.prompt_stats(d["fix"])
                v = d["val"][d["fix"]]
                det = d["detect"]
                body = {
                    "change_summary": f"Switch prompt {cur} -> {d['fix']}: hallucination flags {det['flag_rate']:.1%} "
                                      f"vs {det['baseline']:.1%} normal",
                    "diff": {"prompt_version": {"from": cur, "to": d["fix"]}},
                    "affected_leads": plan.active_leads(self.db, self.id, self.now, self.w["cadence"]),
                    "dry_run": {"current": det, "validation": v,
                                "fix_track_record": {"connected": n, "flag_rate": round(x / n, 4) if n else None,
                                                     "engagement": round(e / n, 4) if n else None}},
                    "impact_score": 0.9,
                    "rationale": f"{det['flags']} flagged calls out of {det['connected']} on {cur} in the last {det['window_h']}h "
                                 f"(p={det['p_value']:.1e}). {d['fix']} passed validation at {v['pass_rate']:.3f} "
                                 f"and has {n} connected calls of history.",
                    "evidence": {"validation_run_id": v["id"]},
                }
                self.gov.send(self.id, "approval", "incident", self.now, self.ver, new, self.cfg,
                              ["prompt_version"], body)
        if st == "verify":
            n, x, e = self.prompt_stats(d["fix"], d["at"])
            if n >= 200:
                hit, ev = plan.halluc(self.db, self.id, d["fix"], self.now, plan.base_flags(self.db, self.id),
                                      max(1, (self.now - d["at"]) // 60))
                bn, bx, be = self.prompt_stats(None, None, history=True)
                low = bn and e / n < 0.9 * be / bn and (be / bn - e / n) / ((be / bn) * (1 - be / bn) / n) ** 0.5 > 3
                if hit or low:
                    d["tried"].append(d["fix"])
                    self.note("incident", f"fix {d['fix']} did not hold ({'flags' if hit else 'engagement'})", ev)
                    d.pop("fix")
                    st = "open"
                else:
                    return self.close(inc, d, "closed", f"fixed: {d['fix']} flag rate {x / n:.1%} on {n} calls, "
                                      f"took {(self.now - inc['opened']) // 60}h from detection")
        self.save(inc, d, st)

    def prompt_stats(self, p, since=None, history=False):
        if history:
            r = self.db.execute("select sum(conn), sum(flags), sum(eng) from prompts where wf=? and day<0",
                                (self.id,)).fetchone()
        else:
            r = self.db.execute(f"select sum(conn), sum(flags), sum(eng) from prompts where wf=? and p=? "
                                f"and day*{DAY}+hour*60>=?", (self.id, p, since if since is not None else -10 ** 9)
                                ).fetchone()
        return tuple(v or 0 for v in r)

    def save(self, inc, d, st):
        self.db.execute("update incidents set status=?, data=? where id=?", (st, json.dumps(d), inc["id"]))

    def close(self, inc, d, st, msg):
        self.db.execute("update incidents set status=?, closed=?, data=? where id=?",
                        (st, self.now, json.dumps(d), inc["id"]))
        self.note("alert" if st == "stuck" else "incident", msg, d)

    def verify(self):
        g = self.obj.get("guardrail", {})
        for r in self.gov.rows(self.id, "applied"):
            if r["tag"] not in ("plan", "did") or not set(json.loads(r["dims"])) & set(VERIFY):
                continue
            note = json.loads(r["note"] or "{}")
            if "verified" in note or self.now - r["done"] < 12 * 60:
                continue
            res = plan.compare(self.db, self.id, r["done"])
            if res["connected"] < 300 and self.now - r["done"] < 48 * 60:
                continue
            bad = []
            tol = g.get("pickup_rate_max_drop", 0.02)
            if res["pickup_ratio"] and res["pickup_ratio"] < 1 - tol and res["pickup_z"] < -3:
                bad.append("pickup")
            tol = g.get("engagement_rate_max_drop")
            if tol and res["engage_ratio"] and res["engage_ratio"] < 1 - tol and res["engage_z"] < -3:
                bad.append("engagement")
            note["verified"] = {"at": self.now, "result": res, "breach": bad}
            self.gov.set(r["pid"], note=json.dumps(note))
            self.note("verified", f"{r['pid']}: pickup x{res['pickup_ratio'] or 0:.3f}, "
                      f"engagement x{res['engage_ratio'] or 0:.3f} vs same hours before"
                      + (f" -> rolling back ({', '.join(bad)})" if bad else ""), res)
            if bad:
                self.rollback(r, bad)

    def rollback(self, r, why):
        prev, mine = json.loads(r["prev"]), json.loads(r["cfg"])
        new = copy.deepcopy(self.cfg)
        dims = []
        for d in json.loads(r["dims"]):
            if d in self.frozen:
                continue
            if d == "schedule" and self.cfg["schedule"] == mine["schedule"]:
                new["schedule"] = prev["schedule"]
                dims.append(d)
            ban = meta(self.db, f"banned:{self.id}", {})
            back = dist(prev, "default", d) if d == "caller_id" else {}
            if d == "caller_id" and dist(self.cfg, "default", d) == dist(mine, "default", d) and not set(back) & set(ban):
                new["allocations"]["default"][d] = back
                dims.append(d)
        if not dims:
            return
        self.submit(new, dims, "rollback", urgent=True, why=f"undo {r['pid']}: {', '.join(why)} dropped")

    def optimise(self):
        now = self.now
        t = now % DAY
        a, b = self.g["approver_hours"]
        if "caller_id" not in self.frozen:
            dt, ban, rate = self.callers()
            live = dist(self.cfg, "default", "caller_id")
            hot = [d for d in ban if live.get(d)]
            if hot and not any(r["tag"] == "did" for r in self.gov.rows(self.id, *OPEN)):
                only = copy.deepcopy(self.cfg)
                only["allocations"]["default"]["caller_id"] = dt
                self.submit(only, ["caller_id"], "did", urgent=True, info={"did_rate": rate, "bad_dids": ban},
                            why=f"caller ID {', '.join(hot)} pickup collapsed")
                return
        if not (a + 1) * 60 <= t < (b - 1) * 60 or self.gov.rows(self.id, *OPEN):
            return
        planned = self.db.execute("select 1 from props where wf=? and tag='plan' and made>=? and status in "
                                  "('new','pending','approved','applied')", (self.id, now - t)).fetchone()
        if planned:
            if self.obj["primary"] != "engagement_rate" or self.db.execute(
                    "select 1 from props where wf=? and tag='decay' and made>=? and status in "
                    "('new','pending','approved','applied')", (self.id, now - t)).fetchone():
                return
            if not self.decays():
                return
        new, info = self.desired()
        dims = self.changes(self.cfg, new)
        if not dims:
            return
        if not planned:
            self.submit(new, dims, "plan", info=info)
        elif info.get("decay") and set(dims) & set(info["decay"]):
            self.submit(new, dims, "decay", urgent=True, info=info,
                        why=f"live variant {info['decay']} is losing engagement")

    def decays(self, live=True):
        k = f"decay:{self.id}"
        st = {d: {o: at for o, at in x.items() if self.now - at < 3 * DAY} for d, x in meta(self.db, k, {}).items()}
        for d in ("welcome_message", "voice"):
            if d in self.frozen:
                continue
            for o in plan.decay(self.db, self.id, d, self.now, dist(self.cfg, "default", d)):
                if o not in st.setdefault(d, {}):
                    st[d][o] = self.now
                    self.note("decay", f"{d} {o} engagement fell in the last 24h vs the 3 days before")
        put(self.db, k, st)
        out = {d: [o for o in x if not live or dist(self.cfg, "default", d).get(o, 0) >= 0.3] for d, x in st.items()}
        return {d: x for d, x in out.items() if x and d not in self.frozen}

    def callers(self):
        k = f"banned:{self.id}"
        ban = meta(self.db, k, {})
        t, bad, rate = plan.dids(self.db, self.id, self.opts["caller_id"], self.now, ban)
        for d in bad:
            ban[d] = self.now
            self.db.execute("insert into incidents(wf, kind, status, opened, closed, data) values(?,?,?,?,?,?)",
                            (self.id, "caller_id", "closed", self.now, self.now, json.dumps({"did": d, "rate": rate})))
            self.note("incident", f"caller ID {d} pickup {rate.get(d) or 0:.1%} vs others, rotating it out until a person clears it",
                      rate)
        put(self.db, k, ban)
        return t, list(ban), rate

    def submit(self, new, dims, tag, urgent=False, info=None, why=None):
        if self.db.execute("select 1 from props where wf=? and tag=? and status='failed' and made>?",
                           (self.id, tag, self.now - 180)).fetchone():
            return
        needs = [d for d in dims if d in FACING or d not in self.auto]
        if not needs:
            new = self.step(new, dims)
            self.gov.send(self.id, "auto", tag, self.now, self.ver, new, self.cfg, dims,
                          self.pack(new, dims, info or {}, why))
            self.load()
            return
        cap = self.g["max_requests_per_24h"] if urgent else max(1, min(self.g["max_requests_per_24h"] - 1, 2))
        n = self.gov.sent24(self.id, self.now)
        if n >= cap:
            self.blocked(f"{tag}: {n} requests in 24h, cap {cap}")
            return
        self.gov.send(self.id, "approval", tag, self.now, self.ver, new, self.cfg, dims,
                      self.pack(new, dims, info or {}, why))

    def blocked(self, msg):
        if not self.db.execute("select 1 from log where wf=? and kind='blocked' and msg=? and at>=?",
                               (self.id, msg, self.now - self.now % DAY)).fetchone():
            self.note("blocked", msg)

    def step(self, new, dims):
        out = copy.deepcopy(new)
        keys = {"default"} | {c["id"] for c in new["cohorts"]}
        for d in dims:
            if d not in AGENT:
                continue
            for k in keys:
                o, n = dist(self.cfg, k, d), dist(new, k, d)
                x = tv(o, n)
                if x > self.shift + 1e-9 and k in out["allocations"] and d in out["allocations"][k]:
                    f = max(self.shift - 0.005, 0) / x
                    out["allocations"][k][d] = norm({p: o.get(p, 0) + f * (n.get(p, 0) - o.get(p, 0))
                                                     for p in set(o) | set(n)})
        return out

    def desired(self):
        cur = self.cfg
        new = copy.deepcopy(cur)
        coh = self.cohorts()
        info = {}
        if not cur["cohorts"] and "cohorts" not in self.frozen:
            new["cohorts"] = coh
        ours = new["cohorts"] == coh
        if ours and "schedule" not in self.frozen:
            prof, rates = plan.schedule(self.db, self.id, coh, self.win, self.now)
            p0, e0 = plan.replay(cur["schedule"]["hour_weights"], rates, self.win)
            g = self.obj.get("guardrail", {})
            for k in (2, 1, 0.5):
                hw = plan.tables(prof, k, self.win)
                p1, e1 = plan.replay(hw, rates, self.win)
                if hw and p1 >= p0 and e1 >= e0 * (1 - g.get("engagement_rate_max_drop", 0.02) / 2):
                    new["schedule"]["hour_weights"] = hw
                    info["pickup_schedule"] = {"old": p0, "new": p1, "engagement_old": e0, "engagement_new": e1,
                                               "sharpness": k}
                    break
            if "engagement_rate_max_drop" in g:
                live = "select distinct camp from camps where wf=? and day>?"
                arg = (self.id, self.now // DAY - len(self.w["cadence"]))
                q = self.db.execute(f"select distinct person_id from calls where camp in ({live}) and "
                                    f"disp='short_hangup' and lead_id not in (select lead_id from calls where "
                                    f"camp in ({live}) and eng=1)", arg + arg).fetchall()
                new["schedule"]["lead_preferred_hour"] = {r[0]: self.win[1] - 1 for r in q[:200000]}
                info["deprioritised"] = len(q)
        if "caller_id" not in self.frozen:
            t, ban, rate = self.callers()
            new["allocations"]["default"]["caller_id"] = t
            info["bad_dids"] = ban
            info["did_rate"] = rate
        if self.obj["primary"] == "engagement_rate":
            use = coh if ours else []
            dec, past = self.decays(), self.decays(live=False)
            if dec:
                info["decay"] = dec
            A = plan.arms(self.db, self.id, self.opts, use, self.now, cur, recent=past, fresh=set(dec))
            info["arms"] = A
            for d, x in A.items():
                if d in self.frozen:
                    continue
                tg = x["target"]
                ok = lambda p: p is None or p >= (0.8 if d in dec else plan.SURE)
                t, p = tg["default"]
                if ok(p):
                    new["allocations"]["default"][d] = t
                for c in [c["id"] for c in new["cohorts"]]:
                    al = new["allocations"].get(c)
                    if c in tg and ok(tg[c][1]):
                        new["allocations"].setdefault(c, {})[d] = tg[c][0]
                    elif c not in tg and al and d in al:
                        del al[d]
            new["allocations"] = {k: v for k, v in new["allocations"].items() if v}
        return new, info

    def changes(self, cur, new):
        out = []
        if cur["cohorts"] != new["cohorts"]:
            out.append("cohorts")
        keys = {"default"} | {c["id"] for c in cur["cohorts"]} | {c["id"] for c in new["cohorts"]}
        for d in AGENT:
            m = max(tv(dist(cur, k, d), dist(new, k, d)) for k in keys)
            if m >= (0.04 if d == "caller_id" else 0.1):
                out.append(d)
                continue
            for k in keys:
                c = (cur["allocations"].get(k) or {}).get(d)
                if c:
                    new["allocations"].setdefault(k, {})[d] = c
                elif d in (new["allocations"].get(k) or {}):
                    del new["allocations"][k][d]
            new["allocations"] = {k: v for k, v in new["allocations"].items() if v}
        a, b = cur["schedule"]["hour_weights"], new["schedule"]["hour_weights"]
        diff = set(a) != set(b) or any(abs(a[k].get(h, 0) - b[k].get(h, 0)) > 0.3
                                       for k in a for h in set(a[k]) | set(b[k]))
        diff |= cur["schedule"]["lead_preferred_hour"] != new["schedule"]["lead_preferred_hour"]
        if diff or "cohorts" in out and a != b:
            out.append("schedule")
        else:
            new["schedule"] = copy.deepcopy(cur["schedule"])
        if cur["prompt_version"] != new["prompt_version"]:
            out.append("prompt_version")
        return out

    def engagement(self, cfg, A):
        tot = e = 0.0
        share = A["welcome_message"]["share"]
        for c, n in share.items():
            f = 1.0
            base = None
            for d in ("welcome_message", "voice"):
                mu = A[d]["mu"].get(c) or A[d]["mu"]["default"]
                b = sum(mu.values()) / len(mu)
                base = b if base is None else base
                f *= sum(w * mu.get(o, b) for o, w in dist(cfg, c, d).items()) / b
            tot += n
            e += n * base * f
        return e / tot if tot else None

    def pack(self, new, dims, info, why=None):
        cur = self.cfg
        parts, diff, dry = [], {}, {}
        if "cohorts" in dims:
            parts.append(f"use {len(new['cohorts'])} age x language cohorts")
            diff["cohorts"] = {"from": [c["id"] for c in cur["cohorts"]], "to": [c["id"] for c in new["cohorts"]]}
        if "schedule" in dims:
            ps = info.get("pickup_schedule") or {}
            parts.append("per-cohort call hours" + (f" (replay pickup {ps['old']:.1%} -> {ps['new']:.1%})" if ps else ""))
            diff["schedule"] = {"hour_weights": new["schedule"]["hour_weights"],
                                "lead_preferred_hour": len(new["schedule"]["lead_preferred_hour"])}
            if info.get("deprioritised"):
                parts.append(f"move {info['deprioritised']} people who already declined to the last dialling hour")
            if ps:
                dry["pickup_schedule_replay"] = ps
        keys = ["default"] + [c["id"] for c in new["cohorts"]]
        for d in AGENT:
            if d not in dims:
                continue
            ch = {k: {"from": dist(cur, k, d), "to": dist(new, k, d)} for k in keys
                  if dist(cur, k, d) != dist(new, k, d)}
            diff[d] = ch
            over = sum(1 for k in ch if k != "default" and d in (new["allocations"].get(k) or {}))
            head = fmt(dist(new, "default", d)) if "default" in ch else "default unchanged"
            parts.append(f"{d.replace('_', ' ')} {head}" + (f" (+{over} cohort overrides)" if over else ""))
        if "caller_id" in dims and info.get("did_rate"):
            r = {k: v for k, v in info["did_rate"].items() if v is not None}
            m = sum(r.values()) / len(r) if r else 0
            p = lambda cfg: sum(w * r.get(o, m) for o, w in dist(cfg, "default", "caller_id").items())
            dry["pickup_caller_id_24h"] = {"old": p(cur), "new": p(new), "per_did": r, "flagged": info.get("bad_dids")}
        if "prompt_version" in dims:
            diff["prompt_version"] = {"from": cur["prompt_version"], "to": new["prompt_version"]}
            parts.append(f"prompt {new['prompt_version']}")
        A = info.get("arms")
        if A:
            e0, e1 = self.engagement(cur, A), self.engagement(new, A)
            dry["engagement_3d"] = {"old": e0, "new": e1,
                                    "arms": {d: {o: v for o, v in A[d]["global"].items()} for d in A},
                                    "p_best": {d: A[d]["pbest"] for d in A}, "exploring": {d: A[d]["under"] for d in A}}
        prim = self.obj["primary"]
        lift = 0.0
        if prim == "engagement_rate" and dry.get("engagement_3d", {}).get("old"):
            lift = dry["engagement_3d"]["new"] / dry["engagement_3d"]["old"] - 1
        if prim == "pickup_rate":
            for k in ("pickup_schedule_replay", "pickup_caller_id_24h"):
                if dry.get(k, {}).get("old"):
                    lift += dry[k]["new"] / dry[k]["old"] - 1
        cf = any(d in dims for d in ("cohorts", "schedule")) or any(
            "default" in diff.get(d, {}) for d in AGENT)
        changed = {k for d in AGENT for k in diff.get(d, {})}
        aff = plan.active_leads(self.db, self.id, self.now, self.w["cadence"]) if cf else \
            plan.active_leads(self.db, self.id, self.now, self.w["cadence"], new["cohorts"], changed)
        if not dry:
            dry = {"note": "no measurable replay for this change", "dims": dims}
        rat = why or f"daily plan at {when(self.now)}"
        if info.get("decay"):
            rat += f"; decay detected on {info['decay']}"
        if A:
            rat += "; " + "; ".join(f"{d}: p(best) {fmt(A[d]['pbest'])}" + (f", exploring {A[d]['under']}" if A[d]["under"] else "")
                                    for d in A)
        return {"change_summary": f"{self.id}: " + "; ".join(parts or dims),
                "diff": diff or {"dims": dims}, "affected_leads": int(aff), "dry_run": dry,
                "impact_score": round(min(1.0, max(0.05, lift / 0.1)), 3), "rationale": rat,
                "evidence": {"lift_estimate": round(lift, 4), "primary": prim}}
