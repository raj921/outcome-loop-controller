import os
import sys
import time

from .api import Api
from .gov import OPEN, Gov, log
from .ingest import Ingest, connect, meta, put
from .loop import Flow


def fresh(path, st):
    if os.path.exists(path):
        db = connect(path)
        old = meta(db, "scenario")
        cur = meta(db, "cursor", -1)
        at = meta(db, "minute", 0)
        if old == st["scenario"] and cur < st["chunks"] and at <= st["sim_minute"]:
            return db
        db.close()
        for x in ("", "-wal", "-shm"):
            if os.path.exists(path + x):
                os.rename(path + x, f"{path}.{int(time.time())}.old{x}")
    db = connect(path)
    put(db, "scenario", st["scenario"])
    return db


def run(url):
    api = Api(url)
    st = api.get("/sim/state")
    db = fresh(os.environ.get("CONTROLLER_DB", "state/controller.db"), st)
    ing, gov = Ingest(db, api), Gov(db, api)
    flows = [Flow(db, api, gov, w) for w in api.get("/workflows")]
    n, ti = ing.catch_up(), 0.0
    while True:
        st = api.get("/sim/state")
        now = st["sim_minute"]
        put(db, "credits", st["credits_remaining"])
        put(db, "minute", now)
        if st["finished"]:
            break
        t = time.time()
        for f in flows:
            f.tick(now)
        td = time.time() - t
        pend = sum(len(gov.rows(f.id, *OPEN)) for f in flows)
        db.execute("insert or replace into ticks values(?,?,?,?,?,?,?)",
                   (now, time.time(), n, ti, td, st["credits_remaining"], pend))
        if st["credits_remaining"] < 20 and now % 1440 == 0:
            log(db, now, None, "alert", f"credits low: {st['credits_remaining']}")
        r = api.post("/sim/advance", {"minutes": 60})
        if r.status_code not in (200, 409):
            raise RuntimeError(f"advance failed {r.status_code} {r.text[:200]}")
        t = time.time()
        n = ing.catch_up()
        ti = time.time() - t
    print(f"finished at {st['ts']}, credits left {st['credits_remaining']}")


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print("usage: python -m controller <sim_url> | why <wf> [D3 14:00] | heard <person|lead> | view [wf] | status | unban <wf> <did>")
        return
    if a[0] in ("why", "heard", "view", "status", "unban"):
        from . import report
        db = connect(os.environ.get("CONTROLLER_DB", "state/controller.db"))
        return getattr(report, a[0])(db, *a[1:])
    run(a[0])


if __name__ == "__main__":
    main(sys.argv[1:])
