import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .hf_parser import RemoteFile


WEIGHT_EXTENSIONS = (".gguf", ".safetensors", ".bin", ".onnx", ".pt", ".pth")

# Ordered from most specific to most general so UD-Q4_K_XL matches before Q4_K
QUANT_TAG_RE = re.compile(
    r"(?:^|[-_. /])("
    r"UD-(?:IQ\d+_[A-Z0-9_]+|Q\d+_[A-Z0-9_]+)"
    r"|IQ\d+_[A-Z0-9_]+"
    r"|Q\d+_(?:K(?:_(?:XXS|XS|XL|S|M|L))?|[01]|NL)"
    r"|MXFP4|NVFP4|FP8(?:_E4M3|_E5M2|_DYNAMIC)?|FP16|F16|BF16|F32|INT4|INT8|AWQ|GPTQ"
    r")(?:$|[-_. /])",
    re.IGNORECASE,
)

SHARD_SUFFIX_RE = re.compile(r"-\d{5}-of-\d{5}(?=\.[^.]+$)", re.IGNORECASE)


@dataclass(frozen=True)
class QuantOption:
    key: str
    label: str
    filenames: List[str]
    total_size: int
    file_count: int
    kind: str  # "dir" or "file"


@dataclass
class DetectionResult:
    options: List[QuantOption] = field(default_factory=list)
    common_files: List[str] = field(default_factory=list)
    mmproj_files: List[str] = field(default_factory=list)

    @property
    def is_multi_quant(self) -> bool:
        return len(self.options) >= 2


def is_weight_file(rfilename: str) -> bool:
    return rfilename.lower().endswith(WEIGHT_EXTENSIONS)


def is_mmproj_file(rfilename: str) -> bool:
    base = rfilename.rsplit("/", 1)[-1].lower()
    return base.endswith(".gguf") and "mmproj" in base


def extract_quant_tag(name: str) -> Optional[str]:
    """Extract normalized uppercase quantization tag from a filename or folder name."""
    cleaned = SHARD_SUFFIX_RE.sub("", name)
    for ext in WEIGHT_EXTENSIONS:
        if cleaned.lower().endswith(ext):
            cleaned = cleaned[: -len(ext)]
            break
    m = QUANT_TAG_RE.search(cleaned)
    if not m:
        return None
    return m.group(1).upper()


def detect_quantizations(files: List[RemoteFile]) -> DetectionResult:
    """Detect multiple quantization variants in a Hugging Face model repository."""
    if not files:
        return DetectionResult()

    file_sizes: Dict[str, int] = {f.rfilename: f.size for f in files}
    mmproj_files: List[str] = [f.rfilename for f in files if is_mmproj_file(f.rfilename)]
    mmproj_set: Set[str] = set(mmproj_files)

    # Root non-weight files (configs, tokenizers, README, LICENSE, etc.)
    common_files: List[str] = [
        f.rfilename
        for f in files
        if "/" not in f.rfilename
        and f.rfilename not in mmproj_set
        and not is_weight_file(f.rfilename)
    ]

    # Strategy A: Subfolder-based quantization grouping (e.g. BF16/, Q8_0/, UD-Q4_K_XL/)
    dir_groups: Dict[str, List[str]] = {}
    dir_has_weights: Dict[str, bool] = {}
    for f in files:
        if "/" not in f.rfilename or f.rfilename in mmproj_set:
            continue
        top_dir = f.rfilename.split("/", 1)[0]
        dir_groups.setdefault(top_dir, []).append(f.rfilename)
        if is_weight_file(f.rfilename):
            dir_has_weights[top_dir] = True

    weight_dirs = [d for d, has_w in dir_has_weights.items() if has_w]
    quant_dirs = [d for d in weight_dirs if extract_quant_tag(d) is not None]

    if len(quant_dirs) >= 2:
        options: List[QuantOption] = []
        for d in weight_dirs:
            # Keep folders whose name looks like a quant OR all weight-bearing dirs if quant_dirs >= 2
            if d not in quant_dirs:
                continue
            members = sorted(dir_groups[d])
            total_sz = sum(file_sizes[name] for name in members)
            options.append(
                QuantOption(
                    key=f"dir:{d}",
                    label=d,
                    filenames=members,
                    total_size=total_sz,
                    file_count=len(members),
                    kind="dir",
                )
            )
        options.sort(key=lambda o: (o.total_size, o.label.lower()))
        return DetectionResult(
            options=options,
            common_files=sorted(common_files),
            mmproj_files=sorted(mmproj_files),
        )

    # Strategy B: Flat filename/shard quantization clustering (e.g. model-q4_k_m.gguf, *-Q4_K_M-00001-of-00003.gguf)
    tag_groups: Dict[str, List[str]] = {}
    for f in files:
        if f.rfilename in mmproj_set or not is_weight_file(f.rfilename):
            continue
        base = f.rfilename.rsplit("/", 1)[-1]
        tag = extract_quant_tag(base)
        if tag:
            tag_groups.setdefault(tag, []).append(f.rfilename)

    if len(tag_groups) >= 2:
        options = []
        for tag, members in tag_groups.items():
            members_sorted = sorted(members)
            total_sz = sum(file_sizes[name] for name in members_sorted)
            options.append(
                QuantOption(
                    key=f"tag:{tag}",
                    label=tag,
                    filenames=members_sorted,
                    total_size=total_sz,
                    file_count=len(members_sorted),
                    kind="file",
                )
            )
        options.sort(key=lambda o: (o.total_size, o.label.lower()))
        return DetectionResult(
            options=options,
            common_files=sorted(common_files),
            mmproj_files=sorted(mmproj_files),
        )

    # Single-precision / standard repo
    return DetectionResult(
        options=[],
        common_files=sorted(common_files),
        mmproj_files=sorted(mmproj_files),
    )
