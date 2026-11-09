# -*- coding: utf-8 -*-
"""Compare actual-date parsed point counts to existing formal v1 grid totals."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json
import pandas as pd
R=Path(_release_path('project_root'));V=R/'formal_v6'
def main():
    g=pd.read_csv(R/'01_panels/taxi_grid_day.csv',encoding='utf-8-sig');n=pd.read_csv(V/'01_internal/taxi_vehicle_day_v6.csv',encoding='utf-8-sig')
    a=g.groupby('date')[['n_points','n_moving']].sum().rename(columns={'n_points':'v1_actual_valid_points','n_moving':'v1_actual_valid_moving_points'})
    b=n.groupby('date').n_valid_xy.sum().rename('v6_actual_valid_points');a=a.join(b);a['valid_point_difference']=a.v6_actual_valid_points-a.v1_actual_valid_points
    a.reset_index().to_csv(V/'00_env/taxi_actualdate_point_validation_v6.csv',index=False,encoding='utf-8-sig')
    report=dict(source_reads=False,key_reads=False,dates=len(a),all_26_actual_valid_point_counts_equal=bool(len(a)==26 and a.valid_point_difference.eq(0).all()),total_v1_valid_points=int(a.v1_actual_valid_points.sum()),total_v6_valid_points=int(a.v6_actual_valid_points.sum()),max_absolute_daily_count_difference=int(a.valid_point_difference.abs().max()))
    (V/'00_env/taxi_actualdate_point_validation_v6.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
