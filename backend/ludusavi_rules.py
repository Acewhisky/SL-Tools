"""Ludusavi 规则库联网增强扫描。

从官方 Ludusavi Manifest（覆盖 19000+ 游戏）下载规则并解析，
与本机文件系统比对，找出匹配的存档路径，增强扫描范围。

- 仅联网时生效（网络不可用/下载失败时自动回退到内置规则）
- 下载缓存到 data/ludusavi/manifest.yaml，用 ETag 判断是否有更新（304 跳过下载）
- manifest 占位符（%APPDATA% 等）展开为真实路径后再做存在性检查
"""
import os
import re
import time
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from .config import store
from .utils import log

MANIFEST_URL = "https://raw.githubusercontent.com/mtkennerly/ludusavi-manifest/master/data/manifest.yaml"

CACHE_DIR_NAME = "ludusavi"
MANIFEST_FILE = "manifest.yaml"
ETAG_FILE = "etag.txt"

# manifest 整体下载超时（秒）：网络慢时不无限阻塞，超时降级为缓存/离线
DOWNLOAD_TIMEOUT = 120

# 允许的 Windows 存档占位符（其余如 <base>/<installDir> 等 store 相关占位符会跳过）

# 常见占位符 -> 环境变量名映射（Ludusavi 用 <xxx> 表示路径段）
_PLACEHOLDER_ENV = {
    "winAppData": "APPDATA",
    "winLocalAppData": "LOCALAPPDATA",
    "winLocalAppDataLow": None,  # 特判
    "winUserProfile": "USERPROFILE",
    "winPublic": "PUBLIC",
    "winProgramData": "PROGRAMDATA",
    "winWindows": "WINDIR",
    "winSavedGames": None,  # 特判
    "winDocuments": None,   # 特判
    "home": "USERPROFILE",
    "appData": "APPDATA",
    "localAppData": "LOCALAPPDATA",
    "localAppDataLow": None,
    "userProfile": "USERPROFILE",
    "public": "PUBLIC",
    "programData": "PROGRAMDATA",
    "savedGames": None,
    "documents": None,
    "windows": "WINDIR",
}


def _special_path(name: str) -> str:
    """处理非标准环境变量占位符。"""
    home = Path(os.environ.get("USERPROFILE", ""))
    if name in ("winSavedGames", "savedGames"):
        return str(home / "Saved Games")
    if name in ("winDocuments", "documents", "doc"):
        return str(home / "Documents")
    if name in ("winLocalAppDataLow", "localAppDataLow"):
        return str(home / "AppData" / "LocalLow")
    return None


def _expand_placeholder(path: str) -> str:
    """展开 manifest 路径占位符（<winAppData> 等）为真实路径（不做存在性检查）。

    不支持的占位符（<base>/<root>/<xdgConfig> 等）返回原始串（调用方跳过）。
    """
    def repl(m):
        key = m.group(1)
        if key in _PLACEHOLDER_ENV:
            env = _PLACEHOLDER_ENV[key]
            if env:
                val = os.environ.get(env)
                return val.replace("\\", "/") if val else ""
            sp = _special_path(key)
            return sp.replace("\\", "/") if sp else ""
        return m.group(0)  # 未知占位符保留原样（调用方会跳过）
    return _PLACEHOLDER_RE.sub(repl, path)


_PLACEHOLDER_RE = re.compile(r"<([a-zA-Z_]+)>")


def _cache_dir() -> Path:
    from .config import DATA_DIR
    return DATA_DIR / CACHE_DIR_NAME


def _fetch_manifest_from(source_url: str, headers: dict, timeout: float) -> tuple:
    """从单个源下载 manifest，返回 (status, body)。失败抛异常由调用方回退。"""
    req = urllib.request.Request(source_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.status
        # 分块读取并限制总时长（manifest 17MB，网络慢时全量 read 可能无限阻塞）
        deadline = time.monotonic() + timeout
        chunks = []
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("manifest 下载超时")
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
        body = b"".join(chunks)
        return status, body, resp.headers.get("ETag")


def download_manifest(force: bool = False) -> Path:
    """下载/更新 Ludusavi manifest 到缓存，返回缓存文件路径。

    网络不可用时返回已有缓存（若有），否则返回 None。

    规则库源由 settings.rules_source 控制：
    - auto（默认）：多源回退 jsDelivr → fastly → GitHub raw → 本地缓存
    - jsdelivr：仅 jsDelivr（国内直连稳定，支持 ETag/304）
    - github：仅 GitHub raw（原源）
    """
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    manifest_path = cache / MANIFEST_FILE
    etag_path = cache / ETAG_FILE

    # 本地已是最新（最近 7 天内下载过且 force=False）-> 直接用缓存
    if not force and manifest_path.exists():
        if etag_path.exists():
            try:
                mtime = manifest_path.stat().st_mtime
                if time.time() - mtime < 7 * 86400:
                    return manifest_path
            except OSError:
                pass
        else:
            return manifest_path

    # 尝试联网更新（多源回退）
    headers = {"User-Agent": "savemgr/1.0"}
    if not force and etag_path.exists():
        try:
            headers["If-None-Match"] = etag_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    # 按设置选择源：auto=多源回退 / jsdelivr=仅CDN / github=仅原源
    source_mode = store.settings.get("rules_source", "auto")
    JSDELIVR = "https://cdn.jsdelivr.net/gh/mtkennerly/ludusavi-manifest@master/data/manifest.yaml"
    JSDELIVR_FASTLY = "https://fastly.jsdelivr.net/gh/mtkennerly/ludusavi-manifest@master/data/manifest.yaml"
    if source_mode == "jsdelivr":
        sources = [("jsDelivr", JSDELIVR), ("jsDelivr-fastly", JSDELIVR_FASTLY)]
    elif source_mode == "github":
        sources = [("GitHub", MANIFEST_URL)]
    else:  # auto
        sources = [
            ("jsDelivr", JSDELIVR),
            ("jsDelivr-fastly", JSDELIVR_FASTLY),
            ("GitHub", MANIFEST_URL),
        ]
    last_err = None
    for name, url in sources:
        try:
            status, body, new_etag = _fetch_manifest_from(url, headers, DOWNLOAD_TIMEOUT)
            if status == 304:  # 无更新
                log.info("Ludusavi manifest 无更新 (304, %s)", name)
                return manifest_path
            manifest_path.write_bytes(body)
            if new_etag:
                etag_path.write_text(new_etag, encoding="utf-8")
            log.info("Ludusavi manifest 下载完成 (%s): %.1f KB", name, len(body) / 1024)
            return manifest_path
        except Exception as e:
            last_err = e
            log.warning("Ludusavi manifest 下载失败 (%s): %s", name, e)

    log.warning("Ludusavi manifest 所有源均失败（使用缓存或回退）: %s", last_err)
    return manifest_path if manifest_path.exists() else None


def _parse_manifest_fast(manifest_path: Path) -> dict:
    """逐行扫描 manifest.yaml -> {游戏名: [路径模板列表]}。

    manifest 高达 17MB/5万+条目，PyYAML 全量解析需 ~50s；
    逐行解析只提取游戏名与 files 路径，约 2-3s。
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning("读取 manifest 失败: %s", e)
        return {}

    result = {}
    game_name = None
    in_files = False
    cur_paths = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            # 游戏名行（可带引号）
            game_name = stripped[:-1].strip().strip('"').strip("'")
            in_files = False
            cur_paths = []
            result[game_name] = cur_paths
        elif game_name and stripped == "files:":
            in_files = True
        elif game_name and in_files and indent >= 4 and (stripped.startswith(('"', "/", "<"))):
            # 路径行：形如 '  "<winAppData>/xxx":' 或 '  /xxx:'
            path = stripped.split(":", 1)[0].strip()
            # 去掉引号
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            if "{" in path:
                # 含 store 相关占位符（{installDir} 等）-> 跳过
                continue
            cur_paths.append(path)
    return result


def _local_dir_name_set() -> set:
    """收集本机存档候选根目录下的第一级目录名（小写集合）。

    一次 listdir 构建，之后纯内存匹配，避免对 5 万+ 游戏逐个 stat。
    """
    home = Path(os.environ.get("USERPROFILE", ""))
    roots = [
        home / "AppData" / "Roaming",
        home / "AppData" / "Local",
        home / "AppData" / "LocalLow",
        home / "Saved Games",
        home / "Documents",
    ]
    names = set()
    for r in roots:
        try:
            if r.exists():
                for d in r.iterdir():
                    if d.is_dir():
                        names.add(d.name.lower())
        except OSError:
            continue
    return names


def _scan_fast(manifest_path: Path) -> list:
    """快速扫描：先构建本机目录名集合，解析 manifest 做集合匹配，候选精确确认。"""
    local_names = _local_dir_name_set()
    if not local_names:
        return []

    rules = _parse_manifest_fast(manifest_path)
    candidates = {}  # game_name -> set(展开路径)
    for name, paths in rules.items():
        hit_paths = set()
        for p in paths:
            expanded = _expand_placeholder(p)
            if "<" in expanded or ">" in expanded:
                # 仍有未识别的占位符（<base>/<root>/<xdgConfig> 等）-> 跳过
                continue
            # 找到存档根关键字（AppData/Roaming, AppData/Local, LocalLow,
            # Saved Games, Documents），其后的第一级目录名即游戏目录
            segs = [s.lower() for s in expanded.split("/") if s]
            game_dir = None
            for i, s in enumerate(segs):
                if s in ("roaming", "local", "locallow", "saved games", "documents"):
                    if i + 1 < len(segs):
                        game_dir = segs[i + 1]
                    break
            if game_dir and game_dir in local_names:
                hit_paths.add(expanded)
        if hit_paths:
            candidates[name] = hit_paths

    # 候选精确确认（仅确认候选，数量很少）
    found = []
    for name, paths in candidates.items():
        existed = []
        for p in paths:
            try:
                if Path(p).exists():
                    existed.append(str(Path(p)))
            except (OSError, ValueError):
                continue
        if existed:
            found.append({
                "name": name,
                "platform": ["PC"],
                "save_paths": existed,
                "processes": [],
                "detected": True,
                "source": "ludusavi",
            })
    log.info("Ludusavi 快速扫描: 候选 %d 个, 命中 %d 个", len(candidates), len(found))
    return found


def scan_local() -> list:
    """扫描本机：返回匹配的 [{name, save_paths, source}]。

    仅保留至少一个路径真实存在的游戏。
    """
    manifest_path = download_manifest()
    if not manifest_path:
        log.info("Ludusavi manifest 不可用，跳过联网增强")
        return []
    if yaml is None:
        log.warning("未安装 PyYAML，无法解析 Ludusavi manifest")
        return []
    try:
        return _scan_fast(manifest_path)
    except Exception as e:
        log.warning("Ludusavi 快速扫描失败: %s", e)
        return []
