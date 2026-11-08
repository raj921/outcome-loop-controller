import json

OPEN = ("new", "pending", "approved")
SENT = ("new", "pending", "approved", "applied", "rejected", "expired", "lapsed", "stale")


def log(db, at, wf, kind, msg, data=None):
    db.execute("insert into log(at, wf, kind, msg, data) values(?,?,?,?,?)",
               (at, wf, kind, msg, None if data is None else json.dumps(data, default=str)))


class Gov:
    def __init__(self, db, api):
        self.db, self.api = db, api

    def rows(self, wf, *status):
        q = "select * from props where wf=?"
        if status:
            q += f" and status in ({','.join('?' * len(status))})"
        return self.db.execute(q + " order by made", (wf, *status)).fetchall()

    def set(self, pid, **kw):
        cols = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"update props set {cols} where pid=?", (*kw.values(), pid))

    def sent24(self, wf, now):
        return self.db.execute(
            f"select count(*) from props where wf=? and kind='approval' and made>? and status in ({','.join('?' * len(SENT))})",
            (wf, now - 1440, *SENT)).fetchone()[0]

    def send(self, wf, kind, tag, now, base, cfg, prev, dims, body):
        pid = f"{wf}-{now}-{tag}"
        if self.db.execute("select 1 from props where pid=?", (pid,)).fetchone():
            return pid
        self.db.execute("insert into props(pid, wf, kind, tag, status, base, cfg, prev, dims, body, made) "
                        "values(?,?,?,?,?,?,?,?,?,?,?)",
                        (pid, wf, kind, tag, "new", base, json.dumps(cfg), json.dumps(prev), json.dumps(dims),
                         json.dumps(body, default=str), now))
        log(self.db, now, wf, "proposed", f"{kind} {pid}: {body['change_summary']}",
            {"dims": dims, "impact": body["impact_score"], "affected": body["affected_leads"]})
        self.push(self.one(pid), now)
        return pid

    def one(self, pid):
        return self.db.execute("select * from props where pid=?", (pid,)).fetchone()

    def push(self, r, now):
        body = json.loads(r["body"])
        cfg = json.loads(r["cfg"])
        if r["kind"] == "approval":
            x = self.api.post("/approvals", {**body, "proposal_id": r["pid"], "workflow_id": r["wf"],
                                             "base_version": r["base"], "proposed_config": cfg})
            if x.status_code == 200:
                self.set(r["pid"], status="pending", aid=x.json()["approval_id"])
                return
        else:
            x = self.api.put(f"/workflows/{r['wf']}/config",
                             {"proposal_id": r["pid"], "base_version": r["base"], "proposed_config": cfg,
                              "rationale": body["rationale"], "evidence": body.get("evidence")})
            if x.status_code == 200:
                self.set(r["pid"], status="applied", ver=x.json()["version"], done=now)
                log(self.db, now, r["wf"], "applied", f"auto {r['pid']} -> v{x.json()['version']}")
                return
        err = x.json().get("error") if x.headers.get("content-type", "").startswith("application/json") else None
        if err == "duplicate_proposal_id" and self.find(r, now):
            return
        self.set(r["pid"], status="failed", note=x.text[:2000])
        log(self.db, now, r["wf"], "send_failed", f"{r['pid']} {x.status_code} {err}", {"detail": x.text[:2000]})

    def find(self, r, now):
        if r["kind"] == "approval":
            for a in self.api.get("/approvals", params={"workflow_id": r["wf"]}):
                if a["proposal_id"] == r["pid"]:
                    self.set(r["pid"], status=a["status"] if a["status"] != "applied" else "approved",
                             aid=a["approval_id"])
                    return True
            return False
        for v in self.api.get(f"/workflows/{r['wf']}/config/history"):
            if v["proposal_id"] == r["pid"]:
                self.set(r["pid"], status="applied", ver=v["version"], done=now)
                return True
        return False

    def sync(self, wf, now):
        for r in self.rows(wf, *OPEN):
            if r["status"] == "new" and not self.find(r, now):
                self.push(r, now)
            r = self.one(r["pid"])
            if r["status"] == "pending":
                a = self.api.get(f"/approvals/{r['aid']}")
                if a["status"] != "pending":
                    self.set(r["pid"], status=a["status"] if a["status"] != "applied" else "approved",
                             note=json.dumps({"reasons": a.get("reasons"), "decided_at": a.get("decided_at")}))
                    log(self.db, now, wf, "decided", f"{r['pid']} {r['aid']} {a['status']}",
                        {"reasons": a.get("reasons"), "decided_at": a.get("decided_at")})
                r = self.one(r["pid"])
            if r["status"] == "approved":
                self.apply(r, now)

    def apply(self, r, now):
        x = self.api.post(f"/workflows/{r['wf']}/apply", {"approval_id": r["aid"]})
        if x.status_code == 200:
            self.set(r["pid"], status="applied", ver=x.json()["version"], done=now)
            log(self.db, now, r["wf"], "applied", f"{r['pid']} {r['aid']} -> v{x.json()['version']}")
            return
        err = x.json().get("error")
        if err == "not_approved":
            for v in self.api.get(f"/workflows/{r['wf']}/config/history"):
                if v["approval_id"] == r["aid"]:
                    self.set(r["pid"], status="applied", ver=v["version"], done=now)
                    return
            st = self.api.get(f"/approvals/{r['aid']}")["status"]
            self.set(r["pid"], status=st)
            return
        st = {"approval_lapsed": "lapsed", "stale_base_version": "stale"}.get(err, "failed")
        self.set(r["pid"], status=st, note=x.text[:2000])
        log(self.db, now, r["wf"], st, f"{r['pid']} {r['aid']} apply refused: {err}")
