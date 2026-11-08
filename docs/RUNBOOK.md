# Controller runbook

For whoever is on call. It assumes nothing beyond this repo.

## Run it

```bash
pip install -r requirements.txt
python -m sim serve --scenario scenarios/public_02_incidents.yaml --run-dir runs/mine02 --force   # :8700
./run.sh http://127.0.0.1:8700                    # runs until the scenario ends
```

State lives in `state/controller.db` (override with `CONTROLLER_DB=...`). Kill the process at any time and run the same command again: it resumes from the store. If the store belongs to a different or restarted simulator, it gets renamed to `*.old` and a fresh one starts.

Tests: `python -m pytest -q tests` (about 5 s). Kill/restart proof: `python tests/crash_test.py scenarios/public_02_incidents.yaml`.

## Look at it

All of these read only the store, so they work while the controller runs.

| command | answers |
|---|---|
| `python -m controller status` | is the loop healthy: last tick, ingest rate, decision time, credits, open proposals, alerts in the last 24h |
| `python -m controller view [wf]` | supervisor screen: what's being tested, who's winning, what's waiting on an approver, what changed today, pulled caller IDs |
| `python -m controller why <wf> [D3 14:00]` | why the config changed at or before that time, who approved it, what happened next |
| `python -m controller heard <person_id or lead_id> [2027-01-07]` | every call that person got, which variant, and the decision behind it |
| `python -m controller unban <wf> <did>` | put a pulled caller ID back (as a 5% probe) once the carrier clears it |

For anything else, open the store with `sqlite3`. The `log` table holds every decision in time order, `props` holds every proposal with its body and status, and `incidents` holds incident state.

## When it pages

| alert text (in `status`) | what it means | what to do |
|---|---|---|
| `send_failed ... 4xx` | the simulator refused a proposal at send | read `props.note` for that pid; usually a config we built that the contract rejects. Fix the builder, it retries after 3h |
| `lapsed` | an approved change wasn't applied within the apply window | the loop was down or behind; check `ticks` for a gap. The next daily plan re-proposes |
| `no candidate prompt left` | hallucination incident with every known prompt failing validation | needs a human prompt change; the incident stays open |
| `credits low` | under 20 credits | validation and LLM calls will start failing (402); top up or accept that incidents won't auto-fix |
| ticks stop advancing | process dead or the simulator unreachable | restart `./run.sh`; it retries 5xx with backoff on its own |

These don't page: rejections, expiries and stale applies (re-planned automatically), caller-ID rotations, decay flags, and fatigue-capped plans (logged once a day as `blocked`).

## Where things are

| file | what |
|---|---|
| `controller/__main__.py` | entry point, tick loop, new-world detection |
| `controller/ingest.py` | schema, chunk ingestion (one transaction per chunk), rollups |
| `controller/plan.py` | pure decision maths over rollups: cohorts, call-time, caller IDs, arms, decay, hallucination, verification |
| `controller/loop.py` | per-workflow tick: supervisor edits, incidents, verification, the daily plan, proposal packaging |
| `controller/gov.py` | proposal lifecycle and crash reconciliation |
| `controller/report.py` | the read-only commands above |
| `controller/stats.py` | Beta draws, Poisson tail, z-test, exact k/1024 weights |

Knobs worth knowing (all in `plan.py`): `FLOOR` 3% minimum per arm, `EXPLORE` 40% for untried arms, `MIN_ARM` 150 calls before an arm counts as tried, `PROBE` 5% for new caller IDs, `RAMP`/`CAP` 300 calls before an arm may exceed 25%, `LIFT`/`SURE` the move rule (2% expected lift, 97% no-loss).
