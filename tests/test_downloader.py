import hashlib
import http.server
import os
import socketserver
import tempfile
import threading
import unittest

from src.downloader import DownloadEngine, scan_local_files
from src.hf_parser import RemoteFile
from src.verifier import VerifyEngine


class _RangeTestHandler(http.server.BaseHTTPRequestHandler):
    files_data = {}
    fail_once_paths = set()

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        # Path format: /owner/repo/resolve/main/<filename>
        prefix = "/owner/repo/resolve/main/"
        if not self.path.startswith(prefix):
            self.send_response(404)
            self.end_headers()
            return

        rel = self.path[len(prefix):]
        if rel in self.fail_once_paths:
            self.fail_once_paths.remove(rel)
            self.send_response(500)
            self.end_headers()
            return

        if rel not in self.files_data:
            self.send_response(404)
            self.end_headers()
            return

        payload = self.files_data[rel]
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            start = int(rng.split("=")[1].split("-")[0])
            if start >= len(payload):
                self.send_response(416)
                self.end_headers()
                return
            chunk = payload[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(payload)-1}/{len(payload)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)


class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.payload_a = b"0123456789abcdef" * 4096  # 64 KB
        self.payload_b = b"fedcba9876543210" * 2048  # 32 KB
        _RangeTestHandler.files_data = {
            "a.safetensors": self.payload_a,
            "b.safetensors": self.payload_b,
        }
        _RangeTestHandler.fail_once_paths = set()

        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _RangeTestHandler)
        self.port = self.httpd.server_address[1]
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.endpoint = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmpdir.cleanup()

    def test_resume_from_part_and_retry_failed_after_sha_mismatch(self):
        sha_a = hashlib.sha256(self.payload_a).hexdigest()
        sha_b = hashlib.sha256(self.payload_b).hexdigest()

        # Pre-seed a.safetensors.part with first 10 KB to test HTTP Range resume
        with open(os.path.join(self.tmpdir.name, "a.safetensors.part"), "wb") as f:
            f.write(self.payload_a[:10240])

        # Force b.safetensors to fail on first run (max_retries=0)
        _RangeTestHandler.fail_once_paths.add("b.safetensors")

        remote_files = [
            RemoteFile("a.safetensors", len(self.payload_a), sha256=sha_a),
            RemoteFile("b.safetensors", len(self.payload_b), sha256=sha_b),
        ]
        tasks = scan_local_files(remote_files, self.tmpdir.name)
        self.assertEqual(tasks[0].state, "resumable")
        self.assertEqual(tasks[0].downloaded, 10240)

        done_info = []
        engine = DownloadEngine(
            log_fn=lambda _: None,
            on_done_fn=lambda st, fc: done_info.append((st, fc)),
            max_retries=0,
            retry_backoff_base=1.0,
        )
        engine.start(tasks, self.endpoint, "owner/repo", "main", self.tmpdir.name, workers=2)
        engine.wait(timeout=10)

        # a.safetensors resumed & completed, b.safetensors failed
        self.assertEqual(done_info[-1], ("部分失败", 1))
        self.assertEqual(tasks[0].state, "completed")
        self.assertEqual(tasks[1].state, "failed")

        # Now one-click retry_failed should download only b.safetensors
        queued = engine.start(
            tasks, self.endpoint, "owner/repo", "main", self.tmpdir.name, workers=2, only_failed=True
        )
        self.assertEqual(queued, 1)
        engine.wait(timeout=10)
        self.assertEqual(done_info[-1], ("已完成", 0))

        # Corrupt 1 byte in a.safetensors, verify catches it, then retry_failed repairs it
        path_a = os.path.join(self.tmpdir.name, "a.safetensors")
        with open(path_a, "rb") as f:
            data = bytearray(f.read())
        data[100] ^= 0xFF
        with open(path_a, "wb") as f:
            f.write(data)

        ver_results = []
        verifier = VerifyEngine(log_fn=lambda _: None, on_done_fn=ver_results.append)
        verifier.start(tasks, self.tmpdir.name, workers=2)
        verifier.wait(timeout=10)
        self.assertEqual(ver_results[-1].mismatch, 1)
        self.assertEqual(ver_results[-1].passed, 1)

        # One-click retry failed should remove corrupted a.safetensors and re-download cleanly
        queued2 = engine.start(
            tasks, self.endpoint, "owner/repo", "main", self.tmpdir.name, workers=2, only_failed=True
        )
        self.assertEqual(queued2, 1)
        engine.wait(timeout=10)

        # Re-verify -> 2/2 passed!
        verifier.start(tasks, self.tmpdir.name, workers=2)
        verifier.wait(timeout=10)
        self.assertEqual(ver_results[-1].passed, 2)
        self.assertEqual(ver_results[-1].mismatch, 0)


if __name__ == "__main__":
    unittest.main()
