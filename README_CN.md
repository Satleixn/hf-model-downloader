# Hugging Face 模型下载与校验工具 (GUI)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Cross--Platform-lightgrey.svg)](#快速开始)

[English](README.md) | [中文说明](README_CN.md)

一款轻量、无冗余依赖的桌面端 GUI 工具，支持输入**任意 Hugging Face 模型主页链接**下载完整权重，内置中英文界面实时切换、真断点续传（暂停 / 继续 / 终止）、**一键重试失败**以及带可视化进度条的**官方 SHA 完整性校验**。

## 核心功能

- **支持任意模型主页链接**：直接粘贴 `https://huggingface.co/owner/model`、分支链接（`/tree/<branch>`）、镜像链接（`https://hf-mirror.com/...`）或 `owner/model` 仓库 ID 均可自动解析。
- **中英文界面实时切换（默认中文）**：界面右上角提供语言下拉菜单（`中文` / `English`），无需重启即可即时切换全部界面文字。
- **真断点续传与控制**：基于 HTTP `Range` 分块流式写入 `.part` 临时文件，支持随时**暂停 / 继续 / 终止**，关闭重启软件也不会丢失已下载进度。
- **一键重试失败（`🔄 重试失败`）**：下载结束后若存在失败文件，或 SHA 校验发现损坏/缺失文件，点击一次即可仅重新下载异常文件（自动清理损坏文件），无需重下整个模型。
- **一键官方 SHA 校验（`✔ 校验 SHA`）**：
  - 独立可视化**校验进度条**，实时显示进度百分比、已校验体积、读取速度（MB/s）、预计剩余时间及每个文件的校验结果。
  - **LFS 大文件**自动对比官方 `SHA-256`，**非 LFS 小文件**自动对比官方 `Git Blob SHA-1`。
  - 既可在下载完成后直接校验，也可输入已有本地目录独立校验历史下载的模型。
- **镜像与 Token 支持**：内置 `huggingface.co` / `hf-mirror.com` 切换、1–8 并发线程调节，并支持填写可选 `HF Token` 下载受限仓库。
- **根目录一键启动**：双击根目录 `start.bat` 即可自动检测依赖并静默拉起 GUI 窗口。

## 快速开始

### 方式一：直接下载 Windows 独立 EXE（免装 Python，一键启动）
前往 [Releases](https://github.com/Satleixn/hf-model-downloader/releases) 页面下载 **`HF-Model-Downloader-v1.0.0-win64.exe`**，双击即可直接运行。

- 默认保存目录：`C:\Users\<用户名>\Downloads`（C 盘下载文件夹）
- 点击 **浏览...** 选择目录后会自动记住；若下次打开或下载时该路径不存在，会自动弹窗提示重新选择。

### 方式二：从源码运行
- 环境要求：Python 3.9+（自带 `tkinter`）与 `requests`（`pip install -r requirements.txt`）
- Windows 一键启动：直接双击项目根目录的 **`start.bat`**。
- 命令行启动：
```bash
pip install -r requirements.txt
python app.py
```

支持通过参数预填模型链接、保存目录与界面语言：
```bash
python app.py --url "https://huggingface.co/owner/model" --dir "H:\Models" --lang zh --autostart
```

## 运行测试

```bash
python -m unittest discover -s tests -v
```

## 开源协议

本项目基于 **MIT License** 开源，完整条款请参阅 [LICENSE](LICENSE) 文件。

## 免责声明

- 本项目为独立开发的开源下载辅助工具，**与 Hugging Face 官方无任何隶属、合作或背书关系**。
- 使用本工具下载任何模型或文件时，使用者须自行遵守目标模型对应的开源协议、使用限制（包括受限模型授权条款）以及所在地区的法律法规。
- 本软件按**“现状（AS IS）”**提供，不附带任何明示或暗示的担保。因使用本工具导致的任何数据损失、网络/存储费用或合规风险，作者及贡献者均不承担任何责任。
