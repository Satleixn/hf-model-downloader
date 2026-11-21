import hashlib
import os
import tempfile
import unittest

from src.downloader import FileTask
from src.verifier import VerifyEngine, VerifySummary


class TestVerifier(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.logs = []
        self.summary: VerifySummary | None = None

    def tearDown(self):
        self.tmpdir.cleanup()

    def _on_done(self, summary: VerifySummary):
        self.summary = summary

    def test_sha256_and_git_sha1_pass_and_mismatch(self):
        lfs_data = b"A" * 1024 + b"B" * 1024
        lfs_sha256 = hashlib.sha256(lfs_data).hexdigest()

        cfg_data = b'{"model_type": "test"}'
        cfg_git_sha1 = hashlib.sha1(f"blob {len(cfg_data)}\0".encode() + cfg_data).hexdigest()

        bad_data = b"corrupted-payload"
        good_sha256 = hashlib.sha256(b"original-payload!").hexdigest()

        p_lfs = os.path.join(self.tmpdir.name, "weights.safetensors")
        p_cfg = os.path.join(self.tmpdir.name, "config.json")
        p_bad = os.path.join(self.tmpdir.name, "bad.safetensors")

        with open(p_lfs, "wb") as f:
            f.write(lfs_data)
        with open(p_cfg, "wb") as f:
            f.write(cfg_data)
        with open(p_bad, "wb") as f:
            f.write(bad_data)

        tasks = [
            FileTask("weights.safetensors", len(lfs_data), expected_sha256=lfs_sha256),
            FileTask("config.json", len(cfg_data), expected_blob_id=cfg_git_sha1),
            FileTask("bad.safetensors", len(bad_data), expected_sha256=good_sha256),
            FileTask("missing.bin", 123, expected_sha256="0" * 64),
        ]

        engine = VerifyEngine(log_fn=self.logs.append, on_done_fn=self._on_done)
        engine.start(tasks, self.tmpdir.name, workers=2)
        engine.wait(timeout=10)

        self.assertIsNotNone(self.summary)
        self.assertEqual(self.summary.passed, 2)
        self.assertEqual(self.summary.mismatch, 1)
        self.assertEqual(self.summary.missing, 1)
        self.assertFalse(self.summary.cancelled)

        self.assertEqual(tasks[0].verify_state, "passed")
        self.assertEqual(tasks[0].verified_bytes, len(lfs_data))
        self.assertEqual(tasks[1].verify_state, "passed")
        self.assertEqual(tasks[2].verify_state, "mismatch")
        self.assertTrue(tasks[2].needs_retry)
        self.assertEqual(tasks[3].verify_state, "missing")
        self.assertTrue(tasks[3].needs_retry)


if __name__ == "__main__":
    unittest.main()
