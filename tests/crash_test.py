import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sim(scenario, run):
    p = port()
    proc = subprocess.Popen([sys.executable, "-m", "sim", "serve", "--scenario", scenario, "--run-dir", run,
                             "--port", str(p), "--force"], cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{p}"
    for _ in range(900):
        try:
            if httpx.get(url + "/health").status_code == 200:
                return proc, url
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    sys.exit("FAIL: simulator did not start")


def ctl(url, db):
    return subprocess.Popen(["./run.sh", url], cwd=ROOT, env={**os.environ, "CONTROLLER_DB": db},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def check(url, db, out):
    c = sqlite3.connect(db)
    q = lambda s, *a: c.execute(s, a).fetchone()[0]
    st = httpx.get(url + "/sim/state").json()
    fails = []
    hist = json.loads(q("select v from meta where k='history_last_event_id'"))
    stored = q("select count(*) from (select event_id from calls union all select event_id from misc where "
               "event_id>? union all select event_id from leads where event_id>?)", hist, hist)
    distinct = q("select count(distinct event_id) from (select event_id from calls union all select event_id "
                 "from misc where event_id>? union all select event_id from leads where event_id>?)", hist, hist)
    want = st["last_event_id"] - hist
    out.append(f"events after history: stored {stored}, distinct {distinct}, simulator emitted {want}")
    if not stored == distinct == want:
        fails.append("events lost or duplicated")
    hc = 0
    for ch in httpx.get(url + "/events/chunks", params={"kind": "history"}).json():
        hc += httpx.get(f"{url}/events/chunks/{ch['chunk']}", timeout=300).text.count('"type":"call"')
    hr = q("select sum(dials) from hours where day<0")
    ev = q("select sum(dials) from hours where day>=0")
    out.append(f"history calls in rollups {hr} vs {hc} counted from chunks; D0+ rollups {ev} vs {q('select count(*) from calls')} rows")
    if hr != hc or ev != q("select count(*) from calls"):
        fails.append("rollups disagree with raw events")
    for w in httpx.get(url + "/workflows").json():
        wf = w["workflow_id"]
        hist_v = httpx.get(f"{url}/workflows/{wf}/config/history").json()
        pids = [v["proposal_id"] for v in hist_v if v["proposal_id"]]
        if len(pids) != len(set(pids)):
            fails.append(f"{wf}: a proposal was applied twice")
        mine = {r[0]: (r[1], r[2]) for r in c.execute("select pid, status, ver from props where wf=?", (wf,))}
        stale = sum(1 for s, _ in mine.values() if s in ("stale", "lapsed"))
        for v in hist_v:
            if v["proposal_id"] and mine.get(v["proposal_id"], (None,))[0] != "applied":
                fails.append(f"{wf}: v{v['version']} applied on the server but not recorded as applied here")
        for a in httpx.get(url + "/approvals", params={"workflow_id": wf}).json():
            if a["proposal_id"] not in mine:
                fails.append(f"{wf}: approval {a['approval_id']} unknown to the controller")
            if a["status"] == "approved" and mine.get(a["proposal_id"], (None,))[0] not in ("stale", "lapsed"):
                fails.append(f"{wf}: approval {a['approval_id']} approved but never applied")
        out.append(f"{wf}: {len(pids)} controller versions applied, {len(mine)} proposals tracked, {stale} went stale and were re-planned, "
                   f"cohorts kept: {q('select count(*) from meta where k=?', 'cohorts:' + wf) == 1}")
    return fails


def main(scenario="scenarios/public_02_incidents.yaml", kills=(900, 3300, 5160, 5220, 8000, 11000)):
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "c.db")
        proc, url = sim(scenario, os.path.join(tmp, "run"))
        out = [f"# Crash recovery: {os.path.basename(scenario)}", ""]
        try:
            t0 = time.time()
            for k in kills:
                p = ctl(url, db)
                while httpx.get(url + "/sim/state").json()["sim_minute"] < k:
                    if p.poll() is not None:
                        sys.exit("FAIL: controller exited before the kill point")
                    time.sleep(0.01)
                p.send_signal(signal.SIGKILL)
                p.wait()
                m = httpx.get(url + "/sim/state").json()["sim_minute"]
                out.append(f"- SIGKILL at sim minute {m} (D{m // 1440} {m % 1440 // 60:02d}:{m % 60:02d}), "
                           f"{time.time() - t0:.0f}s wall")
            p = ctl(url, db)
            if p.wait(timeout=1800) != 0:
                sys.exit("FAIL: final controller run exited nonzero")
            if not httpx.get(url + "/sim/state").json()["finished"]:
                sys.exit("FAIL: scenario not finished")
            out += ["", f"finished after {len(kills)} kills and {len(kills) + 1} starts", ""]
            fails = check(url, db, out)
            out += ["", "RESULT: " + ("PASS" if not fails else "FAIL " + "; ".join(fails))]
        finally:
            proc.kill()
        print("\n".join(out))
        if len(sys.argv) > 2:
            with open(sys.argv[2], "w") as f:
                f.write("\n".join(out) + "\n")
        if fails:
            sys.exit(1)


if __name__ == "__main__":
    main(*(sys.argv[1:2] or []))
