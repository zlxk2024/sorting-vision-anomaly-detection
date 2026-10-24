"""Bounded JPEG prebuffer; fixed-duration evidence clips, never whole-stream recording."""
from __future__ import annotations
from collections import deque
from pathlib import Path
import shutil

class Evidence:
    def __init__(self,root,camera_id,settings):
        self.root=Path(root);self.camera_id=camera_id;self.settings=settings
        self.frames=deque(maxlen=settings['max_buffer_frames']);self.recorders={}
    def push(self,frame,t):
        import cv2
        width=min(frame.shape[1],self.settings['evidence_width']);height=round(frame.shape[0]*width/frame.shape[1])
        resized=cv2.resize(frame,(width,height))
        ok,jpg=cv2.imencode('.jpg',resized,[cv2.IMWRITE_JPEG_QUALITY,80])
        if not ok:return []
        item=(t,jpg.tobytes());self.frames.append(item)
        while self.frames and self.frames[0][0]<t-self.settings['pre_seconds']:self.frames.popleft()
        completed=[]
        for key,rec in list(self.recorders.items()):
            if t<=rec['until']:rec['frames'].append(item)
            if t>=rec['until']:
                completed.append(self.finish(key))
        return completed
    def begin(self,event,t):
        result=dict(event)
        try:
            if shutil.disk_usage(self.root).free<self.settings['min_free_mb']*1024**2:raise OSError('low_space')
            directory=self.root/'evidence'/self.camera_id/event['start_at'][:10];directory.mkdir(parents=True,exist_ok=True)
            snapshot=directory/(event['event_id']+'.jpg')
            snapshot.write_bytes(self.frames[-1][1])
            result.update(snapshot_path=str(snapshot.relative_to(self.root)),evidence_status='snapshot_ready')
            if len(self.recorders)>=self.settings['max_recorders']:
                result['evidence_status']='snapshot_only_recorder_limit'
            else:
                self.recorders[event['event_id']]=dict(event=result,frames=deque(self.frames,maxlen=self.settings['max_buffer_frames']*2),until=t+self.settings['post_seconds'],directory=directory)
        except Exception:result['evidence_status']='evidence_failed'
        return result
    def finish(self,key):
        import cv2,numpy as np
        rec=self.recorders.pop(key);event=dict(rec['event']);frames=rec['frames'];writer=None
        try:
            if not frames:raise ValueError('empty_clip')
            path=rec['directory']/(key+'.mp4');temp=rec['directory']/(key+'.partial.mp4')
            first=cv2.imdecode(np.frombuffer(frames[0][1],np.uint8),cv2.IMREAD_COLOR)
            height,width=first.shape[:2];width-=width%2;height-=height%2
            writer=cv2.VideoWriter(str(temp),cv2.VideoWriter_fourcc(*'mp4v'),self.settings['output_fps'],(width,height))
            if not writer.isOpened():raise ValueError('encoder_failed')
            # Timestamp resampling preserves elapsed time despite inference frame drops.
            index=0;duration=max(1/self.settings['output_fps'],frames[-1][0]-frames[0][0])
            for tick in range(int(duration*self.settings['output_fps'])+1):
                at=frames[0][0]+tick/self.settings['output_fps']
                while index+1<len(frames) and frames[index+1][0]<=at:index+=1
                image=cv2.imdecode(np.frombuffer(frames[index][1],np.uint8),cv2.IMREAD_COLOR)
                writer.write(cv2.resize(image,(width,height)))
            writer.release();writer=None
            if temp.stat().st_size<100:raise ValueError('empty_video')
            temp.replace(path);event.update(clip_path=str(path.relative_to(self.root)),evidence_status='ready')
        except Exception:event['evidence_status']='snapshot_only_clip_failed'
        finally:
            if writer is not None:writer.release()
        return event
    def flush(self):
        return [self.finish(key) for key in list(self.recorders)]
