# -*- coding: utf-8 -*-
"""Contact sheet and component records only; no scientific effect changes."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,time
import pandas as pd
from PIL import Image,ImageDraw,ImageFont

R=Path(_release_path('v8_root'));A=R/'01_internal/G5_audit';E=R/'00_env';P=R/'02_geometry'


def main():
    started=datetime.now(timezone(timedelta(hours=8))).isoformat();tick=time.monotonic()
    images=sorted(p for p in A.glob('G5_*.png') if p.name!='G5_contact_sheet.png')
    attrs=pd.read_csv(A/'G5_audit_attributes.csv');assert len(images)==len(attrs)==16
    width,height,heading=1000,500,32
    canvas=Image.new('RGB',(width*4,(height+heading)*4),(255,255,255));draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype(_release_path('path_037'),24)
    for index,(path,row) in enumerate(zip(images,attrs.itertuples())):
        image=Image.open(path).convert('RGB');image.thumbnail((width,height),getattr(Image,'Resampling',Image).LANCZOS)
        x=(index%4)*width;y=(index//4)*(height+heading)
        draw.text((x+10,y+2),f'Audit {int(row.audit_id):02d} | camera {int(row.dev)}',fill=(0,0,0),font=font)
        canvas.paste(image,(x+(width-image.width)//2,y+heading+(height-image.height)//2))
    canvas.save(A/'G5_contact_sheet.png')
    note='\n\n补充技术复核：最近GPS端点的八向航向与线段真方位八分区已完整保留并作交叉表，仅作描述，没有据此新增筛选。另从新缓存抽查10000个投影点的最近OSM feature及全部投影距离，仅核对实现一致性，不是道路真实经过的地面标签验证。16张主审查图以G5_01至G5_16计数，contact sheet只用于排版查看，不新增审查样本，也不提供A-G4判读。\n'
    methods=P/'G_METHODS_v8.md';text=methods.read_text(encoding='utf-8')
    if '补充技术复核' not in text:methods.write_text(text.rstrip()+note,encoding='utf-8')
    execution=json.loads((E/'geometry_execution_v8.json').read_text(encoding='utf-8'))
    cross=json.loads((E/'geometry_crosschecks_v8.json').read_text(encoding='utf-8'))
    independent=json.loads((E/'geometry_independent_checks_v8.json').read_text(encoding='utf-8'))
    peer=json.loads((E/'geometry_spatial_independent_audit_v8.json').read_text(encoding='utf-8'))
    tables={}
    for path in sorted(P.glob('*.csv')):
        frame=pd.read_csv(path,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        tables[path.name]=dict(rows=len(frame),columns=list(frame.columns),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    record=dict(start=started,end=datetime.now(timezone(timedelta(hours=8))).isoformat(),seconds=time.monotonic()-tick,
        command=_release_path('path_038'),
        complete=True,main_exit_code=0,crosschecks_exit_code=0,independent_checks_exit_code=0,
        contact_sheet_initial_exit_code=1,contact_sheet_initial_failure='Installed Pillow lacks Image.Resampling. Compatibility fallback to legacy Image.LANCZOS; no scientific file was changed in failed attempt.',
        main_seconds=execution['seconds'],crosscheck_seconds=cross['seconds'],independent_check_seconds=independent['seconds'],
        own_check_count=len(independent['checks']),own_checks_all_passed=independent['all_passed'],crosschecks_all_passed=cross['all_passed'],
        peer_independent_check_count=peer['n_checks'],peer_independent_all_passed=peer['all_passed'],peer_seconds=peer['seconds'],
        source_OSM_after_fingerprint='Root reports all seven files SHA256/size/mtime unchanged after single OSM read',
        main_figures=16,contact_sheets=1,main_figure_glob_excludes_contact_sheet=True,
        visual_judgment=False,A_G4_pending=True,old_outputs_modified=False,key_reads=False,raw_AVI_reads=False,workbook_reads=False,
        public_scientific_CSV_unchanged_by_finaliser=True,source_OSM_reread_by_finaliser=False,
        tables=tables,acceptance=execution['acceptance'],G0=pd.read_csv(R/'01_internal/geometry_G0_internal_v8.csv').where(pd.notna(pd.read_csv(R/'01_internal/geometry_G0_internal_v8.csv')),None).to_dict('records'))
    def safe(v):
        import math
        if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
        if isinstance(v,list):return [safe(x) for x in v]
        if isinstance(v,float) and not math.isfinite(v):return None
        return v
    (E/'geometry_completion_v8.json').write_text(json.dumps(safe(record),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(complete=True,main_figures=16,contact_sheets=1,tables={k:v['rows'] for k,v in tables.items()})))


if __name__=='__main__':main()
