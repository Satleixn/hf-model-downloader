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

from .config import get_default_downloads_dir, load_saved_dir, save_selected_dir
from .downloader import DownloadEngine, FileTask, format_bytes, format_duration, scan_local_files
from .hf_parser import DEFAULT_ENDPOINT, ParsedRepo, fetch_repo_files, parse_hf_input
from .i18n import LABEL_TO_LANG, LANG_OPTIONS, LANG_TO_LABEL, format_task_status, tr
from .verifier import VerifyEngine, VerifySummary


class HFDownloaderGUI:
    def __init__(
        self,
        root: tk.Tk,
        initial_url: str = "",
        initial_dir: Optional[str] = None,
        autostart: bool = False,
        lang: str = "zh",
        config_path: Optional[str] = None,
    ) -> None:
        self.root = root
        self.config_path = config_path
        self.lang = lang if lang in LANG_TO_LABEL else "zh"
        self.root.geometry("1120x790")
        self.root.minsize(940, 660)

        saved_dir = load_saved_dir(self.config_path) if initial_dir is None else None
        resolved_init_dir = initial_dir or saved_dir or get_default_downloads_dir()
        self._startup_missing_dir = (
            saved_dir if (saved_dir and not os.path.isdir(saved_dir)) else None
        )

        self.lang_var = tk.StringVar(value=LANG_TO_LABEL[self.lang])
        self.url_var = tk.StringVar(value=initial_url)
        self.save_dir_var = tk.StringVar(value=resolved_init_dir)
        self.auto_subdir_var = tk.BooleanVar(value=True)
        self.endpoint_var = tk.StringVar(value=DEFAULT_ENDPOINT)
        self.token_var = tk.StringVar(value=os.environ.get("HF_TOKEN", ""))
        self.workers_var = tk.IntVar(value=4)

        self.state_lock = threading.Lock()
        self.tasks: List[FileTask] = []
        self.active_repo: Optional[ParsedRepo] = None
        self.active_save_dir: str = ""
        self.is_fetching = False
        self.last_dl_state_key = "state_ready"
        self.last_verify_state_key = "ver_not_started"
        self.last_verify_bad_count = 0

        self.dl_speed_samples: List[Tuple[float, int]] = []
        self.verify_speed_samples: List[Tuple[float, int]] = []
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.dl_engine = DownloadEngine(log_fn=self._log, on_done_fn=self._on_download_done)
        self.verify_engine = VerifyEngine(log_fn=self._log, on_done_fn=self._on_verify_done)

        self._build_ui()
        self._apply_language()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._refresh_disk_info()
        self._schedule_ui_update()

        if self._startup_missing_dir:
            self.root.after(150, self._check_saved_dir_on_startup)

        if autostart and initial_url.strip():
            self.root.after(400, self.start_or_resume)

    def _t(self, key: str, **kwargs) -> str:
        return tr(self.lang, key, **kwargs)

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Top Language Bar ---
        top_bar = ttk.Frame(main)
        top_bar.pack(fill=tk.X, pady=(0, 4))
        self.lang_combo = ttk.Combobox(
            top_bar,
            textvariable=self.lang_var,
            values=[label for label, _ in LANG_OPTIONS],
            state="readonly",
            width=10,
        )
        self.lang_combo.pack(side=tk.RIGHT)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)
        self.lang_label_widget = ttk.Label(top_bar)
        self.lang_label_widget.pack(side=tk.RIGHT, padx=(0, 6))

        # --- Configuration Frame ---
        self.cfg_frame = ttk.LabelFrame(main, padding=8)
        self.cfg_frame.pack(fill=tk.X, pady=(0, 8))
        self.cfg_frame.columnconfigure(1, weight=3)
        self.cfg_frame.columnconfigure(3, weight=1)

        self.url_label_widget = ttk.Label(self.cfg_frame)
        self.url_label_widget.grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=3)
        self.url_entry = ttk.Entry(self.cfg_frame, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 12), pady=3)

        self.endpoint_label_widget = ttk.Label(self.cfg_frame)
        self.endpoint_label_widget.grid(row=0, column=2, sticky=tk.W, padx=(0, 6), pady=3)
        self.endpoint_combo = ttk.Combobox(
            self.cfg_frame,
            textvariable=self.endpoint_var,
            values=["https://huggingface.co", "https://hf-mirror.com"],
        )
        self.endpoint_combo.grid(row=0, column=3, sticky=tk.EW, pady=3)

        self.save_dir_label_widget = ttk.Label(self.cfg_frame)
        self.save_dir_label_widget.grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=3)
        path_frame = ttk.Frame(self.cfg_frame)
        path_frame.grid(row=1, column=1, sticky=tk.EW, padx=(0, 12), pady=3)
        path_frame.columnconfigure(0, weight=1)
        self.save_entry = ttk.Entry(path_frame, textvariable=self.save_dir_var)
        self.save_entry.grid(row=0, column=0, sticky=tk.EW)
        self.browse_btn = ttk.Button(path_frame, width=9, command=self._browse_dir)
        self.browse_btn.grid(row=0, column=1, padx=(6, 0))
        self.auto_subdir_chk = ttk.Checkbutton(path_frame, variable=self.auto_subdir_var)
        self.auto_subdir_chk.grid(row=0, column=2, padx=(8, 0))

        opt_frame = ttk.Frame(self.cfg_frame)
        opt_frame.grid(row=1, column=2, columnspan=2, sticky=tk.EW, pady=3)
        self.workers_label_widget = ttk.Label(opt_frame)
        self.workers_label_widget.pack(side=tk.LEFT, padx=(0, 6))
        self.workers_spin = ttk.Spinbox(opt_frame, from_=1, to=8, width=4, textvariable=self.workers_var)
        self.workers_spin.pack(side=tk.LEFT, padx=(0, 12))
        self.token_label_widget = ttk.Label(opt_frame)
        self.token_label_widget.pack(side=tk.LEFT, padx=(0, 6))
        self.token_entry = ttk.Entry(opt_frame, textvariable=self.token_var, show="*")
        self.token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Action Controls ---
        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(ctrl, width=15, command=self.start_or_resume)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.pause_btn = ttk.Button(ctrl, width=10, command=self.pause_download, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = ttk.Button(ctrl, width=10, command=self.stop_download, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.retry_btn = ttk.Button(ctrl, width=17, command=self.retry_failed, state=tk.DISABLED)
        self.retry_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.verify_btn = ttk.Button(ctrl, width=14, command=self.toggle_verify_sha)
        self.verify_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_btn = ttk.Button(ctrl, width=13, command=self._open_folder)
        self.open_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.disk_label = ttk.Label(ctrl, foreground="#444444")
        self.disk_label.pack(side=tk.RIGHT)

        # --- Download Overall Progress ---
        self.dl_prog_frame = ttk.LabelFrame(main, padding=8)
        self.dl_prog_frame.pack(fill=tk.X, pady=(0, 6))

        self.overall_bar = ttk.Progressbar(self.dl_prog_frame, mode="determinate", maximum=100.0)
        self.overall_bar.pack(fill=tk.X, pady=(0, 4))

        self.overall_stats_var = tk.StringVar()
        ttk.Label(self.dl_prog_frame, textvariable=self.overall_stats_var, font=("Segoe UI", 9, "bold")).pack(
            anchor=tk.W
        )

        # --- SHA Verification Progress ---
        self.ver_prog_frame = ttk.LabelFrame(main, padding=8)
        self.ver_prog_frame.pack(fill=tk.X, pady=(0, 8))

        self.verify_bar = ttk.Progressbar(self.ver_prog_frame, mode="determinate", maximum=100.0)
        self.verify_bar.pack(fill=tk.X, pady=(0, 4))

        self.verify_stats_var = tk.StringVar()
        ttk.Label(self.ver_prog_frame, textvariable=self.verify_stats_var, font=("Segoe UI", 9)).pack(
            anchor=tk.W
        )

        # --- Split Pane: File List + Logs ---
        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self.list_frame = ttk.LabelFrame(paned, padding=6)
        paned.add(self.list_frame, weight=3)

        columns = ("file", "size", "downloaded", "progress", "speed", "status")
        self.tree = ttk.Treeview(self.list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.column("file", width=380, anchor=tk.W)
        self.tree.column("size", width=105, anchor=tk.E)
        self.tree.column("downloaded", width=130, anchor=tk.E)
        self.tree.column("progress", width=80, anchor=tk.E)
        self.tree.column("speed", width=105, anchor=tk.E)
        self.tree.column("status", width=180, anchor=tk.W)

        vsb = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_frame = ttk.LabelFrame(paned, padding=6)
        paned.add(self.log_frame, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, height=7, state=tk.DISABLED, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _on_language_change(self, _event=None) -> None:
        selected_label = self.lang_var.get()
        new_lang = LABEL_TO_LANG.get(selected_label, "zh")
        if new_lang != self.lang:
            self.set_language(new_lang)

    def set_language(self, lang: str) -> None:
        if lang not in LANG_TO_LABEL:
            return
        self.lang = lang
        self.lang_var.set(LANG_TO_LABEL[lang])
        self._apply_language()

    def _apply_language(self) -> None:
        self.root.title(self._t("window_title"))
        self.lang_label_widget.config(text=self._t("lang_label"))
        self.cfg_frame.config(text=self._t("cfg_frame"))
        self.url_label_widget.config(text=self._t("url_label"))
        self.endpoint_label_widget.config(text=self._t("endpoint_label"))
        self.save_dir_label_widget.config(text=self._t("save_dir_label"))
        self.browse_btn.config(text=self._t("browse_btn"))
        self.auto_subdir_chk.config(text=self._t("auto_subdir"))
        self.workers_label_widget.config(text=self._t("workers_label"))
        self.token_label_widget.config(text=self._t("token_label"))

        self.start_btn.config(text=self._t("start_btn"))
        self.pause_btn.config(text=self._t("pause_btn"))
        self.stop_btn.config(text=self._t("stop_btn"))
        self.open_btn.config(text=self._t("open_btn"))

        self.dl_prog_frame.config(text=self._t("dl_prog_frame"))
        self.ver_prog_frame.config(text=self._t("ver_prog_frame"))
        self.list_frame.config(text=self._t("list_frame"))
        self.log_frame.config(text=self._t("log_frame"))

        self.tree.heading("file", text=self._t("col_file"))
        self.tree.heading("size", text=self._t("col_size"))
        self.tree.heading("downloaded", text=self._t("col_done"))
        self.tree.heading("progress", text=self._t("col_progress"))
        self.tree.heading("speed", text=self._t("col_speed"))
        self.tree.heading("status", text=self._t("col_status"))

        self._refresh_disk_info()
        self._sync_button_states()
        self._render_empty_stats_if_needed()
        self._update_ui_once()

    def _render_empty_stats_if_needed(self) -> None:
        with self.state_lock:
            has_tasks = bool(self.tasks)
        if not has_tasks:
            self.overall_stats_var.set(
                self._t(
                    "dl_stats",
                    state=self._t(self.last_dl_state_key),
                    pct=0.0,
                    done="0.00 B",
                    total="0.00 B",
                    completed=0,
                    count=0,
                    failed=0,
                    speed="0.00 B",
                    eta="--:--:--",
                )
            )
            self.verify_stats_var.set(
                self._t(
                    "ver_stats",
                    state=self._format_verify_state(),
                    pct=0.0,
                    done="0.00 B",
                    total="0.00 B",
                    passed=0,
                    count=0,
                    bad=0,
                    speed="0.00 B",
                    eta="--:--:--",
                )
            )

    def _format_verify_state(self) -> str:
        if self.last_verify_state_key == "ver_found_bad":
            return self._t("ver_found_bad", count=self.last_verify_bad_count)
        return self._t(self.last_verify_state_key)

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {msg}\n")

    def _resolve_target(self) -> Tuple[ParsedRepo, str]:
        parsed = parse_hf_input(self.url_var.get(), default_endpoint=self.endpoint_var.get())
        base_dir = self.save_dir_var.get().strip()
        if not base_dir:
            raise ValueError(self._t("err_no_save_dir"))
        if self.auto_subdir_var.get():
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

    def _reset_to_default_downloads(self, missing_path: str) -> str:
        default_dir = get_default_downloads_dir()
        self.save_dir_var.set(default_dir)
        save_selected_dir(default_dir, self.config_path)
        self._refresh_disk_info()
        messagebox.showwarning(
            self._t("dlg_dir_missing_title"),
            self._t("dlg_dir_missing_msg", path=missing_path, default_dir=default_dir),
        )
        return default_dir

    def _check_saved_dir_on_startup(self) -> None:
        missing = self._startup_missing_dir
        self._startup_missing_dir = None
        if missing and not os.path.isdir(missing):
            self._reset_to_default_downloads(missing)

    def _ensure_base_dir_exists(self) -> bool:
        base_dir = self.save_dir_var.get().strip()
        if base_dir and os.path.isdir(base_dir):
            return True
        self._reset_to_default_downloads(base_dir or "(empty)")
        return False

    def _browse_dir(self) -> None:
        current = self.save_dir_var.get().strip()
        init_dir = current if (current and os.path.isdir(current)) else get_default_downloads_dir()
        if not os.path.isdir(init_dir):
            init_dir = os.path.expanduser("~")
        chosen = filedialog.askdirectory(initialdir=init_dir)
        if chosen:
            norm_path = os.path.normpath(chosen)
            self.save_dir_var.set(norm_path)
            save_selected_dir(norm_path, self.config_path)
            self._refresh_disk_info()

    def _open_folder(self) -> None:
        if not self._ensure_base_dir_exists():
            return
        path = self.active_save_dir
        if not path or not os.path.isdir(path):
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
                text=self._t(
                    "disk_info",
                    target=target,
                    free=format_bytes(usage.free),
                    total=format_bytes(usage.total),
                )
            )
        except Exception:
            self.disk_label.config(text=self._t("disk_unknown"))

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
            self.retry_btn.config(text=self._t("retry_btn", count=failed_count), state=tk.DISABLED)
            self.verify_btn.config(text=self._t("verify_btn"), state=tk.DISABLED)
        elif busy_dl:
            if self.dl_engine.pause_event.is_set():
                self.start_btn.config(state=tk.NORMAL)
                self.pause_btn.config(state=tk.DISABLED)
            else:
                self.start_btn.config(state=tk.DISABLED)
                self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
            self.retry_btn.config(text=self._t("retry_btn", count=failed_count), state=tk.DISABLED)
            self.verify_btn.config(text=self._t("verify_btn"), state=tk.DISABLED)
        elif busy_ver:
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.retry_btn.config(text=self._t("retry_btn", count=failed_count), state=tk.DISABLED)
            self.verify_btn.config(text=self._t("stop_verify_btn"), state=tk.NORMAL)
        else:
            self.start_btn.config(state=tk.NORMAL)
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.retry_btn.config(
                text=self._t("retry_btn", count=failed_count),
                state=tk.NORMAL if failed_count > 0 else tk.DISABLED,
            )
            self.verify_btn.config(text=self._t("verify_btn"), state=tk.NORMAL)

    def _load_repo_async(self, parsed: ParsedRepo, target_dir: str, on_loaded) -> None:
        self.is_fetching = True
        self.last_dl_state_key = "state_loading"
        self._sync_button_states()
        token = self.token_var.get().strip()

        def _worker() -> None:
            try:
                self._log(
                    f"正在获取模型列表 / Fetching repo: {parsed.repo_id} "
                    f"(rev={parsed.revision}, endpoint={parsed.endpoint}) ..."
                )
                remote_files = fetch_repo_files(
                    endpoint=parsed.endpoint,
                    repo_id=parsed.repo_id,
                    revision=parsed.revision,
                    token=token,
                )
                if not remote_files:
                    raise ValueError(self._t("err_empty_repo"))

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
                    f"加载成功 / Loaded: {len(tasks)} files, total {format_bytes(total_bytes)}, "
                    f"local {format_bytes(already_bytes)}, pending {pending_count}. Dir: {target_dir}"
                )

                try:
                    usage = shutil.disk_usage(target_dir)
                    needed = max(0, total_bytes - already_bytes)
                    if usage.free < needed:
                        self._log(
                            f"警告 / Warning: free disk ({format_bytes(usage.free)}) < needed ({format_bytes(needed)})!"
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
                self._log(f"获取仓库信息失败 / Fetch failed: {exc}")

                def _fail_load() -> None:
                    self.is_fetching = False
                    self.last_dl_state_key = "state_load_failed"
                    self._sync_button_states()
                    messagebox.showerror(self._t("dlg_fetch_error_title"), str(exc))

                self.root.after(0, _fail_load)

        threading.Thread(target=_worker, daemon=True).start()

    def start_or_resume(self) -> None:
        if self.dl_engine.is_running and self.dl_engine.pause_event.is_set():
            self.dl_engine.resume()
            self.dl_speed_samples.clear()
            self._log("继续下载 / Resuming download...")
            self._sync_button_states()
            return

        if self.dl_engine.is_running or self.verify_engine.is_running or self.is_fetching:
            return

        if not self._ensure_base_dir_exists():
            return

        try:
            parsed, target_dir = self._resolve_target()
        except ValueError as exc:
            messagebox.showwarning(self._t("dlg_invalid_input_title"), str(exc))
            return

        def _launch() -> None:
            self.dl_speed_samples.clear()
            self.last_dl_state_key = "state_downloading"
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
                self._log("所有文件均已下载完成 / All files already downloaded.")
            self._sync_button_states()

        self._load_repo_async(parsed, target_dir, _launch)

    def pause_download(self) -> None:
        if not self.dl_engine.is_running or self.dl_engine.pause_event.is_set():
            return
        self.dl_engine.pause()
        self._log("已请求暂停 / Pausing download...")
        self._sync_button_states()

    def stop_download(self) -> None:
        if not self.dl_engine.is_running:
            return
        self.dl_engine.stop()
        self._log("已请求终止下载 / Stopping download (.part files preserved)...")
        self._sync_button_states()

    def retry_failed(self) -> None:
        if self.dl_engine.is_running or self.verify_engine.is_running or self.is_fetching:
            return
        if not self.active_repo or not self.active_save_dir:
            return

        self.dl_speed_samples.clear()
        self.last_dl_state_key = "state_retrying"
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
            self._log(f"开始一键重试 {queued} 个失败文件 / Retrying {queued} failed file(s)...")
        self._sync_button_states()

    def toggle_verify_sha(self) -> None:
        if self.verify_engine.is_running:
            self.verify_engine.stop()
            self._log("正在停止 SHA 校验 / Stopping SHA verification...")
            return

        if self.dl_engine.is_running or self.is_fetching:
            return

        if not self._ensure_base_dir_exists():
            return

        try:
            parsed, target_dir = self._resolve_target()
        except ValueError as exc:
            messagebox.showwarning(self._t("dlg_invalid_input_title"), str(exc))
            return

        def _launch_verify() -> None:
            self.verify_speed_samples.clear()
            self.last_verify_state_key = "ver_running"
            self.last_verify_bad_count = 0
            self.verify_engine.start(
                tasks=self.tasks,
                save_dir=target_dir,
                workers=self._get_workers(),
            )
            self._sync_button_states()

        if (
            self.tasks
            and self.active_repo == parsed
            and os.path.normpath(self.active_save_dir) == os.path.normpath(target_dir)
        ):
            _launch_verify()
        else:
            self._load_repo_async(parsed, target_dir, _launch_verify)

    def _on_download_done(self, final_state: str, _failed_count: int) -> None:
        state_map = {
            "已完成": "state_completed",
            "已终止": "state_stopped",
            "部分失败": "state_partial_failed",
        }
        key = state_map.get(final_state, "state_ready")

        def _ui() -> None:
            self.last_dl_state_key = key
            self._refresh_disk_info()
            self._sync_button_states()
            self._update_ui_once()

        self.root.after(0, _ui)

    def _on_verify_done(self, summary: VerifySummary) -> None:
        def _ui() -> None:
            if summary.cancelled:
                self.last_verify_state_key = "ver_cancelled"
                self.last_verify_bad_count = 0
            elif summary.mismatch == 0 and summary.missing == 0 and summary.errors == 0:
                self.last_verify_state_key = "ver_all_passed"
                self.last_verify_bad_count = 0
            else:
                self.last_verify_state_key = "ver_found_bad"
                self.last_verify_bad_count = summary.mismatch + summary.missing + summary.errors
            self._sync_button_states()
            self._update_ui_once()

        self.root.after(0, _ui)

    def _populate_treeview(self) -> None:
        self.tree.delete(*self.tree.get_children())
        with self.state_lock:
            snapshot = list(self.tasks)
        for t in snapshot:
            status_str = format_task_status(t.state, t.verify_state, t.error, self.lang)
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
                    status_str,
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
                t_err = t.error
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
                status_str = format_task_status(t_state, v_state, t_err, self.lang)
                self.tree.item(
                    t.rfilename,
                    values=(t.rfilename, format_bytes(t_size), col_done, col_pct, col_spd, status_str),
                )

        now = time.monotonic()

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
            dl_state_str = self._t("state_downloading")
        elif self.dl_engine.is_running and self.dl_engine.pause_event.is_set():
            dl_speed = 0.0
            dl_state_str = self._t("state_paused")
        else:
            dl_speed = 0.0
            dl_state_str = self._t(self.last_dl_state_key)

        dl_pct = (downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
        dl_eta = (max(0, total_bytes - downloaded_bytes) / dl_speed) if dl_speed > 0 else float("inf")
        self.overall_bar["value"] = dl_pct
        self.overall_stats_var.set(
            self._t(
                "dl_stats",
                state=dl_state_str,
                pct=dl_pct,
                done=format_bytes(downloaded_bytes),
                total=format_bytes(total_bytes),
                completed=completed_files,
                count=len(snapshot),
                failed=failed_files,
                speed=format_bytes(dl_speed),
                eta=format_duration(dl_eta),
            )
        )

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
            ver_state_str = self._t("ver_running")
        else:
            ver_speed = 0.0
            ver_state_str = self._format_verify_state()

        ver_pct = (
            (verified_bytes / total_bytes * 100.0)
            if total_bytes > 0
            else (100.0 if verify_passed == len(snapshot) and len(snapshot) > 0 else 0.0)
        )
        ver_eta = (max(0, total_bytes - verified_bytes) / ver_speed) if ver_speed > 0 else float("inf")
        self.verify_bar["value"] = ver_pct
        self.verify_stats_var.set(
            self._t(
                "ver_stats",
                state=ver_state_str,
                pct=ver_pct,
                done=format_bytes(verified_bytes),
                total=format_bytes(total_bytes),
                passed=verify_passed,
                count=len(snapshot),
                bad=verify_bad,
                speed=format_bytes(ver_speed),
                eta=format_duration(ver_eta),
            )
        )

        if not self.dl_engine.is_running and not self.verify_engine.is_running and not self.is_fetching:
            self.retry_btn.config(
                text=self._t("retry_btn", count=failed_files),
                state=tk.NORMAL if failed_files > 0 else tk.DISABLED,
            )

    def _schedule_ui_update(self) -> None:
        self._update_ui_once()
        self.root.after(250, self._schedule_ui_update)

    def _on_close(self) -> None:
        if self.dl_engine.is_running or self.verify_engine.is_running:
            if not messagebox.askyesno(self._t("dlg_exit_title"), self._t("dlg_exit_msg")):
                return
            self.dl_engine.stop()
            self.verify_engine.stop()
        self.root.destroy()
