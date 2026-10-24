"""Bounded latest-frame capture with reconnect and stream session IDs."""
from __future__ import annotations
import os, threading, time, uuid
from .live_rules import utc_now

class LatestCapture:
    def __init__(self,camera):
        self.camera=camera;self.stop_event=threading.Event();self.condition=threading.Condition()
        self.latest=None;self.sequence=0;self.consumed=0;self.dropped=0;self.captured=0;self.reconnects=0
        self.state='starting';self.session=None;self.last_frame_at=None
        self.last_frame_t=None
        self.thread=threading.Thread(target=self.run,name='capture-'+camera['id'],daemon=True)
    def start(self):self.thread.start()
    def open(self):
        os.environ.setdefault('OPENCV_LOG_LEVEL','OFF');os.environ.setdefault('OPENCV_FFMPEG_LOGLEVEL','-8')
        import cv2
        source=self.camera['_source']
        if source.isdecimal():return cv2.VideoCapture(int(source))
        return cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,int(self.camera['open_timeout_seconds']*1000),cv2.CAP_PROP_READ_TIMEOUT_MSEC,int(self.camera['read_timeout_seconds']*1000)])
    def publish(self,frame,t,at,session):
        with self.condition:
            if self.latest is not None and self.latest['sequence']>self.consumed:self.dropped+=1
            self.sequence+=1;self.captured+=1;self.last_frame_at=at
            self.last_frame_t=t;self.state='online'
            self.latest=dict(frame=frame,t=t,at=at,session=session,sequence=self.sequence)
            self.condition.notify_all()
    def next(self,timeout=.5):
        with self.condition:
            self.condition.wait_for(lambda:self.stop_event.is_set() or (self.latest is not None and self.latest['sequence']>self.consumed),timeout)
            if self.latest is None or self.latest['sequence']<=self.consumed:return None
            self.consumed=self.latest['sequence'];return self.latest
    def run(self):
        import cv2
        source=self.camera['_source'];is_file=not source.isdecimal() and '://' not in source
        backoff=self.camera['reconnect_seconds']
        while not self.stop_event.is_set():
            cap=None
            try:
                cap=self.open()
                if not cap.isOpened():raise RuntimeError('capture_open_failed')
                self.session=uuid.uuid4().hex;self.state='connecting';began=time.monotonic();index=0
                fps=cap.get(cv2.CAP_PROP_FPS) or 25
                if fps<=0 or fps>240:fps=25
                while not self.stop_event.is_set():
                    ok,frame=cap.read()
                    if not ok:break
                    if is_file and self.camera['file_realtime']:
                        if self.stop_event.wait(max(0,began+index/fps-time.monotonic())):break
                    self.publish(frame,time.monotonic(),utc_now(),self.session);index+=1
                    backoff=self.camera['reconnect_seconds']
                if is_file and not self.camera['loop_file']:
                    self.state='eof';break
            except Exception:
                self.state='offline'
            finally:
                if cap is not None:cap.release()
                with self.condition:self.latest=None
            if not self.stop_event.is_set():
                self.state='reconnecting';self.reconnects+=1
                if self.stop_event.wait(backoff):break
                backoff=min(backoff*2,self.camera['max_reconnect_seconds'])
        if self.stop_event.is_set():self.state='stopped'
    def stop(self):
        self.stop_event.set()
        with self.condition:self.condition.notify_all()
        self.thread.join(timeout=self.camera['open_timeout_seconds']+self.camera['read_timeout_seconds']+3)
        if self.thread.is_alive():raise RuntimeError('capture_stop_timeout')
    def status(self):
        state=self.state
        if state=='online' and (self.last_frame_t is None or time.monotonic()-self.last_frame_t>self.camera['max_frame_age_seconds']):state='degraded'
        return dict(state=state,frames_captured=self.captured,frames_dropped=self.dropped,reconnects=self.reconnects,last_frame_at=self.last_frame_at)
