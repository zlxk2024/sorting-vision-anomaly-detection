import json,tempfile,unittest
from pathlib import Path
from sorting_vision.event_store import Outbox,EventStore,Delivery
EVENT=dict(event_id='a'*32,site_id='site',camera_id='camera',event_type='chute_stall',status='open',start_at='2026-10-24T00:00:00.000+00:00',end_at='2026-10-24T00:00:01.200+00:00',duration_seconds=1.2,review_status='pending',snapshot_path=None,clip_path=None)
class StoreTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_revision_ack_does_not_delete_newer_event(self):
        q=Outbox(self.root/'out.db');q.put('event',EVENT['event_id'],EVENT);row=q.due()[0]
        q.put('event',EVENT['event_id'],dict(EVENT,status='closed'));q.ack(row[0],row[3])
        self.assertEqual(1,q.count());self.assertEqual('closed',json.loads(q.due()[0][2])['status'])
    def test_duplicate_delivery_is_single_row_and_updates(self):
        store=EventStore('sqlite:///'+str(self.root/'target.db'))
        store.deliver('event',EVENT);store.deliver('event',EVENT);store.deliver('event',dict(EVENT,status='closed'))
        rows=store.list_events();self.assertEqual(1,len(rows));self.assertEqual('closed',rows[0]['status']);store.engine.dispose()
    def test_database_outage_survives_local_restart(self):
        q=Outbox(self.root/'out.db');q.put('event',EVENT['event_id'],EVENT)
        class Broken:
            def deliver(self,*args):raise ConnectionError('test')
        Delivery(q,Broken()).run_once();self.assertEqual(1,q.count())
        q=Outbox(self.root/'out.db')
        with q.connect() as db:db.execute('UPDATE outbox SET retry_at=0')
        target=EventStore('sqlite:///'+str(self.root/'target.db'));worker=Delivery(q,target);worker.run_once()
        self.assertEqual(0,q.count());self.assertEqual(EVENT['event_id'],target.list_events()[0]['event_id']);target.engine.dispose()
    def test_heartbeat_coalesces(self):
        q=Outbox(self.root/'out.db')
        for i in range(30):q.put('camera','cam',dict(camera_id='cam',state='online',frames=i))
        self.assertEqual(1,q.count());self.assertEqual(29,json.loads(q.due()[0][2])['frames'])

class RestartRecoveryTests(unittest.TestCase):
    def test_unclosed_events_are_interrupted_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);url='sqlite:///'+str(path/'target.db')
            first=EventStore(url);first.deliver('event',EVENT);first.engine.dispose()
            next_store=EventStore(url,recover_cameras=[('site','camera')])
            self.assertEqual('interrupted',next_store.list_events()[0]['status']);next_store.engine.dispose()
            box=Outbox(path/'out.db');box.put('event',EVENT['event_id'],EVENT);box.interrupt_open_events()
            self.assertEqual('interrupted',json.loads(box.due()[0][2])['status'])
