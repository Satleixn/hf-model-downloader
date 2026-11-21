# Hugging Face 模型下载与校验工具 (GUI)

[English](README.md) | [中文说明](README_CN.md)

一款轻量、无冗余依赖的桌面端 GUI 工具，支持输入**任意 Hugging Face 模型主页链接**下载完整权重，内置真断点续传（暂停 / 继续 / 终止）、**一键重试失败**以及带可视化进度条的**官方 SHA 完整性校验**。

## 核心功能

- **支持任意模型主页链接**：直接粘贴 `https://huggingface.co/owner/model`、分支链接（`/tree/<branch>`）、镜像链接（`https://hf-mirror.com/...`）或 `owner/model` 仓库 ID 均可自动解析。
- **真断点续传与控制**：基于 HTTP `Range` 分块流式写入 `.part` 临时文件，支持随时**暂停 / 继续 / 终止**，关闭重启软件也不会丢失已下载进度。
- **一键重试失败（`🔄 重试失败`）**：下载结束后若存在失败文件，或 SHA 校验发现损坏/缺失文件，点击一次即可仅重新下载异常文件（自动清理损坏文件），无需重下整个模型。
- **一键官方 SHA 校验（`✔ 校验 SHA`）**：
  - 独立可视化**校验进度条**，实时显示进度百分比、已校验体积、读取速度（MB/s）、预计剩余时间及每个文件的校验结果。
  - **LFS 大文件**自动对比官方 `SHA-256`，**非 LFS 小文件**自动对比官方 `Git Blob SHA-1`。
  - 既可在下载完成后直接校验，也可输入已有本地目录独立校验历史下载的模型。
- **镜像与 Token 支持**：内置 `huggingface.co` / `hf-mirror.com` 切换、1–8 并发线程调节，并支持填写可选 `HF Token` 下载受限仓库。
- **根目录一键启动**：双击根目录 `start.bat` 即可自动检测依赖并静默拉起 GUI 窗口。

## 快速开始

### 环境要求
- Python 3.9+（自带 `tkinter`）
- `requests`（`pip install -r requirements.txt`）

### Windows 一键启动
直接双击项目根目录的 **`start.bat`** 即可运行。

### 命令行启动
```bash
pip install -r requirements.txt
python app.py
```

也支持通过参数预填模型链接与保存目录：
```bash
python app.py --url "https://huggingface.co/owner/model" --dir "H:\Models" --autostart
```

## 运行测试

```bash
python -m unittest discover -s tests -v
```

## 开源协议

[MIT](LICENSE)
