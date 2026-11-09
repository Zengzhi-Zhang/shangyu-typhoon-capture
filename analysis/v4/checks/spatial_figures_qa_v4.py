# -*- coding: utf-8 -*-
"""Structural and provenance checks for the six converted manuscript figures."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json,re,hashlib,zlib
from datetime import datetime,timezone,timedelta
from PIL import Image
import pandas as pd

ROOT=Path(_release_path('v4_root'));FIG=ROOT/'20_manuscript/figures';DATA=ROOT/'20_manuscript/source_data'
NAMES=['fig1_v4','fig3_v4','ed1_v4','ed2_v4','ed6_v4','ed7_v4']
def main():
    checks={};detail={}
    for name in NAMES:
        with Image.open(FIG/(name+'.png')) as im:
            dpi=im.info.get('dpi',(0,0));size=im.size
        pdf=(FIG/(name+'.pdf')).read_bytes()
        box=re.search(rb'/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]',pdf)
        width=(float(box[3])-float(box[1]))*25.4/72 if box else None
        checks[name+'_300dpi']=min(dpi)>=299.99
        checks[name+'_180mm_PDF_width']=width is not None and abs(width-180)<.001
        checks[name+'_embedded_TrueType']=b'/FontFile2' in pdf and b'/ToUnicode' in pdf and b'/Subtype /Type3' not in pdf
        # Heatmap cells and continuous colour bars can be image objects while
        # plot paths and every label remain vector/text in the page stream.
        contents=re.search(rb'/Contents\s+(\d+)\s+0\s+R',pdf)
        page=re.search(rb'(?m)^'+contents[1]+rb'\s+0\s+obj\s*(.*?)\s*endobj',pdf,re.S) if contents else None
        stream=page[1].split(b'stream\n',1)[1].rsplit(b'\nendstream',1)[0] if page else b''
        decoded=zlib.decompress(stream) if b'/FlateDecode' in page[1] else stream
        checks[name+'_vector_paths_and_editable_text']=bool(re.search(rb'[0-9.]+\s+[0-9.]+\s+m\b',decoded)) and b'BT' in decoded and (b'TJ' in decoded or b'Tj' in decoded)
        q=pd.read_csv(DATA/(name+'_source_data.csv'),encoding='utf-8-sig')
        checks[name+'_provenance_columns']=all(c in q for c in ['source_file','source_row_or_key','panel'])
        checks[name+'_source_files_exist']=all(Path(p).exists() for p in q.source_file.dropna().unique())
        for c in ['plot_lon','plot_lat','lon','lat']:
            if c in q:checks[name+'_'+c+'_2dp']=bool((q[c].dropna()-q[c].dropna().round(2)).abs().lt(1e-12).all())
        checks[name+'_no_identifier_columns']=not any(c in q for c in ['dev','ph','plate','vehicle_id'])
        checks[name+'_no_replacement_character']='\ufffd' not in (DATA/(name+'_source_data.csv')).read_text(encoding='utf-8-sig')
        detail[name]={'PNG_pixels':size,'PNG_dpi':dpi,'PDF_width_mm':width,'PDF_height_mm':(float(box[4])-float(box[2]))*25.4/72,'source_rows':len(q),'PDF_image_objects':pdf.count(b'/Subtype /Image')}
    p=pd.read_csv(DATA/'spatial_number_provenance_v4.csv',encoding='utf-8-sig')
    checks['all_numeric_provenance_sources_exist']=all(Path(s).exists() for s in p.source_file.unique())
    checks['numeric_provenance_required_columns']=all(c in p for c in ['value','source_file','source_row_or_key','usage'])
    record=json.loads((ROOT/'00_env/spatial_figures_execution_v4.json').read_text(encoding='utf-8'))
    checks['all_frozen_inputs_still_unchanged']=all(hashlib.sha256(Path(s).read_bytes()).hexdigest()==h for s,h in record['input_sha256'].items())
    failed=[k for k,v in checks.items() if not v]
    result=dict(ended=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),all_passed=not failed,n_checks=len(checks),failed=failed,checks=checks,figures=detail)
    (ROOT/'00_env/spatial_figures_structural_qa_v4.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(all_passed=not failed,n_checks=len(checks),failed=failed)))
    if failed:raise RuntimeError('Figure structural QA failed')
if __name__=='__main__':main()
