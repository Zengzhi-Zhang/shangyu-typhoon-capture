# -*- coding: utf-8 -*-
"""Cached-only heading and geometry cross-checks, without visual judgments."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,time
import numpy as np,pandas as pd,geopandas as gpd,shapely
from shapely.strtree import STRtree
from pyproj import Transformer

R=Path(_release_path('v8_root'));BASE=R.parent


def main():
    start=datetime.now(timezone(timedelta(hours=8))).isoformat();tick=time.monotonic()
    p=pd.read_parquet(R/'01_internal/geometry_passages_v8.parquet')
    labels=np.asarray(['N','NE','E','SE','S','SW','W','NW'])
    p['segment_octant']=labels[(np.floor((p.bearing+22.5)/45).astype(int)%8)]
    raw=p.GPS_heading.fillna('').astype(str).str.strip()
    mapping={'北':'N','正北':'N','东北':'NE','东':'E','正东':'E','东南':'SE','南':'S','正南':'S','西南':'SW','西':'W','正西':'W','西北':'NW',
             'N':'N','NE':'NE','E':'E','SE':'SE','S':'S','SW':'SW','W':'W','NW':'NW'}
    p['GPS_heading_octant']=raw.map(mapping).fillna('unmapped')
    period=[('control_full8',p[p.date.lt('2021-07-20')]),('control_h11_8',p[p.date.lt('2021-07-20')&p.sec.ge(39600)])]
    for day in ['2021-07-25','2021-07-26','2021-07-27','2021-07-28']:
        period.append((day,p[p.date.eq(day)&(p.sec.ge(39600) if day=='2021-07-25' else np.ones(len(p),bool))]))
    tables=[];description=[]
    for name,part in period:
        t=part.groupby(['GPS_heading_octant','segment_octant'],dropna=False).size().reset_index(name='expected_passages');t.insert(0,'period',name);tables.append(t)
        mapped=part.GPS_heading_octant.ne('unmapped')
        description.append(dict(period=name,expected_passages=len(part),mapped_heading_passages=int(mapped.sum()),unmapped_heading_passages=int((~mapped).sum()),
            exact_octant_agreement=float(part.loc[mapped,'GPS_heading_octant'].eq(part.loc[mapped,'segment_octant']).mean()) if mapped.any() else np.nan,
            use='crosscheck_only_not_selection'))
    cross=pd.concat(tables,ignore_index=True);describe=pd.DataFrame(description)
    cross.to_csv(R/'01_internal/geometry_heading_crosscheck_internal_v8.csv',index=False,encoding='utf-8-sig')
    describe.to_csv(R/'01_internal/geometry_heading_summary_internal_v8.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    for frame,name in [(cross,'G_heading_crosscheck_v8.csv'),(describe,'G_heading_summary_v8.csv')]:
        f=frame.copy()
        for col in [c for c in f if c.endswith('passages')]:f[col]=f[col].map(lambda x:'<10' if x<10 else str(int(x)))
        f.to_csv(R/'02_geometry'/name,index=False,encoding='utf-8-sig',float_format='%.4f',na_rep='NA')
    dirs=json.loads((R/'01_internal/geometry_directions_v8.json').read_text(encoding='utf-8'))
    cube=np.load(R/'01_internal/geometry_counts_v8.npz',allow_pickle=False)
    pd.DataFrame([dict(dev=int(cube['camera_ids'][int(i)]),direction_set='|'.join(sorted(v)),wildcard='其他' in v,n_direction_labels=len(v)) for i,v in dirs.items()]).to_csv(R/'02_geometry/G1_direction_sets_v8.csv',index=False,encoding='utf-8-sig')
    rng=np.random.default_rng(20261005);sample=p.iloc[np.sort(rng.choice(len(p),min(len(p),10000),replace=False))]
    roads=gpd.read_parquet(R/'01_internal/geometry_roads_projected_v8.parquet');tree=STRtree(roads.geometry.to_numpy())
    pairs=tree.query_nearest(shapely.points(sample.x.to_numpy(),sample.y.to_numpy()),all_matches=True)
    order=np.lexsort((pairs[1],pairs[0]));pairs=pairs[:,order];_,first=np.unique(pairs[0],return_index=True);pairs=pairs[:,first]
    result=np.full(len(sample),-1,int);result[pairs[0]]=pairs[1]
    road_ok=np.array_equal(result,sample.road_i.to_numpy())
    attrs=pd.read_csv(BASE/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True)
    all_xy=np.column_stack(Transformer.from_crs(4326,32651,always_xy=True).transform(attrs.lon.to_numpy(),attrs.lat.to_numpy()))
    camera_xy=all_xy[cube['camera_ids'].astype(int)-1]
    near=np.hypot(p.x.to_numpy()-camera_xy[p.camera_i.to_numpy(int),0],p.y.to_numpy()-camera_xy[p.camera_i.to_numpy(int),1])
    projection_error=float(np.max(np.abs(near-p.distance_m.to_numpy())))
    checks=dict(nearest_OSM_feature_sample_10000_exact=bool(road_ok),all_projection_distances_match=projection_error<1e-6,
                octants_cover_all_passages=int(cross[cross.period.eq('control_full8')].expected_passages.sum())==int(p.date.lt('2021-07-20').sum()))
    report=dict(start=start,end=datetime.now(timezone(timedelta(hours=8))).isoformat(),seconds=time.monotonic()-tick,
        command=_release_path('path_036'),
        source_reads=False,key_reads=False,no_selection_or_effect_changes=True,OSM_cache_only=True,checks=checks,all_passed=all(checks.values()),
        projection_error_max_m=projection_error,nearest_OSM_sample_size=len(sample),heading_labels=raw.value_counts().to_dict(),
        heading_note='Nearest endpoint GPS label versus segment true-bearing octant is descriptive only; turn/sample timing may differ. No heading disagreement is used as an exclusion.',
        visual_verdict_performed=False)
    (R/'00_env/geometry_crosschecks_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],checks=checks,heading_labels=list(raw.unique()),projection_error_max_m=projection_error),ensure_ascii=False))
    if not report['all_passed']:raise RuntimeError('cached_geometry_crosscheck_failure')


if __name__=='__main__':main()
