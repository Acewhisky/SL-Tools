"""工具函数：路径展开、哈希计算、进程检测、日志等。"""
import json
import os
import re
import time
import hashlib
import logging
import threading
from pathlib import Path
from datetime import datetime

log = logging.getLogger("savemgr")


def expand_env_path(raw: str) -> Path:
    """展开存档路径中的 %XXX% 占位符与 ~ 等，返回 Path。

    支持常见 Windows 环境变量，以及自定义的 %SAVED_GAMES%。
    """
    if not raw:
        return Path("")

    # 自定义占位符
    saved = Path.home() / "Saved Games"
    user = Path.home()
    custom = {
        "SAVED_GAMES": str(saved),
        "USERPROFILE": str(user),
        "HOME": str(user),
        "DOCUMENTS": str(user / "Documents"),
        "DOCUMENTS_X64": str(user / "Documents"),
        "PUBLIC": r"C:\Users\Public",
    }

    result = raw
    for key, val in custom.items():
        result = result.replace(f"%{key}%", val)

    result = os.path.expandvars(result)
    result = os.path.expanduser(result)
    p = Path(result)
    # 展开后的路径如果还是带 % 的变量未识别，原样返回（可能无效）
    return p


def is_game_running(processes) -> bool:
    """检测指定进程名（如 eldenring.exe）是否在运行。"""
    import psutil

    names = {p.lower() for p in (processes or []) if p}
    if not names:
        return False
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name") or ""
                if name.lower() in names:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        return False
    return False


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def dir_size(path: Path) -> int:
    """计算目录总大小（字节）。"""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def ts_now() -> str:
    """当前时间戳字符串，用于备份目录命名。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ts_display(ts: str) -> str:
    """时间戳转友好显示。"""
    try:
        return datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts


def safe_name(name: str) -> str:
    """文件/目录名安全化（去非法字符）。"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
    return name.strip() or "unnamed"


def fmt_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    if nbytes < 1024**2:
        return f"{nbytes/1024:.1f} KB"
    if nbytes < 1024**3:
        return f"{nbytes/1024**2:.1f} MB"
    return f"{nbytes/1024**3:.2f} GB"


def ts_mtime(path: Path) -> int:
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return 0


def is_subpath(child: Path, parent: Path) -> bool:
    """判断 child 是否在 parent 目录内（含相等）。用于防循环递归检测。"""
    try:
        child = child.resolve()
        parent = parent.resolve()
        return child == parent or parent in child.parents
    except OSError:
        return False


def read_json(path: Path, default=None):
    """读取 JSON 文件，失败（不存在/损坏）返回 default。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data):
    """写入 JSON 文件（UTF-8，缩进，保留中文）。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
