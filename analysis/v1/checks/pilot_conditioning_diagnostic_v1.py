# -*- coding: utf-8 -*-
"""Read-only conditioning diagnostic for Appendix D3, with actual source roads.

The legacy 40% is P(failure | corrected-road primary), 12/30, rather than
P(primary | failure). This diagnostic preserves both probabilities and their
denominators. It does not alter any frozen observation set or main covariate.
Run after final M4/M5 on the final local source attributes.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import hashlib
from common_v1 import *

SEED = 20261005
DATE = '2021-07-26'
CORRECTED = SOURCE/'10_上虞数据/AVI/(corrected)sensor_allroad_matched.csv'
OUTPUT = ROOT/'07_m6_robustness/m6_pilot_conditioning_diagnostic.csv'


def fingerprint(path):
    path=Path(path);stat=path.stat()
    with path.open('rb') as stream:
        head=stream.read(1024*1024)
        stream.seek(max(0,stat.st_size-1024*1024));tail=stream.read(1024*1024)
    return dict(path=str(path),size=stat.st_size,mtime_ns=stat.st_mtime_ns,
                sha256_head1MB=hashlib.sha256(head).hexdigest(),
                sha256_tail1MB=hashlib.sha256(tail).hexdigest())


def main():
    started=now()
    pilot_dir=REF/'results'
    inputs=[ROOT/'01_panels/device_attributes.csv',ROOT/'01_panels/device_hour.csv',
            ROOT/'01_panels/device_id_map.csv',ROOT/'06_m5_bias_correction/m5_failure_counts.csv',
            pilot_dir/'device_panel.csv',pilot_dir/'device_osm_attributes.csv',
            pilot_dir/'device_group_summary.csv',CORRECTED]
    before=[fingerprint(p) for p in inputs]
    dh,attr,dd=load_panels()
    selected=attr.index[attr.in_A200.eq(1)]
    n,den,_,kind=failure_vectors(DATE,dh,dd,'B1',False)
    failed=n.reindex(selected)<.05*den.reindex(selected)
    failure_days=pd.read_csv(inputs[3],encoding='utf-8-sig').set_index('date')
    if int(failed.sum())!=int(failure_days.loc[DATE,'n_failed_prevweek']):
        raise AssertionError('Formal diagnostic failure flags differ from final M5')
    corrected=pd.read_csv(CORRECTED,encoding='utf-8-sig',dtype=str)
    corrected['counts']=pd.to_numeric(corrected['counts'],errors='coerce')
    corrected=corrected.sort_values('counts',ascending=False).drop_duplicates('DEVICE_NAME').set_index('DEVICE_NAME')
    mapping=pd.read_csv(inputs[2],encoding='utf-8-sig',dtype=str).set_index('dev')
    names=mapping.dev_name.reindex(selected)
    road=names.map(corrected['Type'])
    pilot=pd.read_csv(inputs[4],encoding='utf-8-sig',index_col=0)
    pilot=pilot[pd.to_numeric(pilot.baseline_0712_0721,errors='coerce').ge(200)]
    osm=pd.read_csv(inputs[5],encoding='utf-8-sig',index_col=0)
    osm=osm[pd.to_numeric(osm.baseline_0712_0721,errors='coerce').ge(200)]
    rows=[]

    def add(sample,attribute,values,flags,scope,road_definition,denominator):
        values=values.fillna('missing').astype(str);flags=flags.reindex(values.index).astype(bool)
        total=len(values);nf=int(flags.sum())
        for category in sorted(values.unique()):
            m=values.eq(category);ng=int(m.sum());nfg=int(flags[m].sum())
            rows.append(dict(date=DATE,sample=sample,attribute=attribute,category=category,
                n_devices_total=total,n_failed_total=nf,n_group=ng,n_failed_group=nfg,
                P_failure_given_group=nfg/ng if ng else np.nan,
                P_group_given_failure=nfg/nf if nf else np.nan,
                sample_scope=scope,road_definition=road_definition,failure_denominator=denominator,
                failure_rate_definition='P(F|group)=n_failed_group/n_group',
                failure_composition_definition='P(group|F)=n_failed_group/n_failed_total'))

    pilot_failed=pd.to_numeric(pilot.off_0726,errors='coerce').eq(1)
    add('pilot_corrected_full_A200','road_class',pilot.road_class,pilot_failed,
        'Legacy mean B2 >=200, including devices without coordinates',
        'corrected sensor_allroad_matched Type; highest counts per device',
        'B2 same weekday; missing ratios filled 0 in frozen pilot')
    add('pilot_org_full_A200','org',pilot.org,pilot_failed,
        'Legacy mean B2 >=200, including devices without coordinates','not applicable',
        'B2 same weekday; missing ratios filled 0 in frozen pilot')
    osm_failed=pd.to_numeric(osm.off_0726,errors='coerce').eq(1)
    add('pilot_osm80m_coordinate_A200','road_level',osm.road_level,osm_failed,
        'Legacy mean B2 >=200, coordinate-valid subset',
        'Source OSM nearest road <=80m in UTM51N; primary includes primary_link',
        'B2 same weekday; frozen pilot off_0726')
    add('formal_corrected_full_A200','road_class',road,failed,
        'Frozen formal A200, including devices without coordinates',
        'Actual source corrected sensor_allroad_matched Type; highest counts per device',kind)
    formal=attr.reindex(selected)
    add('formal_osm80m_full_A200','road_level',formal.road_level,failed,
        'Frozen formal A200; missing coordinate/road is a reported missing layer',
        'Final formal source OSM nearest road <=80m in UTM51N; primary includes primary_link',kind)
    valid=formal.lon.notna()&formal.lat.notna()
    add('formal_osm80m_coordinate_A200','road_level',formal.loc[valid,'road_level'],failed,
        'Frozen formal A200, coordinate-valid subset',
        'Final formal source OSM nearest road <=80m in UTM51N; primary includes primary_link',kind)
    add('formal_org_full_A200','org',formal.org,failed,
        'Frozen formal A200, including devices without coordinates','not applicable',kind)
    out=pd.DataFrame(rows)
    primary=out[(out['sample']=='pilot_corrected_full_A200')&out.category.eq('primary')].iloc[0]
    source_org=out[(out['sample']=='pilot_org_full_A200')&out.category.eq(_release_private('private_value_001'))]
    group=pd.read_csv(inputs[6],encoding='utf-8-sig')
    legacy_primary=group[(group.group_by=='road_class')&group.road_class.eq('primary')].iloc[0]
    checks=dict(formal_failure_flags_match_final_M5=True,
        pilot_primary_reproduces_12_of_30=int(primary.n_failed_group)==12 and int(primary.n_group)==30,
        pilot_primary_40_percent_is_conditional=abs(float(legacy_primary.off_0726)-float(primary.P_failure_given_group))<.000001,
        pilot_org_reproduces_90_of_344=len(source_org)==1 and int(source_org.iloc[0].n_failed_group)==90 and int(source_org.iloc[0].n_group)==344)
    for sample,part in out.groupby('sample'):
        checks[sample+'_partition']=int(part.n_group.sum())==int(part.n_devices_total.iloc[0]) and int(part.n_failed_group.sum())==int(part.n_failed_total.iloc[0])
    after=[fingerprint(p) for p in inputs]
    checks['all_inputs_unchanged']=before==after
    if not all(checks.values()):raise AssertionError('Pilot conditioning diagnostic failed an explicit denominator check')
    save_csv(out,OUTPUT)
    write_json(ROOT/'00_env/pilot_conditioning_diagnostic_execution.json',dict(seed=SEED,started=started,ended=now(),
        status='complete',source_before=before,source_after=after,checks=checks,
        output=str(OUTPUT.relative_to(ROOT)),rows=len(out),
        interpretation='40% is legacy corrected-primary failure risk 12/30, not primary share among failures. 26% is legacy org failure risk 90/344. Road definition, A200 baseline and failure denominator remain labelled; comparison does not replace frozen formal definitions.',
        privacy='Only aggregate group counts/probabilities exported. Original device names exist in memory for joining and are never written.'))
    print(json.dumps(dict(pilot_conditioning='complete',rows=len(out),checks=len(checks)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
