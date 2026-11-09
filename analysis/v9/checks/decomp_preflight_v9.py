# -*- coding: utf-8 -*-
"""Input structure only. No new effect estimate or bootstrap is computed."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import hashlib,json
import pandas as pd

ROOT=Path(_release_path('project_root'))
FILES={
 'state':ROOT/'formal_v7/02_device_state/device_state_v7.csv',
 'family':ROOT/'formal_v7/07_consequences/T37_estimator_family_v7.csv',
 'day':ROOT/'01_panels/device_day.csv',
 'hour':ROOT/'01_panels/device_hour.csv',
 'attrs':ROOT/'01_panels/device_attributes.csv',
}
def main():
    report={'scope':'Schema, masking and fixed-membership coverage only; no new effects calculated','files':{}}
    frames={}
    for key,p in FILES.items():
        raw=p.read_bytes(); df=pd.read_csv(p,encoding='utf-8-sig',low_memory=False);frames[key]=df
        s=p.stat(); report['files'][key]={'path':str(p),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(df),'columns':df.columns.tolist()}
    state,attrs=frames['state'],frames['attrs'].sort_values('dev').reset_index(drop=True)
    public_a100=set((attrs.index[attrs.in_A100.eq(1)]+1).tolist())
    public_a200=set((attrs.index[attrs.in_A200.eq(1)]+1).tolist())
    event=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
    report['state']={'dev_dtype':str(state.dev.dtype),'dev_unique':int(state.dev.nunique()),'dates':sorted(state.date.unique().tolist()),'A100_fixed_n':len(public_a100),'A200_fixed_n':len(public_a200),'daily_coverage':{},'masking':{}}
    for date in event:
        q=state[state.date.eq(date)];ids=set(q.dev.tolist())
        report['state']['daily_coverage'][date]={'rows':len(q),'unique_dev':len(ids),'A100_missing':len(public_a100-ids),'A200_missing':len(public_a200-ids),'duplicates':int(q.dev.duplicated().sum()),'hour_matched_values':sorted(q.hour_matched.unique().tolist())}
    for col in ['n_day','baseline_B1','denominator_A1','n_unread','in_health','in_health_strict']:
        s=state[col].astype(str);num=pd.to_numeric(state[col],errors='coerce')
        report['state']['masking'][col]={'literal_lt10':int(s.eq('<10').sum()),'other_nonnumeric_nonmissing':int((num.isna()&state[col].notna()).sum()),'numeric_under10_nonnegative':int(((num>=0)&(num<10)).sum()),'missing':int(state[col].isna().sum())}
    report['attrs']={'rows':len(attrs),'unique_dev':int(attrs.dev.nunique()),'public_id_map_rule':'1-based row after dev lexical sort, as frozen v7','A100_n':len(public_a100),'A200_n':len(public_a200)}
    report['day']={'n_dtype':str(frames['day'].n.dtype),'duplicate_dev_date':int(frames['day'].duplicated(['dev','date']).sum()),'date_min':str(frames['day'].date.min()),'date_max':str(frames['day'].date.max())}
    report['hour']={'n_dtype':str(frames['hour'].n.dtype),'hour_values':sorted(frames['hour'].hour.unique().tolist()),'duplicate_dev_date_hour':int(frames['hour'].duplicated(['dev','date','hour']).sum()),'date_min':str(frames['hour'].date.min()),'date_max':str(frames['hour'].date.max())}
    out=ROOT/'formal_v9/00_env/decomp_preflight_v9.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['state','attrs','day','hour']},ensure_ascii=False))
if __name__=='__main__':main()
