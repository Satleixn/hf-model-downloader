import os
import queue
import shutil
import subprocess
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List, Optional, Tuple

from .downloader import DownloadEngine, FileTask, format_bytes, format_duration, scan_local_files
from .hf_parser import DEFAULT_ENDPOINT, ParsedRepo, fetch_repo_files, parse_hf_input
from .verifier import VerifyEngine, VerifySummary


def default_base_dir() -> str:
    if os.path.isdir(r"H:\Models"):
        return r"H:\Models"
    return os.path.join(os.path.expanduser("~"), "Models")


class HFDownloaderGUI:
    def __init__(
        self,
        root: tk.Tk,
        initial_url: str = "",
        initial_dir: Optional[str] = None,
        autostart: bool = False,
    ) -> None:
        self.root = root
        self.root.title("Hugging Face 模型下载与校验工具")
        self.root.geometry("1100x780")
        self.root.minsize(920, 660)

        self.url_var = tk.StringVar(value=initial_url)
        self.save_dir_var = tk.StringVar(value=initial_dir or default_base_dir())
        self.auto_subdir_var = tk.BooleanVar(value=True)
        self.endpoint_var = tk.StringVar(value=DEFAULT_ENDPOINT)
        self.token_var = tk.StringVar(value=os.environ.get("HF_TOKEN", ""))
        self.workers_var = tk.IntVar(value=4)

        self.state_lock = threading.Lock()
        self.tasks: List[FileTask] = []
        self.active_repo: Optional[ParsedRepo] = None
        self.active_save_dir: str = ""
        self.is_fetching = False
        self.last_dl_state = "就绪"
        self.last_verify_state = "未开始"

        self.dl_speed_samples: List[Tuple[float, int]] = []
        self.verify_speed_samples: List[Tuple[float, int]] = []
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.dl_engine = DownloadEngine(log_fn=self._log, on_done_fn=self._on_download_done)
        self.verify_engine = VerifyEngine(log_fn=self._log, on_done_fn=self._on_verify_done)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._refresh_disk_info()
        self._schedule_ui_update()

        if autostart and initial_url.strip():
            self.root.after(400, self.start_or_resume)

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Configuration Frame ---
        cfg = ttk.LabelFrame(main, text="模型与下载配置", padding=8)
        cfg.pack(fill=tk.X, pady=(0, 8))
        cfg.columnconfigure(1, weight=3)
        cfg.columnconfigure(3, weight=1)

        ttk.Label(cfg, text="模型主页链接 / ID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=3)
        self.url_entry = ttk.Entry(cfg, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 12), pady=3)

        ttk.Label(cfg, text="默认站点/镜像:").grid(row=0, column=2, sticky=tk.W, padx=(0, 6), pady=3)
        self.endpoint_combo = ttk.Combobox(
            cfg,
            textvariable=self.endpoint_var,
            values=["https://huggingface.co", "https://hf-mirror.com"],
        )
        self.endpoint_combo.grid(row=0, column=3, sticky=tk.EW, pady=3)

        ttk.Label(cfg, text="保存路径:").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=3)
        path_frame = ttk.Frame(cfg)
        path_frame.grid(row=1, column=1, sticky=tk.EW, padx=(0, 12), pady=3)
        path_frame.columnconfigure(0, weight=1)
        self.save_entry = ttk.Entry(path_frame, textvariable=self.save_dir_var)
        self.save_entry.grid(row=0, column=0, sticky=tk.EW)
        self.browse_btn = ttk.Button(path_frame, text="浏览...", width=8, command=self._browse_dir)
        self.browse_btn.grid(row=0, column=1, padx=(6, 0))
        self.auto_subdir_chk = ttk.Checkbutton(
            path_frame, text="按模型名建子目录", variable=self.auto_subdir_var
        )
        self.auto_subdir_chk.grid(row=0, column=2, padx=(8, 0))

        opt_frame = ttk.Frame(cfg)
        opt_frame.grid(row=1, column=2, columnspan=2, sticky=tk.EW, pady=3)
        ttk.Label(opt_frame, text="并发线程:").pack(side=tk.LEFT, padx=(0, 6))
        self.workers_spin = ttk.Spinbox(opt_frame, from_=1, to=8, width=4, textvariable=self.workers_var)
        self.workers_spin.pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(opt_frame, text="HF Token (可选):").pack(side=tk.LEFT, padx=(0, 6))
        self.token_entry = ttk.Entry(opt_frame, textvariable=self.token_var, show="*")
        self.token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Action Controls ---
        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(ctrl, text="▶ 开始 / 继续", width=13, command=self.start_or_resume)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.pause_btn = ttk.Button(
            ctrl, text="⏸ 暂停", width=9, command=self.pause_download, state=tk.DISABLED
        )
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = ttk.Button(
            ctrl, text="⏹ 终止", width=9, command=self.stop_download, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.retry_btn = ttk.Button(
            ctrl, text="🔄 重试失败 (0)", width=15, command=self.retry_failed, state=tk.DISABLED
        )
        self.retry_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.verify_btn = ttk.Button(ctrl, text="✔ 校验 SHA", width=13, command=self.toggle_verify_sha)
        self.verify_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_btn = ttk.Button(ctrl, text="📂 打开目录", width=11, command=self._open_folder)
        self.open_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.disk_label = ttk.Label(ctrl, text="磁盘空间: --", foreground="#444444")
        self.disk_label.pack(side=tk.RIGHT)

        # --- Download Overall Progress ---
        dl_prog_frame = ttk.LabelFrame(main, text="下载总体进度", padding=8)
        dl_prog_frame.pack(fill=tk.X, pady=(0, 6))

        self.overall_bar = ttk.Progressbar(dl_prog_frame, mode="determinate", maximum=100.0)
        self.overall_bar.pack(fill=tk.X, pady=(0, 4))

        self.overall_stats_var = tk.StringVar(
            value="状态: 就绪 | 进度: 0.00% | 已下载: 0.00 B / 0.00 B | 文件: 0 / 0 | 速度: 0.00 B/s | 剩余时间: --:--:--"
        )
        ttk.Label(dl_prog_frame, textvariable=self.overall_stats_var, font=("Segoe UI", 9, "bold")).pack(
            anchor=tk.W
        )

        # --- SHA Verification Progress ---
        ver_prog_frame = ttk.LabelFrame(main, text="官方 SHA 校验进度", padding=8)
        ver_prog_frame.pack(fill=tk.X, pady=(0, 8))

        self.verify_bar = ttk.Progressbar(ver_prog_frame, mode="determinate", maximum=100.0)
        self.verify_bar.pack(fill=tk.X, pady=(0, 4))

        self.verify_stats_var = tk.StringVar(
            value="校验状态: 未开始 | 进度: 0.00% | 已校验: 0.00 B / 0.00 B | 通过: 0 | 异常: 0 | 速度: 0.00 B/s | 剩余时间: --:--:--"
        )
        ttk.Label(ver_prog_frame, textvariable=self.verify_stats_var, font=("Segoe UI", 9)).pack(
            anchor=tk.W
        )

        # --- Split Pane: File List + Logs ---
        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.LabelFrame(paned, text="文件列表与详情", padding=6)
        paned.add(list_frame, weight=3)

        columns = ("file", "size", "downloaded", "progress", "speed", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("file", text="文件名")
        self.tree.heading("size", text="总大小")
        self.tree.heading("downloaded", text="已下载 / 已校验")
        self.tree.heading("progress", text="进度")
        self.tree.heading("speed", text="速度")
        self.tree.heading("status", text="状态")

        self.tree.column("file", width=380, anchor=tk.W)
        self.tree.column("size", width=105, anchor=tk.E)
        self.tree.column("downloaded", width=120, anchor=tk.E)
        self.tree.column("progress", width=80, anchor=tk.E)
        self.tree.column("speed", width=105, anchor=tk.E)
        self.tree.column("status", width=170, anchor=tk.W)

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        log_frame = ttk.LabelFrame(paned, text="运行日志", padding=6)
        paned.add(log_frame, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=7, state=tk.DISABLED, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {msg}\n")

    def _resolve_target(self) -> Tuple[ParsedRepo, str]:
        parsed = parse_hf_input(self.url_var.get(), default_endpoint=self.endpoint_var.get())
        base_dir = self.save_dir_var.get().strip()
        if not base_dir:
            raise ValueError("请选择保存路径。")
        if self.auto_subdir_var.get():
            # Avoid duplicating the model folder if user already selected it
            norm_base = os.path.normpath(base_dir)
            if os.path.basename(norm_base).lower() == parsed.model_name.lower():
                target_dir = norm_base
            else:
                target_dir = os.path.join(norm_base, parsed.model_name)
        else:
            target_dir = os.path.normpath(base_dir)
        return parsed, target_dir

    def _get_workers(self) -> int:
        try:
            return max(1, min(8, int(self.workers_var.get())))
        except Exception:
            self.workers_var.set(4)
            return 4

    def _browse_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.save_dir_var.get() or os.path.expanduser("~"))
        if chosen:
            self.save_dir_var.set(os.path.normpath(chosen))
            self._refresh_disk_info()

    def _open_folder(self) -> None:
        path = self.active_save_dir
        if not path:
            try:
                _, path = self._resolve_target()
            except Exception:
                path = self.save_dir_var.get().strip()
        if not path:
            return
        os.makedirs(path, exist_ok=True)
        try:
            os.startfile(path)
        except Exception:
            subprocess.Popen(["explorer", path])

    def _refresh_disk_info(self) -> None:
        path = self.active_save_dir or self.save_dir_var.get().strip() or os.path.expanduser("~")
        drive = os.path.splitdrive(path)[0]
        target = drive + "\\" if drive else path
        try:
            usage = shutil.disk_usage(target)
            self.disk_label.config(
                text=f"磁盘 {target} 可用: {format_bytes(usage.free)} / 总计: {format_bytes(usage.total)}"
            )
        except Exception:
            self.disk_label.config(text="磁盘空间: 无法读取")

    def _set_inputs_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.url_entry.config(state=state)
        self.save_entry.config(state=state)
        self.browse_btn.config(state=state)
        self.auto_subdir_chk.config(state=state)
        self.endpoint_combo.config(state=state)
        self.workers_spin.config(state=state)
        self.token_entry.config(state=state)

    def _sync_button_states(self) -> None:
        busy_dl = self.dl_engine.is_running
        busy_ver = self.verify_engine.is_running
        busy = busy_dl or busy_ver or self.is_fetching

        with self.state_lock:
            failed_count = sum(1 for t in self.tasks if t.needs_retry)

        self._set_inputs_enabled(not busy)

        if self.is_fetching:
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.retry_btn.config(state=tk.DISABLED)
            self.verify_btn.config(state=tk.DISABLED)
        elif busy_dl:
            if self.dl_engine.pause_event.is_set():
                self.start_btn.config(state=tk.NORMAL)
                self.pause_btn.config(state=tk.DISABLED)
            else:
                self.start_btn.config(state=tk.DISABLED)
                self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
            self.retry_btn.config(state=tk.DISABLED)
            self.verify_btn.config(state=tk.DISABLED, text="✔ 校验 SHA")
        elif busy_ver:
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.retry_btn.config(state=tk.DISABLED)
            self.verify_btn.config(state=tk.NORMAL, text="⏹ 停止校验")
        else:
            self.start_btn.config(state=tk.NORMAL)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.retry_btn.config(
                text=f"🔄 重试失败 ({failed_count})",
                state=tk.NORMAL if failed_count > 0 else tk.DISABLED,
            )
            self.verify_btn.config(state=tk.NORMAL, text="✔ 校验 SHA")

    def _load_repo_async(self, parsed: ParsedRepo, target_dir: str, on_loaded) -> None:
        """Fetch repo metadata in background thread, populate tasks, then run callback."""
        self.is_fetching = True
        self._sync_button_states()
        token = self.token_var.get().strip()

        def _worker() -> None:
            try:
                self._log(
                    f"正在获取模型列表: {parsed.repo_id} (分支: {parsed.revision}, 站点: {parsed.endpoint}) ..."
                )
                remote_files = fetch_repo_files(
                    endpoint=parsed.endpoint,
                    repo_id=parsed.repo_id,
                    revision=parsed.revision,
                    token=token,
                )
                if not remote_files:
                    raise ValueError("该模型仓库中未找到任何文件。")

                os.makedirs(target_dir, exist_ok=True)
                tasks = scan_local_files(remote_files, target_dir)

                with self.state_lock:
                    self.tasks = tasks
                    self.active_repo = parsed
                    self.active_save_dir = target_dir

                total_bytes = sum(t.total_size for t in tasks)
                already_bytes = sum(t.downloaded for t in tasks)
                pending_count = sum(1 for t in tasks if t.state != "completed")
                self._log(
                    f"加载成功: {len(tasks)} 个文件，总大小 {format_bytes(total_bytes)}，"
                    f"本地已有 {format_bytes(already_bytes)}，待下载 {pending_count} 个。保存路径: {target_dir}"
                )

                try:
                    usage = shutil.disk_usage(target_dir)
                    needed = max(0, total_bytes - already_bytes)
                    if usage.free < needed:
                        self._log(
                            f"警告: 磁盘可用空间 ({format_bytes(usage.free)}) 小于所需空间 ({format_bytes(needed)})！"
                        )
                except Exception:
                    pass

                def _finish_load() -> None:
                    self.is_fetching = False
                    self.endpoint_var.set(parsed.endpoint)
                    self._populate_treeview()
                    self._refresh_disk_info()
                    self._sync_button_states()
                    on_loaded()

                self.root.after(0, _finish_load)
            except Exception as exc:
                self._log(f"获取仓库信息失败: {exc}")

                def _fail_load() -> None:
                    self.is_fetching = False
                    self.last_dl_state = "加载失败"
                    self._sync_button_states()
                    messagebox.showerror("获取模型失败", str(exc))

                self.root.after(0, _fail_load)

        threading.Thread(target=_worker, daemon=True).start()

    def start_or_resume(self) -> None:
        if self.dl_engine.is_running and self.dl_engine.pause_event.is_set():
            self.dl_engine.resume()
            self.dl_speed_samples.clear()
            self._log("继续下载...")
            self._sync_button_states()
            return

        if self.dl_engine.is_running or self.verify_engine.is_running or self.is_fetching:
            return

        try:
            parsed, target_dir = self._resolve_target()
        except ValueError as exc:
            messagebox.showwarning("输入有误", str(exc))
            return

        def _launch() -> None:
            self.dl_speed_samples.clear()
            self.last_dl_state = "下载中"
            queued = self.dl_engine.start(
                tasks=self.tasks,
                endpoint=parsed.endpoint,
                repo_id=parsed.repo_id,
                revision=parsed.revision,
                save_dir=target_dir,
                workers=self._get_workers(),
                token=self.token_var.get().strip(),
                only_failed=False,
            )
            if queued == 0:
                self._log("所有文件均已下载完成，可直接点击“校验 SHA”核对完整性。")
            self._sync_button_states()

        self._load_repo_async(parsed, target_dir, _launch)

    def pause_download(self) -> None:
        if not self.dl_engine.is_running or self.dl_engine.pause_event.is_set():
            return
        self.dl_engine.pause()
        self._log("已请求暂停，正在保存当前断点...")
        self._sync_button_states()

    def stop_download(self) -> None:
        if not self.dl_engine.is_running:
            return
        self.dl_engine.stop()
        self._log("已请求终止下载，正在安全停止所有线程（.part 断点文件将保留）...")
        self._sync_button_states()

    def retry_failed(self) -> None:
        if self.dl_engine.is_running or self.verify_engine.is_running or self.is_fetching:
            return
        if not self.active_repo or not self.active_save_dir:
            return

        self.dl_speed_samples.clear()
        self.last_dl_state = "重试中"
        queued = self.dl_engine.start(
            tasks=self.tasks,
            endpoint=self.active_repo.endpoint,
            repo_id=self.active_repo.repo_id,
            revision=self.active_repo.revision,
            save_dir=self.active_save_dir,
            workers=self._get_workers(),
            token=self.token_var.get().strip(),
            only_failed=True,
        )
        if queued > 0:
            self._log(f"开始一键重试 {queued} 个失败/异常文件...")
        self._sync_button_states()

    def toggle_verify_sha(self) -> None:
        if self.verify_engine.is_running:
            self.verify_engine.stop()
            self._log("正在停止 SHA 校验...")
            return

        if self.dl_engine.is_running or self.is_fetching:
            return

        try:
            parsed, target_dir = self._resolve_target()
        except ValueError as exc:
            messagebox.showwarning("输入有误", str(exc))
            return

        def _launch_verify() -> None:
            self.verify_speed_samples.clear()
            self.last_verify_state = "校验中"
            self.verify_engine.start(
                tasks=self.tasks,
                save_dir=target_dir,
                workers=self._get_workers(),
            )
            self._sync_button_states()

        # Reuse loaded tasks if same repo & dir, otherwise fetch official metadata first
        if (
            self.tasks
            and self.active_repo == parsed
            and os.path.normpath(self.active_save_dir) == os.path.normpath(target_dir)
        ):
            _launch_verify()
        else:
            self._load_repo_async(parsed, target_dir, _launch_verify)

    def _on_download_done(self, final_state: str, failed_count: int) -> None:
        def _ui() -> None:
            self.last_dl_state = final_state
            self._refresh_disk_info()
            self._sync_button_states()
            self._update_ui_once()

        self.root.after(0, _ui)

    def _on_verify_done(self, summary: VerifySummary) -> None:
        def _ui() -> None:
            if summary.cancelled:
                self.last_verify_state = "已取消"
            elif summary.mismatch == 0 and summary.missing == 0 and summary.errors == 0:
                self.last_verify_state = "全部通过 ✔"
            else:
                bad = summary.mismatch + summary.missing + summary.errors
                self.last_verify_state = f"发现 {bad} 个异常 ✘"
            self._sync_button_states()
            self._update_ui_once()

        self.root.after(0, _ui)

    def _populate_treeview(self) -> None:
        self.tree.delete(*self.tree.get_children())
        with self.state_lock:
            snapshot = list(self.tasks)
        for t in snapshot:
            self.tree.insert(
                "",
                tk.END,
                iid=t.rfilename,
                values=(
                    t.rfilename,
                    format_bytes(t.total_size),
                    format_bytes(t.downloaded),
                    f"{t.progress_pct:.1f}%",
                    "--",
                    t.status_text,
                ),
            )

    def _drain_logs(self) -> None:
        lines: List[str] = []
        while True:
            try:
                lines.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, "".join(lines))
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

    def _update_ui_once(self) -> None:
        self._drain_logs()

        with self.state_lock:
            snapshot = list(self.tasks)

        if not snapshot:
            return

        total_bytes = 0
        downloaded_bytes = 0
        completed_files = 0
        failed_files = 0
        active_dl_speed = 0.0

        verified_bytes = 0
        verify_passed = 0
        verify_bad = 0
        active_verify_speed = 0.0
        is_verifying = self.verify_engine.is_running

        for t in snapshot:
            with t.lock:
                t_size = t.total_size
                t_dl = t.downloaded
                t_pct = t.progress_pct
                t_spd = t.speed_bps
                t_state = t.state
                t_status = t.status_text
                v_state = t.verify_state
                v_bytes = t.verified_bytes
                v_pct = t.verify_pct
                v_spd = t.verify_speed_bps
                needs_retry = t.needs_retry

            total_bytes += t_size
            downloaded_bytes += t_dl
            if t_state == "completed":
                completed_files += 1
            if needs_retry:
                failed_files += 1
            if t_state == "downloading":
                active_dl_speed += t_spd

            verified_bytes += v_bytes
            if v_state == "passed":
                verify_passed += 1
            elif v_state in ("mismatch", "missing", "error"):
                verify_bad += 1
            if v_state == "verifying":
                active_verify_speed += v_spd

            if self.tree.exists(t.rfilename):
                if v_state == "verifying":
                    col_done = format_bytes(v_bytes)
                    col_pct = f"{v_pct:.1f}%"
                    col_spd = f"{format_bytes(v_spd)}/s" if v_spd > 0 else "--"
                else:
                    col_done = format_bytes(t_dl)
                    col_pct = f"{t_pct:.1f}%"
                    col_spd = f"{format_bytes(t_spd)}/s" if t_state == "downloading" and t_spd > 0 else "--"
                self.tree.item(
                    t.rfilename,
                    values=(t.rfilename, format_bytes(t_size), col_done, col_pct, col_spd, t_status),
                )

        now = time.monotonic()

        # Download progress bar
        if self.dl_engine.is_running and not self.dl_engine.pause_event.is_set():
            self.dl_speed_samples.append((now, downloaded_bytes))
            cutoff = now - 4.0
            while len(self.dl_speed_samples) > 2 and self.dl_speed_samples[0][0] < cutoff:
                self.dl_speed_samples.pop(0)
            if len(self.dl_speed_samples) >= 2:
                dt = self.dl_speed_samples[-1][0] - self.dl_speed_samples[0][0]
                db = self.dl_speed_samples[-1][1] - self.dl_speed_samples[0][1]
                dl_speed = max(0.0, db / dt) if dt > 0 else active_dl_speed
            else:
                dl_speed = active_dl_speed
            dl_state_str = "下载中"
        elif self.dl_engine.is_running and self.dl_engine.pause_event.is_set():
            dl_speed = 0.0
            dl_state_str = "已暂停"
        else:
            dl_speed = 0.0
            dl_state_str = self.last_dl_state

        dl_pct = (downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
        dl_eta = (max(0, total_bytes - downloaded_bytes) / dl_speed) if dl_speed > 0 else float("inf")
        self.overall_bar["value"] = dl_pct
        self.overall_stats_var.set(
            f"状态: {dl_state_str} | 进度: {dl_pct:.2f}% | "
            f"已下载: {format_bytes(downloaded_bytes)} / {format_bytes(total_bytes)} | "
            f"文件: {completed_files} / {len(snapshot)} (异常: {failed_files}) | "
            f"速度: {format_bytes(dl_speed)}/s | 剩余时间: {format_duration(dl_eta)}"
        )

        # Verification progress bar
        if is_verifying:
            self.verify_speed_samples.append((now, verified_bytes))
            cutoff = now - 3.0
            while len(self.verify_speed_samples) > 2 and self.verify_speed_samples[0][0] < cutoff:
                self.verify_speed_samples.pop(0)
            if len(self.verify_speed_samples) >= 2:
                dt = self.verify_speed_samples[-1][0] - self.verify_speed_samples[0][0]
                db = self.verify_speed_samples[-1][1] - self.verify_speed_samples[0][1]
                ver_speed = max(0.0, db / dt) if dt > 0 else active_verify_speed
            else:
                ver_speed = active_verify_speed
            ver_state_str = "校验中"
        else:
            ver_speed = 0.0
            ver_state_str = self.last_verify_state

        ver_pct = (verified_bytes / total_bytes * 100.0) if total_bytes > 0 else (
            100.0 if verify_passed == len(snapshot) and len(snapshot) > 0 else 0.0
        )
        ver_eta = (max(0, total_bytes - verified_bytes) / ver_speed) if ver_speed > 0 else float("inf")
        self.verify_bar["value"] = ver_pct
        self.verify_stats_var.set(
            f"校验状态: {ver_state_str} | 进度: {ver_pct:.2f}% | "
            f"已校验: {format_bytes(verified_bytes)} / {format_bytes(total_bytes)} | "
            f"通过: {verify_passed} / {len(snapshot)} | 异常: {verify_bad} | "
            f"速度: {format_bytes(ver_speed)}/s | 剩余时间: {format_duration(ver_eta)}"
        )

        # Keep retry button count fresh when idle
        if not self.dl_engine.is_running and not self.verify_engine.is_running and not self.is_fetching:
            self.retry_btn.config(
                text=f"🔄 重试失败 ({failed_files})",
                state=tk.NORMAL if failed_files > 0 else tk.DISABLED,
            )

    def _schedule_ui_update(self) -> None:
        self._update_ui_once()
        self.root.after(250, self._schedule_ui_update)

    def _on_close(self) -> None:
        if self.dl_engine.is_running or self.verify_engine.is_running:
            if not messagebox.askyesno(
                "确认退出",
                "当前有任务正在运行，确定要停止并退出吗？（已下载的断点文件会保留）",
            ):
                return
            self.dl_engine.stop()
            self.verify_engine.stop()
        self.root.destroy()
