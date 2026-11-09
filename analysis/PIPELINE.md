# Analysis pipeline

The directories remain organised by historical round, not by the steps below. Every historical R script has exactly one primary entry here. Cross-step work is described by references to step numbers rather than duplicate primary entries. [ROUNDS.md](ROUNDS.md) gives the round history and excluded scripts. [PAPER_MAP.md](../docs/PAPER_MAP.md) gives the final manuscript item mapping.

Configuration provides all restricted paths and keyword/value lookups. No raw records or private configuration are included. A function-level synthetic exercise is distinct from executing a historical main with fixed real-sample guards. Seven original modules have been exercised at the function level. The complete expected-match and breakeven entry points retain real-sample assertions, so the strict three-chain synthetic acceptance is not claimed to pass. No replacement analysis algorithm was introduced. The synthetic run report records actual coverage.

## 1. Restricted raw reading, HMAC pseudonymisation and parsing

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v1/avi_panel_v1.py` | Restricted camera export chunks; device map; baseline definitions. | Plate-day shards, plate_master.parquet, plate_day_summary.csv, device_hour.csv and online sets. | Figs. 2, 6; ED Figs. 1, 6, 7. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/taxi_grid_resume_v1.py` | Authorised taxi workbook locations and historical parsing checkpoints. | Resumed taxi_grid_day.csv, taxi_grid_centroids.csv and taxi_hour_valid.csv. | ED Fig. 8; taxi-point support in Fig. 2. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/taxi_grid_v1.py` | Authorised taxi workbook locations and frozen validity/bounding rules. | taxi_grid_day.csv, taxi_grid_centroids.csv and taxi_hour_valid.csv. | ED Fig. 8; taxi-point support in Fig. 2. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/avi_taxi_filter_v6.py` | Authorised camera exports, device map and taxi pseudonym crosswalk. | taxi_avi_records_v6.parquet and hash_daily_check_v6.csv. | Restricted input for taxi capture and probe analyses. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/fix_taxi_row_metadata_v6.py` | Parsed taxi checkpoints and authorised workbook row metadata. | taxi_vehicle_day_v6.csv row metadata and before/after reconciliation records. | Taxi input provenance for Fig. 2 and capture analyses. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/taxi_legacy_sheet_validate_v6.py` | Authorised mismatch workbooks, cached parsed checkpoints and legacy daily summary. | Independent sheet-date vehicle/day reconciliation tables and diagnostics. | Taxi parsing provenance; preserves actual-day analysis separately. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/taxi_parse_v6.py` | Authorised taxi workbooks and public town-centroid inputs. | Parsed taxi-fix checkpoints and taxi_vehicle_day_v6.csv. | Fig. 2 taxi coverage and later GPS-camera linkage. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v6/taxi_probe_hash_v6.py` | Existing pseudonymised camera plate shards, taxi vehicle/day inputs and authorised key-file environment setting. | taxi_plate_day_v6.parquet and cross-source hash checks. | Restricted cross-source pseudonym linkage. | Restricted-data entry point; not run on synthetic raw records. |

## 2. Device-day, device-hour and lane panels; recording states

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v1/common_v1.py` | Configured panel root; device_attributes.csv and device_hour.csv. | Shared frozen calendars, device vectors, HMAC interface and ratio/bootstrap helpers; imported library. | All R1 results; Table 1 definitions. | device_vectors/boot_ratio executed on synthetic inputs; the raw/HMAC interface is restricted. |
| `analysis/v1/panels_v1.py` | Parsed camera/direction/lane and taxi caches; sensor metadata; device map; spatial covariates. | device_day.csv, device_hour.csv, device_dir_lane_day.csv, device_attributes.csv and online_sets.csv. | All downstream analyses; ED Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/refresh_spatial_after_avi_v1.py` | Completed AVI execution/hash record and existing device/spatial inputs. | Refreshed spatial attributes and panels, with membership/online-set equivalence diagnostics. | Spatial input provenance for Fig. 5 and ED Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/repair_coordinate_precision_v1.py` | Frozen parsed device-coordinate cache and anonymous device map. | Restored-precision internal device attribute coordinates; no public coordinate release. | Spatial input provenance for Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/spatial_attributes_v1.py` | Device map, source/cached sensor coordinates, public roads/places and terrain attributes. | spatial_covariates.csv and township_centroids_osm.csv. | Fig. 5; ED Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/device_state_v6.py` | Device/hour panels, direction-lane panel and frozen A1/attribute inputs. | device_state_internal_v6.csv, device_state_v6.csv and T27 state summaries. | Fig. 2; ED Fig. 2; later health screens. | load_channels/build_day executed on synthetic inputs; historical main retains fixed-sample validation. |
| `analysis/v6/spatial_helpers_v6.py` | Frozen device_day.csv, device_hour.csv, device_attributes.csv and A1 comparison table. | Shared Panels/A1/channel, projection, ratio and bootstrap helpers; imported library. | R4 device states and pre-event selection. | Panels executed on synthetic day/hour inputs; no independent historical main. |
| `analysis/v7/health_helpers_v7.py` | Frozen device/day/hour attributes and earlier A1 failure comparison. | R5 shared panel, channel, ratio and bootstrap helpers; imported library. | Health-screened recovery definitions in Table 1. | ratio executed on synthetic inputs. |
| `analysis/v7/health_screen_v7.py` | R4 state/pre-event membership internals, panels and frozen estimator comparisons. | Updated T27 states; T36 health/strict/pre-event-health, ring/OLS results and bootstrap draws. | Fig. 4; Table 1; ED Figs. 2, 4, 5. | make_states executed on synthetic inputs; historical main retains frozen-input checks. |

Health-screened ratios also feed step 5. Spatial attribute construction supports step 7.

## 3. GPS-to-camera association and candidate passages

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v6/taxi_ring_update_v6.py` | Parsed taxi-fix checkpoints, existing taxi daily panel and device/ring metadata. | Taxi ring exposure/record tables and updated daily ring diagnostics. | Probe ring inputs supporting Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/geometry_capture_v8.py` | Parsed taxi fixes/AVI records, fixed R5 matchable selection/states and public OSM roads. | G0/G123/G4 tables; passage/road/count/bootstrap caches; restricted G5 review material. | Fig. 3 geometry diagnostics; G5 material is never distributed. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

Capture summaries from these associations are in step 4. Raw parsing is in step 1.

## 4. Capture at matchable cameras and expected recorded passages

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v6/capture_rate_v6.py` | Parsed taxi fixes, taxi-camera records, device attributes/states and frozen match settings. | T29 camera/parameter-grid/summary tables and calibration diagnostics. | Historical capture calibration and limitations; superseded main selection is in R5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v7/capture_wellmatched_v7.py` | Parsed taxi fixes/AVI records, device attributes/states and control-period selection settings. | T35 capture tables; fixed selection, camera counts, vehicle cubes and bootstrap internals. | Fig. 3; ED Fig. 3. | segment_events/dedup_expected/count_captures executed on synthetic geolocated A200 inputs; complete T35 control-selection main is restricted. |
| `analysis/v9/capture_expected_v9.py` | Frozen R5 camera/selection/vehicle cubes and bootstrap results; new decomposition membership/weights. | T40_expected_capture_v9.csv and T39_audit_coverage_v9.csv with internal resampling outputs. | Fig. 3 expected matches; Fig. 4 audit-coverage context. | Restricted historical main: fixed real sample sizes and frozen-result validation; not claimed as a complete synthetic chain. |

See step 3 for passage geometry and step 8 for historical public-table formatting. Expected recorded passages here use original historical calculation code.

## 5. Network-recovery estimators

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v1/m1_m2_v1.py` | Device hour/direction/lane panels, plate-day summaries and taxi_vehicle_day.csv. | m1_daily_coverage.csv, m2_daily_ratios*.csv, hourly/daypart tables and failure counts. | Fig. 2; Table 1; ED Figs. 1, 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m5_bias_v1.py` | Device panels, daily ratio tables and fixed/online camera sets. | m5_* failure profiles, corrections, random/flow-weighted leaveout results and negative controls. | Table 1; ED Figs. 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m6_consolidate_v1.py` | Frozen M2-M5 result tables and their prespecified sensitivity outputs. | m6_robustness_matrix.csv and consolidated baseline, vehicle and spatial sensitivity tables. | Supplementary Table 1; sensitivity statements supporting Figs. 4-6. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/common_v3.py` | Frozen R1 device panels and configured R2 output root. | Shared R2 guards, calendars, vector and table helpers; imported library. | R2 revisions supporting Figs. 4-6. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m5_bias_v3.py` | Frozen device/taxi panels and R1 failure, correction and leaveout results. | m5_*_v3 bias decomposition, failure persistence, ordinary floor and signature tests. | Fig. 4; ED Figs. 2, 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m6_consolidate_v3.py` | Completed R2 spatial, vehicle, bias, drift and sensitivity tables. | m6_robustness_matrix_v3.csv. | Supplementary Table 1 and sensitivity context. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m6_drift_v3.py` | Frozen B3 daily camera ratios and vehicle margins. | m6_b3_drift_v3.csv plus adjusted ratio/margin diagnostics. | Baseline sensitivity for Figs. 4, 6. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/bias_common_v6.py` | Frozen device panels/attributes and online sets. | Shared A1, donor, stratum, ratio and bootstrap helpers; imported library. | Table 1; ED Figs. 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/bounds_v6.py` | Internal device states, probe ring results, earlier corrections and pre-event set results. | T31_recovery_bounds_v6.csv and device/scenario/bootstrap internal tables. | Fig. 4; Table 1; ED Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/probe_daily_v6.py` | Taxi-camera record matches, taxi plate/day and vehicle/day panels, camera attributes and earlier ratios. | T28 daily, ring, coverage and vehicle-distribution probe tables; joined internal panel. | Fig. 4; Table 1; ED Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/s_pre_v6.py` | Frozen device/hour panels, earlier OLS/bias tables and pre-event calendar. | T32_s_pre_v6.csv, fixed pre-event membership, ring/OLS summaries and bootstrap draws. | Fig. 4; Table 1; ED Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v7/probe_bounds_v7.py` | Earlier probe and T31 internals, joined taxi panel and state/bootstrap inputs. | T28 probe/Wednesday sensitivity, unchanged T31 publication copy and probe-product bootstrap tables. | Fig. 4; Table 1; ED Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v7/t37_tables_v7.py` | Completed T28_probe_daily_v7.csv, T31_recovery_bounds_v7.csv, T36_health_screened_v6.csv, device attributes and online memberships. | T37_network_comparison_v7.csv, T37_estimator_family_v7.csv and the matching estimator-family source-data table. | Table 1; Fig. 4 estimator family; ED Fig. 4. Selected original tables() entry point and minimal helpers only; original reports/CLI excluded. | Not executed on synthetic inputs: requires completed T28/T31/T36 tables; selected tables() only, without an automatic main. |
| `analysis/v8/health_baseline_state_provenance_v8.py` | Frozen R5 states/camera counts and device-day records. | W3_state_ratio_medians_version_provenance_0726_v8.csv. | Health-state denominator/provenance checks supporting Fig. 4. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/health_baseline_v8.py` | Frozen state/membership, device panels, earlier T31 scenarios and T37 estimator family. | W1 device baseline sensitivity, W3 partial-channel health variant and state/ring/OLS summaries. | Fig. 4; Table 1; baseline and health-screen sensitivity. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

Health memberships are in step 2; sustained and breakeven rules are in step 6; final exports are in step 8.

## 6. Sustained attainment and breakeven recovery

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v6/consequences_v6.py` | T31 estimator results, T32 pre-event set results and ring daily inputs. | T33 recovery-date, lagging-ring and ring-daily-ratio tables. | Fig. 4 recovery timing; Table 1. | recovery executed on synthetic inputs; historical result assembly is restricted. |
| `analysis/v8/recovery_dates_v8.py` | Frozen T37 family, W1 device changes and Wednesday probe references. | W2_daily_inputs_v8.csv and W2_recovery_dates_v8.csv with censoring/window rules. | Recovery timing context for Fig. 4 and Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v9/decomp_v9.py` | Frozen R5 public states/T37 and device attributes/day/hour panels. | T38 decomposition, T39 breakeven/sustained tables, shared weights and full-precision draws. | Fig. 4c; Table 1 record-ratio contrast. | Restricted historical main: fixed real sample sizes and frozen-result validation; not claimed as a complete synthetic chain. |

The v9 module also computes the paired record-ratio decomposition used in step 5.

## 7. Spatial patterns and vehicle-level analyses

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v1/m3_vehicles_v1.py` | Plate-day shards, plate_master.parquet, fixed camera memberships and vehicle cohorts. | Daily vehicle margins, composition, return curves, placebo and sensitivity tables. | Fig. 6; ED Figs. 6, 7. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/m4_spatial_v1.py` | Device panels/attributes, taxi_grid_day.csv, grid centroids and town points. | m4_* spatial ratios, distance/road summaries, OLS, paired-grid comparisons and spatial negative controls. | Fig. 5; ED Figs. 5, 8. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v1/spatial_stats_v1.py` | Projected coordinates and fixed failed labels passed by callers. | Six-neighbour union edges and label-permutation join-count statistics; imported library. | Spatial dependence checks supporting Fig. 5. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m3_vehicles_v3.py` | R1 plate-day shards/master and frozen M3 return/margin inputs. | m3_*_v3 vehicle margins, five-class composition, persistent gaps and placebo tables. | Fig. 6; ED Figs. 6, 7. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/m4_spatial_v3.py` | Frozen device/grid panels, R1 OLS/negative-control results and public town points. | m4_ols_v3.csv, distance/floor tables, shared taxi-camera grids, correlations and redistribution/threshold tables. | Fig. 5; ED Figs. 5, 8. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v4/supplement_analyses_v4.py` | Frozen plate master/day inputs, coverage and R2 vehicle/robustness results. | t24_plate_quality_v4.csv, t25_* null-envelope tables and t26_* robustness summaries. | ED Figs. 6, 7; Supplementary Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/leaveout_structured_v6.py` | Frozen device panels, internal device states and historical failure counts. | T30 structured/fixed-failure leaveout and applicability tables plus masks/replicates. | ED Fig. 9; estimator applicability in Table 1. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/recovery_vehicle_v8.py` | Frozen plate master/day shards, R2 margins and R5 Wednesday probe sensitivity. | W1 vehicle margins, paired baseline changes and probe reference tables. | Fig. 6; ED Fig. 6; Wednesday baseline sensitivity. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

See steps 2 and 5 for shared panel and estimator libraries.

## 8. Source-data and public-table generation

| Primary R script | Inputs | Outputs | Manuscript use | Synthetic scope |
|---|---|---|---|---|
| `analysis/v1/fig1_taxi_coverage.py` | Restricted parsed GPS-fix checkpoints and configured public grid definition. | fig1_taxi_coverage_cells.csv with the frozen privacy aggregation. | Fig. 2 taxi map; source generation only, not a public drawing entry point. | Restricted-data entry point; not run on synthetic raw records. |
| `analysis/v1/format_counts_v1.py` | Existing public-result CSVs in the round output tree. | The same tables with the historical small-count display policy. | Published tables and figure-source exports. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v3/publication_v3.py` | Completed R2 tables and internal-to-public device map. | Authorised publication copies with integer device identifiers and count suppression. | Public R2 table/source-data exports. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v4/bias_manuscript_v4.py` | Frozen R1/R2 observation, vehicle, spatial, bias and robustness result tables. | Historical supplementary-table/source-data exports, provenance and earlier figure files. | Retained for numerical exports; current plotting uses figures/; ED Figs. 1, 4, 9. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v6/finalise_capture_tables_v6.py` | Completed T29 summary/parameter-grid tables. | Final historical T29 count display and capture-scatter source data. | Historical capture-result publication formatting. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v7/finalise_capture_v7.py` | Completed internal capture summary and existing T35/source-data tables. | Final T35 count/P-value display and capture figure-source tables. | Fig. 3; ED Fig. 3. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v8/geometry_finalise_v8.py` | Completed internal geometry tables and review metadata. | Final geometry public-table display and diagnostic figure aliases. | Fig. 3 geometry/source-data publication. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v9/capture_format_finish_v9.py` | Completed internal audit-coverage and public T39/T40 outputs. | Integer audit-device counts and final public figure-source location policy. | Fig. 3 source-data publication; Fig. 4 coverage display. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |
| `analysis/v9/decomp_display_v9.py` | Full-precision new decomposition/breakeven/sustained points. | Public T39 small-count display and T38 source-precision wording. | Fig. 4 source-data publication. | Not exercised by the synthetic runner; authorised inputs and historical guards required. |

These are export/formatting stages; final public drawing is in step 9.

## 9. Public figure drawing

The public drawing component reads only bundled source data and declared public layers, then writes generated figures below `outputs/figures/`. It is separate from the restricted analysis history. Run `python figures/make_all.py`. Figure scripts are not counted as historical R entries.

| Drawing scripts | Inputs | Outputs | Manuscript items | Synthetic scope |
|---|---|---|---|---|
| `figures/fig1_concept.py`; `figures/fig2_overview.py`; `figures/fig3_capture.py`; `figures/fig4_recovery.py`; `figures/fig5_spatial.py`; `figures/fig6_vehicles.py` | Public source CSVs and licensed public layers; the concept diagram is illustrative. | Editable-text PDFs and PNGs. | Figs. 1-6. | Public source-data redraw; not a synthetic traffic estimate. |
| `figures/ed1_outage.py` through `figures/ed9_masking.py` | Public extended-data source CSVs and declared layers. | Nine extended-data figures. | ED Figs. 1-9. | Public source-data redraw. |
