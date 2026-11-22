import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from urllib.parse import quote

import requests

from .hf_parser import RemoteFile, build_headers


CHUNK_SIZE = 1024 * 1024  # 1 MB


def format_bytes(num: float) -> str:
    if num < 0:
        num = 0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0 or unit == "TB":
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{num:.2f} TB"


def format_duration(seconds: float) -> str:
    if seconds <= 0 or seconds == float("inf"):
        return "--:--:--"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 99:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass
class FileTask:
    rfilename: str
    total_size: int
    expected_sha256: Optional[str] = None
    expected_blob_id: Optional[str] = None
    downloaded: int = 0
    selected: bool = True
    state: str = "waiting"  # waiting, resumable, downloading, paused, completed, failed, stopped
    status_text: str = "等待中"
    speed_bps: float = 0.0
    error: str = ""
    # Verification fields
    verify_state: str = ""  # "", verifying, passed, mismatch, missing, error
    verified_bytes: int = 0
    verify_speed_bps: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def progress_pct(self) -> float:
        if self.total_size <= 0:
            return 100.0 if self.state == "completed" else 0.0
        return min(100.0, (self.downloaded / self.total_size) * 100.0)

    @property
    def verify_pct(self) -> float:
        if self.total_size <= 0:
            return 100.0 if self.verify_state == "passed" else 0.0
        return min(100.0, (self.verified_bytes / self.total_size) * 100.0)

    @property
    def needs_retry(self) -> bool:
        return self.state == "failed" or self.verify_state in ("mismatch", "missing", "error")


def scan_local_files(remote_files: List[RemoteFile], save_dir: str) -> List[FileTask]:
    """Build sorted FileTask list by inspecting existing completed or .part files on disk."""
    tasks: List[FileTask] = []
    for rf in remote_files:
        final_path = os.path.join(save_dir, *rf.rfilename.split("/"))
        part_path = final_path + ".part"

        task = FileTask(
            rfilename=rf.rfilename,
            total_size=rf.size,
            expected_sha256=rf.sha256,
            expected_blob_id=rf.blob_id,
        )
        if os.path.isfile(final_path) and (rf.size == 0 or os.path.getsize(final_path) == rf.size):
            task.downloaded = rf.size
            task.state = "completed"
            task.status_text = "已完成"
        elif os.path.isfile(part_path):
            existing = os.path.getsize(part_path)
            if rf.size > 0 and existing > rf.size:
                os.remove(part_path)
                task.downloaded = 0
                task.state = "waiting"
                task.status_text = "等待中"
            else:
                task.downloaded = existing
                task.state = "resumable" if existing > 0 else "waiting"
                task.status_text = "待继续" if existing > 0 else "等待中"
        else:
            task.state = "waiting"
            task.status_text = "等待中"
        tasks.append(task)

    # Small config files first, then large weight shards in alphabetical order
    tasks.sort(key=lambda t: (t.total_size > 10 * 1024 * 1024, t.rfilename))
    return tasks


class DownloadEngine:
    """Multi-threaded resumable HTTP Range download engine with Pause/Resume/Stop/Retry Failed."""

    def __init__(
        self,
        log_fn: Callable[[str], None],
        on_done_fn: Optional[Callable[[str, int], None]] = None,
        max_retries: int = 5,
        retry_backoff_base: float = 2.0,
    ) -> None:
        self.log = log_fn
        self.on_done = on_done_fn
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base

        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.is_running = False
        self._work_queue: queue.Queue[Optional[FileTask]] = queue.Queue()
        self._manager_thread: Optional[threading.Thread] = None
        self._worker_threads: List[threading.Thread] = []

    def start(
        self,
        tasks: List[FileTask],
        endpoint: str,
        repo_id: str,
        revision: str,
        save_dir: str,
        workers: int = 4,
        token: str = "",
        only_failed: bool = False,
    ) -> int:
        """Start downloading pending (or only failed) tasks. Returns queued task count."""
        if self.is_running:
            return 0

        os.makedirs(save_dir, exist_ok=True)
        pending: List[FileTask] = []
        for t in tasks:
            with t.lock:
                if not t.selected:
                    continue
                if only_failed:
                    if not t.needs_retry:
                        continue
                    # Remove corrupted file if SHA mismatch before re-downloading
                    if t.verify_state == "mismatch":
                        final_path = os.path.join(save_dir, *t.rfilename.split("/"))
                        if os.path.isfile(final_path):
                            try:
                                os.remove(final_path)
                            except OSError:
                                pass
                        t.downloaded = 0
                    t.state = "waiting"
                    t.status_text = "等待重试"
                    t.error = ""
                    t.verify_state = ""
                    t.verified_bytes = 0
                    pending.append(t)
                else:
                    if t.state == "completed" and t.verify_state not in ("mismatch", "missing", "error"):
                        continue
                    if t.verify_state == "mismatch":
                        final_path = os.path.join(save_dir, *t.rfilename.split("/"))
                        if os.path.isfile(final_path):
                            try:
                                os.remove(final_path)
                            except OSError:
                                pass
                        t.downloaded = 0
                    t.verify_state = ""
                    t.verified_bytes = 0
                    if t.state in ("failed", "stopped"):
                        t.state = "resumable" if t.downloaded > 0 else "waiting"
                        t.status_text = "待继续" if t.downloaded > 0 else "等待中"
                        t.error = ""
                    pending.append(t)

        if not pending:
            if self.on_done:
                self.on_done("已完成", 0)
            return 0

        self.stop_event.clear()
        self.pause_event.clear()
        self.is_running = True

        self._work_queue = queue.Queue()
        for t in pending:
            self._work_queue.put(t)

        self._manager_thread = threading.Thread(
            target=self._run_workers,
            args=(tasks, endpoint, repo_id, revision, save_dir, max(1, workers), token),
            daemon=True,
        )
        self._manager_thread.start()
        return len(pending)

    def pause(self) -> None:
        if self.is_running and not self.pause_event.is_set():
            self.pause_event.set()

    def resume(self) -> None:
        if self.is_running and self.pause_event.is_set():
            self.pause_event.clear()

    def stop(self) -> None:
        if self.is_running:
            self.stop_event.set()
            self.pause_event.clear()

    def wait(self, timeout: Optional[float] = None) -> None:
        if self._manager_thread is not None:
            self._manager_thread.join(timeout=timeout)

    def _run_workers(
        self,
        all_tasks: List[FileTask],
        endpoint: str,
        repo_id: str,
        revision: str,
        save_dir: str,
        workers: int,
        token: str,
    ) -> None:
        try:
            self._worker_threads = []
            for _ in range(workers):
                th = threading.Thread(
                    target=self._worker_loop,
                    args=(endpoint, repo_id, revision, save_dir, token),
                    daemon=True,
                )
                th.start()
                self._worker_threads.append(th)

            for th in self._worker_threads:
                th.join()

            failed_count = sum(1 for t in all_tasks if t.selected and t.needs_retry)
            if self.stop_event.is_set():
                final_state = "已终止"
                self.log("下载已终止。")
            elif failed_count > 0:
                final_state = "部分失败"
                self.log(f"下载结束，有 {failed_count} 个文件失败，可点击“重试失败”一键重试。")
            else:
                final_state = "已完成"
                self.log("全部文件下载完成！")
        finally:
            self.is_running = False
            self.pause_event.clear()

        if self.on_done:
            self.on_done(final_state, failed_count)

    def _worker_loop(
        self, endpoint: str, repo_id: str, revision: str, save_dir: str, token: str
    ) -> None:
        session = requests.Session()
        try:
            while not self.stop_event.is_set():
                while self.pause_event.is_set() and not self.stop_event.is_set():
                    time.sleep(0.15)
                if self.stop_event.is_set():
                    break

                try:
                    task = self._work_queue.get_nowait()
                except queue.Empty:
                    break
                if task is None:
                    break

                self._download_single_file(session, task, endpoint, repo_id, revision, save_dir, token)
        finally:
            session.close()

    def _download_single_file(
        self,
        session: requests.Session,
        task: FileTask,
        endpoint: str,
        repo_id: str,
        revision: str,
        save_dir: str,
        token: str,
    ) -> None:
        final_path = os.path.join(save_dir, *task.rfilename.split("/"))
        part_path = final_path + ".part"
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        encoded_path = quote(task.rfilename, safe="/")
        rev = quote(revision or "main", safe="")
        url = f"{endpoint.rstrip('/')}/{repo_id}/resolve/{rev}/{encoded_path}"

        attempt = 0
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                with task.lock:
                    task.state = "paused"
                    task.status_text = "已暂停"
                    task.speed_bps = 0.0
                while self.pause_event.is_set() and not self.stop_event.is_set():
                    time.sleep(0.15)
                if self.stop_event.is_set():
                    with task.lock:
                        task.state = "stopped"
                        task.status_text = "已终止"
                        task.speed_bps = 0.0
                    return

            if task.total_size == 0:
                with open(final_path, "wb"):
                    pass
                with task.lock:
                    task.downloaded = 0
                    task.speed_bps = 0.0
                    task.state = "completed"
                    task.status_text = "已完成"
                self.log(f"完成: {task.rfilename} (0 B)")
                return

            existing_bytes = os.path.getsize(part_path) if os.path.isfile(part_path) else 0
            if existing_bytes == task.total_size:
                os.replace(part_path, final_path)
                with task.lock:
                    task.downloaded = task.total_size
                    task.speed_bps = 0.0
                    task.state = "completed"
                    task.status_text = "已完成"
                self.log(f"完成: {task.rfilename}")
                return
            if existing_bytes > task.total_size:
                os.remove(part_path)
                existing_bytes = 0

            with task.lock:
                task.downloaded = existing_bytes
                task.state = "downloading"
                task.status_text = "下载中"
                task.error = ""

            headers = build_headers(token, start_byte=existing_bytes)

            try:
                with session.get(url, headers=headers, stream=True, timeout=(15, 30)) as resp:
                    if resp.status_code == 416:
                        if os.path.isfile(part_path) and os.path.getsize(part_path) == task.total_size:
                            os.replace(part_path, final_path)
                            with task.lock:
                                task.downloaded = task.total_size
                                task.speed_bps = 0.0
                                task.state = "completed"
                                task.status_text = "已完成"
                            self.log(f"完成: {task.rfilename}")
                            return
                        if os.path.isfile(part_path):
                            os.remove(part_path)
                        continue

                    resp.raise_for_status()

                    if existing_bytes > 0 and resp.status_code == 200:
                        mode = "wb"
                        existing_bytes = 0
                        with task.lock:
                            task.downloaded = 0
                    else:
                        mode = "ab" if existing_bytes > 0 else "wb"

                    last_speed_time = time.monotonic()
                    bytes_since_last = 0

                    with open(part_path, mode) as fh:
                        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                            if self.stop_event.is_set():
                                fh.flush()
                                with task.lock:
                                    task.state = "stopped"
                                    task.status_text = "已终止"
                                    task.speed_bps = 0.0
                                return

                            if self.pause_event.is_set():
                                fh.flush()
                                with task.lock:
                                    task.state = "paused"
                                    task.status_text = "已暂停"
                                    task.speed_bps = 0.0
                                break

                            if not chunk:
                                continue

                            fh.write(chunk)
                            n = len(chunk)
                            bytes_since_last += n
                            now = time.monotonic()
                            dt = now - last_speed_time

                            with task.lock:
                                task.downloaded += n
                                if dt >= 0.35:
                                    task.speed_bps = bytes_since_last / dt
                                    bytes_since_last = 0
                                    last_speed_time = now

                        fh.flush()

                    if self.pause_event.is_set():
                        continue
                    if self.stop_event.is_set():
                        return

                    final_size = os.path.getsize(part_path) if os.path.isfile(part_path) else 0
                    if final_size == task.total_size:
                        os.replace(part_path, final_path)
                        with task.lock:
                            task.downloaded = task.total_size
                            task.speed_bps = 0.0
                            task.state = "completed"
                            task.status_text = "已完成"
                        self.log(f"完成: {task.rfilename} ({format_bytes(task.total_size)})")
                        return
                    raise IOError(
                        f"文件大小不匹配: 预期 {task.total_size} 字节，实际 {final_size} 字节"
                    )

            except Exception as exc:
                if self.stop_event.is_set():
                    with task.lock:
                        task.state = "stopped"
                        task.status_text = "已终止"
                        task.speed_bps = 0.0
                    return
                if self.pause_event.is_set():
                    continue

                attempt += 1
                with task.lock:
                    task.speed_bps = 0.0
                    task.error = str(exc)

                if attempt > self.max_retries:
                    with task.lock:
                        task.state = "failed"
                        task.status_text = f"失败: {str(exc)[:32]}"
                    self.log(f"失败 [{task.rfilename}]: {exc}")
                    return

                wait_sec = min(30.0, self.retry_backoff_base ** attempt)
                with task.lock:
                    task.status_text = f"重试({attempt}/{self.max_retries})"
                self.log(f"异常 [{task.rfilename}] ({exc})，{wait_sec:.1f}s 后第 {attempt} 次重试...")
                deadline = time.monotonic() + wait_sec
                while time.monotonic() < deadline:
                    if self.stop_event.is_set() or self.pause_event.is_set():
                        break
                    time.sleep(0.1)
