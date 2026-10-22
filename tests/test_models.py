import json
import tempfile
import unittest
from pathlib import Path

from sorting_vision.inference import verify_models


class ModelDeliveryTests(unittest.TestCase):
    def test_included_artifacts_match_release_hashes(self):
        self.assertEqual(2, len(verify_models()))

    def test_lfs_pointer_is_not_accepted_as_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models").mkdir()
            (root / "models/model.pt").write_text("version https://git-lfs.github.com/spec/v1\n")
            (root / "models/manifest.json").write_text(json.dumps({
                "artifacts": [{"filename": "model.pt", "sha256": "0" * 64}]}))
            with self.assertRaisesRegex(ValueError, "git lfs pull"):
                verify_models(root)
