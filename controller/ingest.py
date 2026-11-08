import json
import os
import sqlite3
from datetime import date

D0 = date(2027, 1, 4)
DAY = 1440

SCHEMA = """
create table if not exists meta(k text primary key, v text);
create table if not exists leads(event_id integer primary key, lead_id text, person_id text, wf text,
  camp text, day int, fk text);
create table if not exists calls(event_id integer primary key, ts text, wf text, camp text, lead_id text,
  person_id text, att int, ver int, cohort text, w text, v text, d text, p text, conn int, eng int,
  disp text, flag int);
create table if not exists misc(event_id integer primary key, type text, ts text, at int, wf text, body text);
create table if not exists hours(wf text, day int, hour int, fk text, dials int, conn int, eng int,
  primary key(wf, day, hour, fk));
create table if not exists arms(wf text, day int, fk text, w text, v text, conn int, eng int,
  primary key(wf, day, fk, w, v));
create table if not exists dids(wf text, day int, hour int, d text, dials int, conn int,
  primary key(wf, day, hour, d));
create table if not exists prompts(wf text, day int, hour int, p text, conn int, eng int, flags int,
  primary key(wf, day, hour, p));
create table if not exists vh(wf text, day int, hour int, dim text, o text, conn int, eng int,
  primary key(wf, day, hour, dim, o));
create table if not exists camps(wf text, camp text, fk text, day int, leads int, eng int,
  primary key(wf, camp, fk));
create table if not exists props(pid text primary key, wf text, kind text, tag text, status text, base int,
  cfg text, prev text, dims text, body text, aid text, made int, done int, ver int, note text);
create table if not exists log(id integer primary key, at int, wf text, kind text, msg text, data text);
create table if not exists incidents(id integer primary key, wf text, kind text, status text, opened int,
  closed int, data text);
create table if not exists ticks(at int primary key, wall real, events int, ingest_s real, decide_s real,
  credits real, pending int);
create index if not exists props_wf on props(wf, status);
create index if not exists misc_wf on misc(wf, type);
create index if not exists calls_camp on calls(camp);
"""

UPS = {
    "hours": "insert into hours values(?,?,?,?,?,?,?) on conflict(wf, day, hour, fk) do update set "
             "dials=dials+excluded.dials, conn=conn+excluded.conn, eng=eng+excluded.eng",
    "arms": "insert into arms values(?,?,?,?,?,?,?) on conflict(wf, day, fk, w, v) do update set "
            "conn=conn+excluded.conn, eng=eng+excluded.eng",
    "dids": "insert into dids values(?,?,?,?,?,?) on conflict(wf, day, hour, d) do update set "
            "dials=dials+excluded.dials, conn=conn+excluded.conn",
    "prompts": "insert into prompts values(?,?,?,?,?,?,?) on conflict(wf, day, hour, p) do update set "
               "conn=conn+excluded.conn, eng=eng+excluded.eng, flags=flags+excluded.flags",
    "vh": "insert into vh values(?,?,?,?,?,?,?) on conflict(wf, day, hour, dim, o) do update set "
          "conn=conn+excluded.conn, eng=eng+excluded.eng",
    "camps": "insert into camps values(?,?,?,?,?,?) on conflict(wf, camp, fk) do update set "
             "leads=leads+excluded.leads, eng=eng+excluded.eng",
}


def connect(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("pragma journal_mode=wal")
    db.execute("pragma synchronous=normal")
    db.executescript(SCHEMA)
    return db


def meta(db, k, default=None):
    r = db.execute("select v from meta where k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else default


def put(db, k, v):
    db.execute("insert or replace into meta values(?,?)", (k, json.dumps(v)))


def minute(ts, cache={}):
    d = cache.get(ts[:10])
    if d is None:
        d = cache[ts[:10]] = (date.fromisoformat(ts[:10]) - D0).days
    return d * DAY + int(ts[11:13]) * 60 + int(ts[14:16])


class Ingest:
    def __init__(self, db, api):
        self.db, self.api = db, api
        self.lead, self.cday, self.byc = {}, {}, {}
        for camp, day in db.execute("select distinct camp, day from camps"):
            self.cday[camp] = day
        top = db.execute("select max(day) from leads").fetchone()[0]
        if top is not None:
            for lid, fk, camp in db.execute("select lead_id, fk, camp from leads where day>=?", (top - 7,)):
                self.lead[lid] = fk
                self.byc.setdefault(camp, []).append(lid)

    def catch_up(self):
        cur = meta(self.db, "cursor", -1)
        todo = []
        for kind in ("history", "events"):
            todo += self.api.get("/events/chunks", params={"kind": kind, "after": cur})
        n = 0
        for c in sorted(todo, key=lambda c: c["chunk"]):
            n += self.eat(c)
        return n

    def evict(self, day):
        for camp in [c for c in self.byc if self.cday.get(c, day) < day - 7]:
            for lid in self.byc.pop(camp):
                self.lead.pop(lid, None)

    def eat(self, c):
        if c["chunk"] <= meta(self.db, "cursor", -1):
            return 0
        hist = c["kind"] == "history"
        H, A, D, P, C, V = {}, {}, {}, {}, {}, {}
        leads, calls, misc = [], [], []
        for ln in self.api.text(f"/events/chunks/{c['chunk']}").splitlines():
            if not ln:
                continue
            e = json.loads(ln)
            t = e["type"]
            if t == "call":
                m = minute(e["ts"])
                dy, hr = divmod(m, DAY)
                hr //= 60
                wf, v = e["workflow_id"], e["variant"]
                fk = self.lead.get(e["lead_id"], "?")
                cn, en = int(e["connected"]), int(e["engaged"])
                x = H.setdefault((wf, dy, hr, fk), [0, 0, 0])
                x[0] += 1
                x[1] += cn
                x[2] += en
                x = D.setdefault((wf, dy, hr, v["caller_id"]), [0, 0])
                x[0] += 1
                x[1] += cn
                fl = 0
                if cn:
                    fl = int(e["qa"]["hallucination_flag"])
                    x = A.setdefault((wf, dy, fk, v["welcome_message"], v["voice"]), [0, 0])
                    x[0] += 1
                    x[1] += en
                    x = P.setdefault((wf, dy, hr, v["prompt_version"]), [0, 0, 0])
                    x[0] += 1
                    x[1] += en
                    x[2] += fl
                    for dim in ("welcome_message", "voice"):
                        x = V.setdefault((wf, dy, hr, dim, v[dim]), [0, 0])
                        x[0] += 1
                        x[1] += en
                if en:
                    camp = e["campaign_id"]
                    C.setdefault((wf, camp, fk, self.cday.get(camp, dy)), [0, 0])[1] += 1
                if not hist:
                    calls.append((e["event_id"], e["ts"], wf, e["campaign_id"], e["lead_id"], e["person_id"],
                                  e["attempt_no"], e["config_version"], e["cohort_id"], v["welcome_message"],
                                  v["voice"], v["caller_id"], v["prompt_version"], cn, en, e["disposition"], fl))
            elif t == "lead":
                f = e["features"]
                fk = f"{f['lang']}|{f['city_tier']}|{f['age_band']}|{f['value_band']}"
                lid, camp, wf = e["lead_id"], e["campaign_id"], e["workflow_id"]
                self.lead[lid] = fk
                self.byc.setdefault(camp, []).append(lid)
                dy = self.cday.get(camp, minute(e["ts"]) // DAY)
                C.setdefault((wf, camp, fk, dy), [0, 0])[0] += 1
                leads.append((e["event_id"], lid, e["person_id"], wf, camp, dy, fk))
            else:
                m = minute(e["ts"])
                if t == "campaign_created":
                    self.cday[e["campaign_id"]] = m // DAY
                    self.evict(m // DAY)
                misc.append((e["event_id"], t, e["ts"], m, e.get("workflow_id"), ln))
        db = self.db
        db.execute("begin")
        try:
            db.executemany("insert or ignore into leads values(?,?,?,?,?,?,?)", leads)
            db.executemany("insert or ignore into calls values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", calls)
            db.executemany("insert or ignore into misc values(?,?,?,?,?,?)", misc)
            db.executemany(UPS["hours"], [(*k, *v) for k, v in H.items()])
            db.executemany(UPS["arms"], [(*k, *v) for k, v in A.items()])
            db.executemany(UPS["dids"], [(*k, *v) for k, v in D.items()])
            db.executemany(UPS["prompts"], [(*k, *v) for k, v in P.items()])
            db.executemany(UPS["vh"], [(*k, *v) for k, v in V.items()])
            db.executemany(UPS["camps"], [(wf, camp, fk, dy, *v) for (wf, camp, fk, dy), v in C.items()])
            put(db, "cursor", c["chunk"])
            put(db, "last_event_id", c["last_event_id"])
            if hist:
                put(db, "history_last_event_id", c["last_event_id"])
            db.execute("commit")
        except BaseException:
            db.execute("rollback")
            raise
        return c["events"]
