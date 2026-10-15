import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from defect_vision.download_model import (
    check_local_weights,
    download_from_url,
    download_via_roboflow,
    resolve_api_key,
    resolve_model_id,
    run_model_check,
)


class TestDownloadModel(unittest.TestCase):
    def test_resolve_api_key_cli_priority(self):
        with patch.dict(os.environ, {"ROBOFLOW_API_KEY": "env_key"}):
            resolved = resolve_api_key("cli_key")
            self.assertEqual(resolved, "cli_key")

    def test_resolve_api_key_from_env(self):
        with patch.dict(os.environ, {"ROBOFLOW_API_KEY": "env_key"}):
            resolved = resolve_api_key(None)
            self.assertEqual(resolved, "env_key")

    def test_resolve_model_id_default(self):
        with patch.dict(os.environ, {}, clear=True):
            resolved = resolve_model_id(None)
            self.assertEqual(resolved, "phone-segmentation-uiymg/1")

    def test_resolve_model_id_override(self):
        resolved = resolve_model_id("custom-model/2")
        self.assertEqual(resolved, "custom-model/2")

    def test_check_local_weights_missing(self, tmp_path=None):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = check_local_weights(Path(tmp_dir), check_fallbacks=False)
            self.assertIsNone(path)

    def test_check_local_weights_present(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_weights = Path(tmp_dir) / "weights.pt"
            # Write > 1MB dummy bytes
            fake_weights.write_bytes(b"0" * (1024 * 1024 + 10))
            found = check_local_weights(Path(tmp_dir), check_fallbacks=False)
            self.assertIsNotNone(found)
            self.assertEqual(found, fake_weights.resolve())

    @patch("defect_vision.download_model.check_local_weights")
    def test_run_model_check_local_found(self, mock_check):
        mock_check.return_value = Path("dummy/weights.pt")
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 127 * 1024 * 1024
            result = run_model_check(Path("dummy"), "phone-seg/1", None)
            self.assertTrue(result)

    @patch("defect_vision.download_model.check_local_weights")
    def test_run_model_check_missing_no_key(self, mock_check):
        mock_check.return_value = None
        result = run_model_check(Path("dummy"), "phone-seg/1", None)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
