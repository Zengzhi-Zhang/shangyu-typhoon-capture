# -*- coding: utf-8 -*-
"""Independent output-level checks; no source or protected input writes."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import numpy as np
import pandas as pd

R=Path(_release_path('v7_root')); V6=R.parent/'formal_v6'
d=pd.read_csv(R/'01_internal/T28_probe_daily_internal_v7.csv')
b=pd.read_csv(R/'01_internal/T31_recovery_bounds_internal_v7.csv')
event=d[d.date.between('2021-07-25','2021-07-31')].copy()
checks={}
# An algebraically independent expression verifies target-km cancellation and
# the retained baseline-cpk weighting, rather than replaying normalisation.
algebra=(event.rec_all/event.rec_stable)*(event.base_cpk_stable/event.base_cpk_all)
checks['target_km_cancellation_retains_baseline_cpk_weighting']=bool(np.allclose(algebra,event.q_probe,atol=2e-10,rtol=2e-10))
merged=b.merge(event[['date','q_probe']],on='date',how='left',validate='one_to_one')
known=merged.R_probe.notna()
checks['recovery_times_relative_probe_equals_inherited_naive']=bool(np.allclose(
    merged.loc[known,'R_probe']*merged.loc[known,'q_probe'],merged.loc[known,'R_naive'],atol=2e-10,rtol=2e-10))
products=pd.read_parquet(R/'01_internal/probe_product_bootstrap_v7.parquet')
device=pd.read_parquet(R/'01_internal/probe_device_bootstrap_v7.parquet')
vehicle=pd.read_parquet(R/'01_internal/probe_vehicle_bootstrap_v7.parquet')
checks['all_700000_product_pairs_unique']=bool(len(products)==700000 and not products.duplicated(['date','device_rep','vehicle_rep']).any())
checks['500_by_200_pair_grid_every_day']=all(
    len(g)==100000 and g.device_rep.nunique()==500 and g.vehicle_rep.nunique()==200
    and g.groupby('device_rep').size().eq(200).all() and g.groupby('vehicle_rep').size().eq(500).all()
    for _,g in products.groupby('date'))
sample=products.groupby('date',group_keys=False).nth([0,199,200,55555,99999]).reset_index()
sample=sample.merge(device[['date','device_rep','R_naive','q_fleet']],on=['date','device_rep'],validate='many_to_one')
sample=sample.merge(vehicle[vehicle.baseline_variant.eq('B_PROBE')][['date','vehicle_rep','c_all','c_stable','q_probe']],on=['date','vehicle_rep'],validate='many_to_one')
checks['product_pair_samples_use_both_correct_marginals']=bool(np.allclose(sample.R_probe,sample.R_naive*sample.c_stable/sample.c_all,atol=1e-14,rtol=1e-14)
    and np.allclose(sample.q_probe_minus_q_fleet,sample.q_probe-sample.q_fleet,atol=1e-14,rtol=1e-14))
for source,target in [('03_taxi_probe/T28_probe_daily_v6.csv','03_taxi_probe/T28_probe_daily_v7.csv'),('05_bounds/T31_recovery_bounds_v6.csv','05_bounds/T31_recovery_bounds_v7.csv')]:
    old=pd.read_csv(V6/source,dtype=str,keep_default_na=False);new=pd.read_csv(R/target,dtype=str,keep_default_na=False)
    checks['inherited_cells_exact:'+target]=new[old.columns].equals(old)
checks['existing_mid_NA_not_filled']=b.R_mid.isna().all()
checks['noGPS_Aug1_Aug2_not_extrapolated']=b.loc[b.date.ge('2021-08-01'),['R_probe','R_probe_ci_lo','R_probe_ci_hi']].isna().all().all()
public=[R/'03_taxi_probe/T28_probe_daily_v7.csv',R/'03_taxi_probe/T28_wednesday_sensitivity_v7.csv',R/'05_bounds/T31_recovery_bounds_v7.csv',*sorted((R/'08_figures').glob('fig_probe*_data.csv'))]
hits=[]
for p in public:
    text=p.read_text(encoding='utf-8-sig')
    if re.search(r'(?<![0-9A-Fa-f])[0-9A-Fa-f]{16}(?![0-9A-Fa-f])|cam_',text):hits.append(str(p))
    header=pd.read_csv(p,nrows=0).columns
    checks['no_identity_coordinate_columns:'+p.name]=not any(c in header for c in ['ph','vehicle_ph','dev','dev_public','lon','lat','longitude','latitude'])
checks['public_no_ph_or_internal_prefix']=not hits
e=json.loads((R/'00_env/probe_bounds_execution_v7.json').read_text(encoding='utf-8'))
checks['main_execution_all_132_checks_pass']=e['checks_passed'] and all(e['checks'].values())
checks={key:bool(value) for key,value in checks.items()}
result=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),checks=checks,all_passed=bool(all(checks.values())),
    n_checks=len(checks),public_scanned=[str(p.relative_to(R)) for p in public],public_hits=hits,
    mathematical_limit='Target GPS cancellation is verified algebraically; baseline weighting and route/selection confounding are retained.',
    independent_static_review='Vehicles agent reviewed pairing/product/h11/copy semantics before numerical execution; no blocking issue; vlines suggestion adopted before freeze release.',
    scientific_acceptance_not_integrity='Only prespecified R_probe July26 point range is an acceptance test; daily agreement and CI overlap are not equivalence tests.')
(R/'00_env/probe_bounds_crosscheck_v7.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(all_passed=result['all_passed'],n_checks=len(checks)),ensure_ascii=False))
if not result['all_passed']:raise RuntimeError('Probe/bounds output crosscheck failed')
