# Sanitisation record

The historical R and C source files retain their calculation and formatting. The original five substitutions are configured paths/module search paths, restricted keyword lists, the key-file environment setting, restricted literal lookups, and private-value printing. The author amendment additionally permits synthetic-guard: default-off wrappers around fixed true-sample assertions, plus the mode flag support. It does not permit changing calculations, thresholds, filters or decisions. Original restricted values are intentionally omitted. No analysis bug was fixed.

The selected T37 source blocks and excluded report/CLI remainder are described in ROUNDS.md. Extraction is separately authorised and traced by original line ranges; omitted X source is not described as a sanitisation deletion.

Each row records one actual differing source line, or one added configuration/guard-support line at the stated source boundary. A source line can have more than one permitted category. Source numbering excludes a byte-order mark; none of these sources has one.

| Public file | Source line or insertion boundary | Category | Change |
|---|---|---|---|
| `analysis/v1/checks/audit_m4_v1.py` | 16 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/audit_m4_v1.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/audit_spatial_source_equivalence_v1.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/audit_spatial_source_equivalence_v1.py` | 11 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/audit_spatial_source_equivalence_v1.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/audit_v1.py` | 56 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/audit_v1.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/avi_panel_v1.py` | 6 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/avi_panel_v1.py` | 22 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/avi_panel_v1.py` | 23 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/avi_panel_v1.py` | 73 | key | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/avi_panel_v1.py` | insert_after_7 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/common_v1.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/common_v1.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/common_v1.py` | 11 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/common_v1.py` | 27 | key | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/common_v1.py` | 88 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/common_v1.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/deliverable_spec_v1.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/m3_vehicles_v1.py` | 21 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/m3_vehicles_v1.py` | insert_after_7 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/m4_spatial_v1.py` | 25 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/m4_spatial_v1.py` | insert_after_7 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/m5_bias_v1.py` | 714 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/m5_bias_v1.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/m5_crosscheck_v1.py` | 125 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/m5_crosscheck_v1.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/m6_consolidate_v1.py` | 468 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/m6_consolidate_v1.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/pilot_comparison_v1.py` | 19 | private_list | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/pilot_comparison_v1.py` | 25 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/pilot_comparison_v1.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/pilot_conditioning_diagnostic_v1.py` | 96 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/checks/pilot_conditioning_diagnostic_v1.py` | insert_after_8 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/checks/reference_revalidation_v1.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/refresh_spatial_after_avi_v1.py` | 13 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/refresh_spatial_after_avi_v1.py` | 14 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/refresh_spatial_after_avi_v1.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/spatial_attributes_v1.py` | 19 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/spatial_attributes_v1.py` | 20 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/spatial_attributes_v1.py` | 21 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/spatial_attributes_v1.py` | 22 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/spatial_attributes_v1.py` | 23 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/spatial_attributes_v1.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v1/taxi_grid_resume_v1.py` | 21 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/taxi_grid_resume_v1.py` | 281 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/taxi_grid_resume_v1.py` | 288 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v1/taxi_grid_resume_v1.py` | insert_after_8 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/checks/audit_m4_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/checks/audit_v3.py` | 22 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/checks/audit_v3.py` | 29 | key | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/checks/audit_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/checks/check_vehicle_methods_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/checks/check_vehicle_outputs_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/common_v3.py` | 12 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/common_v3.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/m4_spatial_v3.py` | 392 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/m4_spatial_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/m5_bias_v3.py` | 21 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/m5_bias_v3.py` | 22 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/m5_bias_v3.py` | 488 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/m5_bias_v3.py` | 502 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v3/m5_bias_v3.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/checks/privacy_check_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v3/publication_v3.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v4/bias_manuscript_v4.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/bias_manuscript_v4.py` | 190 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/bias_manuscript_v4.py` | 195 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/bias_manuscript_v4.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v4/checks/check_supplements_v4.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/checks/check_supplements_v4.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v4/checks/number_provenance_final_v4.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/checks/number_provenance_final_v4.py` | 11 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/checks/number_provenance_final_v4.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v4/checks/privacy_check_v4.py` | 6 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/checks/privacy_check_v4.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v4/checks/spatial_figures_qa_v4.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/checks/spatial_figures_qa_v4.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v4/supplement_analyses_v4.py` | 14 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v4/supplement_analyses_v4.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/audit_capture_degradation_spatial_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/audit_public_spatial_v6.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/audit_spatial_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/avi_taxi_filter_v6.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/avi_taxi_filter_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/bias_common_v6.py` | 12 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/bias_common_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/bias_final_crosscheck_v6.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/bias_final_crosscheck_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/bias_selfcheck_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/bias_t34_support_audit_v6.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/bias_t34_support_audit_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/capture_rate_v6.py` | 13 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/capture_rate_v6.py` | 129 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/capture_rate_v6.py` | 254 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/capture_rate_v6.py` | 263 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/capture_rate_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_capture_outputs_v6.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_capture_outputs_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_panel_hour_synthetic_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 10 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 11 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 12 | private_list;private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 13 | private_list;private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 14 | private_list;private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 15 | private_list;private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 16 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | 17 | private_list;private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_public_audit_synthetic_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_s_pre_synthetic_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_spatial_scripts_v6.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_spatial_scripts_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_state_synthetic_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_taxi_actualdate_v6.py` | 6 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_taxi_actualdate_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/check_taxi_parse_v6.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/check_taxi_parse_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/device_state_v6.py` | 151 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/device_state_v6.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/diagnose_taxi_parse_v6.py` | 6 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/diagnose_taxi_parse_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/finalise_capture_tables_v6.py` | 14 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/finalise_capture_tables_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/fix_taxi_row_metadata_v6.py` | 41 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/fix_taxi_row_metadata_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/inspect_state_inputs_v6.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/inspect_state_inputs_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/privacy_check_v6.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/privacy_check_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/probe_daily_v6.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/probe_daily_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/s_pre_v6.py` | 142 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/s_pre_v6.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/spatial_helpers_v6.py` | 14 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/spatial_helpers_v6.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/taxi_legacy_sheet_validate_v6.py` | 87 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/taxi_legacy_sheet_validate_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/taxi_parse_v6.py` | 14 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/taxi_parse_v6.py` | 15 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/taxi_parse_v6.py` | 290 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/taxi_parse_v6.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/taxi_probe_hash_v6.py` | 6 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/taxi_probe_hash_v6.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/taxi_probe_hash_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/test_capture_v6.py` | 16 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/test_capture_v6.py` | 39 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/test_capture_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/test_taxi_projection_v6.py` | 40 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/test_taxi_projection_v6.py` | 41 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/test_taxi_projection_v6.py` | 43 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/test_taxi_projection_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/test_taxi_ring_update_v6.py` | 14 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/test_taxi_ring_update_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v6/checks/verify_delivery_manifest_v6.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v6/checks/verify_delivery_manifest_v6.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/archive_capture_display_v7.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/archive_capture_display_v7.py` | 42 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/archive_capture_display_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/audit_health_v7.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/audit_health_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/audit_public_v7.py` | 15 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/audit_public_v7.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/capture_wellmatched_v7.py` | 25 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/capture_wellmatched_v7.py` | 347 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/capture_wellmatched_v7.py` | insert_after_7 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/check_capture_wellmatched_v7.py` | 15 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/check_capture_wellmatched_v7.py` | 47 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/check_capture_wellmatched_v7.py` | 48 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/check_capture_wellmatched_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/check_health_design_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/finalise_capture_v7.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/finalise_capture_v7.py` | 47 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/finalise_capture_v7.py` | 52 | private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/finalise_capture_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/t37_tables_v7.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/t37_tables_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/health_helpers_v7.py` | 14 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/health_helpers_v7.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/privacy_check_v7.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/privacy_check_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/probe_bounds_audit_v7.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/probe_bounds_audit_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/probe_bounds_v7.py` | 16 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/probe_bounds_v7.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/verify_delivery_v7.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/verify_delivery_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/audit_geometry_spatial_v8.py` | 15 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/audit_geometry_spatial_v8.py` | insert_after_5 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/geometry_capture_v8.py` | 24 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/geometry_capture_v8.py` | 30 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/geometry_capture_v8.py` | 462 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/geometry_capture_v8.py` | insert_after_7 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/geometry_crosschecks_v8.py` | 10 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/geometry_crosschecks_v8.py` | 56 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/geometry_crosschecks_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/geometry_finalise_v8.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/geometry_finalise_v8.py` | 18 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/geometry_finalise_v8.py` | 37 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/geometry_finalise_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/geometry_independent_checks_v8.py` | 13 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/geometry_independent_checks_v8.py` | 84 | private_list;private_value | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/geometry_independent_checks_v8.py` | 102 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/geometry_independent_checks_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/geometry_preflight_v8.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/geometry_preflight_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/health_baseline_audit_v8.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/health_baseline_audit_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/health_baseline_recovery_crossaudit_v8.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/health_baseline_recovery_crossaudit_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/health_baseline_state_provenance_v8.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/health_baseline_state_provenance_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/health_baseline_v8.py` | 11 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/health_baseline_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/privacy_check_v8.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/privacy_check_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/recovery_dates_v8.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/recovery_dates_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/recovery_spatial_independent_audit_v8.py` | 12 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/recovery_spatial_independent_audit_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/recovery_vehicle_v8.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/recovery_vehicle_v8.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v8/checks/verify_delivery_v8.py` | 3 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v8/checks/verify_delivery_v8.py` | insert_after_0 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/checks/audit_v9.py` | 17 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/audit_v9.py` | 18 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/audit_v9.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/capture_expected_v9.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/capture_expected_v9.py` | 91 | synthetic-guard | Wrap original fixed sample-size assert unchanged; active by default and skipped only for explicit synthetic mode. |
| `analysis/v9/capture_expected_v9.py` | 99 | synthetic-guard | Wrap original fixed sample-size assert unchanged; active by default and skipped only for explicit synthetic mode. |
| `analysis/v9/capture_expected_v9.py` | 187 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/capture_expected_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/capture_expected_v9.py` | insert_after_5 | synthetic-guard | Default-off environment flag support; no calculation or predicate changed. |
| `analysis/v9/capture_expected_v9.py` | insert_after_6 | synthetic-guard | Default-off environment flag support; no calculation or predicate changed. |
| `analysis/v9/capture_format_finish_v9.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/capture_format_finish_v9.py` | 27 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/capture_format_finish_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/checks/capture_public_roundtrip_v9.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/capture_public_roundtrip_v9.py` | 27 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/capture_public_roundtrip_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/checks/capture_schema_v9.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/capture_schema_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/checks/decomp_preflight_v9.py` | 7 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/decomp_preflight_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/checks/decomp_public_check_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/decomp_v9.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/decomp_v9.py` | 159 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/decomp_v9.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v9/checks/environment_v9.py` | 5 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/environment_v9.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v9/checks/environment_v9.py` | insert_after_0 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/audit_final_metadata_spatial_v7.py` | 8 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/audit_final_metadata_spatial_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/audit_probe_bounds_spatial_v7.py` | 9 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/audit_probe_bounds_spatial_v7.py` | insert_after_2 | path | One configuration/module-search-path line; no calculation changed. |
| `analysis/v7/checks/audit_public_v7_before_scientific_literal_fix.py` | 15 | path | Restricted source content replaced; original value intentionally omitted. |
| `analysis/v7/checks/audit_public_v7_before_scientific_literal_fix.py` | insert_after_6 | path | One configuration/module-search-path line; no calculation changed. |

Total records: 256. Category memberships: path=228, private_list=7, key=3, private_value=20, print=0, synthetic-guard=4. Multiple categories on one line are counted once in the record total.
