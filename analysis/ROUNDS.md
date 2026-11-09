# Historical analysis rounds

Physical locations preserve the seven historical rounds. R1-R7 correspond to v1, v3, v4, v6, v7, v8 and v9, respectively, as in Supplementary Table 1. The step-based reading order is in [PIPELINE.md](PIPELINE.md); the final manuscript mapping is in [PAPER_MAP.md](../docs/PAPER_MAP.md).

These scripts are an authorised-data audit trail, not a single command that recreates every historical branch. Frozen sample-size and result checks remain in place. Restricted source reading and HMAC steps are not synthetic entry points. Libraries are imported by their callers. Run checks only after their declared inputs exist.

## Configuration and run order

Copy the two examples from `config/` to custodian-supplied `paths.yaml` and `private.yaml`, or set `SHANGYU_PATHS_CONFIG` and `SHANGYU_PRIVATE_CONFIG` to separate configuration files. Never add real configuration or restricted output to the repository. `SHANGYU_HMAC_KEY_FILE` is required only for the restricted pseudonymisation interface. Keep input roots read-only and output roots separate. Names below are paths relative to each configured historical round root, not bundled restricted data.

Proceed through raw parsing/panels, record states, GPS association/capture, estimator families, timing/scenarios, spatial/vehicle variants, and final exports. Revisions consume frozen earlier-round results; they do not overwrite earlier analysis. Follow each original main/CLI for its historical branch. The synthetic runner calls the explicitly listed original functions in this same dependency order.

For the real v9 rerun the order is `decomp_v9.py --run`, `decomp_display_v9.py`, `capture_expected_v9.py`, then `capture_format_finish_v9.py`. Supply the frozen v9 protocol/input manifest in the configured new output environment directory. The source-data aliases are exact copies of the resulting public tables.

## Round purposes

| Round | Version | Purpose | Manuscript context |
|---|---|---|---|
| R1 | v1 | Base parsing, observations, two-source comparisons and the original spatial/vehicle/bias analyses. | Figs. 2, 5, 6; ED Figs. 1, 6-9; ED Table 1. |
| R2 | v3 | Bounded corrections to vehicle, spatial, floor and sensitivity calculations. | Figs. 5, 6; ED Figs. 5, 6, 8, 9. |
| R3 | v4 | Supplementary quality/null-envelope analyses and numerical source/provenance exports. | ED Figs. 6, 7; supplementary evidence and source exports. |
| R4 | v6 | Device recording-state diagnosis, taxi linkage/calibration, probe estimators, structured leaveout and pre-event selection. | Fig. 3 validation context; Fig. 4; Table 1; ED Figs. 2-5, 9. |
| R5 | v7 | Partial-day states, health-screen family, control-selected matchable cameras and revised probe products. | Figs. 3, 4; Table 1; ED Figs. 2-4. |
| R6 | v8 | Post-review baseline/health sensitivity, recovery-rule comparison and passage-geometry diagnostics. | Figs. 3, 4, 6; baseline/geometry context. |
| R7 | v9 | Post-review decomposition, breakeven/sustained scenarios and expected recorded passages. | Figs. 3b and 4c; Table 1 contrast and audit coverage. |

## R1: v1 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v1/avi_panel_v1.py` | 1 | Restricted camera export chunks; device map; baseline definitions. | Plate-day shards, plate_master.parquet, plate_day_summary.csv, device_hour.csv and online sets. | Figs. 2, 6; ED Figs. 1, 6, 7. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/taxi_grid_resume_v1.py` | 1 | Authorised taxi workbook locations and historical parsing checkpoints. | Resumed taxi_grid_day.csv, taxi_grid_centroids.csv and taxi_hour_valid.csv. | ED Fig. 8; taxi-point support in Fig. 2. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/taxi_grid_v1.py` | 1 | Authorised taxi workbook locations and frozen validity/bounding rules. | taxi_grid_day.csv, taxi_grid_centroids.csv and taxi_hour_valid.csv. | ED Fig. 8; taxi-point support in Fig. 2. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/common_v1.py` | 2 | Configured panel root; device_attributes.csv and device_hour.csv. | Shared frozen calendars, device vectors, HMAC interface and ratio/bootstrap helpers; imported library. | All R1 results; Table 1 definitions. | device_vectors/boot_ratio executed on synthetic inputs; the raw/HMAC interface is restricted. |
| `analysis/v1/panels_v1.py` | 2 | Parsed camera/direction/lane and taxi caches; sensor metadata; device map; spatial covariates. | device_day.csv, device_hour.csv, device_dir_lane_day.csv, device_attributes.csv and online_sets.csv. | All downstream analyses; ED Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/refresh_spatial_after_avi_v1.py` | 2 | Completed AVI execution/hash record and existing device/spatial inputs. | Refreshed spatial attributes and panels, with membership/online-set equivalence diagnostics. | Spatial input provenance for Fig. 5 and ED Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/repair_coordinate_precision_v1.py` | 2 | Frozen parsed device-coordinate cache and anonymous device map. | Restored-precision internal device attribute coordinates; no public coordinate release. | Spatial input provenance for Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/spatial_attributes_v1.py` | 2 | Device map, source/cached sensor coordinates, public roads/places and terrain attributes. | spatial_covariates.csv and township_centroids_osm.csv. | Fig. 5; ED Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m1_m2_v1.py` | 5 | Device hour/direction/lane panels, plate-day summaries and taxi_vehicle_day.csv. | m1_daily_coverage.csv, m2_daily_ratios*.csv, hourly/daypart tables and failure counts. | Fig. 2; Table 1; ED Figs. 1, 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m5_bias_v1.py` | 5 | Device panels, daily ratio tables and fixed/online camera sets. | m5_* failure profiles, corrections, random/flow-weighted leaveout results and negative controls. | Table 1; ED Figs. 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m6_consolidate_v1.py` | 5 | Frozen M2-M5 result tables and their prespecified sensitivity outputs. | m6_robustness_matrix.csv and consolidated baseline, vehicle and spatial sensitivity tables. | Supplementary Table 1; sensitivity statements supporting Figs. 4-6. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m3_vehicles_v1.py` | 7 | Plate-day shards, plate_master.parquet, fixed camera memberships and vehicle cohorts. | Daily vehicle margins, composition, return curves, placebo and sensitivity tables. | Fig. 6; ED Figs. 6, 7. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m4_spatial_v1.py` | 7 | Device panels/attributes, taxi_grid_day.csv, grid centroids and town points. | m4_* spatial ratios, distance/road summaries, OLS, paired-grid comparisons and spatial negative controls. | Fig. 5; ED Figs. 5, 8. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/spatial_stats_v1.py` | 7 | Projected coordinates and fixed failed labels passed by callers. | Six-neighbour union edges and label-permutation join-count statistics; imported library. | Spatial dependence checks supporting Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/fig1_taxi_coverage.py` | 8 | Restricted parsed GPS-fix checkpoints and configured public grid definition. | fig1_taxi_coverage_cells.csv with the frozen privacy aggregation. | Fig. 2 taxi map; source generation only, not a public drawing entry point. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/format_counts_v1.py` | 8 | Existing public-result CSVs in the round output tree. | The same tables with the historical small-count display policy. | Published tables and figure-source exports. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## R2: v3 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v3/common_v3.py` | 5 | Frozen R1 device panels and configured R2 output root. | Shared R2 guards, calendars, vector and table helpers; imported library. | R2 revisions supporting Figs. 4-6. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m5_bias_v3.py` | 5 | Frozen device/taxi panels and R1 failure, correction and leaveout results. | m5_*_v3 bias decomposition, failure persistence, ordinary floor and signature tests. | Fig. 4; ED Figs. 2, 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m6_consolidate_v3.py` | 5 | Completed R2 spatial, vehicle, bias, drift and sensitivity tables. | m6_robustness_matrix_v3.csv. | Supplementary Table 1 and sensitivity context. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m6_drift_v3.py` | 5 | Frozen B3 daily camera ratios and vehicle margins. | m6_b3_drift_v3.csv plus adjusted ratio/margin diagnostics. | Baseline sensitivity for Figs. 4, 6. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m3_vehicles_v3.py` | 7 | R1 plate-day shards/master and frozen M3 return/margin inputs. | m3_*_v3 vehicle margins, five-class composition, persistent gaps and placebo tables. | Fig. 6; ED Figs. 6, 7. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m4_spatial_v3.py` | 7 | Frozen device/grid panels, R1 OLS/negative-control results and public town points. | m4_ols_v3.csv, distance/floor tables, shared taxi-camera grids, correlations and redistribution/threshold tables. | Fig. 5; ED Figs. 5, 8. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/publication_v3.py` | 8 | Completed R2 tables and internal-to-public device map. | Authorised publication copies with integer device identifiers and count suppression. | Public R2 table/source-data exports. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## R3: v4 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v4/supplement_analyses_v4.py` | 7 | Frozen plate master/day inputs, coverage and R2 vehicle/robustness results. | t24_plate_quality_v4.csv, t25_* null-envelope tables and t26_* robustness summaries. | ED Figs. 6, 7; Supplementary Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v4/bias_manuscript_v4.py` | 8 | Frozen R1/R2 observation, vehicle, spatial, bias and robustness result tables. | Historical supplementary-table/source-data exports, provenance and earlier figure files. | Retained for numerical exports; current plotting uses figures/; ED Figs. 1, 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## R4: v6 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v6/avi_taxi_filter_v6.py` | 1 | Authorised camera exports, device map and taxi pseudonym crosswalk. | taxi_avi_records_v6.parquet and hash_daily_check_v6.csv. | Restricted input for taxi capture and probe analyses. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/fix_taxi_row_metadata_v6.py` | 1 | Parsed taxi checkpoints and authorised workbook row metadata. | taxi_vehicle_day_v6.csv row metadata and before/after reconciliation records. | Taxi input provenance for Fig. 2 and capture analyses. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/taxi_legacy_sheet_validate_v6.py` | 1 | Authorised mismatch workbooks, cached parsed checkpoints and legacy daily summary. | Independent sheet-date vehicle/day reconciliation tables and diagnostics. | Taxi parsing provenance; preserves actual-day analysis separately. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/taxi_parse_v6.py` | 1 | Authorised taxi workbooks and public town-centroid inputs. | Parsed taxi-fix checkpoints and taxi_vehicle_day_v6.csv. | Fig. 2 taxi coverage and later GPS-camera linkage. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/taxi_probe_hash_v6.py` | 1 | Existing pseudonymised camera plate shards, taxi vehicle/day inputs and authorised key-file environment setting. | taxi_plate_day_v6.parquet and cross-source hash checks. | Restricted cross-source pseudonym linkage. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/device_state_v6.py` | 2 | Device/hour panels, direction-lane panel and frozen A1/attribute inputs. | device_state_internal_v6.csv, device_state_v6.csv and T27 state summaries. | Fig. 2; ED Fig. 2; later health screens. | load_channels/build_day executed on synthetic inputs; historical main retains fixed-sample validation. |
| `analysis/v6/spatial_helpers_v6.py` | 2 | Frozen device_day.csv, device_hour.csv, device_attributes.csv and A1 comparison table. | Shared Panels/A1/channel, projection, ratio and bootstrap helpers; imported library. | R4 device states and pre-event selection. | Panels executed on synthetic day/hour inputs; no independent historical main. |
| `analysis/v6/taxi_ring_update_v6.py` | 3 | Parsed taxi-fix checkpoints, existing taxi daily panel and device/ring metadata. | Taxi ring exposure/record tables and updated daily ring diagnostics. | Probe ring inputs supporting Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/capture_rate_v6.py` | 4 | Parsed taxi fixes, taxi-camera records, device attributes/states and frozen match settings. | T29 camera/parameter-grid/summary tables and calibration diagnostics. | Historical capture calibration and limitations; superseded main selection is in R5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/bias_common_v6.py` | 5 | Frozen device panels/attributes and online sets. | Shared A1, donor, stratum, ratio and bootstrap helpers; imported library. | Table 1; ED Figs. 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/bounds_v6.py` | 5 | Internal device states, probe ring results, earlier corrections and pre-event set results. | T31_recovery_bounds_v6.csv and device/scenario/bootstrap internal tables. | Fig. 4; Table 1; ED Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/probe_daily_v6.py` | 5 | Taxi-camera record matches, taxi plate/day and vehicle/day panels, camera attributes and earlier ratios. | T28 daily, ring, coverage and vehicle-distribution probe tables; joined internal panel. | Fig. 4; Table 1; ED Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/s_pre_v6.py` | 5 | Frozen device/hour panels, earlier OLS/bias tables and pre-event calendar. | T32_s_pre_v6.csv, fixed pre-event membership, ring/OLS summaries and bootstrap draws. | Fig. 4; Table 1; ED Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/consequences_v6.py` | 6 | T31 estimator results, T32 pre-event set results and ring daily inputs. | T33 recovery-date, lagging-ring and ring-daily-ratio tables. | Fig. 4 recovery timing; Table 1. | recovery executed on synthetic inputs; historical result assembly is restricted. |
| `analysis/v6/leaveout_structured_v6.py` | 7 | Frozen device panels, internal device states and historical failure counts. | T30 structured/fixed-failure leaveout and applicability tables plus masks/replicates. | ED Fig. 9; estimator applicability in Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/finalise_capture_tables_v6.py` | 8 | Completed T29 summary/parameter-grid tables. | Final historical T29 count display and capture-scatter source data. | Historical capture-result publication formatting. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## R5: v7 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v7/health_helpers_v7.py` | 2 | Frozen device/day/hour attributes and earlier A1 failure comparison. | R5 shared panel, channel, ratio and bootstrap helpers; imported library. | Health-screened recovery definitions in Table 1. | ratio executed on synthetic inputs. |
| `analysis/v7/health_screen_v7.py` | 2 | R4 state/pre-event membership internals, panels and frozen estimator comparisons. | Updated T27 states; T36 health/strict/pre-event-health, ring/OLS results and bootstrap draws. | Fig. 4; Table 1; ED Figs. 2, 4, 5. | make_states executed on synthetic inputs; historical main retains frozen-input checks. |
| `analysis/v7/capture_wellmatched_v7.py` | 4 | Parsed taxi fixes/AVI records, device attributes/states and control-period selection settings. | T35 capture tables; fixed selection, camera counts, vehicle cubes and bootstrap internals. | Fig. 3; ED Fig. 3. | segment_events/dedup_expected/count_captures executed on synthetic geolocated A200 inputs; complete T35 control-selection main is restricted. |
| `analysis/v7/probe_bounds_v7.py` | 5 | Earlier probe and T31 internals, joined taxi panel and state/bootstrap inputs. | T28 probe/Wednesday sensitivity, unchanged T31 publication copy and probe-product bootstrap tables. | Fig. 4; Table 1; ED Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v7/t37_tables_v7.py` | 5 | Completed T28_probe_daily_v7.csv, T31_recovery_bounds_v7.csv, T36_health_screened_v6.csv, device attributes and online memberships. | T37_network_comparison_v7.csv, T37_estimator_family_v7.csv and the matching estimator-family source-data table. | Table 1; Fig. 4 estimator family; ED Fig. 4. Selected original tables() entry point and minimal helpers only; original reports/CLI excluded. | Not executed on synthetic inputs: requires completed T28/T31/T36 tables; selected tables() only, without an automatic main. |
| `analysis/v7/finalise_capture_v7.py` | 8 | Completed internal capture summary and existing T35/source-data tables. | Final T35 count/P-value display and capture figure-source tables. | Fig. 3; ED Fig. 3. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## R6: v8 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v8/geometry_capture_v8.py` | 3 | Parsed taxi fixes/AVI records, fixed R5 matchable selection/states and public OSM roads. | G0/G123/G4 tables; passage/road/count/bootstrap caches; restricted G5 review material. | Fig. 3 geometry diagnostics; G5 material is never distributed. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/health_baseline_state_provenance_v8.py` | 5 | Frozen R5 states/camera counts and device-day records. | W3_state_ratio_medians_version_provenance_0726_v8.csv. | Health-state denominator/provenance checks supporting Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/health_baseline_v8.py` | 5 | Frozen state/membership, device panels, earlier T31 scenarios and T37 estimator family. | W1 device baseline sensitivity, W3 partial-channel health variant and state/ring/OLS summaries. | Fig. 4; Table 1; baseline and health-screen sensitivity. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/recovery_dates_v8.py` | 6 | Frozen T37 family, W1 device changes and Wednesday probe references. | W2_daily_inputs_v8.csv and W2_recovery_dates_v8.csv with censoring/window rules. | Recovery timing context for Fig. 4 and Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/recovery_vehicle_v8.py` | 7 | Frozen plate master/day shards, R2 margins and R5 Wednesday probe sensitivity. | W1 vehicle margins, paired baseline changes and probe reference tables. | Fig. 6; ED Fig. 6; Wednesday baseline sensitivity. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/geometry_finalise_v8.py` | 8 | Completed internal geometry tables and review metadata. | Final geometry public-table display and diagnostic figure aliases. | Fig. 3 geometry/source-data publication. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## R7: v9 R scripts

Read in the primary-step order below, resolving listed earlier-round inputs first. The original entry point retains its checks and accepted arguments.

| Script | Step | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|---|
| `analysis/v9/capture_expected_v9.py` | 4 | Frozen R5 camera/selection/vehicle cubes and bootstrap results; new decomposition membership/weights. | T40_expected_capture_v9.csv and T39_audit_coverage_v9.csv with internal resampling outputs. | Fig. 3 expected matches; Fig. 4 audit-coverage context. | Restricted historical main: fixed real sample sizes and frozen-result validation; not claimed as a complete synthetic chain. |
| `analysis/v9/decomp_v9.py` | 6 | Frozen R5 public states/T37 and device attributes/day/hour panels. | T38 decomposition, T39 breakeven/sustained tables, shared weights and full-precision draws. | Fig. 4c; Table 1 record-ratio contrast. | Restricted historical main: fixed real sample sizes and frozen-result validation; not claimed as a complete synthetic chain. |
| `analysis/v9/capture_format_finish_v9.py` | 8 | Completed internal audit-coverage and public T39/T40 outputs. | Integer audit-device counts and final public figure-source location policy. | Fig. 3 source-data publication; Fig. 4 coverage display. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v9/decomp_display_v9.py` | 8 | Full-precision new decomposition/breakeven/sustained points. | Public T39 small-count display and T38 source-precision wording. | Fig. 4 source-data publication. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

## C checks

These retained files validate schemas, provenance, privacy, fixtures, calculations or delivery. Their original historical assumptions remain; inclusion is not a claim that every check is runnable on the small synthetic dataset.

| Version | Check files |
|---|---|
| v1 | `analysis/v1/checks/audit_m4_v1.py`, `analysis/v1/checks/audit_spatial_source_equivalence_v1.py`, `analysis/v1/checks/audit_v1.py`, `analysis/v1/checks/deliverable_spec_v1.py`, `analysis/v1/checks/m5_crosscheck_v1.py`, `analysis/v1/checks/pilot_comparison_v1.py`, `analysis/v1/checks/pilot_conditioning_diagnostic_v1.py`, `analysis/v1/checks/reference_revalidation_v1.py` |
| v3 | `analysis/v3/checks/audit_m4_v3.py`, `analysis/v3/checks/audit_v3.py`, `analysis/v3/checks/check_vehicle_methods_v3.py`, `analysis/v3/checks/check_vehicle_outputs_v3.py`, `analysis/v3/checks/privacy_check_v3.py` |
| v4 | `analysis/v4/checks/check_supplements_v4.py`, `analysis/v4/checks/number_provenance_final_v4.py`, `analysis/v4/checks/privacy_check_v4.py`, `analysis/v4/checks/spatial_figures_qa_v4.py` |
| v6 | `analysis/v6/checks/audit_capture_degradation_spatial_v6.py`, `analysis/v6/checks/audit_public_spatial_v6.py`, `analysis/v6/checks/audit_spatial_v6.py`, `analysis/v6/checks/bias_final_crosscheck_v6.py`, `analysis/v6/checks/bias_selfcheck_v6.py`, `analysis/v6/checks/bias_t34_support_audit_v6.py`, `analysis/v6/checks/check_capture_outputs_v6.py`, `analysis/v6/checks/check_panel_hour_synthetic_v6.py`, `analysis/v6/checks/check_public_audit_synthetic_v6.py`, `analysis/v6/checks/check_s_pre_synthetic_v6.py`, `analysis/v6/checks/check_spatial_scripts_v6.py`, `analysis/v6/checks/check_state_synthetic_v6.py`, `analysis/v6/checks/check_taxi_actualdate_v6.py`, `analysis/v6/checks/check_taxi_parse_v6.py`, `analysis/v6/checks/diagnose_taxi_parse_v6.py`, `analysis/v6/checks/inspect_state_inputs_v6.py`, `analysis/v6/checks/privacy_check_v6.py`, `analysis/v6/checks/test_capture_v6.py`, `analysis/v6/checks/test_taxi_projection_v6.py`, `analysis/v6/checks/test_taxi_ring_update_v6.py`, `analysis/v6/checks/verify_delivery_manifest_v6.py` |
| v7 | `analysis/v7/checks/archive_capture_display_v7.py`, `analysis/v7/checks/audit_health_v7.py`, `analysis/v7/checks/audit_public_v7.py`, `analysis/v7/checks/check_capture_wellmatched_v7.py`, `analysis/v7/checks/check_health_design_v7.py`, `analysis/v7/checks/privacy_check_v7.py`, `analysis/v7/checks/probe_bounds_audit_v7.py`, `analysis/v7/checks/verify_delivery_v7.py`, `analysis/v7/checks/audit_final_metadata_spatial_v7.py`, `analysis/v7/checks/audit_probe_bounds_spatial_v7.py`, `analysis/v7/checks/audit_public_v7_before_scientific_literal_fix.py` |
| v8 | `analysis/v8/checks/audit_geometry_spatial_v8.py`, `analysis/v8/checks/geometry_crosschecks_v8.py`, `analysis/v8/checks/geometry_independent_checks_v8.py`, `analysis/v8/checks/geometry_preflight_v8.py`, `analysis/v8/checks/health_baseline_audit_v8.py`, `analysis/v8/checks/health_baseline_recovery_crossaudit_v8.py`, `analysis/v8/checks/privacy_check_v8.py`, `analysis/v8/checks/recovery_spatial_independent_audit_v8.py`, `analysis/v8/checks/verify_delivery_v8.py` |
| v9 | `analysis/v9/checks/audit_v9.py`, `analysis/v9/checks/capture_public_roundtrip_v9.py`, `analysis/v9/checks/capture_schema_v9.py`, `analysis/v9/checks/decomp_preflight_v9.py`, `analysis/v9/checks/decomp_public_check_v9.py`, `analysis/v9/checks/environment_v9.py`, `analysis/v9/checks/verify_v9.py` |

Two C support files are retained because historical checks import them. `analysis/v1/checks/deliverable_spec_v1.py` supplies delivery/table expectations to the R1 audit. `analysis/v9/checks/environment_v9.py` supplies fingerprint-verification utilities to the R7 delivery check. Their presence does not authorise or invoke the original environment, protocol-writing or delivery main entry points.

## X exclusions

These source scripts are inventoried but are not distributed. The pilot/protocol-development directory is outside the actual-results inventory.

| Version | Source filename | Reason |
|---|---|---|
| v1 | `complete_delivery_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `environment_blocked_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `environment_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `finalise_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `monitor_spatial_refresh_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `record_figure_review_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `run_formal_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v1 | `run_vehicles_v1.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v3 | `environment_v3.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v3 | `finalise_v3.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v3 | `review_bundle_v3.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v3 | `run_v3.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v4 | `closeout_v4.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v4 | `consolidate_captions_v4.py` | Earlier plotting or manuscript preparation; not the final public drawing pipeline. |
| v4 | `draft_manuscript_v4.py` | Earlier plotting or manuscript preparation; not the final public drawing pipeline. |
| v4 | `environment_v4.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v4 | `final_materials_v4.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v4 | `inspect_v4.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v4 | `review_manuscript_independent_v4.py` | Earlier plotting or manuscript preparation; not the final public drawing pipeline. |
| v4 | `root_figures_v4.py` | Earlier plotting or manuscript preparation; not the final public drawing pipeline. |
| v4 | `spatial_figures_v4.py` | Earlier plotting or manuscript preparation; not the final public drawing pipeline. |
| v6 | `complete_taxi_capture_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v6 | `complete_taxi_reconciliation_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v6 | `correct_fingerprint_panel_count_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v6 | `environment_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v6 | `finalise_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v6 | `manuscript_fixes_v6.py` | Earlier plotting or manuscript preparation; not the final public drawing pipeline. |
| v6 | `run_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v6 | `snapshot_taxi_main_v6.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v7 | `environment_v7.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v8 | `claim_ledger_v8.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v8 | `environment_v8.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v8 | `finalise_v8.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v8 | `ledger_inspect_v8.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v8 | `manifest_v8.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |
| v9 | `report_v9.py` | Delivery, orchestration, environment or packaging record; no independent scientific estimate. |

### Selected-source exception for T37

`analysis/v7/t37_tables_v7.py` contains only original `finalise_v7.py` lines 1-9, 11-18 and 24-51: imports/globals and the original now, clean, put, read, save and tables functions. There is no automatic main entry point. Invoke the selected original tables() function only after its computed inputs exist. Original line 10, lines 19-23 and lines 52-152 remain X, including report text, logging, digest/manifest routines and the original CLI. No report draft is distributed in the selected R module. Block hashes and the exact original-line map are retained in the private build audit. This is one inventoried source file with selected R blocks and an explicitly excluded X remainder, not two independently counted source files.

Inventory: 158 original Python files; R=57, C=65, X=36; one selected R source also has an excluded X remainder. New configuration/drawing/synthetic/scanner support files are not mislabelled as historical R scripts.
