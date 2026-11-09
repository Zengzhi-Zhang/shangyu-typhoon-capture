# -*- coding: utf-8 -*-
"""Syntax and synthetic rule checks only; no new observed effects."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import ast,json
import numpy as np
from health_helpers_v7 import ROOT,now,write_json
from health_screen_v7 import partial_day_candidate,ORDER,BAD,STRICT_BAD


def main():
    for name in ['health_helpers_v7.py','health_screen_v7.py','check_health_design_v7.py']:
        ast.parse((ROOT/'scripts'/name).read_text(encoding='utf-8-sig'))
    recording=np.array([5,11,4,12,5,7,3,11],float)
    stop=np.array([np.nan,17,np.nan,17,np.nan,15,18,np.nan])
    run=np.array([6,0,10,6,5,0,6,6],float)
    expected=np.array([True,True,False,False,False,True,False,True])
    got=partial_day_candidate(recording,stop,run)
    checks=dict(all_scripts_AST=True,raw5_and11_inclusive=bool(got[0] and got[1]),
        raw4_and12_excluded=bool(not got[2] and not got[3]),
        missing_stop_does_not_trigger_without6zero=bool(not got[4]),
        finite_stop_triggers=bool(got[5]),July25_raw3_does_not_become5=bool(not got[6]),
        exact_synthetic_expected=np.array_equal(got,expected),
        priority_offline_then_partial_day_then_channel=ORDER.index('offline')<ORDER.index('partial_day')<ORDER.index('partial_channel'),
        broad_exclusion_has_no_degraded_ratio_states='degraded_other' not in BAD and 'low_all_channels' not in BAD,
        strict_adds_exactly_two_ratio_states=set(STRICT_BAD)-set(BAD)=={'degraded_other','low_all_channels'})
    result=dict(at=now(),all_passed=all(checks.values()),n_checks=len(checks),checks=checks,
        scope='AST plus synthetic arrays only; no observed state reclassification, ratios, models, panels, source or keys read')
    write_json(ROOT/'00_env/health_design_checks_v7.json',result)
    print(json.dumps(dict(all_passed=result['all_passed'],n_checks=result['n_checks'])))
    if not result['all_passed']:raise AssertionError('Health design checks failed')


if __name__=='__main__':main()
