import unittest
from unittest.mock import patch
from sorting_vision.live_capture import LatestCapture
class CaptureQueueTests(unittest.TestCase):
    def test_latest_frame_replaces_backlog(self):
        cap=LatestCapture({'id':'cam'})
        for i in range(100):cap.publish(i,float(i),'at','session')
        packet=cap.next(0);self.assertEqual(99,packet['frame']);self.assertEqual(99,cap.dropped)
        self.assertIsNone(cap.next(0))
    def test_session_is_carried_with_frame(self):
        cap=LatestCapture({'id':'cam'});cap.publish(1,1,'at','old');cap.publish(2,2,'at','new')
        self.assertEqual('new',cap.next(0)['session'])
    def test_connection_is_not_online_until_fresh_frame(self):
        cap=LatestCapture({'id':'cam','max_frame_age_seconds':2})
        cap.state='connecting'
        self.assertEqual('connecting',cap.status()['state'])
        cap.publish(1,10,'at','session')
        with patch('sorting_vision.live_capture.time.monotonic',return_value=11):
            self.assertEqual('online',cap.status()['state'])
        with patch('sorting_vision.live_capture.time.monotonic',return_value=13):
            self.assertEqual('degraded',cap.status()['state'])
