import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, List, Optional

from .downloader import FileTask


VERIFY_CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB


@dataclass
class VerifySummary:
    total: int
    passed: int
    mismatch: int
    missing: int
    errors: int
    cancelled: bool


class VerifyEngine:
    """Multi-threaded official SHA-256 (LFS) + Git Blob SHA-1 (non-LFS) verifier."""

    def __init__(
        self,
        log_fn: Callable[[str], None],
        on_done_fn: Optional[Callable[[VerifySummary], None]] = None,
    ) -> None:
        self.log = log_fn
        self.on_done = on_done_fn
        self.stop_event = threading.Event()
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, tasks: List[FileTask], save_dir: str, workers: int = 4) -> None:
        selected_tasks = [t for t in tasks if t.selected]
        if self.is_running or not selected_tasks:
            return
        self.stop_event.clear()
        self.is_running = True

        for t in selected_tasks:
            with t.lock:
                t.verify_state = ""
                t.verified_bytes = 0
                t.verify_speed_bps = 0.0

        self._thread = threading.Thread(
            target=self._run,
            args=(selected_tasks, save_dir, max(1, workers)),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self.is_running:
            self.stop_event.set()

    def wait(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self, tasks: List[FileTask], save_dir: str, workers: int) -> None:
        self.log(f"开始校验 {len(tasks)} 个文件的官方 SHA 哈希（{workers} 线程）...")
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(self._verify_single, t, save_dir) for t in tasks]
                for fut in futures:
                    fut.result()
        finally:
            self.is_running = False

        passed = sum(1 for t in tasks if t.verify_state == "passed")
        mismatch = sum(1 for t in tasks if t.verify_state == "mismatch")
        missing = sum(1 for t in tasks if t.verify_state == "missing")
        errors = sum(1 for t in tasks if t.verify_state == "error")
        cancelled = self.stop_event.is_set()

        summary = VerifySummary(
            total=len(tasks),
            passed=passed,
            mismatch=mismatch,
            missing=missing,
            errors=errors,
            cancelled=cancelled,
        )
        if cancelled:
            self.log(f"SHA 校验已停止（已通过 {passed}/{len(tasks)}）。")
        elif mismatch == 0 and missing == 0 and errors == 0:
            self.log(f"全部 {passed}/{len(tasks)} 个文件 SHA 校验通过 ✔，文件完整无损！")
        else:
            self.log(
                f"SHA 校验完成：通过 {passed}，不匹配 {mismatch}，缺失 {missing}，错误 {errors}。"
                f"可点击“重试失败”重新下载异常文件。"
            )

        if self.on_done:
            self.on_done(summary)

    def _verify_single(self, task: FileTask, save_dir: str) -> None:
        if self.stop_event.is_set():
            return

        final_path = os.path.join(save_dir, *task.rfilename.split("/"))
        if not os.path.isfile(final_path):
            with task.lock:
                task.verify_state = "missing"
                task.status_text = "缺失文件 ✘"
                task.verify_speed_bps = 0.0
                task.state = "failed"
            self.log(f"校验缺失: {task.rfilename}")
            return

        actual_size = os.path.getsize(final_path)
        if task.total_size > 0 and actual_size != task.total_size:
            with task.lock:
                task.verify_state = "mismatch"
                task.verified_bytes = actual_size
                task.status_text = "校验失败 ✘ (大小不符)"
                task.verify_speed_bps = 0.0
                task.state = "failed"
            self.log(
                f"校验失败 [{task.rfilename}]: 大小不符（预期 {task.total_size}，实际 {actual_size}）"
            )
            return

        with task.lock:
            task.verify_state = "verifying"
            task.verified_bytes = 0
            task.status_text = "校验中..."

        try:
            if task.expected_sha256:
                hasher = hashlib.sha256()
                expected = task.expected_sha256.lower()
                algo = "SHA-256"
            elif task.expected_blob_id:
                hasher = hashlib.sha1()
                hasher.update(f"blob {actual_size}\0".encode("ascii"))
                expected = task.expected_blob_id.lower()
                algo = "Git SHA-1"
            else:
                with task.lock:
                    task.verify_state = "passed"
                    task.verified_bytes = task.total_size
                    task.status_text = "校验通过 ✔ (仅大小)"
                    task.verify_speed_bps = 0.0
                return

            last_t = time.monotonic()
            chunk_acc = 0

            with open(final_path, "rb") as fh:
                while True:
                    if self.stop_event.is_set():
                        with task.lock:
                            task.verify_state = ""
                            task.verify_speed_bps = 0.0
                            task.status_text = "校验已取消"
                        return
                    chunk = fh.read(VERIFY_CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    n = len(chunk)
                    chunk_acc += n
                    now = time.monotonic()
                    dt = now - last_t
                    with task.lock:
                        task.verified_bytes += n
                        if dt >= 0.3:
                            task.verify_speed_bps = chunk_acc / dt
                            chunk_acc = 0
                            last_t = now

            digest = hasher.hexdigest().lower()
            if digest == expected:
                with task.lock:
                    task.verify_state = "passed"
                    task.verified_bytes = task.total_size
                    task.verify_speed_bps = 0.0
                    task.status_text = "校验通过 ✔"
            else:
                with task.lock:
                    task.verify_state = "mismatch"
                    task.verify_speed_bps = 0.0
                    task.status_text = f"校验失败 ✘ ({algo}不匹配)"
                    task.state = "failed"
                self.log(
                    f"校验失败 [{task.rfilename}] ({algo}): 预期 {expected[:12]}... 实际 {digest[:12]}..."
                )
        except Exception as exc:
            with task.lock:
                task.verify_state = "error"
                task.verify_speed_bps = 0.0
                task.status_text = f"校验异常: {str(exc)[:24]}"
                task.state = "failed"
            self.log(f"校验异常 [{task.rfilename}]: {exc}")
