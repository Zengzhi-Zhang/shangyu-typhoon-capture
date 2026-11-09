"""Validate registered public map fields and raster payloads, without blanket waivers."""
from pathlib import Path
import hashlib,json,math,re


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def tag_signature(tag):
    def numeric(value):
        if isinstance(value,(int,float)):
            if not math.isfinite(value):raise ValueError('nonfinite_metadata_value')
            return value
        if isinstance(value,(tuple,list)):return [numeric(x) for x in value]
        raise ValueError('nonnumeric_standard_metadata')
    if tag.code in {270,305}:
        if not isinstance(tag.value,str):raise ValueError('nonstring_text_metadata')
        value=tag.value
    else:value=numeric(tag.value)
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    return dict(code=int(tag.code),dtype=str(tag.dtype),count=int(tag.count),value_sha256=hashlib.sha256(encoded).hexdigest())


def _coordinates(value):
    if not isinstance(value,list):
        raise ValueError('coordinate_container')
    if value and isinstance(value[0],(float,int)):
        if len(value)!=2 or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in value) or not (-180<=value[0]<=180 and -90<=value[1]<=90):
            raise ValueError('coordinate_pair')
        return 1
    return sum(_coordinates(x) for x in value)


def _metadata_safe(text):
    expressions=[
        r'(?i)(?<![A-Za-z])(?:[A-Z]:[/\\]|[/\\]Users[/\\]|[/\\]home[/\\]|[/\\]tmp[/\\])',
        r'(?<![A-Za-z0-9])[0-9a-fA-F]{16}(?![A-Za-z0-9])',
        r'(?<!\w)cam_[0-9a-fA-F]{8,32}(?!\w)',
        r'(?<![\w.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])',
        r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-ZＡ-Ｚ][A-Z0-9Ａ-Ｚ０-９·.]{5,7}',
    ]
    return not any(re.search(pattern,text) for pattern in expressions)


def verify(root, registry):
    root=Path(root);registrations=registry.get('public_map_fields',{})
    results=[];metadata_texts=[]
    asset_paths=sorted(p for p in (root/'public_layers').rglob('*') if p.is_file() and p.suffix.lower() in {'.geojson','.json','.tif','.tiff','.npz','.png','.jpg','.jpeg'})
    for path in asset_paths:
        relative=path.relative_to(root).as_posix();entry=registrations.get(relative)
        result=dict(file=relative,valid=False,binary=path.suffix.lower() not in {'.geojson','.json'},reason='unregistered_asset')
        try:
            if not entry or _sha(path)!=entry['sha256']:
                raise ValueError('unregistered_or_changed_hash')
            if not entry.get('source_url','').startswith('https://') or entry.get('source_type') not in {'public_OSM','public_Natural_Earth','public_Terrain_Tiles','public_map_documentation'}:
                raise ValueError('missing_public_source_provenance')
            if entry['format']=='geometry_only_geojson':
                obj=json.loads(path.read_text(encoding='utf-8-sig'))
                if sorted(obj)!=entry['top_level_keys'] or obj.get('type')!='FeatureCollection':
                    raise ValueError('unexpected_geojson_top_level')
                features=obj.get('features',[])
                if len(features)!=entry['feature_count']:
                    raise ValueError('unexpected_feature_count')
                coordinate_pairs=0
                for feature in features:
                    if sorted(feature)!=['geometry','properties','type'] or feature.get('type')!='Feature' or feature.get('properties')!={}:
                        raise ValueError('unexpected_feature_attributes')
                    geometry=feature['geometry']
                    if sorted(geometry)!=['coordinates','type'] or geometry['type'] not in entry['geometry_types']:
                        raise ValueError('unexpected_geometry_fields')
                    coordinate_pairs+=_coordinates(geometry['coordinates'])
                extra={k:v for k,v in obj.items() if k not in {'features','type'}}
                if extra!=entry.get('top_level_metadata',{}):
                    raise ValueError('unexpected_top_level_metadata')
                metadata_texts.append(json.dumps(extra,ensure_ascii=False))
                result.update(valid=True,reason='hash_bound_geometry_fields_only',coordinate_pairs=coordinate_pairs)
            elif entry['format']=='float_rgb_tiff':
                import tifffile,numpy as np
                with tifffile.TiffFile(path) as tif:
                    if len(tif.pages)!=1:raise ValueError('unexpected_tiff_pages')
                    page=tif.pages[0]
                    if list(page.shape)!=entry['shape'] or str(page.dtype)!=entry['dtype']:
                        raise ValueError('unexpected_raster_shape_or_type')
                    codes={int(k) for k,_ in page.tags.items()}
                    if sorted(codes)!=entry['tag_codes']:
                        raise ValueError('unexpected_tiff_tags')
                    if not codes.issubset({256,257,258,259,262,270,273,277,278,279,282,283,284,296,305,317,339}):
                        raise ValueError('nonstandard_TIFF_metadata_field')
                    if [tag_signature(tag) for _,tag in sorted(page.tags.items())]!=entry['all_tag_signatures']:
                        raise ValueError('unexpected_metadata_type_count_or_value')
                    strings={str(int(k)):t.value for k,t in page.tags.items() if isinstance(t.value,str)}
                    if set(strings)!=set(entry['string_tag_sha256']):raise ValueError('unexpected_string_tags')
                    for key,text in strings.items():
                        if hashlib.sha256(text.encode('utf-8')).hexdigest()!=entry['string_tag_sha256'][key] or not _metadata_safe(text):
                            raise ValueError('unsafe_or_changed_raster_metadata')
                        metadata_texts.append(text)
                    data=page.asarray()
                    if data.ndim!=3 or data.shape[-1]!=3 or not np.isfinite(data).all() or data.min()<0 or data.max()>1:
                        raise ValueError('unexpected_RGB_numeric_payload')
                    payload_end=max(offset+count for offset,count in zip(page.dataoffsets,page.databytecounts))
                    if payload_end!=path.stat().st_size:raise ValueError('unreviewed_trailing_payload')
                result.update(valid=True,reason='hash_bound_RGB_array_and_all_metadata_tags_verified')
            elif entry['format']=='public_terrain_georeferencing':
                obj=json.loads(path.read_text(encoding='utf-8'))
                if sorted(obj)!=entry['top_level_keys'] or obj['crs']!='EPSG:3857' or obj['coordinate_units']!='metres' or obj['raster_values']!='RGB intensities from public terrain only':
                    raise ValueError('unexpected_georeferencing_fields')
                if obj['source']!=entry['source_url'] or obj['attribution_source']!=entry['attribution_source']:
                    raise ValueError('changed_georeferencing_source')
                if len(obj['rasters'])!=entry['raster_count']:
                    raise ValueError('unexpected_raster_reference_count')
                for record in obj['rasters']:
                    if sorted(record)!=['file','plot_extent','raster_extent','step'] or Path(record['file']).name!=record['file'] or 'public_layers/'+record['file'] not in registrations:
                        raise ValueError('unexpected_raster_reference_fields')
                    for field in ['plot_extent','raster_extent']:
                        values=record[field]
                        if len(values)!=4 or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in values) or not (values[0]<values[1] and values[2]<values[3]):
                            raise ValueError('unexpected_projected_extent')
                    if not isinstance(record['step'],int) or record['step']<=0:raise ValueError('unexpected_sampling_step')
                result.update(valid=True,reason='hash_bound_public_raster_references_and_extent_fields_only')
            elif entry['format']=='public_map_licence_fields':
                obj=json.loads(path.read_text(encoding='utf-8'))
                if sorted(obj)!=['assets','storm_source'] or len(obj['assets'])!=entry['asset_count']:
                    raise ValueError('unexpected_licence_document_structure')
                for item in obj['assets']:
                    if sorted(item)!=['attribution','file','format','license','sha256','source'] or item['file'] not in registrations or item['sha256']!=registrations[item['file']]['sha256']:
                        raise ValueError('unexpected_asset_licence_fields')
                    if not all(isinstance(v,str) and _metadata_safe(v) for v in item.values()):raise ValueError('unsafe_licence_metadata')
                    metadata_texts.extend(item.values())
                storm=obj['storm_source']
                if sorted(storm)!=['citation','files','source'] or storm['source']!='https://www.ncei.noaa.gov/products/international-best-track-archive':
                    raise ValueError('unexpected_storm_provenance_fields')
                if storm['files']!=entry['storm_files'] or not isinstance(storm['citation'],str) or not _metadata_safe(storm['citation']):
                    raise ValueError('unexpected_storm_file_references')
                metadata_texts.append(storm['citation'])
                result.update(valid=True,reason='hash_bound_public_licence_and_source_reference_fields_only')
            else:
                raise ValueError('unsupported_registered_format')
        except Exception as error:
            result['reason']=str(error) if isinstance(error,ValueError) else type(error).__name__
        results.append(result)
    return results,metadata_texts
