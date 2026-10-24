"""Validate live-service configuration; resolve secrets only from the environment."""
from __future__ import annotations
import json, math, os, re
from pathlib import Path

DEFAULT_RULES = dict(open_no_drop_seconds=1.0, stall_seconds=1.2, multi_seconds=0.25,
                     wrong_chute_seconds=0.15, clear_seconds=0.4, max_gap_seconds=2.0,
                     track_ttl_seconds=8.0, stationary_distance=0.025, min_confidence=0.35)

def load_config(path):
    path = Path(path).resolve()
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text())
    else:
        import yaml
        data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict): raise ValueError('Configuration must be a mapping')
    root = path.parent.parent
    storage = data.setdefault('storage', {})
    directory = Path(os.environ.get('SORTING_STORAGE_DIR', storage.get('directory', 'runs/realtime')))
    storage['directory'] = str(directory if directory.is_absolute() else root / directory)
    for k,v in dict(pre_seconds=2., post_seconds=2., max_buffer_frames=90, max_recorders=4,
                    output_fps=10., evidence_width=640, min_free_mb=256).items():
        storage.setdefault(k,v)
        if not isinstance(storage[k],(int,float)) or not math.isfinite(storage[k]) or storage[k] <= 0:
            raise ValueError(f'Invalid storage setting: {k}')
    for k in ['max_buffer_frames','max_recorders','evidence_width']:
        if not isinstance(storage[k],int): raise ValueError(f'{k} must be an integer')
    database = data.setdefault('database', {})
    env = database.setdefault('url_env', 'SORTING_DATABASE_URL')
    if not isinstance(env,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',env): raise ValueError('Database url_env must be an environment variable name')
    if not os.environ.get(env): raise ValueError(f'Missing database environment variable: {env}')
    data['_database_url'] = os.environ[env]
    if not data['_database_url'].startswith(('sqlite:','postgresql+psycopg:','mysql+pymysql:')):
        raise ValueError('Database must use sqlite, postgresql+psycopg or mysql+pymysql')
    database.setdefault('create_tables', True)
    if not isinstance(database['create_tables'],bool): raise ValueError('create_tables must be boolean')
    model = data.setdefault('model', {})
    model.setdefault('weights','models/sorting_yolo11n_v2_mixed_best.pt')
    weights = Path(model['weights']);model['weights'] = str(weights if weights.is_absolute() else root/weights)
    model.setdefault('device','cpu');model.setdefault('image_size',320);model.setdefault('confidence',.15)
    if not isinstance(model['image_size'],int) or model['image_size']<=0 or not 0<float(model['confidence'])<1:
        raise ValueError('Invalid model settings')
    if not Path(model['weights']).is_file(): raise ValueError('Model file missing; run git lfs pull')
    data['rules'] = {**DEFAULT_RULES, **data.get('rules',{})}
    for key,value in data['rules'].items():
        if key not in DEFAULT_RULES or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError(f'Invalid rule setting: {key}')
    if not 0<data['rules']['min_confidence']<1 or not 0<data['rules']['stationary_distance']<1:
        raise ValueError('Confidence and normalized distance must be between zero and one')
    data.setdefault('site_id','site-01')
    if not isinstance(data['site_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',data['site_id']):
        raise ValueError('Site ID must be a safe identifier')
    seen=set()
    for camera in data.get('cameras',[]):
        identifier=camera.get('id','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',identifier) or identifier in seen:
            raise ValueError('Camera IDs must be unique safe identifiers')
        seen.add(identifier)
        camera.setdefault('enabled',True)
        camera.setdefault('open_timeout_seconds',5.);camera.setdefault('read_timeout_seconds',5.)
        camera.setdefault('reconnect_seconds',1.);camera.setdefault('max_reconnect_seconds',15.)
        camera.setdefault('max_frame_age_seconds',2.);camera.setdefault('file_realtime',True)
        camera.setdefault('loop_file',False)
        for key in ['enabled','file_realtime','loop_file']:
            if not isinstance(camera[key],bool): raise ValueError(f'{key} must be boolean')
        for key in ['open_timeout_seconds','read_timeout_seconds','reconnect_seconds','max_reconnect_seconds','max_frame_age_seconds']:
            if not isinstance(camera[key],(int,float)) or not math.isfinite(camera[key]) or camera[key]<=0:
                raise ValueError(f'Invalid camera timeout: {key}')
        if camera['enabled']:
            var=camera.get('source_env','')
            if not isinstance(var,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',var): raise ValueError('Camera source_env must be an environment variable name')
            if not os.environ.get(var): raise ValueError(f'Missing camera environment variable: {var or "source_env"}')
            camera['_source']=os.environ[var]
        ids=set()
        for region in camera.get('regions',[]):
            if region.get('kind') not in {'drawer','chute'}: raise ValueError('ROI kind must be drawer or chute')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',region.get('id','')) or region['id'] in ids:
                raise ValueError('Region IDs must be unique safe identifiers')
            ids.add(region['id'])
            b=region.get('box',[])
            if len(b)!=4 or any(not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in b) or not(b[0]<b[2] and b[1]<b[3]):
                raise ValueError('ROI box must be normalized [x1,y1,x2,y2]')
        for region in camera.get('regions',[]):
            expected=region.get('expected_chute_id')
            if expected and not any(x['id']==expected and x['kind']=='chute' for x in camera.get('regions',[])):
                raise ValueError('Expected chute must name a configured chute ROI')
        if camera['enabled'] and not camera.get('regions'): raise ValueError('Enabled cameras require calibrated ROIs')
    http=data.setdefault('http',{});http.setdefault('host','127.0.0.1');http.setdefault('port',8081)
    http.setdefault('api_key_env','SORTING_API_KEY')
    if not isinstance(http['api_key_env'],str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',http['api_key_env']):
        raise ValueError('HTTP api_key_env must be an environment variable name')
    if not isinstance(http['port'],int) or not 0<=http['port']<=65535: raise ValueError('Invalid HTTP port')
    return data
