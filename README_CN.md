# Hugging Face 模型下载与校验工具 (GUI)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Cross--Platform-lightgrey.svg)](#快速开始)

[English](README.md) | [中文说明](README_CN.md)

一款轻量、无冗余依赖的桌面端 GUI 工具，支持输入**任意 Hugging Face 模型主页链接**，内置**多量化版本与分支自动识别**、文件复选框按需勾选、中英文界面实时切换、真断点续传（暂停 / 继续 / 终止）、**一键重试失败**以及带可视化进度条的**官方 SHA 完整性校验**。

## 核心功能

- **支持任意模型主页链接**：直接粘贴 `https://huggingface.co/owner/model`、分支链接（`/tree/<branch>`）、镜像链接（`https://hf-mirror.com/...`）或 `owner/model` 仓库 ID 均可自动解析。
- **多量化版本与分支自动识别（`v1.1.0` 新增）**：
  - 自动识别**子目录分片型 GGUF 仓库**（如 `unsloth/GLM-5.3-GGUF` 下的 `UD-Q4_K_XL/`、`Q8_0/`、`BF16/`）以及**平铺单文件/多分片型仓库**（如 `Qwen2.5-*-GGUF`），在下拉菜单按体积从小到大展示各量化版本的文件数与总大小。
  - 自动读取仓库全部 Git **分支**（`/api/models/{repo}/refs`），支持下拉切换分支。
  - 选中任意量化版本时自动保留根目录公共配置文件，并对多模态视觉权重（`mmproj-*.gguf`）提供独立开关。
  - **文件列表复选框自由勾选**：点击文件行首 `☑`/`☐` 或按空格键即可任意增减文件；下载、一键重试失败、官方 SHA 校验、总进度条和磁盘预警均严格只针对已选文件生效。
  - **防误下保护**：直接点击开始下载多量化仓库时，会先自动解析并弹窗提醒选择目标量化版本，防止误下数 TB。
- **中英文界面实时切换（默认中文）**：界面右上角提供语言下拉菜单（`中文` / `English`），无需重启即可即时切换全部界面文字。
- **智能保存目录**：首次启动自动读取**系统默认“下载”文件夹**（支持已迁移的 Windows 下载目录）；点击 **浏览...** 选择的目录会自动记住，若上次保存的目录不存在了，会弹窗提示并自动重设为系统默认下载文件夹。
- **真断点续传与控制**：基于 HTTP `Range` 分块流式写入 `.part` 临时文件，支持随时**暂停 / 继续 / 终止**，关闭重启软件也不会丢失已下载进度。
- **一键重试失败（`🔄 重试失败`）**：下载结束后若存在失败文件，或 SHA 校验发现损坏/缺失文件，点击一次即可仅重新下载异常文件（自动清理损坏文件），无需重下整个模型。
- **一键官方 SHA 校验（`✔ 校验 SHA`）**：
  - 独立可视化**校验进度条**，实时显示进度百分比、已校验体积、读取速度（MB/s）、预计剩余时间及每个文件的校验结果。
  - **LFS 大文件**自动对比官方 `SHA-256`，**非 LFS 小文件**自动对比官方 `Git Blob SHA-1`。
  - 既可在下载完成后直接校验，也可输入已有本地目录独立校验历史下载的模型。
- **镜像与 Token 支持**：内置 `huggingface.co` / `hf-mirror.com` 切换、1–8 并发线程调节，并支持填写可选 `HF Token` 下载受限仓库。

## 快速开始

### 方式一：直接下载 Windows 成品包（免装 Python）
前往 [Releases](https://github.com/Satleixn/hf-model-downloader/releases) 页面（`v1.1.0`）：
- **绿色便携版 ZIP（推荐）**：下载 **`HF-Model-Downloader-v1.1.0-win64-portable.zip`**，解压后直接运行 `HF-Model-Downloader.exe`。运行时无需向 `%TEMP%` 解压临时目录，启动更快，彻底避免 `Could not create temporary directory!` 报错。
- **单文件 EXE**：下载 **`HF-Model-Downloader-v1.1.0-win64.exe`**，双击即可启动。

两个版本均**禁用 UPX 压缩**（最大程度降低杀毒软件误报），内置 Windows 版本元数据与自定义图标，并在 Release 页面附带官方 SHA-256 校验值；也可运行 `python packaging/build_exe.py` 本地自行构建。

### 方式二：从源码运行（完全不触发 SmartScreen）
- 环境要求：Python 3.9+（自带 `tkinter`）与 `requests`（`pip install -r requirements.txt`）
- Windows 一键启动：通过 `git clone https://github.com/Satleixn/hf-model-downloader.git` 克隆后，直接双击根目录的 **`start.bat`**。
- 命令行启动：
```bash
pip install -r requirements.txt
python app.py
```

支持通过参数预填模型链接、保存目录与界面语言：
```bash
python app.py --url "https://huggingface.co/owner/model" --dir "D:\Models" --lang zh --autostart
```

## Windows SmartScreen 与常见问题

- **为什么首次运行下载的 `.exe` 可能会弹出 Windows SmartScreen 提示？**
  Windows 会为从浏览器下载的未购买商业代码签名证书的开源 `.exe` 加上“来自互联网”标记并弹出 SmartScreen 提示。
- **安全运行方法**：
  1. 在提示窗点击 **更多信息 → 仍要运行**（或在运行/解压前，右键下载的 `.zip`/`.exe` → **属性** → 勾选底部的 **解除锁定**）。
  2. 或采用 `git clone` + 双击 `start.bat` 源码方式启动，完全不会触发 SmartScreen。
- **如果单文件版出现 `Could not create temporary directory!`？**
  请确认存放 `.exe` 的文件夹没有继承沙箱遗留的 Windows `Low Mandatory Level` 权限（可放到“下载”或桌面运行），或改用同版本的 **`HF-Model-Downloader-v1.1.0-win64-portable.zip`** 绿色便携版。

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
