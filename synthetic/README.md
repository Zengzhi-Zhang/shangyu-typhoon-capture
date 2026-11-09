# Synthetic first-layer panels

Run `python run_synthetic.py` from the repository root. Each run recreates its
own ignored `outputs/synthetic/` directory, including inputs, intermediate
tables, original execution logs and the final `synthetic_summary.csv`.

The generator uses seed 20261005 and the published structural counts: 1,287
A100 devices, 1,221 A200 devices, 66 A100-only devices, 1,075 geolocated A200
devices, 855 stable devices and 290 taxis. The device calendar contains all 37
specified dates: 17 June and 28 June to 2 August 2021. Parsed GPS points cover
6 to 31 July. The matching cube retains the eight control dates and seven
event dates used by the original analysis. The 925 control-exposed locations,
329 main matchable locations and 252 pre-event candidates are also published
counts. Their provenance is Extended Data Table 1 and the control/event
windows stated in the published Methods.

All flows, recording losses, routes and positions are hand-set fiction. No
restricted table is read to choose values or determine schemas. Camera and
taxi identifiers begin with `syn`. Coordinates lie on a fictional regular grid
and have at most two decimal places. Organisations are Unit A to Unit I. The
township lookup required by the original GPS-metric reader contains a
fictional reference coordinate. It does not contain the study area's position.
Frozen set-membership flags are synthetic metadata, not recovered real-device
memberships. The pre-event selection is then computed by the original
selection function from the generated hourly panel.

The generated first layer contains device-hour, device-day and lane panels,
camera metadata, parsed taxi GPS points, taxi camera records and a fictional
road layer. The runner performs no raw-workbook parsing, raw-record reading or
HMAC pseudonymisation. Its configuration points only to the generated tree.
The native producer stage clears the key environment variable and records a
Python read-path audit. Static IO review complements that audit; it does not
claim to intercept every dependency's C++ file open.

`synthetic/original_chain.py` organises IO and calls the unchanged historical
producers. It does not provide substitute estimator, matching, bootstrap,
expected-record or break-even formulas. The original producer chain computes:

1. The full eight-family Table 1 set: naive, health-screened, online, stable,
   strict health-screened, pre-event plus health-screened, neighbour-imputation
   and probe-adjusted estimators. The original T37 writer retains its 99 rows;
   `results/Table1_daily_estimator_family.csv` selects the 72 core rows. Probe
   estimates remain unavailable on 1 and 2 August.
2. GPS passage geometry, deduplication, temporal matching and the original
   control selection, followed by the original T40 expected-record analysis
   with seven event-day rows.
   Its camera and vehicle intervals come from the original 500- and 200-draw
   procedures. The four-date old-interface matching reference is generated
   separately in the same run using the original v6 matching functions. No
   historical real table is copied.
3. The 32 core-estimator threshold-date outcomes through the original recovery
   function and the original T39 analyses: 36 break-even rows and 36 sustained
   classifications, including their retained bootstrap outputs.

The v9 decomposition entry point still applies two exact numerical checks from the real
paper after writing all its scientific outputs. Those historical checks fail
on fictional values. The runner preserves the original failed check files and
the original `AssertionError` type and message. It continues only when the
failure is exactly this terminal audit, its failed keys are limited to
`T38_0726` and `T38_0802`, and both T39 scientific tables exist. Any other error
is raised. T40 also retains its unmet real-paper numerical acceptance target;
its 67 computational integrity checks pass. Synthetic values are never tuned
to satisfy those real-paper comparisons.

Two previously authorised T40 fixed-size assertions retain their opt-in guard.
The flag defaults to false and is set only by `run_synthetic.py`. No analysis
file was changed for this larger demonstration. All 126 analysis files match
the frozen release baseline. The frozen `analysis/PIPELINE.md` and
`analysis/ROUNDS.md` describe the earlier compact synthetic validation range;
the larger demonstration and its additional native entries are documented
here and in the generated `chain_status.json`.

Two consecutive runs of the same frozen generator and runner completed in
317.72 and 325.98 seconds. Scientific outputs were byte-identical. Of all 449
output files, 14 differed: 13 original execution-metadata JSON files and the
Matplotlib font cache. The full-output deterministic acceptance therefore
fails. No clock was frozen and no original log was deleted or excluded from
that acceptance. Scientific-only equality is additional evidence, not a
replacement for the full-output criterion. The runtime criterion is met.

All generated values are synthetic and must not be compared with the paper.
`synthetic_summary.csv` carries this notice and combines the computed recovery
estimators, expected and captured records, and critical-recovery classes.
Generated panels and trajectories remain in ignored outputs and are not
distributed with the source repository.
