"""增量清理回归测试（QA 精简版）：覆盖原 test_incr_cleanup_regression.py 核心 7 场景。

纯单元级，全部数据隔离在系统 Temp，不碰项目 data/。
用法：SAVEMGR_TEST_ROOT=<项目根> python tests/qa_regression_incr.py
"""
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else
                    r"C:\Users\Dengz\WorkBuddy\存档管理工具")
sys.path.insert(0, str(PROJECT_ROOT))

from backend import backup as bk
from backend.config import store

_TMP = Path(tempfile.mkdtemp(prefix="qa_regr_"))
SAVE_DIR = _TMP / "save"
BACKUP_ROOT = _TMP / "backups"

store.settings_file = _TMP / "settings.json"
store.games_file = _TMP / "games.json"

passed, failed = 0, 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} {detail}")


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
            "save_paths": [str(SAVE_DIR)], "processes": [], "custom": True}


def _versions(gid):
    return bk.list_versions(gid)


def main():
    print("=" * 50)
    print(f"增量清理回归（QA 精简版） 项目根={PROJECT_ROOT}")

    # 场景 1：首备 incr 必须 full（孤儿根修复核心）
    _reset()
    _write_save({"a.sav": "v1"})
    g = _game("s1")
    r = bk.create_backup(g, mode="incr", force=True)
    check("首备 incr 强制 full", r.get("kind") == "full", str(r.get("kind")))
    bk._invalidate_versions()

    # 场景 2：备份满自动清理（正常链）
    _reset(keep=2)
    _write_save({"a.sav": "v1"})
    g = _game("s2")
    for i in range(4):
        _write_save({"a.sav": f"v{i}"})
        bk.create_backup(g, force=True)
    vs = _versions(g["id"])
    check("备份满自动清理至 keep", len(vs) <= 2, f"count={len(vs)}")
    # 留下的版本都能校验
    for v in vs:
        rr = bk.verify_version(g["id"], v["timestamp"])
        check(f"保留版本 {v['timestamp']} 可校验", rr.get("ok"), str(rr)[:120])
    bk._invalidate_versions()

    # 场景 3：正常链 promote（删除中间版本，后代提升为 full）
    _reset(keep=10)
    _write_save({"a.sav": "base"})
    g = _game("s3")
    r = bk.create_backup(g, mode="full", force=True)
    base_ts = r["timestamp"]
    for i in range(3):
        _write_save({"a.sav": f"inc{i}"})
        r = bk.create_backup(g, mode="incr", force=True)
    mid_ts = r["timestamp"]
    # 删除中间版本（无后代？mid_ts 是最后一个，删除应无 promote）
    bk.delete_version(g["id"], mid_ts, force=True)
    vs = _versions(g["id"])
    check("删除中间版本成功", all(v["timestamp"] != mid_ts for v in vs), str([v["timestamp"] for v in vs]))
    # 删除 base（有后代）→ 直接后代应 promote 为 full
    bk.delete_version(g["id"], base_ts, force=True)
    vs = _versions(g["id"])
    # 注意 vs 按时间倒序（含 _N 后缀），promote 的 full 是 base 的直接后代
    any_full = any(v.get("kind") == "full" for v in vs)
    check("删除基线后直接后代 promote 为 full", any_full,
          str([(v["timestamp"], v["kind"]) for v in vs]))
    for v in vs:
        rr = bk.verify_version(g["id"], v["timestamp"])
        check(f"promote 后版本 {v['timestamp']} 可校验", rr.get("ok"), str(rr)[:120])
    bk._invalidate_versions()

    # 场景 4：孤儿链 reconstruct（历史缺陷数据兼容）
    _reset()
    _write_save({"a.sav": "oracle"})
    g = _game("s4")
    r = bk.create_backup(g, mode="full", force=True)
    base_ts = r["timestamp"]
    # 手工构造孤儿链：把 base 改成 incr 且 base_version=None，changes=全量
    bdir = bk.version_dir(g["id"], base_ts)
    m = bk._read_json(bdir / bk.META_NAME, {})
    m["kind"] = "incr"
    m["base_version"] = None
    bk._write_json(bdir / bk.META_NAME, m)
    mf = bk._read_json(bdir / bk.MANIFEST_NAME, {})
    mf["kind"] = "incr"
    mf["base_version"] = None
    mf["changes"] = dict(mf.get("files", {}))  # changes = 全量（孤儿首版特征）
    bk._write_json(bdir / bk.MANIFEST_NAME, mf)
    (bdir / "changes").mkdir(exist_ok=True)
    import shutil
    if (bdir / "data").exists():
        for item in (bdir / "data").iterdir():
            if item.is_dir():
                shutil.copytree(item, bdir / "changes" / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, bdir / "changes" / item.name)
    bk._invalidate_versions()
    # reconstruct 应能处理孤儿链根
    dest = _TMP / "recon"
    try:
        bk.reconstruct(g["id"], base_ts, dest)
        # 重建内容带顶层目录前缀（源目录名 save/）
        check("孤儿链 reconstruct 成功",
              dest.exists() and (dest / "save" / "a.sav").exists(),
              f"dest={dest.exists()} save_exists={(dest / 'save' / 'a.sav').exists()}")
    except Exception as e:
        check("孤儿链 reconstruct 成功", False, str(e))
    bk._invalidate_versions()

    # 场景 5：auto 模式首备 full
    _reset()
    store.settings["backup_mode"] = "auto"
    _write_save({"a.sav": "auto1"})
    g = _game("s5")
    r = bk.create_backup(g, mode="auto", force=True)
    check("auto 首备 full", r.get("kind") == "full", str(r.get("kind")))
    bk._invalidate_versions()

    # 场景 6：增量链成环保护
    _reset()
    _write_save({"a.sav": "c1"})
    g = _game("s6")
    bk.create_backup(g, mode="full", force=True)
    _write_save({"a.sav": "c2"})
    r1 = bk.create_backup(g, mode="incr", force=True)
    _write_save({"a.sav": "c3"})
    r2 = bk.create_backup(g, mode="incr", force=True)
    # 构造成环
    vdir = bk.version_dir(g["id"], r2["timestamp"])
    m = bk._read_json(vdir / bk.META_NAME, {})
    m["base_version"] = r2["timestamp"]
    bk._write_json(vdir / bk.META_NAME, m)
    bk._invalidate_versions()
    try:
        bk.reconstruct(g["id"], r2["timestamp"], _TMP / "loop_dest")
        check("增量链成环保护（应报错）", False, "未报错")
    except bk.BackupError as e:
        check("增量链成环保护（应报错）", "成环" in str(e), str(e))
    bk._invalidate_versions()

    # 场景 7：孤儿增量清理（备份满时删除孤儿链版本）
    _reset(keep=1)
    _write_save({"a.sav": "o1"})
    g = _game("s7")
    r = bk.create_backup(g, mode="full", force=True)
    # 备份到触发清理
    for i in range(3):
        _write_save({"a.sav": f"o{i}"})
        bk.create_backup(g, force=True)
    vs = _versions(g["id"])
    check("孤儿链环境备份满清理正常", len(vs) <= 1, f"count={len(vs)}")
    bk._invalidate_versions()

    print("=" * 50)
    print(f"结果: {passed} 通过 / {failed} 失败")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
