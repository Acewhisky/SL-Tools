"""缺陷回归测试：增量模式下备份满后无法删除（孤儿增量根）。

缺陷（dev v2.1.0，main 同样存在）：
- backup_mode=incr（或手动 mode="incr"）且游戏无历史版本时，
  首个备份被 _create_incr_backup 创建为 base_version=None 的"孤儿增量"
  （增量链无 full 根）。
- 备份数满触发 cleanup_versions 删除最老版本时，需先 promote 其后代为 full，
  reconstruct() 沿链回溯到孤儿根（kind=incr 且 base=None）→ 抛
  "增量基线 None 缺失，无法重建"，版本永远删不掉（与用户日志吻合）。

修复：
1. _decide_backup_kind()：无历史版本（prev 缺失）时，无论 mode 一律返回 full，
   增量必须有基线，首个备份不允许为 incr。
2. reconstruct()：回溯遇到 base 缺失（None 或目录不存在）的 incr 时，
   若其 manifest.changes 为全量（孤儿首版特征：changes 键集合 == files 键集合），
   视为链根继续重建，兼容历史缺陷已产生的数据。

测试为纯单元级，全部数据隔离在系统临时目录，不触碰项目 data/。
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\Dengz\WorkBuddy\存档管理工具")

from backend import backup as bk
from backend.config import store

_TMP = Path(tempfile.mkdtemp(prefix="savemgr_regr_"))
SAVE_DIR = _TMP / "save"
BACKUP_ROOT = _TMP / "backups"

# 隔离：settings/games/备份根全部指向临时目录
store.settings_file = _TMP / "settings.json"
store.games_file = _TMP / "games.json"


def _reset(keep=5):
    bk._invalidate_versions()
    store.settings["backup_root"] = str(BACKUP_ROOT)
    store.settings["keep_versions"] = keep
    store.settings["compress_format"] = "none"
    store.settings["backup_mode"] = "incr"  # 缺陷触发条件
    if BACKUP_ROOT.exists():
        bk.force_rmtree(BACKUP_ROOT)
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)


def _write_save(files: dict):
    if SAVE_DIR.exists():
        bk.force_rmtree(SAVE_DIR)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = SAVE_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _game(name="回归测试"):
    return {"id": f"regr_{name}", "name": name,
            "save_paths": [str(SAVE_DIR)], "processes": [], "platform": ["Test"]}


def _orphan_incr(game, ts):
    """构造孤儿增量版本（模拟磁盘上历史缺陷留下的数据，绕过创建 API 的基线防御）：
    base_version=None，changes/ 为全量内容。"""
    import shutil
    full_files, dirs_info, existing = bk._compute_current_state(game)
    vdir = bk.version_dir(game["id"], ts)
    changes_dir = vdir / bk.CHANGES_DIR_NAME
    changes_dir.mkdir(parents=True, exist_ok=True)
    for rel in full_files:
        top = rel.split("/", 1)[0]
        src = None
        for pobj in existing:
            if bk.safe_name(pobj.name) == top:
                src = pobj / (rel[len(top) + 1:] if "/" in rel else "")
                break
        if src and src.exists():
            target = changes_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    meta = {"kind": "incr", "base_version": None, "game_id": game["id"],
            "game_name": game.get("name", ""), "timestamp": ts,
            "note": "孤儿增量(历史缺陷)", "size": bk.dir_size(changes_dir),
            "change_count": len(full_files), "delete_count": 0, "favorite": False,
            "compress": "none"}
    manifest = {"kind": "incr", "base_version": None, "files": full_files,
                "changes": dict(full_files), "deleted": [], "dirs": dirs_info}
    bk.write_json(vdir / bk.MANIFEST_NAME, manifest)
    bk.write_json(vdir / bk.META_NAME, meta)
    bk.write_json(vdir / bk.DELETED_NAME, [])
    return full_files


def _read(out, rel):
    return (out / rel).read_text(encoding="utf-8")


# ---------- 缺陷 1：无历史版本时 mode=incr 首个备份必须为 full ----------

def test_first_backup_with_incr_mode_is_full():
    _reset()
    _write_save({"save1.sav": "v1", "settings.cfg": "cfg1"})
    game = _game("首备")
    v = bk.create_backup(game, mode="incr", force=True)
    assert v["kind"] == "full", f"首个备份应为 full，实际 {v['kind']}"
    assert v["base_version"] is None
    out = bk.reconstruct(game["id"], v["timestamp"], _TMP / "r1")
    assert _read(out, "save/save1.sav") == "v1"


# ---------- 缺陷 2：历史孤儿数据链可正常清理 ----------

def test_cleanup_orphan_chain():
    _reset(keep=5)                                   # 建链阶段不触发内部清理
    _write_save({"save1.sav": "v1"})
    game = _game("孤儿链")
    ts1 = bk.ts_now()
    _orphan_incr(game, ts1)                              # 模拟旧缺陷产生的孤儿根
    _write_save({"save1.sav": "v2"})
    v2 = bk.create_backup(game, mode="incr", force=True)  # 正常增量，base=孤儿
    ts2 = v2["timestamp"]
    assert v2["kind"] == "incr" and v2["base_version"] == ts1

    result = bk.cleanup_versions(game["id"], keep=1)     # 应删除孤儿根 ts1
    assert ts1 in result["deleted"], f"孤儿根应被删除，实际 {result}"
    left = bk.list_versions(game["id"])
    assert [v["timestamp"] for v in left] == [ts2]
    assert left[0]["kind"] == "full", "剩余版本应被提升为 full"
    out = bk.reconstruct(game["id"], ts2, _TMP / "r2")
    assert _read(out, "save/save1.sav") == "v2"


# ---------- 缺陷 3：备份数满时自动清理正常触发（用户场景） ----------

def test_auto_cleanup_when_full():
    _reset(keep=2)
    _write_save({"save1.sav": "v1"})
    game = _game("自动满")
    bk.create_backup(game, mode="incr", force=True)      # 修复后为首个 full
    _write_save({"save1.sav": "v2"})
    bk.create_backup(game, mode="incr", force=True)
    _write_save({"save1.sav": "v3"})
    v3 = bk.create_backup(game, mode="incr", force=True)  # 超过 keep=2，触发清理
    versions = bk.list_versions(game["id"])
    assert len(versions) == 2, [v["timestamp"] for v in versions]
    assert versions[0]["timestamp"] == v3["timestamp"]
    for v in versions:                                    # 剩余版本链完整可重建
        out = bk.reconstruct(game["id"], v["timestamp"], _TMP / ("ra" + v["timestamp"]))
        assert out.exists()


# ---------- 回归：正常 full→incr→incr 链清理（promote 后代） ----------

def test_cleanup_normal_chain_promote():
    _reset(keep=5)                                   # 建链阶段不触发内部清理
    _write_save({"save1.sav": "v1"})
    game = _game("正常链")
    f = bk.create_backup(game, mode="full", force=True)
    _write_save({"save1.sav": "v2"})
    i1 = bk.create_backup(game, mode="incr", force=True)
    _write_save({"save1.sav": "v3"})
    i2 = bk.create_backup(game, mode="incr", force=True)
    result = bk.cleanup_versions(game["id"], keep=1)
    assert f["timestamp"] in result["deleted"], result
    assert i1["timestamp"] in result["deleted"], result
    left = bk.list_versions(game["id"])
    assert [v["timestamp"] for v in left] == [i2["timestamp"]]
    assert left[0]["kind"] == "full"
    out = bk.reconstruct(game["id"], i2["timestamp"], _TMP / "r3")
    assert _read(out, "save/save1.sav") == "v3"


# ---------- 回归：手动删除中间版本，链保持完整 ----------

def test_manual_delete_middle_version():
    _reset(keep=5)
    _write_save({"save1.sav": "v1"})
    game = _game("手动删")
    f = bk.create_backup(game, mode="full", force=True)
    _write_save({"save1.sav": "v2"})
    i1 = bk.create_backup(game, mode="incr", force=True)
    _write_save({"save1.sav": "v3"})
    i2 = bk.create_backup(game, mode="incr", force=True)
    assert bk.delete_version(game["id"], f["timestamp"])
    left = {v["timestamp"]: v for v in bk.list_versions(game["id"])}
    assert left[i1["timestamp"]]["kind"] == "full", "后代应被提升为 full"
    assert left[i2["timestamp"]]["kind"] == "incr"
    assert left[i2["timestamp"]]["base_version"] == i1["timestamp"]
    out = bk.reconstruct(game["id"], i2["timestamp"], _TMP / "r4")
    assert _read(out, "save/save1.sav") == "v3"


# ---------- 回归：孤儿链版本可重建（verify/restore 前置） ----------

def test_reconstruct_orphan_chain():
    _reset(keep=5)
    _write_save({"save1.sav": "v1"})
    game = _game("孤儿恢复")
    ts1 = bk.ts_now()
    _orphan_incr(game, ts1)
    _write_save({"save1.sav": "v2"})
    v2 = bk.create_backup(game, mode="incr", force=True)
    out = bk.reconstruct(game["id"], v2["timestamp"], _TMP / "r5")
    assert _read(out, "save/save1.sav") == "v2"


# ---------- 回归：auto 模式无历史版本时首个备份为 full ----------

def test_auto_mode_first_backup_is_full():
    _reset()
    _write_save({"save1.sav": "v1"})
    game = _game("auto首备")
    v = bk.create_backup(game, mode="auto", force=True)
    assert v["kind"] == "full", f"auto 模式首个备份应为 full，实际 {v['kind']}"
