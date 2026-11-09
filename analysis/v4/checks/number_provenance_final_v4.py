# -*- coding: utf-8 -*-
"""Register individual numeric text occurrences and inherited numeric figure cells.

Uses existing result registries, active figure-source CSVs, and frozen definitions.
Unresolved numeric tokens are reported, never silently assigned to an estimate.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import pandas as pd, re, json, math
from collections import defaultdict
R=Path(_release_path('project_root'));O=R/'formal_v4';M=O/'20_manuscript'
P=Path(_release_path('path_005'))
DISPLAY=dict(ci_level_percent=95,device_bootstrap=500,grid_bootstrap=500,vehicle_bootstrap=200,
    lower_percentile=2.5,upper_percentile=97.5,raw_MAD_multiplier=2.5,
    map_jitter_each_axis_m=200,public_coordinate_decimal_degrees=.01,
    map_colour_scale_max=1.2,box_lower_quartile_percent=25,box_upper_quartile_percent=75,
    box_whisker_IQR_multiplier=1.5)
(O/'00_env/figure_display_parameters_v4.json').write_text(json.dumps(dict(parameters=DISPLAY,
    sources=['v2 §§3.9,8; v3 A6; existing v3 figure-source jitter',
             'root_figures_v4.py; spatial_figures_v4.py; bias_manuscript_v4.py'],
    scope='Presentation conventions inherited from existing estimates; no statistical rules changed'),ensure_ascii=False,indent=2),encoding='utf-8')
RX=re.compile(r'[-+−]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?')
OUT=[];UN=[]
def val(x):
    try:return float(str(x).replace(',','').replace('−','-'))
    except:return None
def equal(a,b):
    return val(a) is not None and val(b) is not None and math.isclose(val(a),val(b),rel_tol=1e-10,abs_tol=1e-12)
def write_row(num,src,loc,exact,deriv,usage,context,kind):
    src=Path(src)
    if not src.is_absolute():src=R/src
    assert src.is_file(),str(src)
    OUT.append(dict(displayed_number=num,source_file=src.as_posix(),source_row_or_key=loc,exact_source_value=exact,derivation=deriv,usage=usage,context=context,registration_kind=kind))
old=pd.read_csv(M/'manuscript_number_provenance_v4.csv',encoding='utf-8-sig',dtype=str,keep_default_na=False)
byline=defaultdict(list)
for _,r in old.iterrows():
    mt=re.match(r'(.*):line (\d+)',r.usage)
    if mt:byline[(Path(mt[1]).name,int(mt[2]))].append(r.to_dict())
protocols=[]
for version in [2,3,4]:
    p=next(P.glob(f'*_v{version}_*版.md'))
    protocols.append((p,p.read_text(encoding='utf-8-sig').splitlines()))
def protocol_locator(token,context,preferred=None):
    options=[]
    for p,lines in protocols:
        for i,line in enumerate(lines,1):
            if any(equal(t[0],token) for t in [(z.group(),z.start()) for z in RX.finditer(line)]):
                # Prefer lines sharing formula terms and definition words.
                words=re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[\u4e00-\u9fff]{2,}',context)
                score=sum(min(len(w),8) for w in words if w in line)+(.1 if '_v4_' in p.name else 0)
                if preferred and preferred in line:score+=1000
                options.append((score,p,i,line))
    if not options:return None
    _,p,i,line=max(options,key=lambda x:x[0])
    return p,f'line {i}',token,'frozen definition or methodological constant; '+line
figcache={}
caption_counts=pd.read_csv(M/'source_data/spatial_number_provenance_v4.csv',encoding='utf-8-sig',dtype=str,keep_default_na=False)
def fig_match(token,key,context):
    caption_label='Fig.'+key[3:] if key.startswith('fig') else key.upper()
    if caption_label:
        q=caption_counts[caption_counts.usage.str.contains(caption_label,regex=False)&caption_counts.usage.str.contains('caption')&caption_counts.value.map(lambda x:equal(x,token))]
        if len(q):
            r=q.iloc[0]
            return Path(r.source_file),r.source_row_or_key,r.value,'existing caption sample size; exact count or sum specified in locator'
    p=M/f'source_data/{key}_v4_source_data.csv'
    if p not in figcache:figcache[p]=pd.read_csv(p,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    df=figcache[p];v=val(token);nd=len(token.split('.')[-1]) if '.' in token else 0
    if v is None:return None
    matches=[]
    for col in df.columns:
        if col.startswith('source_') or col in ['panel','k','hour','device_id','day_index']:continue
        nv=pd.to_numeric(df[col],errors='coerce')
        exact_mask=(nv-v).abs().le(1e-10)
        display_mask=nv.round(nd).eq(v) if nd else exact_mask
        for idx in nv.index[(exact_mask|display_mask)&nv.notna()][:5]:
            n=float(nv.loc[idx]);same=equal(n,v) or (nd and math.isclose(round(n,nd),v,abs_tol=1e-12))
            if not same:continue
            score=5 if equal(n,v) else 0
            if v<0 and n>=0:continue
            if 'p=' in context or 'P=' in context:score+=3 if col in ['p','spearman_p','kendall_p'] else 0
            if '系数' in context:score+=3 if 'coef' in col or col=='beta' else 0
            if any(w in context for w in ['台','设备','n=']):score+=3 if col.startswith('n_') or col in ['A100','A200','Sstar'] else 0
            matches.append((score,idx,col,df.loc[idx,col]))
        # Individual components of source date strings and ring labels.
        if col in ['date','target_date','baseline_date','ring','ring_merged','ring_original','ring_label']:
            for idx,s in df[col].drop_duplicates().items():
                if any(equal(z.group(),token) for z in RX.finditer(s)):
                    matches.append((-5,idx,col,s))
    if not matches:return None
    _,idx,col,raw=max(matches,key=lambda x:x[0])
    return p,f'CSV row {idx+2}; column {col}',raw,'existing figure-source value or date/ring component; rounded for display where applicable'
def explicit_caption(token,key,context,near,prefix,suffix):
    def pointer(p,k,derive='rounded source value'):
        p=R/p;raw=json.loads(p.read_text(encoding='utf-8-sig'))
        for part in k[1:].split('/'):raw=raw[int(part)] if isinstance(raw,list) else raw[part]
        return p,k,raw,derive
    if key=='fig4':
        persistence='formal_v3/06_m5_bias_correction/m5_failure_persistence_summary_v3.json'
        counts={'227':'/n_event_cohort','77':'/not_recovered_by_0802','1221':'/n_A200','1,221':'/n_A200','57':'/current_failed_A1_0802'}
        if token in counts:return pointer(persistence,counts[token])
        if token=='6.31':return pointer(persistence,'/share_A200','100*share_A200, rounded to two decimals')
        if token=='0.0217':return pointer('formal_v3/06_m5_bias_correction/m5_h4_verdict_v3.json','/criteria/3/observed/per_date_masking/8/drop_bias')
        if token=='0.02':
            return pointer('formal_v3/06_m5_bias_correction/m5_h4_verdict_v3.json','/criteria/3/threshold','frozen .02 threshold within complete textual criterion')
        if token in ['1,000','1000']:
            p=R/'formal_v3/06_m5_bias_correction/m5_leaveout_replicates.csv'
            return p,'count rows per method and masking across five dates',1000,'200 repeats/date * 5 dates per box'
        if token=='200' and ('重复' in near or 'repeats' in near):
            return R/'formal_v3/06_m5_bias_correction/m5_leaveout_replicates.csv','count distinct replicate per date/method/masking',200,'leave-out repetition count; differs from vehicle bootstrap count'
        if token=='5' and '日期' in near:
            return R/'formal_v3/06_m5_bias_correction/m5_leaveout_replicates.csv','count distinct date',5,'five leave-out target dates'
    if key=='ed8':
        indices={'0.9001':0,'0.8794':1,'0.9215':2}
        if token in indices:return pointer('formal_v3/07_m6_robustness/m6_b3_drift_v3.json','/phi/'+str(indices[token]))
        if token=='15':return pointer('formal_v3/07_m6_robustness/m6_b3_drift_v3.json','/n_dates')
    if key in ['fig2','ed3']:
        counts={'23':'/ordinary_n','32':'/combined_n','9':'/placebo_n'}
        if token in counts:return pointer('formal_v4/10_supplementary_analyses/t25_summary_v4.json',counts[token])
    if key=='ed5' and prefix.endswith('第'):
        p=R/'formal_v3/04_m3_vehicles/m3_return_gap.csv';df=pd.read_csv(p,encoding='utf-8-sig')
        q=df[df.first_k_gap_le_005.eq(val(token))]
        if len(q):
            r=q.iloc[0];return p,f'CSV row {r.name+2}; column first_k_gap_le_005; grp={r.grp}; thr={r.thr}',r.first_k_gap_le_005,'existing first day meeting deficit boundary'
    if key=='ed5' and token=='0.05':
        p=R/'formal_v3/04_m3_vehicles/m3_h2_verdict_v3.json';return p,'/criteria/0; frozen first deficit rule','0.05','first placebo-minus-typhoon deficit <=0.05'
    if key=='ed6' and token in ['0.006','0.001']:
        p=R/'formal_v3/07_m6_robustness/m6_signature_comparison_v3.csv';df=pd.read_csv(p,encoding='utf-8-sig')
        date='2021-07-08' if token=='0.006' else '2021-07-26' if '0.001' in prefix else '2021-07-10'
        r=df[df.date.eq(date)].iloc[0];return p,f'CSV row {r.name+2}; column joincount_knn6_p; date={date}',r.joincount_knn6_p,'existing join-count p; the same .001 also applies to July26'
    return None
# All numbers in the main text, methods, and both language caption files are
# registered at a precise text position. Methods are included beyond §5 scope.
files=[M/x for x in ['main_text_zh.md','methods_zh.md','figure_captions_zh.md','figure_captions_en.md']]
for p in files:
    key=None
    for ln,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
        if line.startswith('## '):
            mt=re.search(r'Extended Data Fig\. ([1-8])',line)
            mf=re.search(r'Fig\. ([1-4])',line)
            if mt:key='ed'+mt[1]
            elif mf:key='fig'+mf[1]
        for mt in RX.finditer(line):
            token=mt.group();usage=f'{p.relative_to(O).as_posix()}:line {ln}:char {mt.start()+1}'
            context=line[max(0,mt.start()-70):mt.end()+100]
            # Authored scientific and definition references take precedence.
            regs=[r for r in byline[(p.name,ln)] if equal(r['displayed_number'],token)]
            if regs:
                r=regs[0];src=Path(r['source_file'])
                if not src.is_absolute():src=R/src
                if not src.exists() and src.name.endswith('.md'):src=P/src.name
                write_row(token,src,r['source_row_or_key'],r['exact_source_value'],r['derivation'],usage,context,'authored_text_occurrence');continue
            # Bibliographic identifiers are verified metadata, not data effects.
            if line.startswith('[1]') or line.startswith('[2]') or ('[1,2]' in line and mt.start()>line.find('[1,2]')-1 and mt.start()<line.find('[1,2]')+6):
                write_row(token,M/'references_verified_v4.json','references; DOI/year/journal-volume/reference-index',token,'bibliographic or citation token',usage,context,'bibliographic_occurrence');continue
            # Identifiers embedded in H/A/B/T/v/HC/UTF/SHA and file paths.
            prefix=line[max(0,mt.start()-18):mt.start()]
            suffix=line[mt.end():mt.end()+15]
            identifier=bool(re.search(r'(?:H|A|B|T|v|HC|UTF-|SHA|AVI_|ED|Fig\. |表|§|log)\s*$',prefix)) or line.startswith('##') or bool(re.search(r'(?:formal_v|_v|\.csv|\.json|\.md|01_panels|Anaconda)',context) and val(token) in [1,2,3,4,8,16,24,25,26,256,20210627])
            if identifier:
                src=O/'00_env/protocol_frozen_v4.json'
                write_row(token,src,'/protocol_text; document/formula identifier','identifier '+token,'structural identifier, not an estimated quantity',usage,context,'structural_occurrence');continue
            near=line[max(0,mt.start()-30):mt.end()+45]
            if key and 'caption' in p.name:
                found=explicit_caption(token,key,context,near,prefix,suffix)
                if found:
                    write_row(token,*found,usage,context,'caption_exact_result_or_derived_count');continue
            param=None
            if token in ['200','500'] and (suffix.startswith('次') or re.search(r'(?:from|used|use|pooled|combine) '+token+r' |'+token+r' (?:device|vehicle|taxi|repeats|resamples)',near)):
                param='vehicle_bootstrap' if token=='200' else 'device_bootstrap'
            elif token=='95':param='ci_level_percent'
            elif token=='97.5':param='upper_percentile'
            elif token=='2.5':param='raw_MAD_multiplier' if 'MAD' in near else 'lower_percentile'
            elif token in ['25','75'] and suffix.startswith('%'):param='box_lower_quartile_percent' if token=='25' else 'box_upper_quartile_percent'
            elif token=='1.5' and ('IQR' in near or 'interquartile' in near):param='box_whisker_IQR_multiplier'
            elif token=='0.01' and '°' in near:param='public_coordinate_decimal_degrees'
            elif token=='1.2' and '色阶' in near:param='map_colour_scale_max'
            elif token in ['200','+200'] and ('抖动' in near or 'jitter' in near):param='map_jitter_each_axis_m'
            if param:
                write_row(token,O/'00_env/figure_display_parameters_v4.json','/parameters/'+param,DISPLAY[param],'verified presentation/resampling convention',usage,context,'display_parameter_occurrence');continue
            date_component=suffix.startswith(('月','日','年',':')) or (prefix.endswith(':')) or bool(re.search(r'(?:July|August|June|Jul|Aug|Jun)\s*$',prefix)) or bool(re.match(r' (?:July|August|June|Jul|Aug|Jun)',suffix))
            if date_component:
                found=protocol_locator(token,context)
                if found:
                    write_row(token,*found,usage,context,'frozen_date_component');continue
            # Source data resolve caption effect/count/interval values.
            found=fig_match(token,key,context) if key and 'caption' in p.name else None
            if found:
                write_row(token,*found,usage,context,'caption_source_cell');continue
            # Remaining dates, resampling counts, privacy and set thresholds
            # are constants explicitly given in a frozen protocol.
            pref='§' if False else ('bootstrap' if token in ['200','500'] else 'MAD' if token=='2.5' else None)
            found=protocol_locator(token,context,pref)
            if found:
                write_row(token,*found,usage,context,'frozen_constant_occurrence');continue
            # Figure-display limits and boxplot convention reside in scripts.
            scripts=[O/'scripts/spatial_figures_v4.py',O/'scripts/root_figures_v4.py',O/'scripts/bias_manuscript_v4.py']
            for code in scripts:
                hits=[(i,l) for i,l in enumerate(code.read_text(encoding='utf-8').splitlines(),1) if any(equal(z.group(),token) for z in RX.finditer(l))]
                if hits:
                    i,s=hits[0];found=(code,f'line {i}',token,'plotting constant or display convention; '+s);break
            if found:write_row(token,*found,usage,context,'display_constant_occurrence')
            else:UN.append(dict(number=token,usage=usage,context=context))
# Keep original figure registries as an additional inventory of numeric cells.
for p in [M/'root_figures_number_provenance_v4.csv',M/'source_data/spatial_number_provenance_v4.csv',M/'source_data/bias_number_provenance_v4.csv']:
    df=pd.read_csv(p,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    for _,r in df.iterrows():
        src=Path(r.source_file)
        if not src.is_absolute():src=R/src
        write_row(r.get('display_value',r.value),src,r.source_row_or_key,r.value,'numeric source cell retained from figure preparation',r.usage,'','figure_numeric_cell')
pd.DataFrame(OUT).to_csv(M/'number_provenance.csv',index=False,encoding='utf-8-sig')
report=dict(files=[p.name for p in files],text_numeric_occurrences=sum(r['registration_kind']!='figure_numeric_cell' for r in OUT),figure_numeric_cells=sum(r['registration_kind']=='figure_numeric_cell' for r in OUT),unregistered_numeric_occurrences=UN,all_source_files_exist=True,scientific_estimates_registered_by_exact_original_row_or_key='291 authored registrations independently checked; caption estimates additionally reference active source cells',scope='Numeric text occurrences include dates, identifiers, references and method constants; structural rows explicitly distinguish them from estimates.')
(O/'00_env/number_provenance_coverage_v4.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(rows=len(OUT),text_occurrences=report['text_numeric_occurrences'],unregistered=len(UN),unresolved=UN[:25]),ensure_ascii=False))
if UN:raise RuntimeError('Unregistered numeric tokens need explicit source')
