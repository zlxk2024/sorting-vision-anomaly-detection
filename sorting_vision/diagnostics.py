"""Independent camera, model, SQL and readiness checks; never prints credentials."""
from __future__ import annotations
import argparse
import json
import os
import time
import uuid
from pathlib import Path

os.environ.setdefault('OPENCV_LOG_LEVEL','OFF')
os.environ.setdefault('OPENCV_FFMPEG_LOGLEVEL','-8')
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS','rtsp_transport;tcp')
os.environ.setdefault('YOLO_OFFLINE','true')
os.environ.setdefault('YOLO_AUTOINSTALL','false')


def camera_probe(source, seconds=5, snapshot=None):
    import cv2
    live='://' in source
    cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
    count=0;frame=None;interrupted=False;began=time.monotonic()
    try:
        if not cap.isOpened():
            return {'passed':False,'stage':'camera','error_code':'stream_open_failed'}
        while time.monotonic()-began<seconds and count<10000:
            ok,item=cap.read()
            if not ok:
                interrupted=True
                break
            count+=1;frame=item
        elapsed=time.monotonic()-began
        passed=count>=2 and (not live or (not interrupted and elapsed>=seconds*.95))
        result=dict(passed=passed,stage='camera',input_kind='live-stream' if live else 'local-replay',
                    decoded_frames=count,elapsed_seconds=round(elapsed,3))
        if frame is not None:
            result.update(width=frame.shape[1],height=frame.shape[0])
            if snapshot:
                path=Path(snapshot);path.parent.mkdir(parents=True,exist_ok=True)
                if not cv2.imwrite(str(path),frame):
                    raise OSError('snapshot_write_failed')
                result['snapshot_saved']=True
        if not passed:
            result['error_code']='insufficient_or_interrupted_frames'
        return result
    finally:
        cap.release()


def model_probe(image, device='0', output=None):
    import torch
    if device!='cpu' and not torch.cuda.is_available():
        return {'passed':False,'stage':'model','error_code':'cuda_unavailable'}
    from .inference import verify_models,DEFAULT_WEIGHTS
    verify_models()
    if not Path(image).is_file():
        raise ValueError('Image file missing')
    from ultralytics import YOLO
    began=time.monotonic()
    model=YOLO(str(DEFAULT_WEIGHTS))
    result=model.predict(str(image),device=device,imgsz=320,conf=.15,verbose=False)[0]
    actual_device=str(result.boxes.data.device)
    if device!='cpu' and not actual_device.startswith('cuda:'):
        raise RuntimeError('gpu_not_used')
    labels=[dict(class_id=int(c),class_name=model.names[int(c)],confidence=round(float(p),4))
            for c,p in zip(result.boxes.cls.cpu().tolist(),result.boxes.conf.cpu().tolist())]
    if output:
        import cv2
        path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
        if not cv2.imwrite(str(path),result.plot()):
            raise OSError('annotation_write_failed')
    return dict(passed=True,stage='model',device=device,actual_device=actual_device,
                gpu_name=torch.cuda.get_device_name(0) if device!='cpu' else None,
                torch_cuda=torch.version.cuda,detections=labels,
                cold_call_seconds=round(time.monotonic()-began,3),
                business_event_accuracy_verified=False)


def database_probe(url, write_test=False):
    from sqlalchemy import inspect,select,insert,update,delete,text
    from .event_store import EventStore
    from .live_rules import utc_now
    store=EventStore(url,create_tables=False)
    try:
        missing=[];mismatch=[]
        with store.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            inspector=inspect(conn)
            for table in [store.events,store.cameras]:
                if not inspector.has_table(table.name):
                    missing.append(table.name);continue
                columns={c['name'] for c in inspector.get_columns(table.name)}
                if not set(table.c.keys()).issubset(columns):
                    mismatch.append(table.name)
                actual=set(inspector.get_pk_constraint(table.name).get('constrained_columns') or [])
                if actual!={c.name for c in table.primary_key} and table.name not in mismatch:
                    mismatch.append(table.name)
        result=dict(passed=not(missing or mismatch),stage='database',backend=store.engine.dialect.name,
                    connection=True,missing_tables=missing,schema_mismatch=mismatch,ddl_executed=False)
        if not result['passed']:
            result['error_code']='dba_schema_setup_required';return result
        if write_test:
            if store.engine.dialect.name=='mysql':
                with store.engine.connect() as conn:
                    engines=conn.execute(text('SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (:events,:cameras)'),{'events':store.events.name,'cameras':store.cameras.name}).all()
                if len(engines)!=2 or any(str(row[1]).lower()!='innodb' for row in engines):
                    return dict(result,passed=False,error_code='transactional_innodb_tables_required')
            key='probe-'+uuid.uuid4().hex
            payload=dict(event_id=key,site_id='deployment-probe',camera_id='deployment-probe',
                         event_type='chute_stall',event_type_name='格口包裹滞留',is_test=True,
                         status='test',start_at=utc_now(),end_at=utc_now(),duration_seconds=0.,review_status='test')
            values={c.name:payload.get(c.name) for c in store.events.c if c.name!='payload'}
            values['payload']=payload
            with store.engine.connect() as conn:
                transaction=conn.begin()
                try:
                    conn.execute(insert(store.events).values(**values))
                    changed=dict(payload,duration_seconds=1.)
                    condition=(store.events.c.event_id==key)&(store.events.c.site_id=='deployment-probe')
                    conn.execute(update(store.events).where(condition).values(duration_seconds=1.,payload=changed))
                    if conn.execute(select(store.events.c.payload).where(condition)).scalar_one()!=changed:
                        raise RuntimeError('json_round_trip_failed')
                    conn.execute(delete(store.events).where(condition))
                    if conn.execute(select(store.events.c.event_id).where(condition)).first() is not None:
                        raise RuntimeError('delete_probe_failed')
                    conn.execute(insert(store.cameras).values(camera_id=key,site_id='deployment-probe',state='test',heartbeat_at=utc_now(),payload={'is_test':True}))
                finally:
                    transaction.rollback()
            result['crud_test']='passed_and_rolled_back'
            result['durable_commit_verified']=False
        return result
    finally:
        store.engine.dispose()


def _api_get(route,port):
    import urllib.request,urllib.error
    headers={}
    if os.environ.get('SORTING_API_KEY'):
        headers['Authorization']='Bearer '+os.environ['SORTING_API_KEY']
    request=urllib.request.Request(f'http://127.0.0.1:{port}'+route,headers=headers)
    try:
        response=urllib.request.urlopen(request,timeout=10)
    except urllib.error.HTTPError as exc:
        response=exc
    with response:
        payload=json.load(response)
        return response.status,payload


def readiness_probe(port=8081):
    status,payload=_api_get('/ready',port)
    return dict(passed=status==200 and payload.get('ready') is True,stage='service',http_status=status,details=payload)


def events_probe(port=8081):
    status,payload=_api_get('/v1/events?limit=10',port)
    return dict(passed=status==200,stage='events',http_status=status,details=payload)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path)
    commands=parser.add_subparsers(dest='command',required=True)
    camera=commands.add_parser('camera',help='Decode frames only; no model or SQL')
    camera.add_argument('--source-env',default='SORTING_CAMERA_1_URL')
    camera.add_argument('--seconds',type=float,default=5)
    camera.add_argument('--snapshot',type=Path)
    model=commands.add_parser('model',help='One-image detection, not business-event acceptance')
    model.add_argument('--image',type=Path,required=True)
    model.add_argument('--device',choices=['0','cpu'],default='0')
    model.add_argument('--output',type=Path)
    database=commands.add_parser('database',help='Read-only schema check unless --write-test is selected')
    database.add_argument('--write-test',action='store_true',help='Exercise CRUD in a rolled-back transaction; no committed test event')
    status=commands.add_parser('status')
    status.add_argument('--port',type=int,default=8081)
    events=commands.add_parser('events',help='Query the running service for its latest committed events')
    events.add_argument('--port',type=int,default=8081)
    args=parser.parse_args()
    try:
        from .runtime_env import load_runtime_env
        load_runtime_env(args.env_file)
        if args.command=='camera':
            source=os.environ.get(args.source_env)
            if not source or not 1<=args.seconds<=60:
                raise ValueError('Camera environment variable required; seconds must be 1..60')
            result=camera_probe(source,args.seconds,args.snapshot)
        elif args.command=='model':
            result=model_probe(args.image,args.device,args.output)
        elif args.command=='database':
            url=os.environ.get('SORTING_DATABASE_URL')
            if not url:
                raise ValueError('Database environment variable required')
            result=database_probe(url,args.write_test)
        elif args.command=='status':
            result=readiness_probe(args.port)
        else:
            result=events_probe(args.port)
    except Exception as exc:
        # Native OpenCV logs are suppressed above; never serialize raw SQL/URL errors.
        result=dict(passed=False,stage=args.command,error_code=type(exc).__name__,secrets='not_displayed')
        original=getattr(exc,'orig',exc)
        if getattr(original,'args',None) and isinstance(original.args[0],int):
            result['database_error_code']=original.args[0]
    print(json.dumps(result,ensure_ascii=True,indent=2))
    raise SystemExit(0 if result['passed'] else 2)


if __name__=='__main__':
    main()
