from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests


DEFAULT_ENDPOINT = "https://huggingface.co"


@dataclass(frozen=True)
class ParsedRepo:
    endpoint: str
    repo_id: str
    revision: str = "main"

    @property
    def model_name(self) -> str:
        return self.repo_id.split("/")[-1]


@dataclass(frozen=True)
class RemoteFile:
    rfilename: str
    size: int
    sha256: Optional[str] = None
    blob_id: Optional[str] = None


def parse_hf_input(raw_input: str, default_endpoint: str = DEFAULT_ENDPOINT) -> ParsedRepo:
    """Parse a Hugging Face model URL or `owner/repo` string into (endpoint, repo_id, revision)."""
    text = (raw_input or "").strip()
    if not text:
        raise ValueError("请输入 Hugging Face 模型链接或仓库 ID（如 owner/model）。")

    endpoint = (default_endpoint or DEFAULT_ENDPOINT).strip().rstrip("/")
    revision = "main"

    # Normalize bare host URLs like "huggingface.co/owner/repo"
    if not text.startswith(("http://", "https://")) and (
        text.startswith("huggingface.co/")
        or text.startswith("www.huggingface.co/")
        or text.startswith("hf-mirror.com/")
    ):
        text = "https://" + text

    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        if not parsed.netloc:
            raise ValueError(f"无法解析链接: {raw_input}")
        endpoint = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        parts = [p for p in parsed.path.split("/") if p]

        # Reject non-model URLs clearly
        if parts and parts[0] in ("datasets", "spaces"):
            raise ValueError(f"当前工具仅支持模型仓库，不支持 {parts[0]} 链接: {raw_input}")
        if parts and parts[0] == "models":
            parts = parts[1:]

        if len(parts) < 2:
            raise ValueError(f"链接缺少完整的 owner/model 路径: {raw_input}")

        owner, repo = parts[0], parts[1]
        if len(parts) >= 4 and parts[2] in ("tree", "blob", "resolve", "raw"):
            revision = parts[3]

        repo_id = f"{owner}/{repo}"
    else:
        # Raw repo ID like "owner/repo" or "owner/repo@rev"
        text = text.strip("/")
        if "@" in text:
            text, revision = text.split("@", 1)
            revision = revision.strip() or "main"
        parts = [p for p in text.split("/") if p]
        if len(parts) != 2:
            raise ValueError(f"无效的仓库 ID，请使用 owner/model 格式或完整链接: {raw_input}")
        repo_id = f"{parts[0]}/{parts[1]}"

    return ParsedRepo(endpoint=endpoint, repo_id=repo_id, revision=revision)


def build_headers(token: str = "", start_byte: int = 0) -> Dict[str, str]:
    headers = {"User-Agent": "HFModelDownloader/2.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"
    return headers


def fetch_repo_files(
    endpoint: str,
    repo_id: str,
    revision: str = "main",
    token: str = "",
    timeout: int = 30,
) -> List[RemoteFile]:
    """Fetch full file list with size and official SHA metadata from Hugging Face API."""
    base = endpoint.rstrip("/")
    if revision and revision != "main":
        api_url = f"{base}/api/models/{repo_id}/revision/{revision}?blobs=true"
    else:
        api_url = f"{base}/api/models/{repo_id}?blobs=true"

    resp = requests.get(api_url, headers=build_headers(token), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    siblings = data.get("siblings", [])
    files: List[RemoteFile] = []
    for item in siblings:
        rfilename = item.get("rfilename")
        if not rfilename:
            continue
        lfs = item.get("lfs") if isinstance(item.get("lfs"), dict) else None
        size = item.get("size")
        if size is None and lfs is not None:
            size = lfs.get("size", 0)
        sha256 = lfs.get("sha256") if lfs is not None else None
        blob_id = item.get("blobId")
        files.append(
            RemoteFile(
                rfilename=rfilename,
                size=int(size or 0),
                sha256=sha256,
                blob_id=blob_id,
            )
        )

    return files
