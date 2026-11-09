# -*- coding: utf-8 -*-
"""Required protocol deliverables, shared by finalisation and semantic audit."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
from common_v1 import ROOT,D_ALL
REQUIRED={
 '01_panels':['device_hour.csv','device_dir_lane_day.csv','device_attributes.csv','plate_master.parquet','taxi_vehicle_day.csv','taxi_grid_day.csv','taxi_grid_centroids.csv'],
 '02_m1_observation':['m1_daily_coverage.csv','m1_hourly_0718_0728.csv','m1_blackout_survivors.csv','m1_platform_outage_summary.json'],
 '03_m2_two_sources':['m2_daily_ratios.csv','m2_daily_ratios_B2.csv','m2_daily_ratios_B3.csv','m2_hourly_ratios_0722_0728.csv','m2_daypart_summary.csv'],
 '04_m3_vehicles':['m3_daily_by_group.csv','m3_daily_by_group_B2.csv','m3_daily_by_group_B3.csv','m3_two_margins_table.csv','m3_return_curve.csv','m3_return_gap.csv','m3_composition.csv','m3_first_hour.csv','m3_h1_h2_verdict.json'],
 '05_m4_spatial':['m4_device_ratios.csv','m4_by_distance_ring.csv','m4_by_road_level.csv','m4_by_town.csv','m4_by_elev.csv','m4_ols.csv','m4_moran.json','m4_taxi_grid_ratio.csv','m4_taxi_vs_camera_grid.csv','m4_distance_ring_by_road_level.csv','m4_h3_verdict.json'],
 '06_m5_bias_correction':['m5_visible_bias.csv','m5_visible_bias_B2.csv','m5_failure_counts.csv','m5_failure_timing.csv','m5_failure_nonrandomness.csv','m5_failure_profile.csv','m5_correction_methods.csv','m5_leaveout_validation.csv','m5_leaveout_by_flow_quantile.csv','m5_leaveout_validation_flowweighted.csv','m5_h4_verdict.json'],
 '07_m6_robustness':['m6_negative_control_0708_0710.csv','m6_negative_control_hourly.csv','m6_baseline_sensitivity.csv','m6_threshold_sensitivity.csv','m6_identification_correction.csv','m6_exclude_nev.csv','m6_online_set_variant.csv','m6_gateway_split.csv','m6_robustness_matrix.csv','m6_summary.md'],
 '08_figures':['fig1_daily_series.png','fig2_two_sources.png','fig3_two_margins.png','fig4_return_curves.png','fig5_spatial.png','fig6_bias_correction.png']}
FIGURE_ALIASES={'fig1_daily_series':'fig1_data','fig2_two_sources':'fig2_data','fig3_two_margins':'fig3_data','fig4_return_curves':'fig4_data','fig5_spatial':'fig5_data','fig6_bias_correction':'fig6_data'}
def missing_deliverables():
    rels=[folder+'/'+name for folder,names in REQUIRED.items() for name in names]
    rels+=['01_panels/plate_day/'+d+'.parquet' for d in D_ALL]
    rels+=['08_figures/'+s+'_data.csv' for s in FIGURE_ALIASES]
    return [r for r in rels if not (ROOT/r).is_file() or (ROOT/r).stat().st_size==0]
