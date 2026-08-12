"""业务服务层：游戏列表组装、批量备份编排等（app.py 只保留 HTTP 薄壳）。

目标：避免路由层堆积业务逻辑，便于复用与测试。
"""
from pathlib import Path

from .config import store
from . import backup as bk
from . import steam_search
from .utils import log, expand_env_path


def game_dict(g) -> dict:
    """游戏配置转前端展示结构：游戏列表 - 存档路径 - 备份目录。"""
    versions = bk.list_versions(g.get("id", ""))
    return {
        "id": g.get("id"),
        "name": g.get("name", ""),
        "platform": g.get("platform", []),
        "save_paths": g.get("save_paths", []),
        "processes": g.get("processes", []),
        "custom": g.get("custom", False),
        "source": g.get("source", "custom" if g.get("custom") else "builtin"),
        "auto_backup": g.get("auto_backup", False),
        "favorite": bool(g.get("favorite", False)),
        # 最近一次备份时间戳（字符串可字典序比较：%Y%m%d_%H%M%S）
        "last_backup_ts": versions[0]["timestamp"] if versions else "",
        "version_count": len(versions),
        "backup_dir": str(bk.game_backup_dir(g.get("id", ""))),
        "detected": any(expand_env_path(p).exists() for p in g.get("save_paths", [])),
        # Steam 图标（仅联网时生效，前端 img onerror 回退默认图标）
        "icon_url": steam_search.icon_url_for(g),
    }


def list_games_sorted() -> list:
    """游戏列表（过滤隐藏）+ 收藏置顶排序。

    排序规则：收藏在前（多个收藏按最近备份时间倒序，最新变更排最前），
    其余按版本数倒序、名称升序。
    """
    games = [game_dict(g) for g in store.games if not g.get("hidden")]
    fav = [g for g in games if g.get("favorite")]
    other = [g for g in games if not g.get("favorite")]
    fav.sort(key=lambda x: (x.get("last_backup_ts") or ""), reverse=True)
    other.sort(key=lambda x: (-x.get("version_count", 0), x["name"]))
    return fav + other


def backup_all(force: bool = False, note: str = "", mode: str = None) -> dict:
    """备份所有游戏（无变更自动跳过）。返回汇总结果，供路由与测试复用。"""
    results = []
    for g in store.games:
        if g.get("hidden"):
            continue  # 隐藏的游戏不参与批量备份
        item = {"id": g.get("id"), "name": g.get("name", ""), "status": "skipped", "timestamp": None}
        try:
            # create_backup 内部已做无变更检测（BackupUnchanged -> skipped），
            # 不再重复预检（Q1 修复：避免大存档双重全量 SHA256）
            v = bk.create_backup(g, note=note, mode=mode, force=force)
            item["status"] = "ok"
            item["timestamp"] = v["timestamp"]
        except bk.BackupUnchanged as e:
            item["status"] = "skipped"
            item["reason"] = str(e)
        except bk.BackupError as e:
            item["status"] = "error"
            item["reason"] = str(e)
        except Exception as e:
            item["status"] = "error"
            item["reason"] = str(e)
        results.append(item)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = [r for r in results if r["status"] == "error"]
    return {"results": results, "ok": ok_count, "skipped": skipped,
            "error": len(errors), "errors": errors}


def check_backup_root_conflict() -> str:
    """检测备份根目录是否与任一游戏存档路径重叠（防循环递归）。返回警告文案或空串。"""
    conflicts = bk.find_backup_root_conflicts()
    if conflicts:
        c = conflicts[0]
        return (
            "⚠️ 备份目录与存档目录存在重叠，自动备份已被停止，防止循环递归！\n"
            f"存档: {c['save']}\n备份: {c['backup']}\n"
            "请更换备份位置（不要放在存档目录内）。"
        )
    return ""
