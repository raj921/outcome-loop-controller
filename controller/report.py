import json

from . import plan
from .ingest import DAY, meta, minute
from .loop import fmt, when
from .plan import dist


def parse(s):
    d, hm = s.split()
    h, m = hm.split(":")
    return int(d.lstrip("Dd")) * DAY + int(h) * 60 + int(m)


def prop(db, pid):
    return db.execute("select * from props where pid=?", (pid,)).fetchone() if pid else None


def why(db, wf, *at):
    t = parse(" ".join(at)) if at else None
    rows = [json.loads(r["body"]) | {"at": r["at"]} for r in db.execute(
        "select at, body from misc where wf=? and type='config_changed' and at>=0 order by event_id", (wf,))]
    if t is not None:
        last = max((r["at"] for r in rows if r["at"] <= t), default=None)
        rows = [r for r in rows if r["at"] == last] or rows[:1]
    if not rows:
        print(f"{wf}: no config changes since D0")
    for e in rows:
        print(f"\n{when(e['at'])}  v{e['version']}  by {e['actor']}  dims={e['changed_dims']}")
        p = prop(db, e["proposal_id"])
        if p is None:
            print("  not ours: supervisor edit, left alone for 48h" if e["actor"] == "supervisor" else "")
            continue
        b, note = json.loads(p["body"]), json.loads(p["note"] or "{}")
        print(f"  proposal {p['pid']} ({p['kind']}, {p['tag']}) made {when(p['made'])}")
        print(f"  summary: {b['change_summary']}")
        print(f"  why: {b['rationale']}")
        print(f"  impact {b['impact_score']}, affected leads {b['affected_leads']}, evidence {b.get('evidence')}")
        if p["aid"]:
            print(f"  approved: {p['aid']} decided {note.get('decided_at', '?')} reasons {note.get('reasons')}")
        else:
            print("  auto-applied within policy")
        r = plan.compare(db, wf, e["at"])
        print(f"  after: {r['connected']} connected; pickup x{r['pickup_ratio'] or 0:.3f} (z {r['pickup_z']:.1f}), "
              f"engagement x{r['engage_ratio'] or 0:.3f} (z {r['engage_z']:.1f}) vs same hours before")
        if "verified" in note:
            v = note["verified"]
            print(f"  verified {when(v['at'])}: breach {v['breach'] or 'none'}")
        for l in db.execute("select at, kind, msg from log where wf=? and at>? and at<=? and kind in "
                            "('verified','incident','supervisor_edit','proposed','decided') order by id",
                            (wf, e["at"], e["at"] + DAY)):
            print(f"    {when(l['at'])} {l['kind']}: {l['msg']}")


def heard(db, who, *day):
    q = "select * from calls where (person_id=? or lead_id=?)"
    args = [who, who]
    if day:
        q += " and ts like ?"
        args.append(f"%{day[0]}%")
    rows = db.execute(q + " order by event_id", args).fetchall()
    if not rows:
        print(f"no calls for {who}")
    seen = {}
    for r in rows:
        print(f"{when(minute(r['ts']))} {r['lead_id']} attempt {r['att']} v{r['ver']} cohort {r['cohort']}: "
              f"welcome {r['w']} voice {r['v']} caller {r['d']} prompt {r['p']} -> {r['disp']}")
        seen[(r["wf"], r["ver"])] = 1
    for wf, v in seen:
        c = meta(db, f"cfg:{wf}:{v}") or {}
        e = db.execute("select body from misc where wf=? and type='config_changed' and body like ?",
                       (wf, f'%"version":{v},%')).fetchone()
        e = json.loads(e["body"]) if e else {"actor": c.get("actor", "business_default"), "proposal_id": None}
        p = prop(db, e.get("proposal_id"))
        print(f"\n{wf} v{v}: set by {e['actor']}" + (f", proposal {p['pid']}" if p else ""))
        if p:
            b = json.loads(p["body"])
            print(f"  {b['change_summary']}\n  why: {b['rationale']}\n  approval: {p['aid'] or 'auto-apply within policy'}")


def kpi(db, wf, d):
    r = db.execute("select sum(dials), sum(conn), sum(eng) from hours where wf=? and day=?", (wf, d)).fetchone()
    n, c, e = (x or 0 for x in r)
    return f"pickup {c / n:.1%} engagement {e / c:.1%} ({n} dials)" if n and c else "no calls"


def view(db, *wf):
    now = meta(db, "minute", 0)
    wfs = wf or [r[0] for r in db.execute("select distinct wf from hours")]
    for w in wfs:
        v = meta(db, f"cfg:{w}")
        cfg = (meta(db, f"cfg:{w}:{v}") or {}).get("config")
        print(f"\n== {w}  at {when(now)}  config v{v}")
        print(f"  today:     {kpi(db, w, now // DAY)}")
        print(f"  yesterday: {kpi(db, w, now // DAY - 1)}")
        coh = meta(db, f"cohorts:{w}") or []
        if cfg:
            opts = {d: sorted({o for k in cfg["allocations"] for o in (cfg["allocations"][k].get(d) or {})}
                              | set(dist(cfg, "default", d))) for d in ("welcome_message", "voice")}
            A = plan.arms(db, w, opts, coh if cfg["cohorts"] == coh else [], now, cfg)
            for d, x in A.items():
                print(f"  testing {d}: live {fmt(dist(cfg, 'default', d))}")
                for o, (n, e) in sorted(x["global"].items()):
                    pb = x["pbest"].get(o)
                    print(f"    {o}: {n:.0f} recent connected, engaged {e / n if n else 0:.1%}"
                          + (f", p(best) {pb:.2f}" if pb is not None else ", still exploring"))
                over = [k for k in cfg["allocations"] if k != "default" and d in cfg["allocations"][k]]
                if over:
                    print(f"    cohort overrides: {', '.join(over)}")
            print(f"  caller IDs live: {fmt(dist(cfg, 'default', 'caller_id'))}; prompt {cfg['prompt_version']}")
            for d, at in (meta(db, f"banned:{w}") or {}).items():
                print(f"  caller ID {d} pulled at {when(at)} for low pickup; clear with: python -m controller unban {w} {d}")
        for p in db.execute("select * from props where wf=? and status in ('new','pending','approved')", (w,)):
            b = json.loads(p["body"])
            print(f"  WAITING ON YOU: {p['pid']} impact {b['impact_score']}: {b['change_summary']}")
        for p in db.execute("select * from props where wf=? and status='applied' and done>=?", (w, now - now % DAY)):
            print(f"  changed today {when(p['done'])}: {json.loads(p['body'])['change_summary']}")
        for i in db.execute("select * from incidents where wf=? and (closed is null or closed>=?)", (w, now - DAY)):
            print(f"  incident {i['kind']} {i['status']} since {when(i['opened'])}")


def status(db):
    t = db.execute("select * from ticks order by at desc limit 24").fetchall()
    if not t:
        print("no ticks yet")
        return
    last = t[0]
    ev = sum(r["events"] for r in t)
    ing = sum(r["ingest_s"] for r in t) or 1e-9
    print(f"last tick {when(last['at'])}, credits {last['credits']}, open proposals {last['pending']}")
    print(f"last {len(t)} ticks: {ev} events, ingest {ev / ing:.0f} ev/s, decide avg {sum(r['decide_s'] for r in t) / len(t):.2f}s")
    n = db.execute("select count(*) from log where kind in ('proposed','applied','decided') and at>?",
                   (last["at"] - DAY,)).fetchone()[0]
    print(f"decisions in last 24h: {n}")
    for l in db.execute("select at, wf, msg from log where kind in ('alert','send_failed','lapsed','stale') "
                        "and at>? order by id", (last["at"] - DAY,)):
        print(f"  ALERT {when(l['at'])} {l['wf'] or ''}: {l['msg']}")


def unban(db, wf, did):
    b = meta(db, f"banned:{wf}") or {}
    b.pop(did, None)
    db.execute("insert or replace into meta values(?,?)", (f"banned:{wf}", json.dumps(b)))
    print(f"{did} cleared for {wf}; it comes back as a 5% probe")
