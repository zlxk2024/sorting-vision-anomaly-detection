import unittest
from sorting_vision.live_rules import RuleEngine
REGIONS=[{'id':'drawer','kind':'drawer','box':[0,0,1,.4]},
         {'id':'left','kind':'chute','box':[0,.4,.5,1]}, {'id':'right','kind':'chute','box':[.5,.4,1,1]}]
def parcel(tid=1,x=.2,y=.6):return dict(class_id=0,confidence=.9,track_id=tid,box=[x-.03,y-.03,x+.03,y+.03])
def door(x=.2):return dict(class_id=1,confidence=.9,track_id=20,box=[x-.08,.24,x+.08,.34])
class RulesTests(unittest.TestCase):
    def engine(self,regions=REGIONS):
        e=RuleEngine('site','cam',regions);e.reset('session');return e
    def test_stationary_parcel_emits_once_then_closes(self):
        e=self.engine();events=[]
        for t in [0,.4,.8,1.3,1.5]:events+=e.update([parcel()],t)
        opened=[x for x in events if x['status']=='open'];self.assertEqual(1,len(opened));self.assertEqual('chute_stall',opened[0]['event_type'])
        closed=e.update([],2.0);self.assertEqual('closed',closed[0]['status']);self.assertEqual(opened[0]['event_id'],closed[0]['event_id'])
    def test_moving_and_successive_parcels_do_not_stall(self):
        e=self.engine();events=[]
        for i in range(15):events+=e.update([parcel(x=.1+i*.025)],i*.15)
        self.assertEqual([],events)
        e=self.engine();events=[]
        for i in range(20):events+=e.update([parcel(tid=i//3,x=.2)],i*.2)
        self.assertFalse(any(x['event_type']=='chute_stall' for x in events))
    def test_no_drop_uses_motion_relative_to_open_door(self):
        e=RuleEngine('site','cam',REGIONS,{'enabled_event_types':['open_no_drop']});e.reset('session');events=[]
        for i in range(8):
            x=.1+i*.05;events+=e.update([parcel(x=x,y=.2),door(x)],i*.2)
        self.assertEqual(['open_no_drop'],[x['event_type'] for x in events])
    def test_current_default_types_and_names(self):
        from sorting_vision.event_types import DEFAULT_EVENT_TYPES,EVENT_NAMES
        e=self.engine();events=[]
        for i in range(8):events+=e.update([parcel(x=.2,y=.2),door(.2)],i*.2)
        self.assertEqual([],events)
        self.assertEqual({'wrong_chute','multi_parcel_drawer','chute_stall'},set(DEFAULT_EVENT_TYPES))
        e=self.engine();e.update([parcel()],0);event=e.update([parcel()],1.3)[0]
        self.assertEqual(EVENT_NAMES['chute_stall'],event['event_type_name'])
        self.assertEqual('live-v2',event['rule_version'])
    def test_only_selected_event_types_are_emitted(self):
        e=RuleEngine('site','cam',REGIONS,{'enabled_event_types':['wrong_chute']})
        e.update([parcel()],0);self.assertEqual([],e.update([parcel()],1.3))
    def test_two_tracks_debounce_and_duplicate_box(self):
        e=self.engine();a=parcel(1,.2,.2);b=parcel(2,.6,.2)
        self.assertEqual([],e.update([a,b],0));events=e.update([a,b],.3)
        self.assertEqual('multi_parcel_drawer',events[0]['event_type'])
        e=self.engine();e.update([a,dict(a,track_id=2)],0);self.assertEqual([],e.update([a,dict(a,track_id=2)],.4))
    def test_unknown_target_only_crossing_candidate(self):
        e=self.engine();e.update([parcel(x=.4)],0);e.update([parcel(x=.6)],.2)
        events=e.update([parcel(x=.65)],.4)
        event=next(x for x in events if x['event_type']=='wrong_chute')
        self.assertIsNone(event['expected_chute_id']);self.assertEqual('pending',event['review_status'])
        self.assertEqual('visual_cross_chute_candidate',event['judgement_basis'])
    def test_gap_and_reconnect_interrupt_and_clear_state(self):
        e=self.engine();e.update([parcel()],0);opened=e.update([parcel()],1.3)
        gap=e.update([parcel()],5);self.assertEqual('interrupted',gap[0]['status'])
        self.assertEqual([],e.reset('new-session'));self.assertEqual({},e.tracks)
        e.update([parcel()],6);e.update([parcel()],7.3)
        self.assertEqual('interrupted',e.reset('another-session')[0]['status'])
    def test_duplicate_timestamps_do_not_accumulate_time(self):
        e=self.engine()
        for _ in range(20):self.assertEqual([],e.update([parcel()],1.0))
    def test_configured_expected_chute_is_preserved(self):
        regions=[dict(REGIONS[0],expected_chute_id='left'),*REGIONS[1:]]
        e=self.engine(regions);e.update([parcel(x=.2,y=.2)],0)
        e.update([parcel(x=.7,y=.6)],.2)
        event=next(x for x in e.update([parcel(x=.7,y=.6)],.4) if x['event_type']=='wrong_chute')
        self.assertEqual('left',event['expected_chute_id']);self.assertEqual('right',event['actual_chute_id'])
        self.assertEqual('configured_target_candidate',event['judgement_basis'])
