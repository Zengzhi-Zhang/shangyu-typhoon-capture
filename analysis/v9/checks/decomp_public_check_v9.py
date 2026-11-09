# -*- coding: utf-8 -*-
"""Read-only validation of this component's public display and identifiers."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
from pathlib import Path
import json,re
import numpy as np,pandas as pd
from decomp_v9 import OUT,INTERNAL,ENV,INPUTS,read,sha,write_json

def main():
    files=[OUT/'02_decomposition/T38_decomposition_v9.csv',OUT/'02_decomposition/T38_checks_v9.json',OUT/'03_breakeven/T39_breakeven_v9.csv',OUT/'03_breakeven/T39_sustained_v9.csv']
    before={str(p):sha(p) for p in files};checks={};hits={}
    attrs=read(INPUTS['attrs'],usecols=['dev','org']);restricted=set(attrs.dev.astype(str))|set(attrs.org.dropna().astype(str))
    numeric=re.compile(r'(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?(?![\w.])')
    alias=re.compile(r'(?i)(?<![0-9a-f])[0-9a-f]{16}(?![0-9a-f])')
    for path in files:
        text=path.read_text(encoding='utf-8');legal=[m.span() for m in numeric.finditer(text)]
        token_hits=[m for m in alias.finditer(text) if not any(a<=m.start() and m.end()<=b for a,b in legal)]
        exact_hits=sum(bool(v and v in text) for v in restricted)
        hits[path.name]={'hex16':len(token_hits),'internal_prefix':len(re.findall(r'(?i)cam_',text)),'exact_device_or_org':exact_hits}
    checks['no_public_identifier_hits']=not any(sum(v.values()) for v in hits.values())
    checks['no_coordinate_columns']=all(not any(c.lower() in {'lon','lat','longitude','latitude','x','y'} for c in read(p).columns) for p in files if p.suffix=='.csv')
    configs=[('decomp_points_v9.parquet',files[0],['n_A100','n_A200','n_H','n_O','n_O_ci_lo','n_O_ci_hi']),
      ('decomp_breakeven_points_v9.parquet',files[2],['n_invalid','RO_above_RH_bootstrap_n']),
      ('decomp_sustained_points_v9.parquet',files[3],['n_tail_dates','n_invalid'])]
    for source,path,count_cols in configs:
        full=pd.read_parquet(INTERNAL/source);pub=read(path,dtype=str,keep_default_na=False)
        checks[path.name+'_row_count']=len(full)==len(pub)
        for c in full:
            if c in count_cols:
                expected=full[c].map(lambda x:'NA' if pd.isna(x) else '<10' if 0<=x<10 else str(int(np.rint(x))))
            elif pd.api.types.is_float_dtype(full[c]):expected=full[c].map(lambda x:'NA' if pd.isna(x) else f'{x:.4f}')
            else:expected=full[c].astype(str)
            checks[path.name+'_'+c+'_display_exact']=expected.tolist()==pub[c].tolist()
    checks['all_checked_files_unchanged']=before=={p:sha(p) for p in before}
    report={'all_passed':all(checks.values()),'n_checks':len(checks),'privacy_total_hits':sum(sum(v.values()) for v in hits.values()),'n_public_files':len(files),'checks':checks,'hits':hits,'sha256':before,'scientific_files_modified':False}
    write_json(ENV/'decomp_public_checks_v9.json',report)
    print(json.dumps({k:report[k] for k in ['all_passed','n_checks','privacy_total_hits','n_public_files']}))
    if not report['all_passed']:raise AssertionError('Display/privacy audit failed')
if __name__=='__main__':main()
