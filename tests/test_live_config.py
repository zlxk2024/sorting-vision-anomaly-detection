import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sorting_vision.live_config import load_config
ROOT=Path(__file__).resolve().parents[1]
class ConfigTests(unittest.TestCase):
    def config(self):return {'model':{'weights':str(ROOT/'models/sorting_yolo11n_v2_mixed_best.pt')},'cameras':[{'id':'camera','source_env':'TEST_CAMERA_URL','regions':[{'id':'r','kind':'chute','box':[0,0,1,1]}]}]}
    def load(self,values):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json';p.write_text(json.dumps(values));return load_config(p)
    def test_missing_connections_fail_without_printing_secrets(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'SORTING_DATABASE_URL'):self.load(self.config())
        with patch.dict(os.environ,{'SORTING_DATABASE_URL':'sqlite:///test.db'},clear=True):
            with self.assertRaisesRegex(ValueError,'TEST_CAMERA_URL'):self.load(self.config())
    def test_valid_environment_connections_and_bad_roi(self):
        with patch.dict(os.environ,{'SORTING_DATABASE_URL':'sqlite:///test.db','TEST_CAMERA_URL':'rtsp://example.invalid/camera'},clear=True):
            data=self.config();self.assertEqual('cpu',self.load(data)['model']['device'])
            data['cameras'][0]['regions'][0]['box']=[0,0,2,1]
            with self.assertRaisesRegex(ValueError,'normalized'):self.load(data)
    def test_duplicate_camera_and_unknown_target_fail(self):
        with patch.dict(os.environ,{'SORTING_DATABASE_URL':'sqlite:///test.db','TEST_CAMERA_URL':'rtsp://example.invalid/camera'},clear=True):
            data=self.config();data['cameras'].append(dict(data['cameras'][0]))
            with self.assertRaisesRegex(ValueError,'unique'):self.load(data)
            data=self.config();data['cameras'][0]['regions'][0]['expected_chute_id']='missing'
            with self.assertRaisesRegex(ValueError,'Expected chute'):self.load(data)
    def test_current_types_default_and_invalid_type_rejected(self):
        with patch.dict(os.environ,{'SORTING_DATABASE_URL':'sqlite:///test.db','TEST_CAMERA_URL':'rtsp://example.invalid/camera'},clear=True):
            self.assertEqual(['wrong_chute','multi_parcel_drawer','chute_stall'],self.load(self.config())['rules']['enabled_event_types'])
            for enabled in [['wrong_chute','wrong_chute'],['unknown'],[],['open_no_drop']]:
                data=self.config();data['rules']={'enabled_event_types':enabled}
                with self.assertRaisesRegex(ValueError,'enabled_event_types'):self.load(data)
