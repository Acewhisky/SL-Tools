"""游戏扫描识别。

策略：
1. 遍历内置规则库（game_db.GAME_RULES），展开 %XXX% 路径，
   若存档路径存在则视为「检测到该游戏」。
2. 扫描 Steam userdata 目录（%LOCALAPPDATA%/Steam/userdata/<steamid>/<appid>/remote），
   生成「Steam 云存档」条目。
3. 结合用户已手动添加的游戏。
"""
import os
from pathlib import Path

from .config import store
from .game_db import get_rules
from .utils import log, expand_env_path, safe_name, ts_mtime


def _steam_userdata_dir() -> Path:
    """定位 Steam userdata 目录。"""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Steam" / "userdata",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam" / "userdata",
        Path(r"C:\Program Files\Steam\userdata"),
        Path.home() / "AppData" / "Local" / "Steam" / "userdata",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _scan_steam_appid_remote(steamid: Path, appid_dir: Path) -> dict:
    """扫描单个 appid 的 remote 目录，有实际内容返回条目 dict，否则 None。"""
    remote = appid_dir / "remote"
    if not (remote.exists() and remote.is_dir()):
        return None
    files = [f for f in remote.rglob("*") if f.is_file()]
    if not files:
        return None
    return {
        "name": f"[Steam 云存档] appid={appid_dir.name}",
        "path": str(remote),
        "appid": appid_dir.name,
        "steamid": steamid.name,
        "mtime": max((ts_mtime(f) for f in files), default=0),
    }


def _steam_remote_saves() -> list:
    """扫描 Steam userdata/<uid>/<appid>/remote 下的存档目录。

    返回: [{name, path, appid, steamid, mtime}]
    """
    ud = _steam_userdata_dir()
    results = []
    if not ud or not ud.exists():
        return results
    try:
        for steamid in ud.iterdir():
            if not steamid.is_dir():
                continue
            for appid_dir in steamid.iterdir():
                if not appid_dir.is_dir():
                    continue
                entry = _scan_steam_appid_remote(steamid, appid_dir)
                if entry:
                    results.append(entry)
    except Exception as e:
        log.warning("扫描 Steam userdata 失败: %s", e)
    return results


def _scan_builtin_rules(rules: dict) -> tuple:
    """扫描内置规则，返回 (found, missing)。存真实路径（便于前端判断与备份）。"""
    found, missing = [], []
    for name, rule in rules.items():
        paths = rule.get("paths", [])
        existed = [str(expand_env_path(p)) for p in paths if expand_env_path(p).exists()]
        item = {
            "name": name,
            "platform": rule.get("platform", []),
            # 存在则用实际存在路径，否则保留模板供用户查看
            "save_paths": existed if existed else paths,
            "processes": rule.get("processes", []),
            "detected": bool(existed),
            "source": "builtin",
        }
        (found if existed else missing).append(item)
    return found, missing


def _build_custom_games() -> list:
    """构建用户自定义游戏列表。"""
    custom = []
    for g in store.games:
        save_paths = g.get("save_paths", [])
        custom.append({
            "name": g.get("name", ""),
            "platform": g.get("platform", ["Other"]),
            "save_paths": save_paths,
            "processes": g.get("processes", []),
            "detected": any(Path(p).exists() for p in save_paths),
            "source": "custom",
            "id": g.get("id"),
        })
    return custom


def _merge_online_found(found: list, custom: list) -> int:
    """联网增强：合并 Ludusavi 扫描结果（去重已存在游戏名），返回新增数量。"""
    try:
        from . import ludusavi_rules
        luda_found = ludusavi_rules.scan_local()
    except Exception as e:
        log.warning("联网增强扫描失败（忽略）: %s", e)
        return 0
    existing_names = {g["name"] for g in found} | {g["name"] for g in custom}
    added = 0
    for item in luda_found:
        if item["name"] not in existing_names:
            found.append(item)
            added += 1
    log.info("联网增强扫描: 新增 %d 个游戏", added)
    return added


def scan_games(online: bool = True) -> dict:
    """扫描本机游戏存档。

    online=True 时联网增强（Ludusavi 规则库）；False 仅用内置规则（秒级，供首次启动）。

    返回:
    {
      "found": [ {name, platform, save_paths, processes, detected:true, source:"builtin"} ... ],
      "steam_remote": [...],
      "custom": [...],   # 用户手动添加的
      "missing": [...],  # 内置规则中路径不存在的（保留展示）
    }
    """
    rules = get_rules()
    found, missing = _scan_builtin_rules(rules)
    custom = _build_custom_games()

    # 联网增强扫描（Ludusavi 规则库）：仅在线时生效，失败自动降级
    if online and store.settings.get("scan_online", True):
        _merge_online_found(found, custom)

    steam_remote = _steam_remote_saves()

    return {
        "found": found,
        "missing": missing,
        "custom": custom,
        "steam_remote": steam_remote,
    }


def _add_builtin_games(result: dict, existing_ids: set, existing_names: set) -> list:
    """把内置检测到的游戏（含 ludusavi 联网增强）写入 store，返回新增列表。"""
    added = []
    for item in result["found"]:
        if item["name"] in existing_names:
            continue
        g = {
            "id": "builtin_" + safe_name(item["name"])[:40],
            "name": item["name"],
            "platform": item["platform"],
            "save_paths": item["save_paths"],
            "processes": item["processes"],
            "custom": False,
            "auto_backup": False,
        }
        if item.get("source") == "ludusavi":
            g["source"] = "ludusavi"
        # 避免 id 冲突
        while g["id"] in existing_ids:
            g["id"] += "_x"
        store.upsert_game(g)
        existing_ids.add(g["id"])
        existing_names.add(item["name"])
        added.append(g)
    return added


def _add_steam_games(result: dict) -> list:
    """把 Steam 云存档条目写入 store（以 steamid+appid 命名去重），返回新增列表。"""
    steam_ids = {g.get("id") for g in store.games if g.get("source") == "steam"}
    added = []
    for sr in result["steam_remote"]:
        gid = f"steam_{sr['steamid']}_{sr['appid']}"
        if gid in steam_ids:
            continue
        g = {
            "id": gid,
            "name": sr["name"],
            "platform": ["Steam"],
            "save_paths": [sr["path"]],
            "processes": [],
            "custom": False,
            "source": "steam",
            "auto_backup": False,
        }
        store.upsert_game(g)
        added.append(g)
    return added


def sync_builtin_to_store(online: bool = True) -> dict:
    """把内置规则中「检测到」的游戏写入 games.json（幂等），返回新增列表。"""
    result = scan_games(online=online)
    existing_ids = {g.get("id") for g in store.games}
    existing_names = {g.get("name") for g in store.games}

    added = _add_builtin_games(result, existing_ids, existing_names)
    added += _add_steam_games(result)

    # 日志输出新增游戏具体名称（方便用户确认扫描结果）
    added_names = [g.get("name", "") for g in added]
    if added_names:
        log.info("扫描新增 %d 个游戏: %s", len(added_names), "、".join(added_names))
    else:
        log.info("扫描完成，无新增游戏（共 %d 个）", len(store.games))

    return {"added": len(added), "total": len(store.games), "added_names": added_names}
