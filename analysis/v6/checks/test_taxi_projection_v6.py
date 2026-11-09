# -*- coding: utf-8 -*-
"""Synthetic-only parser checks; never reads any source workbook."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import struct,json
from pathlib import Path
import pandas as pd
import taxi_parse_v6 as p

def rec(code,data):return struct.pack('<HH',code,len(data))+data
def string(s):return struct.pack('<HB',len(s),1)+s.encode('utf-16le')
def main():
    # A deliberately invalid UTF16 value in an excluded SST entry must not decode.
    raw=struct.pack('<II',3,3)+string('时间')+struct.pack('<HB',1,1)+b'\x00\xd8'+string('速度')
    selected,meta=p.selected_sst([memoryview(raw)],{0,2})
    assert selected=={0:'时间',2:'速度'} and meta['sst_decoded']==2
    # A UTF16 character sequence continues as compressed Latin1 at CONTINUE.
    a=struct.pack('<II',1,1)+struct.pack('<HB',4,1)+'中A'.encode('utf-16le')
    b=b'\x00BC';q,_=p.selected_sst([memoryview(a),memoryview(b)],{0});assert q[0]=='中ABC'
    headers=list(p.COLS.values());strings=headers+['2021-07-19 08:00:00','载客','实时']
    # Add an excluded invalid SST value and cell. Neither gets decoded.
    sst=struct.pack('<II',len(strings)+1,len(strings)+1)+b''.join(string(s) for s in strings)+struct.pack('<HB',1,1)+b'\x00\xd8'
    sheet=rec(0x0809,struct.pack('<HH',0x600,0x10))
    for i,col in enumerate(p.COLS):sheet+=rec(0xfd,struct.pack('<HHHI',1,col,0,i))
    for col,idx in [(0,7),(3,8),(7,9)]:sheet+=rec(0xfd,struct.pack('<HHHI',2,col,0,idx))
    for col,val in [(1,25.),(8,120.9),(9,30.0)]:sheet+=rec(0x203,struct.pack('<HHHd',2,col,0,val))
    sheet+=rec(0x27e,struct.pack('<HHHI',2,2,0,(90<<2)|2))
    sheet+=rec(0xfd,struct.pack('<HHHI',2,10,0,10))+rec(0x0a,b'')
    bof=rec(0x0809,struct.pack('<HH',0x600,5));date=rec(0x22,struct.pack('<H',0))
    bounds=lambda off:rec(0x85,struct.pack('<IBBBB',off,0,0,8,0)+b'20210719')
    off=len(bof+date+bounds(0)+rec(0xfc,sst)+rec(0x0a,b''))
    wb=bof+date+bounds(off)+rec(0xfc,sst)+rec(0x0a,b'')+sheet
    frames,mode,counts=p.projected_biff(wb)
    assert len(frames)==1 and list(frames[0].columns)==headers and frames[0].iloc[0]['速度']==25
    assert frames[0].iloc[0]['方向']==90 and counts['sst_decoded']==10 and counts['unselected_cells_skipped']==1
    wrong=wb.replace('车辆状态'.encode('utf-16le'),'司机XX'.encode('utf-16le')).replace(rec(0xfd,struct.pack('<HHHI',2,3,0,8)),rec(0xfd,struct.pack('<HHHI',2,3,0,10)))
    try:p.projected_biff(wrong);raise AssertionError('mismatched header accepted')
    except p.SafeParseError as exc:assert str(exc)=='seven_column_header_mismatch'
    ts=p.parse_times(pd.Series(['2021/7/19 08:00:00',44396.5]),0);assert ts.notna().all()
    # Equivalent vectorised carry-forward legacy distance on synthetic values.
    p.baiguan_xy=lambda:(0.,0.)
    f=pd.DataFrame(dict(timestamp=pd.to_datetime(['2021-07-19 10:00:00','2021-07-19 10:00:30','2021-07-19 10:01:00']),date=['2021-07-19']*3,lon=[120.90,float('nan'),_release_private('private_value_015')],lat=[30.,float('nan'),30.],valid_xy=[True,False,True],moving=[True,True,True],occupied=[True]*3))
    m=p.daily_metrics(f,'synthetic')[0];d=float(p.haversine(120.90,30.,_release_private('private_value_015'),30.));assert abs(m['dist_km']-d)<1e-10
    report=dict(all_passed=True,source_workbooks_read=0,unselected_invalid_UTF16_skipped=True,header_validation_precedes_data_decode=True,continuation_encoding_switch=True,full_projected_BIFF=True,legacy_carry_forward_distance=True,selected_columns=list(p.COLS),counters=counts)
    target=Path(_release_path('path_029'));target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
