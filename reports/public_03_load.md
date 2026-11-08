# public_03_load: throughput and memory

Machine: Apple M-series laptop, one controller process (`./run.sh`), simulator on the same machine.
Command: `/usr/bin/time -l env CONTROLLER_DB=state/public_03_load.db ./run.sh http://127.0.0.1:8760`

| measure | value |
|---|---|
| whole run (14 history days + 5 simulated days, simulator included) | 175 s wall |
| history bootstrap (5.5M events) | ~39 s including world generation |
| wall time per simulated day (simulator + ingest + decisions) | 20 / 28 / 25 / 27 / 36 s |
| events per simulated day | 840,030 |
| ingest rate per day | 86k / 76k / 87k / 96k / 69k events/s |
| decision time per day (12 workflows, 24 ticks) | 1.1 / 3.2 / 3.6 / 6.0 / 8.6 s |
| decision lag | ≤ 1 tick (60 sim minutes); ingest of an hour's chunk ≈ 0.4 s |
| peak resident memory (controller) | 1.02 GB |
| SQLite file after the run | 0.88 GB |

Budget from the SRE memo: one simulated day in under 10 wall-clock minutes. Worst day here: 36 s.

Outcome on the same run (`reports/public_03_load_grade.md`): conclusion rate +19.3% across 12 workflows,
pickup +10.8%, engagement +5.2%, 52 changes applied, 0 harmful.

Decision time grows with the size of the raw `calls` table, because the "people who already declined"
query reads live campaigns from it. It is indexed by campaign. At 10× it is the first query to move
into a rollup table.
