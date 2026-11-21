from typing import Any, Dict, Tuple


LANG_OPTIONS: Tuple[Tuple[str, str], ...] = (
    ("中文", "zh"),
    ("English", "en"),
)

LABEL_TO_LANG: Dict[str, str] = {label: code for label, code in LANG_OPTIONS}
LANG_TO_LABEL: Dict[str, str] = {code: label for label, code in LANG_OPTIONS}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh": {
        "window_title": "Hugging Face 模型下载与校验工具",
        "lang_label": "语言:",
        "cfg_frame": "模型与下载配置",
        "url_label": "模型主页链接 / ID:",
        "endpoint_label": "默认站点/镜像:",
        "save_dir_label": "保存路径:",
        "browse_btn": "浏览...",
        "auto_subdir": "按模型名建子目录",
        "workers_label": "并发线程:",
        "token_label": "HF Token (可选):",
        "start_btn": "▶ 开始 / 继续",
        "pause_btn": "⏸ 暂停",
        "stop_btn": "⏹ 终止",
        "retry_btn": "🔄 重试失败 ({count})",
        "verify_btn": "✔ 校验 SHA",
        "stop_verify_btn": "⏹ 停止校验",
        "open_btn": "📂 打开目录",
        "disk_info": "磁盘 {target} 可用: {free} / 总计: {total}",
        "disk_unknown": "磁盘空间: 无法读取",
        "dl_prog_frame": "下载总体进度",
        "ver_prog_frame": "官方 SHA 校验进度",
        "list_frame": "文件列表与详情",
        "log_frame": "运行日志",
        "col_file": "文件名",
        "col_size": "总大小",
        "col_done": "已下载 / 已校验",
        "col_progress": "进度",
        "col_speed": "速度",
        "col_status": "状态",
        "dl_stats": (
            "状态: {state} | 进度: {pct:.2f}% | 已下载: {done} / {total} | "
            "文件: {completed} / {count} (异常: {failed}) | 速度: {speed}/s | 剩余时间: {eta}"
        ),
        "ver_stats": (
            "校验状态: {state} | 进度: {pct:.2f}% | 已校验: {done} / {total} | "
            "通过: {passed} / {count} | 异常: {bad} | 速度: {speed}/s | 剩余时间: {eta}"
        ),
        # Overall states
        "state_ready": "就绪",
        "state_loading": "加载中",
        "state_load_failed": "加载失败",
        "state_downloading": "下载中",
        "state_retrying": "重试中",
        "state_paused": "已暂停",
        "state_stopped": "已终止",
        "state_completed": "已完成",
        "state_partial_failed": "部分失败",
        "ver_not_started": "未开始",
        "ver_running": "校验中",
        "ver_cancelled": "已取消",
        "ver_all_passed": "全部通过 ✔",
        "ver_found_bad": "发现 {count} 个异常 ✘",
        # Per-file task states
        "task_waiting": "等待中",
        "task_resumable": "待继续",
        "task_downloading": "下载中",
        "task_paused": "已暂停",
        "task_completed": "已完成",
        "task_stopped": "已终止",
        "task_failed": "失败",
        "task_failed_detail": "失败: {detail}",
        "task_verifying": "校验中...",
        "task_verify_passed": "校验通过 ✔",
        "task_verify_mismatch": "校验失败 ✘ (SHA不匹配)",
        "task_verify_missing": "缺失文件 ✘",
        "task_verify_error": "校验异常 ✘",
        # Dialogs
        "dlg_invalid_input_title": "输入有误",
        "dlg_fetch_error_title": "获取模型失败",
        "dlg_exit_title": "确认退出",
        "dlg_exit_msg": "当前有任务正在运行，确定要停止并退出吗？（已下载的断点文件会保留）",
        "err_no_save_dir": "请选择保存路径。",
        "err_empty_repo": "该模型仓库中未找到任何文件。",
    },
    "en": {
        "window_title": "Hugging Face Model Downloader & SHA Verifier",
        "lang_label": "Language:",
        "cfg_frame": "Model & Download Settings",
        "url_label": "Model URL / Repo ID:",
        "endpoint_label": "Endpoint / Mirror:",
        "save_dir_label": "Save Directory:",
        "browse_btn": "Browse...",
        "auto_subdir": "Auto Subfolder",
        "workers_label": "Workers:",
        "token_label": "HF Token (Optional):",
        "start_btn": "▶ Start / Resume",
        "pause_btn": "⏸ Pause",
        "stop_btn": "⏹ Stop",
        "retry_btn": "🔄 Retry Failed ({count})",
        "verify_btn": "✔ Verify SHA",
        "stop_verify_btn": "⏹ Stop Verify",
        "open_btn": "📂 Open Folder",
        "disk_info": "Disk {target} Free: {free} / Total: {total}",
        "disk_unknown": "Disk space: Unavailable",
        "dl_prog_frame": "Overall Download Progress",
        "ver_prog_frame": "Official SHA Verification Progress",
        "list_frame": "Files & Details",
        "log_frame": "Activity Log",
        "col_file": "File",
        "col_size": "Size",
        "col_done": "Downloaded / Verified",
        "col_progress": "Progress",
        "col_speed": "Speed",
        "col_status": "Status",
        "dl_stats": (
            "Status: {state} | Progress: {pct:.2f}% | Downloaded: {done} / {total} | "
            "Files: {completed} / {count} (Failed: {failed}) | Speed: {speed}/s | ETA: {eta}"
        ),
        "ver_stats": (
            "Verify: {state} | Progress: {pct:.2f}% | Verified: {done} / {total} | "
            "Passed: {passed} / {count} | Issues: {bad} | Speed: {speed}/s | ETA: {eta}"
        ),
        # Overall states
        "state_ready": "Ready",
        "state_loading": "Loading",
        "state_load_failed": "Load Failed",
        "state_downloading": "Downloading",
        "state_retrying": "Retrying",
        "state_paused": "Paused",
        "state_stopped": "Stopped",
        "state_completed": "Completed",
        "state_partial_failed": "Partial Failure",
        "ver_not_started": "Idle",
        "ver_running": "Verifying",
        "ver_cancelled": "Cancelled",
        "ver_all_passed": "All Passed ✔",
        "ver_found_bad": "{count} Issue(s) Found ✘",
        # Per-file task states
        "task_waiting": "Waiting",
        "task_resumable": "Resumable",
        "task_downloading": "Downloading",
        "task_paused": "Paused",
        "task_completed": "Completed",
        "task_stopped": "Stopped",
        "task_failed": "Failed",
        "task_failed_detail": "Failed: {detail}",
        "task_verifying": "Verifying...",
        "task_verify_passed": "Verified ✔",
        "task_verify_mismatch": "SHA Mismatch ✘",
        "task_verify_missing": "Missing ✘",
        "task_verify_error": "Verify Error ✘",
        # Dialogs
        "dlg_invalid_input_title": "Invalid Input",
        "dlg_fetch_error_title": "Failed to Fetch Model",
        "dlg_exit_title": "Confirm Exit",
        "dlg_exit_msg": "A task is currently running. Stop and exit? (Downloaded .part files will be kept)",
        "err_no_save_dir": "Please select a save directory.",
        "err_empty_repo": "No files were found in this model repository.",
    },
}


def tr(lang: str, key: str, **kwargs: Any) -> str:
    table = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
    template = table.get(key, TRANSLATIONS["zh"].get(key, key))
    return template.format(**kwargs) if kwargs else template


def format_task_status(
    state: str,
    verify_state: str,
    error: str,
    lang: str,
) -> str:
    if verify_state == "verifying":
        return tr(lang, "task_verifying")
    if verify_state == "passed":
        return tr(lang, "task_verify_passed")
    if verify_state == "mismatch":
        return tr(lang, "task_verify_mismatch")
    if verify_state == "missing":
        return tr(lang, "task_verify_missing")
    if verify_state == "error":
        return tr(lang, "task_verify_error")

    if state == "failed":
        if error:
            return tr(lang, "task_failed_detail", detail=error[:32])
        return tr(lang, "task_failed")

    state_key_map = {
        "waiting": "task_waiting",
        "resumable": "task_resumable",
        "downloading": "task_downloading",
        "paused": "task_paused",
        "completed": "task_completed",
        "stopped": "task_stopped",
    }
    return tr(lang, state_key_map.get(state, "task_waiting"))
