import copy
import json

import pytest

from controller import plan
from controller.gov import Gov
from controller.ingest import Ingest, connect, meta
from controller.loop import Flow
from controller.stats import norm, pbest, ptail, tv


class Resp:
    def __init__(self, code, body):
        self.status_code, self.body = code, body
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(body)

    def json(self):
        return self.body


class FakeApi:
    def __init__(self, chunks=None):
        self.chunks = chunks or {}
        self.approvals, self.history, self.calls = {}, [], []

    def get(self, path, params=None):
        self.calls.append(("GET", path))
        if path == "/events/chunks":
            after = params["after"]
            return [m for m, _ in self.chunks.values() if m["kind"] == params["kind"] and m["chunk"] > after]
        if path == "/approvals":
            return list(self.approvals.values())
        if path.startswith("/approvals/"):
            return self.approvals[path.split("/")[-1]]
        if path.endswith("/config/history"):
            return self.history
        raise KeyError(path)

    def text(self, path):
        return self.chunks[int(path.split("/")[-1])][1]

    def post(self, path, body):
        self.calls.append(("POST", path))
        if path == "/approvals":
            if any(a["proposal_id"] == body["proposal_id"] for a in self.approvals.values()):
                return Resp(409, {"error": "duplicate_proposal_id"})
            aid = f"apr_{len(self.approvals) + 1:05d}"
            self.approvals[aid] = {"approval_id": aid, "proposal_id": body["proposal_id"], "status": "pending"}
            return Resp(200, self.approvals[aid])
        if path.endswith("/apply"):
            a = self.approvals[body["approval_id"]]
            if a["status"] != "approved":
                return Resp(409, {"error": "not_approved"})
            a["status"] = "applied"
            self.history.append({"version": len(self.history) + 2, "approval_id": a["approval_id"],
                                 "proposal_id": a["proposal_id"]})
            return Resp(200, {"version": len(self.history) + 1})
        raise KeyError(path)


def ev(i, t, **kw):
    return json.dumps({"event_id": i, "type": t, "ts": "2027-01-04T10:05:00+05:30", **kw})


def chunk_lines():
    lines = [ev(1, "campaign_created", workflow_id="w", campaign_id="w:c1", leads=2, tenant_id="t",
                config_version_at_creation=1),
             ev(2, "lead", workflow_id="w", campaign_id="w:c1", lead_id="w:l1", person_id="w:p1",
                features={"lang": "hi", "city_tier": "1", "age_band": "60+", "value_band": "mid"})]
    for i, (cn, en) in enumerate([(1, 1), (1, 0), (0, 0)]):
        lines.append(ev(3 + i, "call", tenant_id="t", workflow_id="w", campaign_id="w:c1", lead_id="w:l1",
                        person_id="w:p1", attempt_no=i + 1, campaign_day_index=0, config_version=1,
                        cohort_id="default", connected=bool(cn), engaged=bool(en), disposition="x",
                        duration_s=1, turns=1,
                        variant={"welcome_message": "W1", "voice": "V1", "caller_id": "D1", "prompt_version": "P1"},
                        qa={"hallucination_flag": False, "flow_adherence": 0.9} if cn else None))
    return "\n".join(lines) + "\n"


def test_norm_is_exact_and_stable():
    for d in [{"a": 1, "b": 1, "c": 1}, {"x": 0.6, "y": 0.2, "z": 0.2}, {"a": 0.97, "b": 0.01, "c": 0.02}]:
        n = norm(d)
        assert sum(n.values()) == 1.0
        assert norm(n) == n
        assert tv(n, d) < 0.002


def test_stats():
    assert ptail(0, 3) == 1.0
    assert abs(ptail(10, 3.0) - 0.0011025) < 1e-6
    assert ptail(5, 0) == 0.0
    a = pbest([50, 40], [50, 60])
    assert a[0] > 0.9 and list(a) == list(pbest([50, 40], [50, 60]))


def test_cohort_first_match():
    cs = [{"id": "60+_hi", "where": {"age_band": ["60+"], "lang": ["hi"]}}, {"id": "60+", "where": {"age_band": ["60+"]}}]
    assert plan.cohort_of(cs, "hi|1|60+|mid") == "60+_hi"
    assert plan.cohort_of(cs, "ta|1|60+|mid") == "60+"
    assert plan.cohort_of(cs, "ta|1|18-30|mid") == "default"
    assert plan.cohort_of(cs, "?") == "default"


def test_ramp_caps_thin_arms():
    t = plan.ramp({"V1": 0.03, "V2": 0.9, "V4": 0.07}, {"V1": 1000, "V2": 60, "V4": 1500})
    assert t["V2"] == pytest.approx(plan.CAP, abs=0.002) and sum(t.values()) == 1.0


def test_ingest_is_idempotent(tmp_path):
    db = connect(str(tmp_path / "c.db"))
    api = FakeApi({0: ({"chunk": 0, "kind": "events", "events": 5, "last_event_id": 5}, chunk_lines())})
    ing = Ingest(db, api)
    assert ing.catch_up() == 5
    assert ing.catch_up() == 0
    assert ing.eat({"chunk": 0, "kind": "events", "events": 5, "last_event_id": 5}) == 0
    assert tuple(db.execute("select sum(dials), sum(conn), sum(eng) from hours").fetchone()) == (3, 2, 1)
    assert db.execute("select count(*) from calls").fetchone()[0] == 3
    assert tuple(db.execute("select leads, eng from camps").fetchone()) == (1, 1)
    assert meta(db, "cursor") == 0


def seed(db, rows):
    db.executemany("insert into dids values(?,?,?,?,?,?)", rows)


def test_bad_did_is_pulled_and_new_did_must_earn_share(tmp_path):
    db = connect(str(tmp_path / "c.db"))
    now = 2 * 1440 + 15 * 60
    seed(db, [("w", 2, h, d, 100, c) for h in range(9, 15) for d, c in (("D1", 30), ("D2", 30), ("D3", 10))])
    t, bad, rate = plan.dids(db, "w", ["D1", "D2", "D3", "D4"], now)
    assert bad == ["D3"] and "D3" not in t
    assert t["D4"] == pytest.approx(plan.PROBE, abs=0.002)
    t, bad, _ = plan.dids(db, "w", ["D1", "D2", "D3", "D4"], now, {"D3": now})
    assert "D3" not in t and not bad


def test_hallucination_tiers(tmp_path):
    db = connect(str(tmp_path / "c.db"))
    now = 5 * 1440 + 15 * 60
    db.execute("insert into prompts values('w', 1, 10, 'P1', 5000, 3000, 75)")
    db.execute("insert into prompts values('w', 5, 12, 'P1', 600, 300, 20)")
    assert not plan.halluc(db, "w", "P1", now, 0.015)[0]
    db.execute("insert into prompts values('w', 5, 12, 'P2', 300, 150, 15)")
    assert plan.halluc(db, "w", "P2", now, 0.015)[0]
    db.execute("insert into prompts values('w', 5, 13, 'P3', 300, 150, 6)")
    assert not plan.halluc(db, "w", "P3", now, 0.015)[0]


def flow(db, api, shift=0.2):
    w = {"workflow_id": "w", "governance": {"auto_apply": {"enabled": True, "allowed_dims": ["caller_id"],
                                                           "max_shift": shift},
                                            "approver_hours": [10, 19], "max_requests_per_24h": 3,
                                            "min_validation_pass_rate": 0.97},
         "objective": {"primary": "engagement_rate", "guardrail": {"pickup_rate_max_drop": 0.02}},
         "dialling_window": [9, 21], "options": {}, "cadence": [2, 2]}
    f = Flow(db, api, Gov(db, api), w)
    f.cfg = {"cohorts": [], "prompt_version": "P1", "schedule": {"hour_weights": {}, "lead_preferred_hour": {}},
             "allocations": {"default": {"welcome_message": {"W1": 1.0}, "voice": {"V1": 1.0},
                                         "caller_id": {"D1": 0.5, "D2": 0.5}}}}
    return f


def test_step_respects_max_shift(tmp_path):
    f = flow(connect(str(tmp_path / "c.db")), FakeApi())
    new = copy.deepcopy(f.cfg)
    new["allocations"]["default"]["caller_id"] = {"D3": 1.0}
    out = f.step(new, ["caller_id"])
    x = tv(f.cfg["allocations"]["default"]["caller_id"], out["allocations"]["default"]["caller_id"])
    assert 0.15 < x <= 0.2
    assert sum(out["allocations"]["default"]["caller_id"].values()) == 1.0


def test_gov_survives_crash_between_send_and_record(tmp_path):
    db = connect(str(tmp_path / "c.db"))
    api = FakeApi()
    g = Gov(db, api)
    body = {"change_summary": "s", "diff": {"a": 1}, "affected_leads": 1, "dry_run": {"a": 1},
            "impact_score": 0.1, "rationale": "r"}
    pid = g.send("w", "approval", "plan", 660, 1, {"x": 1}, {"x": 0}, ["voice"], body)
    db.execute("update props set status='new', aid=null where pid=?", (pid,))
    g.sync("w", 720)
    assert len(api.approvals) == 1
    r = g.one(pid)
    assert r["status"] == "pending" and r["aid"] == "apr_00001"
    api.approvals["apr_00001"]["status"] = "approved"
    g.sync("w", 780)
    db.execute("update props set status='approved' where pid=?", (pid,))
    g.sync("w", 840)
    assert g.one(pid)["status"] == "applied"
    assert sum(1 for m, p in api.calls if p.endswith("/apply")) == 2
    assert len(api.history) == 1


def test_steady_weaker_did_is_not_banned_but_sudden_drop_is(tmp_path):
    db = connect(str(tmp_path / "c.db"))
    now = 4 * 1440 + 15 * 60
    hist = [("w", 2, h, d, 100, c) for h in range(9, 21) for d, c in (("D1", 30), ("D2", 30), ("D3", 18))]
    seed(db, hist + [("w", 4, h, d, 100, c) for h in range(9, 15) for d, c in (("D1", 30), ("D2", 30), ("D3", 18))])
    assert plan.dids(db, "w", ["D1", "D2", "D3"], now)[1] == []
    db.execute("delete from dids where day=4 and d='D3'")
    seed(db, [("w", 4, h, "D3", 100, 8) for h in range(9, 15)])
    assert plan.dids(db, "w", ["D1", "D2", "D3"], now)[1] == ["D3"]


def test_guard_rarely_moves_on_noise_and_never_away_from_a_true_best():
    import numpy as np
    rng = np.random.default_rng(3)
    cur = {"A": 0.8, "B": 0.1, "C": 0.1}
    aa = harm = 0
    for _ in range(300):
        e = rng.binomial(1000, 0.55, 3)
        t, _, p = plan.choose([1 + x for x in e], [1001 - x for x in e], ["A", "B", "C"], [], cur)
        aa += p >= plan.SURE
        e = rng.binomial(1000, np.array([0.58, 0.55, 0.55]))
        t, _, p = plan.choose([1 + x for x in e], [1001 - x for x in e], ["A", "B", "C"], [], cur)
        true = np.array([0.58, 0.55, 0.55])
        worse = np.array([t[o] for o in "ABC"]) @ true < 0.99 * (np.array([cur[o] for o in "ABC"]) @ true)
        harm += p >= plan.SURE and worse
    assert aa / 300 <= 0.12
    assert harm / 300 <= 0.02
