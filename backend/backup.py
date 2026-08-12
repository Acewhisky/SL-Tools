"""备份/恢复核心逻辑（支持完整备份 + 增量备份）。

备份结构（备份根目录下，每个游戏一个子目录，每个版本一个时间戳目录）：

  full 版本:
    <ts>/
      manifest.json     # 文件清单 + SHA256（含完整清单 files、来源 dirs）
      meta.json         # 版本元信息（kind=full, base_version=null）
      data/             # 实际存档文件（未压缩时）
      snapshot.zip      # 实际存档文件（压缩时，可选）

  incr 版本:
    <ts>/
      manifest.json     # files=完整清单（逻辑）, changes=本版本存储的文件,
                        #   deleted=相对 base 删除的文件列表, kind=incr
      meta.json         # kind=incr, base_version=上一个版本 ts
      changes/          # 仅存放新增/修改的文件（相对 base）
      deleted.json      # 相对 base 删除的文件相对路径列表

版本目录命名: %Y%m%d_%H%M%S，同秒冲突自动加 _N 后缀。

恢复 / 校验流程统一为「沿 base_version 链回溯到 full，复原后依次应用每个 incr 的 changes/deleted」，
由 reconstruct() 完成；清理版本时若被后代引用，会先提升首个后代为 full 以保持链完整。
"""
import json
import os
import shutil
import time
import zipfile
import tarfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

from .config import store
from .utils import (log, is_game_running, sha256_file, dir_size, ts_now, ts_display,
                    safe_name, fmt_size, expand_env_path, is_subpath, read_json, write_json)

# 兼容别名（保留 _read_json/_write_json 旧调用名，统一走 utils 实现）
_read_json = read_json
_write_json = write_json

MANIFEST_NAME = "manifest.json"
META_NAME = "meta.json"
DATA_DIR_NAME = "data"
CHANGES_DIR_NAME = "changes"
DELETED_NAME = "deleted.json"

KIND_FULL = "full"
KIND_INCR = "incr"

_backup_lock = threading.RLock()


def force_rmtree(path: Path) -> bool:
    """彻底删除目录（使用底层 os API，逐文件/目录清理）。

    相比 shutil.rmtree：不依赖系统回收站，删除更可靠。
    返回是否删除成功（目录已不存在视为成功）。
    """
    path = Path(path)
    if not path.exists():
        return True
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                try:
                    os.unlink(os.path.join(root, name))
                except OSError as e:
                    log.warning("删除文件失败 %s: %s", os.path.join(root, name), e)
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except OSError:
                    pass
        try:
            os.rmdir(path)
        except OSError:
            pass
    except Exception as e:
        log.warning("删除目录 %s 异常: %s", path, e)
    if path.exists():
        log.warning("删除目录未完全清理: %s（可能被占用）", path)
        return False
    return True


def game_backup_dir(game_id: str) -> Path:
    root = Path(store.settings["backup_root"])
    return root / safe_name(game_id)


def version_dir(game_id: str, ts: str) -> Path:
    return game_backup_dir(game_id) / ts


def _relative(full_path: Path, base: Path) -> str:
    try:
        return full_path.relative_to(base).as_posix()
    except ValueError:
        return full_path.name


def _collect_files(src: Path) -> list:
    """收集目录下所有文件相对路径，保持排序稳定。"""
    result = []
    for root, _dirs, files in os.walk(src):
        for name in sorted(files):
            full = Path(root) / name
            result.append(_relative(full, src))
    return sorted(result)


def _copy_tree(src: Path, dst: Path):
    """复制目录树（保留空目录）。"""
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore_dangling_symlinks=True)


def _merge_copy(src: Path, dst: Path):
    """合并覆盖复制（不依赖删除目录，避免数据丢失窗口）。"""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _merge_copy(item, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _prune_extra(src: Path, dst: Path, removed: list):
    """删除 dst 中 src 没有的文件（尽力而为，失败仅记录日志）。"""
    if not dst.exists():
        return
    for item in dst.iterdir():
        corresponding = src / item.name
        if item.is_dir():
            if corresponding.is_dir():
                _prune_extra(corresponding, item, removed)
            else:
                try:
                    force_rmtree(item)
                    removed.append(str(item))
                except OSError as e:
                    log.warning("清理多余目录失败 %s: %s", item, e)
        else:
            if not corresponding.exists():
                try:
                    os.unlink(item)
                    removed.append(str(item))
                except OSError as e:
                    log.warning("清理多余文件失败 %s: %s", item, e)


# ---------------- 备份 ----------------

class BackupError(Exception):
    pass


class BackupUnchanged(Exception):
    """存档无变更，无需备份。"""


def check_changes(game: dict, full_files: dict = None, dirs_info: dict = None,
                  existing: list = None) -> dict:
    """检测存档自最近一次备份以来是否有变化。

    可传入 _compute_current_state 的预计算结果（full_files 等），
    避免与调用方重复全量 SHA256 计算（大存档性能关键）。
    返回: {"changed": bool, "latest": 最近版本时间戳 or None, "reason": 说明}
    """
    game_id = game["id"]
    if full_files is None:
        try:
            full_files, dirs_info, existing = _compute_current_state(game)
        except Exception as e:
            return {"changed": False, "latest": None, "reason": f"读取存档失败: {e}"}
    if not full_files:
        return {"changed": False, "latest": None, "reason": "存档目录不存在"}
    versions = list_versions(game_id)
    if not versions:
        return {"changed": True, "latest": None, "reason": "尚无任何备份"}
    latest = versions[0]
    prev_manifest = _read_json(version_dir(game_id, latest["timestamp"]) / MANIFEST_NAME, {})
    prev_files = prev_manifest.get("files", {})
    if prev_files == full_files:
        return {"changed": False, "latest": latest["timestamp"], "reason": "存档无变更"}
    changed = len(full_files) - len(prev_files)
    changed = max(changed, 1)
    return {"changed": True, "latest": latest["timestamp"], "reason": f"{changed} 个文件有变化"}


def _compute_current_state(game: dict) -> tuple:
    """计算当前存档状态：(完整文件清单 manifest.files, dirs 元信息, 实际占用路径列表)。

    完整文件清单以"相对 source 顶层目录名"为前缀：例如存档在 C:/.../Hades II，
    则文件键为 'Hades II/save.dat'。这是为了在多个源目录共存时仍能清晰区分。
    """
    existing = []
    for p in game.get("save_paths", []):
        if p:
            ep = expand_env_path(p)
            if ep.exists():
                existing.append(ep)

    full_files = {}      # 完整清单（相对路径 -> sha256）
    dirs_info = {}       # {顶层目录名: {source, file_count}}
    for pobj in existing:
        key = safe_name(pobj.name)
        if pobj.is_dir():
            files = _collect_files(pobj)
            for rel in files:
                full_files[f"{key}/{rel}"] = sha256_file(pobj / rel)
            dirs_info[key] = {"source": str(pobj), "file_count": len(files)}
        else:
            full_files[key] = sha256_file(pobj)
            dirs_info[key] = {"source": str(pobj), "file_count": 1}
    return full_files, dirs_info, existing


def _create_full_backup(game: dict, ts: str, full_files: dict, dirs_info: dict, existing: list, note: str) -> dict:
    """创建完整备份（存储 data/，可选压缩为 zip/tar.gz）。"""
    game_id = game["id"]
    vdir = version_dir(game_id, ts)
    data_dir = vdir / DATA_DIR_NAME
    data_dir.mkdir(parents=True, exist_ok=True)

    for pobj in existing:
        key = safe_name(pobj.name)
        if pobj.is_dir():
            _copy_tree(pobj, data_dir / key)
        else:
            shutil.copy2(pobj, data_dir / key)

    size = dir_size(data_dir)
    meta = {
        "kind": KIND_FULL,
        "base_version": None,
        "game_id": game_id,
        "game_name": game.get("name", ""),
        "timestamp": ts,
        "created": datetime.now().isoformat(timespec="seconds"),
        "note": note or "",
        "size": size,
        "source_paths": [str(p) for p in existing],
        "status": "ok",
        "verified": False,
        "favorite": False,
        "compress": "none",
    }

    fmt = store.settings.get("compress_format", "none")
    if fmt == "zip":
        zip_path = vdir / "snapshot.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _d, files in os.walk(data_dir):
                for name in files:
                    full = Path(root) / name
                    arc = _relative(full, data_dir)
                    zf.write(full, arcname=arc)
        meta["compress"] = "zip"
        meta["zip_size"] = zip_path.stat().st_size
        force_rmtree(data_dir)
    elif fmt == "tar.gz":
        tar_path = vdir / "snapshot.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(data_dir, arcname="data")
        meta["compress"] = "tar.gz"
        meta["zip_size"] = tar_path.stat().st_size
        force_rmtree(data_dir)

    manifest = {"kind": KIND_FULL, "files": full_files, "dirs": dirs_info,
                "changes": {}, "deleted": []}
    _write_json(vdir / MANIFEST_NAME, manifest)
    _write_json(vdir / META_NAME, meta)
    return meta


def _create_incr_backup(game: dict, ts: str, prev_manifest: dict, prev_meta: dict,
                       full_files: dict, dirs_info: dict, existing: list, note: str) -> dict:
    """创建增量备份（仅存新增/变更文件 + 删除清单）。

    prev_manifest["files"] 是上一版本完整清单，full_files 是当前完整清单。
    changed = 新增或哈希不一致；deleted = 上一版本有但当前没有。
    """
    game_id = game["id"]
    # base_version 使用上一版本"目录名"（prev_meta["base_dir"] 优先，兼容旧数据）
    base_ts = prev_meta.get("base_dir") or prev_meta.get("timestamp")
    if not base_ts:
        # 防御：无基线不允许创建增量（增量链必须最终回溯到某个 full）
        raise BackupError("增量备份缺少基线版本（无历史版本时请先做 full 备份）")
    vdir = version_dir(game_id, ts)
    changes_dir = vdir / CHANGES_DIR_NAME
    changes_dir.mkdir(parents=True, exist_ok=True)

    prev_files = prev_manifest.get("files", {})
    changed = {}  # 本次实际复制的文件
    deleted = []  # 相对 base 删除的文件相对路径

    # 计算 changed 与 deleted
    for rel, h in full_files.items():
        if prev_files.get(rel) != h:
            changed[rel] = h
    for rel in prev_files:
        if rel not in full_files:
            deleted.append(rel)

    # 把变更文件物理复制到 changes/
    for rel in changed:
        # rel 形如 "顶层/子/文件"，需要从 existing 中找到这个顶层对应的源
        top = rel.split("/", 1)[0]
        src_path = None
        for pobj in existing:
            if safe_name(pobj.name) == top:
                src_path = pobj / (rel[len(top) + 1:] if "/" in rel else "")
                break
        if src_path and src_path.exists():
            target = changes_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, target)

    # 计算 changes 占用大小
    size = dir_size(changes_dir)
    meta = {
        "kind": KIND_INCR,
        "base_version": base_ts,
        "game_id": game_id,
        "game_name": game.get("name", ""),
        "timestamp": ts,
        "created": datetime.now().isoformat(timespec="seconds"),
        "note": note or "",
        "size": size,
        "source_paths": [str(p) for p in existing],
        "status": "ok",
        "verified": False,
        "favorite": False,
        "compress": "none",
        "change_count": len(changed),
        "delete_count": len(deleted),
    }
    manifest = {
        "kind": KIND_INCR,
        "base_version": base_ts,
        "files": full_files,
        "changes": changed,
        "deleted": sorted(deleted),
        "dirs": dirs_info,
    }
    _write_json(vdir / MANIFEST_NAME, manifest)
    _write_json(vdir / META_NAME, meta)
    _write_json(vdir / DELETED_NAME, sorted(deleted))
    return meta


def _decide_backup_kind(game: dict, mode: str, prev_meta: dict, prev_manifest: dict,
                       full_files: dict, existing: list) -> str:
    """决定本次备份类型（full / incr）。

    无历史版本（prev 缺失）时强制 full：增量必须有基线，否则首个备份会被
    创建为 base_version=None 的孤儿增量，导致备份满后清理/恢复失败（缺陷修复）。
    """
    if not prev_manifest or not prev_meta:
        return KIND_FULL
    if mode == "full":
        return KIND_FULL
    if mode == "incr":
        return KIND_INCR
    # auto：基于变更文件大小比例 + 文件数比例综合判断（变更小→增量；变更大→完整重置链）
    prev_files = prev_manifest.get("files", {})
    changed_size = 0
    total_prev_size = max(1, meta_size_of_files(prev_files))
    total_now_size = max(1, meta_size_of_files(full_files))
    for rel, h in full_files.items():
        if prev_files.get(rel) != h:
            p = _path_for(rel, existing)
            try:
                sz = p.stat().st_size if p and p.exists() else len(h) // 2
            except OSError:
                sz = len(h) // 2
            changed_size += sz
    changed_in_cur = sum(1 for rel, h in full_files.items() if prev_files.get(rel) != h)
    deleted = sum(1 for rel in prev_files if rel not in full_files)
    changed_files_total = changed_in_cur + deleted
    total_files = max(1, len(prev_files))
    ratio_by_files = changed_files_total / total_files
    ratio_by_size = changed_size / max(1, max(total_prev_size, total_now_size))
    # 任一比例 > 50% 则升级为 full
    return KIND_INCR if max(ratio_by_files, ratio_by_size) <= 0.5 else KIND_FULL


def _path_for(rel: str, existing: list):
    """根据完整清单键（如 "顶层/子/文件"）找到实际路径。"""
    top = rel.split("/", 1)[0]
    sub = rel[len(top) + 1:] if "/" in rel else ""
    for pobj in existing:
        if safe_name(pobj.name) == top:
            return pobj / sub if sub else pobj
    return None


def meta_size_of_files(files: dict) -> int:
    """估算哈希清单表示的文件总大小（用每个哈希长度估算）。"""
    return sum(len(v) // 2 for v in files.values())


def find_backup_root_conflicts(game: dict = None) -> list:
    """检测备份根目录与存档路径的重叠（防循环递归），返回冲突描述列表。

    每个条目: {game: 游戏名, save: 存档路径, backup: 备份根目录}
    game=None 时检查所有游戏；否则只检查指定游戏。
    """
    backup_root = Path(store.settings.get("backup_root", ""))
    games = [game] if game else store.games
    conflicts = []
    for g in games:
        for sp in g.get("save_paths", []):
            p = expand_env_path(sp)
            if not p:
                continue
            if is_subpath(backup_root, p) or is_subpath(p, backup_root):
                conflicts.append({
                    "game": g.get("name", ""),
                    "save": str(p),
                    "backup": str(backup_root),
                })
    return conflicts


def create_backup(game: dict, note: str = "", mode: str = None, force: bool = False) -> dict:
    """对单个游戏执行一次备份。mode: 'full' / 'incr' / 'auto'，None 时按 settings.backup_mode。

    force=True 时即使存档无变更也强制备份（用于手动备份确认"是"后）。
    """
    with _backup_lock:
        game_id = game["id"]
        save_paths = [p for p in game.get("save_paths", []) if p]
        if not save_paths:
            raise BackupError("该游戏没有配置存档路径")
        if mode is None:
            mode = store.settings.get("backup_mode", "full")

        # 防循环递归保护：备份根目录不能位于存档源目录内（反之亦然）。
        # 否则"备份写入 → 触发文件监听 → 再次备份"会无限循环。
        conflicts = find_backup_root_conflicts(game)
        if conflicts:
            c = conflicts[0]
            raise BackupError(
                "⚠️ 备份目录与存档源目录存在重叠，已停止备份，防止循环递归。\n"
                f"存档: {c['save']}\n备份: {c['backup']}\n"
                "请到「设置」中更换备份位置（不要放在存档所在目录内），"
                "或将备份目录改到存档目录之外。"
            )

        full_files, dirs_info, existing = _compute_current_state(game)
        if not full_files:
            raise BackupError("存档目录不存在，无法备份")

        # 无变更检测：非强制时，若与最近备份一致则跳过。
        # 复用已计算的 full_files，避免对同一存档重复全量 SHA256（Q1 修复）
        if not force:
            chk = check_changes(game, full_files=full_files,
                                dirs_info=dirs_info, existing=existing)
            if not chk["changed"]:
                log.info("存档无变更，跳过备份 [%s] %s", game_id, game.get("name"))
                raise BackupUnchanged(chk["reason"])

        ts = ts_now()
        base_ts = ts
        seq = 1
        while version_dir(game_id, ts).exists():
            seq += 1
            ts = f"{base_ts}_{seq}"

        # 决定 kind：需要找"最新版本"作为增量基准
        versions = list_versions(game_id)
        prev_meta = None
        prev_manifest = None
        if versions:
            latest = versions[0]  # 已倒序
            prev_meta = _read_json(version_dir(game_id, latest["timestamp"]) / META_NAME, {})
            prev_manifest = _read_json(version_dir(game_id, latest["timestamp"]) / MANIFEST_NAME, {})
            # 关键：base_version 必须以"目录名"为准（恢复前快照等目录名含后缀，
            # 而 meta.timestamp 可能不含后缀，会导致增量链指向不存在的目录）
            if prev_meta:
                prev_meta["base_dir"] = latest["timestamp"]

        kind = _decide_backup_kind(game, mode, prev_meta, prev_manifest, full_files, existing)

        try:
            if kind == KIND_FULL:
                _create_full_backup(game, ts, full_files, dirs_info, existing, note)
            else:
                _create_incr_backup(game, ts, prev_manifest or {"files": {}},
                                    prev_meta or {}, full_files, dirs_info, existing, note)
        except Exception as e:
            force_rmtree(version_dir(game_id, ts))
            log.error("备份失败 [%s]: %s\n%s", game_id, e, traceback.format_exc())
            raise BackupError(f"备份失败: {e}") from e
        _invalidate_versions(game_id)  # 新备份后缓存失效

        try:
            cleanup_versions(game_id, keep=store.settings.get("keep_versions", 5))
        except Exception as e:
            log.warning("清理旧版本失败: %s", e)

        log.info("备份完成 [%s] %s kind=%s -> %s", game_id, game.get("name"), kind, ts)
        return load_version(game_id, ts)


# ---------------- 元信息读取 ----------------

def load_version(game_id: str, ts: str) -> dict:
    """读取某个版本的 meta + manifest 信息。"""
    vdir = version_dir(game_id, ts)
    meta_path = vdir / META_NAME
    if not meta_path.exists():
        return None
    meta = _read_json(meta_path, {})
    manifest = _read_json(vdir / MANIFEST_NAME, {"files": {}})
    file_count = len(manifest.get("files", {}))
    return {
        "timestamp": ts,
        "display": ts_display(ts),
        "note": meta.get("note", ""),
        "size": meta.get("size", 0),
        "zip_size": meta.get("zip_size"),
        "status": meta.get("status", "ok"),
        "verified": meta.get("verified", False),
        "favorite": meta.get("favorite", False),
        "compress": meta.get("compress", "none"),
        "kind": meta.get("kind", KIND_FULL),
        "base_version": meta.get("base_version"),
        "change_count": meta.get("change_count", 0),
        "delete_count": meta.get("delete_count", 0),
        "file_count": file_count,
        "source_paths": meta.get("source_paths", []),
    }


# 版本列表缓存：TTL 秒，写操作后失效（避免列表页每次请求都全量扫盘）
_versions_cache = {}
_VERSIONS_TTL = 5


def _invalidate_versions(game_id: str = None):
    """使版本缓存失效。game_id=None 时清空全部。"""
    if game_id:
        _versions_cache.pop(game_id, None)
    else:
        _versions_cache.clear()


def list_versions(game_id: str) -> list:
    """列出某游戏的全部备份版本，按时间倒序。带 5 秒 TTL 缓存。"""
    now = time.time()
    hit = _versions_cache.get(game_id)
    if hit and hit[0] > now:
        return hit[1]
    bdir = game_backup_dir(game_id)
    if not bdir.exists():
        _versions_cache[game_id] = (now + _VERSIONS_TTL, [])
        return []
    versions = []
    for child in bdir.iterdir():
        if child.is_dir() and (child / META_NAME).exists():
            v = load_version(game_id, child.name)
            if v:
                versions.append(v)
    versions.sort(key=lambda x: x["timestamp"], reverse=True)
    _versions_cache[game_id] = (now + _VERSIONS_TTL, versions)
    return versions


def _has_descendant_using(game_id: str, ts: str) -> bool:
    """是否存在某版本以 ts 为直接 base_version。"""
    bdir = game_backup_dir(game_id)
    if not bdir.exists():
        return False
    for child in bdir.iterdir():
        if not child.is_dir() or child.name == ts:
            continue
        m = _read_json(child / META_NAME, None)
        if m and m.get("base_version") == ts:
            return True
    return False


def _first_descendant(game_id: str, ts: str):
    """找到以 ts 为 base_version 的最早一个版本（时间正序中最早的）。"""
    bdir = game_backup_dir(game_id)
    if not bdir.exists():
        return None
    candidates = []
    for child in bdir.iterdir():
        if not child.is_dir() or child.name == ts:
            continue
        m = _read_json(child / META_NAME, None)
        if m and m.get("base_version") == ts:
            candidates.append(child.name)
    candidates.sort()
    return candidates[0] if candidates else None


def promote_to_full(game_id: str, ts: str):
    """将指定版本从 incr 提升为 full（重建其完整内容存为 full）。

    用于清理链断裂时，保持增量链完整。
    临时重建目录放在版本目录外部（game 目录下），避免残留干扰版本删除。
    """
    vdir = version_dir(game_id, ts)
    meta = _read_json(vdir / META_NAME, None)
    if not meta:
        raise BackupError(f"版本 {ts} 不存在")
    if meta.get("kind") == KIND_FULL:
        return
    # 重建到临时目录（版本目录外，删除版本时不受影响）
    tmp = game_backup_dir(game_id) / f".promote_{ts}"
    force_rmtree(tmp)
    reconstruct(game_id, ts, tmp)
    # 删除原 changes/ 和 deleted.json（容错：删除失败不中断）
    force_rmtree(vdir / CHANGES_DIR_NAME)
    try:
        deleted_path = vdir / DELETED_NAME
        if deleted_path.exists():
            os.unlink(str(deleted_path))
    except OSError as e:
        log.warning("promote 删除 deleted.json 失败(忽略): %s", e)
    # 将临时目录内容移到 data/
    new_data = vdir / DATA_DIR_NAME
    force_rmtree(new_data)
    (vdir / DATA_DIR_NAME).mkdir(parents=True, exist_ok=True)
    for item in tmp.iterdir():
        shutil.move(str(item), str(vdir / DATA_DIR_NAME / item.name))
    force_rmtree(tmp)

    # 更新 meta + manifest
    meta["kind"] = KIND_FULL
    meta["base_version"] = None
    meta["size"] = dir_size(vdir / DATA_DIR_NAME)
    meta["change_count"] = 0
    meta["delete_count"] = 0
    meta["compress"] = "none"
    meta.pop("zip_size", None)
    _write_json(vdir / META_NAME, meta)

    manifest = _read_json(vdir / MANIFEST_NAME, {})
    manifest["kind"] = KIND_FULL
    manifest["base_version"] = None
    manifest["changes"] = {}
    manifest["deleted"] = []
    _write_json(vdir / MANIFEST_NAME, manifest)


def set_favorite(game_id: str, ts: str, fav: bool) -> dict:
    vdir = version_dir(game_id, ts)
    meta_path = vdir / META_NAME
    if not meta_path.exists():
        raise BackupError("版本不存在")
    meta = _read_json(meta_path, {})
    meta["favorite"] = bool(fav)
    _write_json(meta_path, meta)
    _invalidate_versions(game_id)  # 收藏状态写入 meta，版本缓存需失效
    return load_version(game_id, ts)


def delete_version(game_id: str, ts: str, force: bool = False) -> bool:
    """删除某个版本。收藏版本默认不允许删除（force 可绕过）。

    若被后续版本引用（增量链基线），会先提升首个后代为 full 以保持链完整。
    """
    v = load_version(game_id, ts)
    if v and v.get("favorite") and not force:
        raise BackupError("该版本已收藏，禁止删除。请先取消收藏。")
    vdir = version_dir(game_id, ts)
    if not vdir.exists():
        return False
    if _has_descendant_using(game_id, ts):
        d = _first_descendant(game_id, ts)
        if d:
            promote_to_full(game_id, d)
    force_rmtree(vdir)
    if vdir.exists():
        raise BackupError(f"删除版本 {ts} 失败：目录仍存在")
    _invalidate_versions(game_id)
    log.info("删除版本 [%s] %s", game_id, ts)
    return True


def cleanup_versions(game_id: str, keep: int = None) -> dict:
    """清理过期版本：保留最近 keep 个非收藏 + 全部收藏。

    删除时按从旧到新顺序，逐个处理链完整性：被后代引用时先提升后代为 full。
    """
    if keep is None:
        keep = store.settings.get("keep_versions", 5)
    versions = list_versions(game_id)
    favorites = [v for v in versions if v.get("favorite")]
    kept = [v for v in versions if not v.get("favorite")]
    to_delete = kept[keep:] if keep is not None else []
    deleted = []
    # 从最旧开始删，确保链处理顺序正确
    for v in sorted(to_delete, key=lambda x: x["timestamp"]):
        try:
            if delete_version(game_id, v["timestamp"], force=True):
                deleted.append(v["timestamp"])
        except Exception as e:
            log.warning("清理版本失败 %s: %s", v["timestamp"], e)
    if deleted:
        log.info("清理过期版本 [%s]: 删除 %d 个", game_id, len(deleted))
    return {"deleted": deleted, "kept": len(kept) - len(deleted), "favorites": len(favorites)}


# ---------------- 重建（核心算法） ----------------

def _materialize_full(game_id: str, ts: str, dest: Path):
    """将 full 版本的内容展开到 dest 目录（含解压）。"""
    vdir = version_dir(game_id, ts)
    meta = _read_json(vdir / META_NAME, {})
    fmt = meta.get("compress", "none")
    if fmt == "zip":
        with zipfile.ZipFile(vdir / "snapshot.zip") as zf:
            zf.extractall(dest)
    elif fmt == "tar.gz":
        with tarfile.open(vdir / "snapshot.tar.gz") as tf:
            tf.extractall(dest)
    else:
        src = vdir / DATA_DIR_NAME
        if src.exists():
            _copy_tree(src, dest)


def _materialize_changes(src_dir: Path, dest: Path):
    """把 changes/ 目录内容覆盖复制到 dest。"""
    if not src_dir.exists():
        return
    _merge_copy(src_dir, dest)


def _apply_deletions(deleted: list, dest: Path):
    """删除 dest 中对应的文件（尽力而为）。"""
    for rel in deleted:
        target = dest / rel
        if target.is_dir():
            force_rmtree(target)
        elif target.exists():
            try:
                os.unlink(target)
            except OSError:
                pass


def reconstruct(game_id: str, ts: str, dest: Path) -> Path:
    """重建指定版本到 dest 目录（沿 base_version 链回溯到 full，再依次应用 incr）。

    兼容历史缺陷产生的"孤儿增量根"：首个备份即 incr 且 base_version=None，
    此时其 changes/ 为全量（创建时 prev 清单为空），可安全作为链根。
    返回 dest 路径。用于恢复和校验。
    """
    dest = Path(dest)
    if dest.exists():
        force_rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # 收集链：从 ts 沿 base_version 回溯到最老的 base，再正向应用
    chain = []
    cur_ts = ts
    seen = set()
    while True:
        if cur_ts in seen:
            raise BackupError(f"增量链成环: {cur_ts}")
        seen.add(cur_ts)
        chain.append(cur_ts)
        vdir = version_dir(game_id, cur_ts)
        meta = _read_json(vdir / META_NAME, None)
        if not meta:
            raise BackupError(f"版本 {cur_ts} 元数据缺失")
        if meta.get("kind") == KIND_FULL:
            break
        base = meta.get("base_version")
        if not base or not version_dir(game_id, base).exists():
            # 孤儿增量根：incr 但无基线目录（历史缺陷：首个备份即 incr）。
            # 若其 changes 为全量（changes 键 == files 键），可安全作为链根。
            mf = _read_json(vdir / MANIFEST_NAME, {})
            if set(mf.get("changes", {}).keys()) == set(mf.get("files", {}).keys()):
                log.warning("孤儿增量根 %s 作为链根处理（changes 为全量）", cur_ts)
                break
            raise BackupError(f"增量基线 {base} 缺失，无法重建")
        cur_ts = base

    # chain 顺序：[ts, ..., 根]；根是 full 或"全量孤儿增量"
    root_ts = chain[-1]
    root_vdir = version_dir(game_id, root_ts)
    root_meta = _read_json(root_vdir / META_NAME, {})
    if root_meta.get("kind") == KIND_FULL:
        _materialize_full(game_id, root_ts, dest)
    else:
        # 孤儿增量根：changes/ 为全量内容，直接作为根展开
        _merge_copy(root_vdir / CHANGES_DIR_NAME, dest)
        _apply_deletions(_read_json(root_vdir / DELETED_NAME, []), dest)
    # 反向回溯到 ts（中间每个 incr 应用 changes + deleted）
    for incr_ts in reversed(chain[:-1]):
        vdir = version_dir(game_id, incr_ts)
        _materialize_changes(vdir / CHANGES_DIR_NAME, dest)
        deleted = _read_json(vdir / DELETED_NAME, [])
        _apply_deletions(deleted, dest)
    return dest


# ---------------- 恢复 ----------------

def restore_backup(game: dict, ts: str, safety_backup: bool = True) -> dict:
    """恢复指定版本。防呆：游戏运行中拒绝；恢复前自动快照；失败自动回滚。"""
    with _backup_lock:
        game_id = game["id"]
        vdir = version_dir(game_id, ts)
        if not vdir.exists():
            raise BackupError("版本不存在")
        v = load_version(game_id, ts)
        if not v:
            raise BackupError("版本元数据缺失")

        if is_game_running(game.get("processes", [])):
            raise BackupError("检测到游戏正在运行，请先关闭游戏再执行恢复。")

        rollback_dir = None
        safety_ts = None
        if safety_backup:
            try:
                safety_ts = ts_now()
                rollback_dir = version_dir(game_id, safety_ts + "_pre_restore")
                rb_data = rollback_dir / DATA_DIR_NAME
                rb_data.mkdir(parents=True, exist_ok=True)
                existing = [expand_env_path(p) for p in
                            v.get("source_paths", game.get("save_paths", []))
                            if expand_env_path(p).exists()]
                manifest = {"files": {}, "dirs": {}}
                for pobj in existing:
                    key = safe_name(pobj.name)
                    if pobj.is_dir():
                        _copy_tree(pobj, rb_data / key)
                        for rel in _collect_files(rb_data / key):
                            manifest["files"][f"{key}/{rel}"] = sha256_file(rb_data / key / rel)
                    else:
                        shutil.copy2(pobj, rb_data / key)
                        manifest["files"][key] = sha256_file(rb_data / key)
                _write_json(rollback_dir / MANIFEST_NAME, manifest)
                rollback_meta = {
                    "kind": KIND_FULL, "base_version": None,
                    "game_id": game_id, "game_name": game.get("name", ""),
                    "timestamp": safety_ts, "created": datetime.now().isoformat(timespec="seconds"),
                    "note": "恢复前自动快照", "status": "ok", "verified": False,
                    "favorite": False, "compress": "none",
                    "source_paths": [str(p) for p in existing],
                    "size": dir_size(rb_data),
                }
                _write_json(rollback_dir / META_NAME, rollback_meta)
            except Exception as e:
                force_rmtree(rollback_dir)
                log.error("创建恢复前快照失败，中止恢复: %s", e)
                raise BackupError(f"创建恢复前快照失败，已中止恢复: {e}") from e

        try:
            tmp = version_dir(game_id, ".restore_tmp")
            force_rmtree(tmp)
            tmp.mkdir(parents=True, exist_ok=True)
            reconstruct(game_id, ts, tmp)

            target_paths = v.get("source_paths", game.get("save_paths", []))
            replaced = []
            for target in target_paths:
                t = expand_env_path(target)
                src_name = safe_name(Path(target).name)
                src = tmp / src_name
                if not src.exists():
                    continue
                t.parent.mkdir(parents=True, exist_ok=True)
                _merge_copy(src, t)
                removed = []
                _prune_extra(src, t, removed)
                replaced.append(str(t))
            force_rmtree(tmp)
            _invalidate_versions(game_id)  # 恢复会创建快照/回滚，缓存失效
            log.info("恢复完成 [%s] %s -> %s", game_id, ts, " | ".join(replaced))
            return {"ok": True, "timestamp": ts, "safety_snapshot": safety_ts, "replaced": replaced}
        except Exception as e:
            if rollback_dir and rollback_dir.exists():
                try:
                    rb_data = rollback_dir / DATA_DIR_NAME
                    rb_meta = _read_json(rollback_dir / META_NAME, {})
                    for p in rb_meta.get("source_paths", []):
                        t = expand_env_path(p)
                        key = safe_name(t.name)
                        src = rb_data / key
                        if src.exists():
                            _merge_copy(src, t)
                            removed = []
                            _prune_extra(src, t, removed)
                    log.warning("恢复失败，已回滚 [%s] %s: %s", game_id, ts, e)
                    raise BackupError(f"恢复失败，已自动回滚。原因: {e}") from e
                except Exception as rollback_e:
                    log.error("回滚失败: %s", rollback_e)
                    raise BackupError(f"恢复失败且回滚失败，请手动检查。原因: {e}") from e
            raise BackupError(f"恢复失败: {e}") from e


# ---------------- 校验 ----------------

def verify_version(game_id: str, ts: str) -> dict:
    """沿增量链重建到临时目录，逐文件计算 SHA256 与 manifest.files 对比。"""
    vdir = version_dir(game_id, ts)
    meta_path = vdir / META_NAME
    if not meta_path.exists():
        raise BackupError("版本不存在")
    meta = _read_json(meta_path, {})
    manifest = _read_json(vdir / MANIFEST_NAME, {"files": {}})

    tmp = vdir / ".verify_tmp"
    if tmp.exists():
        force_rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        reconstruct(game_id, ts, tmp)
        mismatched = []
        checked = 0
        for rel, expected in manifest.get("files", {}).items():
            full = tmp / rel
            if not full.exists():
                mismatched.append({"file": rel, "reason": "缺失"})
                continue
            checked += 1
            actual = sha256_file(full)
            if actual != expected:
                mismatched.append({"file": rel, "reason": "哈希不一致"})
        ok = not mismatched
        meta["verified"] = ok
        meta["status"] = "ok" if ok else "异常"
        _write_json(meta_path, meta)
        _invalidate_versions(game_id)  # verified/status 写入 meta，缓存需失效
        return {
            "timestamp": ts, "ok": ok, "checked": checked,
            "mismatched": mismatched, "status": meta["status"],
        }
    finally:
        force_rmtree(tmp)