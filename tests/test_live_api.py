import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from types import SimpleNamespace
from sorting_vision.realtime import create_live_server
from sorting_vision.event_store import EventStore
class LiveAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        store=EventStore('sqlite:///'+str(root/'target.db'));self.store=store
        self.event=dict(event_id='e'*32,site_id='s',camera_id='c',event_type='chute_stall',status='closed',start_at='2026-10-24T00:00:00Z',end_at='2026-10-24T00:00:01Z',duration_seconds=1.,review_status='pending',snapshot_path='../outside.jpg',clip_path=None)
        store.deliver('event',self.event)
        app=SimpleNamespace(root=root,store=store,config={'site_id':'s'},status=lambda:dict(status='degraded',ready=False,cameras=[],database={}))
        self.server=create_live_server(app,'127.0.0.1',0,'key');self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close();self.store.engine.dispose();self.temp.cleanup()
    def get(self,path,auth=True):
        return urllib.request.urlopen(urllib.request.Request(self.url+path,headers={'Authorization':'Bearer key'} if auth else {}))
    def test_health_and_readiness_are_distinct(self):
        with self.get('/health',False) as response:self.assertFalse(json.load(response)['ready'])
        with self.assertRaises(urllib.error.HTTPError) as error:self.get('/ready')
        self.assertEqual(503,error.exception.code)
    def test_auth_and_event_query(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.get('/v1/events',False)
        self.assertEqual(401,error.exception.code)
        with self.get('/v1/events?camera_id=c&limit=1') as response:self.assertEqual('e'*32,json.load(response)['events'][0]['event_id'])
    def test_evidence_path_cannot_escape_storage(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.get('/v1/events/'+'e'*32+'/snapshot')
        self.assertEqual(404,error.exception.code)
    def test_other_site_events_are_not_returned(self):
        self.store.deliver('event',dict(self.event,event_id='f'*32,site_id='other'))
        with self.get('/v1/events') as response:self.assertEqual(1,len(json.load(response)['events']))
        with self.assertRaises(urllib.error.HTTPError) as error:self.get('/v1/events/'+'f'*32)
        self.assertEqual(404,error.exception.code)
