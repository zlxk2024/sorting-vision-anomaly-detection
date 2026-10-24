"""Continuous camera analysis, durable event delivery and a read-only status API."""
from __future__ import annotations
import os
os.environ.setdefault('OPENCV_LOG_LEVEL','OFF')
os.environ.setdefault('OPENCV_FFMPEG_LOGLEVEL','-8')
os.environ.setdefault('YOLO_OFFLINE','true')
os.environ.setdefault('YOLO_AUTOINSTALL','false')
import argparse, collections, hmac, json, signal, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .live_config import load_config
from .live_rules import RuleEngine,utc_now
from .live_capture import LatestCapture
from .live_evidence import Evidence
from .event_store import Outbox,EventStore,Delivery

class Detector:
    def __init__(self,settings):
        from ultralytics import YOLO
        self.model=YOLO(settings['weights']);self.settings=settings
        if self.model.names != {0:'parcel',1:'drawer_open',2:'drawer_closed',3:'chute',4:'bag'}:
            raise ValueError('incompatible_model_classes')
    def reset(self):
        predictor=getattr(self.model,'predictor',None)
        for tracker in getattr(predictor,'trackers',[]):tracker.reset()
    def detect(self,frame):
        result=self.model.track(frame,persist=True,tracker='bytetrack.yaml',imgsz=self.settings['image_size'],
                                conf=self.settings['confidence'],device=self.settings['device'],verbose=False)[0]
        boxes=result.boxes;ids=boxes.id
        ids=ids.int().cpu().tolist() if ids is not None else [None]*len(boxes)
        h,w=frame.shape[:2]
        return [dict(box=[b[0]/w,b[1]/h,b[2]/w,b[3]/h],class_id=int(c),confidence=float(s),track_id=tid)
                for b,c,s,tid in zip(boxes.xyxy.cpu().tolist(),boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist(),ids)]

class CameraWorker:
    def __init__(self,app,camera,detector_factory=Detector):
        self.app=app;self.camera=camera;self.capture=LatestCapture(camera)
        self.rules=RuleEngine(app.config['site_id'],camera['id'],camera['regions'],app.config['rules'])
        self.evidence=Evidence(app.root,camera['id'],app.config['storage'])
        self.factory=detector_factory;self.stop_event=threading.Event();self.events={};self.last_processed=0
        self.processed=0;self.stale=0;self.error=None;self.last_latency=0;self.times=collections.deque(maxlen=100)
        self.thread=threading.Thread(target=self.run,name='worker-'+camera['id'],daemon=True)
    def save(self,event):
        event=dict(event)
        previous=self.events.get(event['event_id'],{})
        for field in ['snapshot_path','clip_path','evidence_status']:
            if previous.get(field):event[field]=previous[field]
        self.events[event['event_id']]=event
        self.app.outbox.put('event',event['event_id'],event)
        if len(self.events)>2000:
            for key in list(self.events):
                if len(self.events)<=1000:break
                if self.events[key]['status']!='open' and key not in self.evidence.recorders:del self.events[key]
    def evidence_completed(self,event):
        current=dict(self.events.get(event['event_id'],event))
        current.update({k:event[k] for k in ['snapshot_path','clip_path','evidence_status']})
        self.events[event['event_id']]=current
        self.app.outbox.put('event',event['event_id'],current)
    def reset(self,session,at=None):
        for event in self.rules.reset(session,at):self.save(event)
        for event in self.evidence.flush():self.evidence_completed(event)
        self.evidence.frames.clear()
    def heartbeat(self):
        status=self.status();status.update(site_id=self.app.config['site_id'],heartbeat_at=utc_now())
        self.app.outbox.put('camera',self.camera['id'],status)
    def run(self):
        detector=None;last_heartbeat=0
        try:
            with self.app.inference_lock:detector=self.factory(self.app.config['model'])
            self.capture.start()
            while not self.stop_event.is_set():
                packet=self.capture.next(.25);now=time.monotonic()
                if now-last_heartbeat>=2:self.heartbeat();last_heartbeat=now
                if packet is None:
                    if self.rules.last_t is not None and now-self.rules.last_t>self.rules.rules['max_gap_seconds']:
                        self.reset('disconnected');detector.reset()
                    continue
                if now-packet['t']>self.camera['max_frame_age_seconds']:self.stale+=1;continue
                if packet['session']!=self.rules.session:
                    self.reset(packet['session'],packet['at']);detector.reset()
                began=time.monotonic()
                with self.app.inference_lock:detections=detector.detect(packet['frame'])
                self.last_latency=time.monotonic()-began
                if time.monotonic()-packet['t']>self.camera['max_frame_age_seconds']:
                    self.stale+=1;continue
                for event in self.evidence.push(packet['frame'],packet['t']):self.evidence_completed(event)
                for event in self.rules.update(detections,packet['t'],packet['at']):
                    if event['event_id'] not in self.events:event=self.evidence.begin(event,packet['t'])
                    self.save(event)
                self.processed+=1;self.last_processed=time.monotonic();self.times.append(self.last_processed)
                self.error=None
        except Exception as exc:
            self.error=type(exc).__name__
            print(json.dumps({'camera_id':self.camera['id'],'error_code':self.error}),flush=True)
        finally:
            try:
                if self.capture.thread.ident is not None:self.capture.stop()
                self.reset('shutdown');self.heartbeat()
            except Exception as exc:
                self.error=type(exc).__name__
    def status(self):
        status=self.capture.status();now=time.monotonic()
        fps=(len(self.times)-1)/(self.times[-1]-self.times[0]) if len(self.times)>1 and self.times[-1]>self.times[0] else 0
        state='error' if self.error else status['state']
        if state=='online' and (not self.last_processed or now-self.last_processed>10):state='degraded'
        status.update(camera_id=self.camera['id'],state=state,worker_alive=self.thread.is_alive(),frames_processed=self.processed,
                      stale_frames=self.stale,analysis_fps=round(fps,3),last_inference_seconds=round(self.last_latency,4),
                      error_code=self.error,processed_age_seconds=round(now-self.last_processed,3) if self.last_processed else None)
        return status
    def stop(self):
        self.stop_event.set();self.thread.join(timeout=20)
        if self.thread.is_alive():raise RuntimeError('worker_stop_timeout')

class LiveApp:
    def __init__(self,config,detector_factory=Detector):
        self.config=config;self.root=Path(config['storage']['directory']);self.root.mkdir(parents=True,exist_ok=True)
        self.outbox=Outbox(self.root/'outbox.sqlite3')
        self.outbox.interrupt_open_events()
        self.store=EventStore(config['_database_url'],config['database']['create_tables'],[(config['site_id'],c['id']) for c in config['cameras'] if c['enabled']])
        self.delivery=Delivery(self.outbox,self.store);self.inference_lock=threading.Lock()
        self.workers=[CameraWorker(self,c,detector_factory) for c in config['cameras'] if c['enabled']]
        if not self.workers:raise ValueError('No enabled cameras')
    def start(self):
        self.delivery.start()
        for worker in self.workers:worker.thread.start()
    def status(self):
        cameras=[worker.status() for worker in self.workers];database=self.delivery.status()
        ready=all(x['state']=='online' and x['worker_alive'] for x in cameras) and bool(database['last_success']) and not database['error_code'] and database['writer_alive']
        return dict(status='ok' if ready else 'degraded',ready=ready,mode='live-camera',cameras=cameras,database=database)
    def stop(self):
        for worker in self.workers:
            worker.stop();worker.heartbeat()
        deadline=time.monotonic()+5
        while self.outbox.count() and time.monotonic()<deadline:time.sleep(.1)
        self.delivery.stop()
        self.store.engine.dispose()

def create_live_server(app,host,port,key=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send_json(self,status,payload):
            body=json.dumps(payload,ensure_ascii=False).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            parsed=urlparse(self.path);route=parsed.path
            if route=='/health':
                status=app.status();self.send_json(200,{'status':status['status'],'mode':'live-camera','ready':status['ready']});return
            if key and not hmac.compare_digest(self.headers.get('Authorization','').encode(),('Bearer '+key).encode()):
                self.send_json(401,{'error':'unauthorized'});return
            if route=='/ready':
                state=app.status();self.send_json(200 if state['ready'] else 503,state);return
            if route=='/v1/cameras':self.send_json(200,{'cameras':app.status()['cameras']});return
            parts=route.strip('/').split('/');query=parse_qs(parsed.query)
            if len(parts)>=2 and parts[:2]==['v1','events']:
                try:
                    limit=min(200,max(1,int(query.get('limit',['50'])[0])))
                    rows=app.store.list_events(query.get('camera_id',[None])[0],limit,parts[2] if len(parts)>2 else None,app.config['site_id'])
                except ValueError:self.send_json(400,{'error':'invalid_limit'});return
                except Exception:self.send_json(503,{'error':'database_unavailable'});return
                if len(parts)==2:self.send_json(200,{'events':rows});return
                if not rows:self.send_json(404,{'error':'not_found'});return
                if len(parts)==3:self.send_json(200,rows[0]);return
                field={'snapshot':'snapshot_path','clip':'clip_path'}.get(parts[3]) if len(parts)==4 else None
                value=rows[0].get(field) if field else None
                path=(app.root/value).resolve() if value else None
                if not path or not path.is_relative_to(app.root.resolve()) or not path.is_file():self.send_json(404,{'error':'evidence_unavailable'});return
                self.send_response(200);self.send_header('Content-Type','image/jpeg' if field=='snapshot_path' else 'video/mp4')
                self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
                with path.open('rb') as stream:
                    while chunk:=stream.read(1024*1024):self.wfile.write(chunk)
                return
            self.send_json(404,{'error':'not_found'})
    return ThreadingHTTPServer((host,port),Handler)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--check-config',action='store_true');parser.add_argument('--init-db',action='store_true')
    parser.add_argument('--run-seconds',type=float,help='Optional bounded run for integration tests')
    args=parser.parse_args()
    try:config=load_config(args.config)
    except Exception as exc:
        # Validation messages are controlled; avoid emitting parser or URL exception details.
        print(json.dumps({'status':'invalid_config','error_code':type(exc).__name__,
                          'message':str(exc) if isinstance(exc,ValueError) else 'Unable to read configuration'}));raise SystemExit(2)
    if args.check_config:
        print(json.dumps({'status':'valid','enabled_cameras':sum(c['enabled'] for c in config['cameras']),'secrets':'not_displayed'}));return
    if args.init_db:
        store=EventStore(config['_database_url'],True)
        try:store.initialize();print('{"status":"schema_initialized"}')
        except Exception as exc:print(json.dumps({'status':'database_error','error_code':type(exc).__name__}));raise SystemExit(2)
        finally:store.engine.dispose()
        return
    from .inference import verify_models
    verify_models()
    app=LiveApp(config);http=config['http'];key=os.environ.get(http['api_key_env'])
    server=create_live_server(app,http['host'],http['port'],key);stop=threading.Event()
    for signum in [signal.SIGINT,signal.SIGTERM]:signal.signal(signum,lambda *_:stop.set())
    app.start();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    print(json.dumps({'status':'started','mode':'live-camera','camera_ids':[w.camera['id'] for w in app.workers],'port':server.server_port}),flush=True)
    try:stop.wait(args.run_seconds)
    finally:
        server.shutdown();thread.join();server.server_close();app.stop()
        print(json.dumps({'status':'stopped','pending_database_messages':app.outbox.count()}),flush=True)
if __name__=='__main__':main()
