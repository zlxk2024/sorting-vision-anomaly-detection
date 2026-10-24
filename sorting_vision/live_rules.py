"""Incremental, elapsed-time anomaly candidates with normalized ROI coordinates."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
import math, uuid
from .live_config import DEFAULT_RULES

def utc_now(): return datetime.now(timezone.utc).isoformat(timespec='milliseconds')
def center(box): return ((box[0]+box[2])/2,(box[1]+box[3])/2)
def inside(box,p): return box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3]
def area(b): return max(0,b[2]-b[0])*max(0,b[3]-b[1])
def overlap(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))/max(area(a),1e-9)

class RuleEngine:
    def __init__(self,site_id,camera_id,regions,rules=None):
        self.site_id=site_id;self.camera_id=camera_id;self.regions=regions
        self.rules={**DEFAULT_RULES,**(rules or {})};self.session='';self.last_t=None
        self.tracks={};self.conditions={}
    def reset(self,session,now=None):
        events=[]
        for state in self.conditions.values():
            if state.get('event'):
                event=dict(state['event'],status='interrupted',closed_at=now or utc_now(),close_reason='stream_session_changed')
                events.append(event)
        self.session=session;self.last_t=None;self.tracks.clear();self.conditions.clear()
        return events
    def _region(self,kind,p):
        regions=[r for r in self.regions if r['kind']==kind and inside(r['box'],p)]
        return min(regions,key=lambda r:area(r['box'])) if regions else None
    def update(self,detections,t,at=None):
        at=at or utc_now();events=[]
        if self.last_t is not None and (t<=self.last_t or t-self.last_t>self.rules['max_gap_seconds']):
            events+=self.reset(self.session,at)
        self.last_t=t
        detections=[d for d in detections if d['confidence']>=self.rules['min_confidence']]
        parcels=[]
        for d in sorted((d for d in detections if d['class_id']==0 and d.get('track_id') is not None),key=lambda d:-d['confidence']):
            if not any(d['track_id']==p['track_id'] or overlap(d['box'],p['box'])>.7 for p in parcels): parcels.append(d)
        opens=[d for d in detections if d['class_id']==1]
        present={};assigned={}
        for d in parcels:
            tid=int(d['track_id']);p=center(d['box']);drawer=self._region('drawer',p);chute=self._region('chute',p)
            track=self.tracks.setdefault(tid,{'points':deque(maxlen=500),'expected':None,'first_chute':None})
            points=track['points'];points.append((t,p));track['last']=t
            while points and points[0][0]<t-self.rules['track_ttl_seconds']:points.popleft()
            if drawer:
                assigned.setdefault(drawer['id'],[]).append(d)
                if drawer.get('expected_chute_id'):track['expected']=drawer['expected_chute_id']
                matching=[o for o in opens if overlap(o['box'],drawer['box'])>.3]
                if matching:
                    door=min(matching,key=lambda o:math.dist(p,center(o['box'])))
                    door_point=center(door['box']);relative=(p[0]-door_point[0],p[1]-door_point[1])
                    present[('open_no_drop',str(tid)+':'+drawer['id'])]=(d,drawer,None,relative,'parcel_stationary_relative_to_open_drawer')
            if chute:
                present[('chute_stall',str(tid)+':'+chute['id'])]=(d,None,chute,p,'tracked_parcel_stationary_in_chute')
                first=track['first_chute']
                if (track['expected'] and track['expected']!=chute['id']) or (not track['expected'] and first and first!=chute['id']):
                    basis='configured_target_candidate' if track['expected'] else 'visual_cross_chute_candidate'
                    present[('wrong_chute',str(tid))]=(d,None,chute,p,basis)
                if first is None:track['first_chute']=chute['id']
        for region in self.regions:
            group=assigned.get(region['id'],[]) if region['kind']=='drawer' else []
            if len(group)>=2:
                d={'track_id':None,'track_ids':sorted(int(x['track_id']) for x in group), 'confidence':min(x['confidence'] for x in group)}
                present[('multi_parcel_drawer',region['id'])]=(d,region,None,None,'multiple_independent_tracks')
        thresholds={'open_no_drop':self.rules['open_no_drop_seconds'],'chute_stall':self.rules['stall_seconds'],
                    'multi_parcel_drawer':self.rules['multi_seconds'],'wrong_chute':self.rules['wrong_chute_seconds']}
        for key,value in present.items():
            d,drawer,chute,p,basis=value
            state=self.conditions.setdefault(key,{'since':t,'start_at':at,'anchor':p,'last':t,'event':None})
            if key[0] in {'open_no_drop','chute_stall'} and state['anchor'] is not None:
                if math.dist(p,state['anchor'])>self.rules['stationary_distance']:
                    if state['event']:
                        events.append(dict(state['event'],status='closed',closed_at=at,close_reason='parcel_moved'))
                    state.update(since=t,start_at=at,anchor=p,event=None)
            state['last']=t
            if state['event'] is None and t-state['since']>=thresholds[key[0]]:
                tid=d.get('track_id');track=self.tracks.get(tid,{})
                identity=f'{self.site_id}:{self.camera_id}:{self.session}:{key}:{state["since"]:.6f}'
                event={'event_id':uuid.uuid5(uuid.NAMESPACE_URL,identity).hex,'site_id':self.site_id,'camera_id':self.camera_id,
                       'session_id':self.session,'event_type':key[0],'status':'open','start_at':state['start_at'],'end_at':at,
                       'duration_seconds':round(t-state['since'],3),'confidence':float(d['confidence']),
                       'track_ids':d.get('track_ids',[tid]),'drawer_id':drawer['id'] if drawer else None,
                       'actual_chute_id':chute['id'] if chute else None,'expected_chute_id':track.get('expected'),
                       'judgement_basis':basis,'review_status':'pending','model_version':'YOLO11n-V2','rule_version':'live-v1',
                       'evidence_status':'pending','snapshot_path':None,'clip_path':None}
                state['event']=event;state['emitted']=t;events.append(dict(event))
            elif state['event'] is not None:
                state['event'].update(end_at=at,duration_seconds=round(t-state['since'],3))
                if t-state.get('emitted',t)>=1:
                    state['emitted']=t;events.append(dict(state['event']))
        for key,state in list(self.conditions.items()):
            if key not in present:
                if not state['event'] or t-state['last']>self.rules['clear_seconds']:
                    if state['event']:events.append(dict(state['event'],status='closed',closed_at=at,close_reason='condition_cleared'))
                    del self.conditions[key]
        for tid,track in list(self.tracks.items()):
            if t-track['last']>self.rules['track_ttl_seconds']:del self.tracks[tid]
        return events
