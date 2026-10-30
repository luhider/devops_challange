import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import inference_worker.worker as worker
import vision_api.app as app


class TestInferenceWorker(unittest.TestCase):
    def test_verify_engine_valid(self):
        valid, expected, actual = worker.verify_engine()
        self.assertTrue(valid)
        self.assertEqual(expected, actual)

    def test_verify_engine_corrupted(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_engine:
            tmp_engine.write(b"corrupted_engine_bytes")
            tmp_engine_path = tmp_engine.name

        try:
            with patch.object(worker, "ENGINE_PATH", tmp_engine_path):
                valid, expected, actual = worker.verify_engine()
                self.assertFalse(valid)
                self.assertNotEqual(expected, actual)
        finally:
            if os.path.exists(tmp_engine_path):
                os.remove(tmp_engine_path)


class TestVisionApi(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_check_worker_healthy(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"engine_loaded": true, "checksum_valid": true}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertTrue(app.check_worker())

    @patch("urllib.request.urlopen")
    def test_check_worker_unhealthy(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertFalse(app.check_worker())

    @patch("urllib.request.urlopen", side_effect=Exception("connection refused"))
    def test_check_worker_unreachable(self, mock_urlopen):
        self.assertFalse(app.check_worker())


if __name__ == "__main__":
    unittest.main()
