# -*- coding: utf-8 -*-
"""Synthetic equivalence and moving-h11 checks without source or panel IO."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json
import numpy as np
import pandas as pd
import taxi_parse_v6 as p
import taxi_ring_update_v6 as u


def main():
    x,y=p.PROJECT.transform(120.9,30.0)
    p.baiguan_xy=lambda:(x,y);u.baiguan_xy=lambda:(x,y)
    g=pd.DataFrame(dict(timestamp=pd.to_datetime(['2021-07-25 10:59:00','2021-07-25 11:00:00','2021-07-25 11:01:00','2021-07-25 11:02:00','2021-07-25 11:03:00']),date=['2021-07-25']*5,lon=[120.9,_release_private('private_value_016'),np.nan,_release_private('private_value_015'),_release_private('private_value_017')],lat=[30.,30.,np.nan,30.,30.],valid_xy=[True,True,False,True,True],moving=[False,True,False,False,True],occupied=[False]*5))
    checks={}
    for method in ['raw_WGS84','constant_UTM_shift','GCJ02_to_WGS84']:
        cal=dict(selected_method=method,applied_dx_m=100.,applied_dy_m=-50.)
        previous=p.daily_metrics(g,'synthetic',cal)[0];new=u.calibrated_ring_rows(g,cal)[0]
        fields=[c for c in previous if c.startswith(('km_ring_','km_total_ring_','km_moving_ring_','pts_ring_'))]
        assert all(np.isclose(new[c],previous[c],rtol=0,atol=1e-12) for c in fields)
        assert np.isclose(sum(new['km_moving_ring_h11_'+r] for r in p.RINGS),new['km_moving_from_11h'])
        assert 0<new['km_moving_from_11h']<previous['km_from_11h']<previous['dist_km']
        checks[method]=True
    report=dict(all_passed=True,source_reads=0,panel_reads=0,key_reads=0,existing_ring_semantics_equal=True,moving_h11_start_hour_and_endpoint_rule=True,methods=checks)
    (p.OUT/'00_env/taxi_ring_update_synthetic_v6.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
