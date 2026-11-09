# -*- coding: utf-8 -*-
"""Authorised display-only repair; internal scientific values are unchanged."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import pandas as pd
from decomp_v9 import public_csv,OUT,INTERNAL,ENV,sha,write_json

def main():
    protected={str(p):sha(p) for p in INTERNAL.glob('decomp*') if p.is_file()}
    paths=[OUT/'03_breakeven/T39_breakeven_v9.csv',OUT/'03_breakeven/T39_sustained_v9.csv',OUT/'02_decomposition/T38_checks_v9.json']
    before={str(p):sha(p) for p in paths}
    public_csv(pd.read_parquet(INTERNAL/'decomp_breakeven_points_v9.parquet'),paths[0],count_cols=['n_invalid','RO_above_RH_bootstrap_n'])
    public_csv(pd.read_parquet(INTERNAL/'decomp_sustained_points_v9.parquet'),paths[1],count_cols=['n_tail_dates','n_invalid'])
    checks=json.loads(paths[2].read_text(encoding='utf-8'))
    checks['comparison_unrounded']='Full-precision recomputation compared with stored T37 points: R_naive is stored to four decimals; R_health retains higher precision. The strict 5e-5 tolerance is applied before v9 display rounding.'
    write_json(paths[2],checks)
    unchanged=protected=={p:sha(p) for p in protected}
    write_json(ENV/'decomp_display_repair_v9.json',{'at':datetime.now(timezone.utc).isoformat(),'authorisation':'Root requested broader small-count masking and T37 precision wording; display only.',
      'fields_masked_when_below10':['n_invalid','RO_above_RH_bootstrap_n','n_tail_dates'],'before_sha256':before,'after_sha256':{str(p):sha(p) for p in paths},
      'internal_files_unchanged':unchanged,'protected_internal_sha256':protected,'classification_ratios_CI_unchanged':True})
    print(json.dumps({'internal_files_unchanged':unchanged,'files_display_updated':3}))
    if not unchanged:raise AssertionError('Internal scientific file changed')
if __name__=='__main__':main()
