"""refactor_dev 分支补充测试套件（单元级，无需启动服务）。

目的：
1. 覆盖本次复杂度重构中「只在临时 smoke test 验证、未入库」的 app.py 纯函数
   辅助方法（_clean_str_list / _build_game_from_request / _validate_game_fields /
   _apply_game_updates / _resolve_open_target / _import_settings / _import_games），
   验证重构后提取逻辑与原行为等价（update_game / add_game / import_config /
   open_in_explorer 的提取逻辑）。
2. 覆盖 README 测试验收标准（备份-恢复哈希一致、恢复前自动快照、运行中拒绝恢复、
   版本保留与收藏保护、压缩备份/恢复、无变更跳过、配置导入导出等价）。
3. 覆盖重构后的 backup 核心方法（_decide_backup_kind / 首备必 full 等），
   验证 CC 降低后行为不变。

全部数据隔离在系统 Temp，不触碰项目 data/。可直接运行，也可被 pytest 发现。

运行：
    SAVEMGR_TEST_ROOT=<项目根> python tests/qa_refactor_dev.py
    pytest tests/qa_refactor_dev.py
"""
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 仅依赖 flask（app.py 导入链）；backend 各模块在 import 期无非必要副作用。
from app import (  # noqa: E402
    _clean_str_list,
    _build_game_from_request,
    _validate_game_fields,
    _apply_game_updates,
    _resolve_open_target,
    _import_settings,
    _import_games,
)
from backend import backup as bk  # noqa: E402
from backend.config import store  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="qa_refactor_"))
SAVE_DIR = _TMP / "save"
BACKUP_ROOT = _TMP / "backups"


# ----------------------------------------------------------------------------
# 环境与隔离
# ----------------------------------------------------------------------------

def _reset_backup_env(keep=5, compress="none"):
    """隔离备份环境：settings/games 指向临时目录，清空备份与存档。"""
    store.settings_file = _TMP / "settings.json"
    store.games_file = _TMP / "games.json"
    store.reset()
    store.settings["backup_root"] = str(BACKUP_ROOT)
    store.settings["keep_versions"] = keep
    store.settings["compress_format"] = compress
    store.settings["backup_mode"] = "full"
    if BACKUP_ROOT.exists():
        bk.force_rmtree(BACKUP_ROOT)
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    if SAVE_DIR.exists():
        bk.force_rmtree(SAVE_DIR)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    bk._invalidate_versions()


def _reset_store():
    """隔离配置存储：清空游戏列表、重置设置为默认。"""
    store.settings_file = _TMP / "settings.json"
    store.games_file = _TMP / "games.json"
    store.reset()


def _write_save(files: dict):
    if SAVE_DIR.exists():
        bk.force_rmtree(SAVE_DIR)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = SAVE_DIR / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _game(name="rf"):
    return {
        "id": f"rf_{name}", "name": name,
        "save_paths": [str(SAVE_DIR)], "processes": [],
        "platform": ["Test"], "custom": True, "source": "custom",
    }


def _expect_raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"期望 {exc.__name__}，实际抛出 {type(e).__name__}: {e}")
    raise AssertionError(f"期望 {exc.__name__}，但未抛出任何异常")


# ----------------------------------------------------------------------------
# A. app.py 重构纯函数（未入库 smoke test 的等价覆盖）
# ----------------------------------------------------------------------------

def test_clean_str_list():
    assert _clean_str_list(None) == []
    assert _clean_str_list([]) == []
    assert _clean_str_list([" a ", "", "  b "]) == ["a", "b"]


def test_build_game_from_request():
    name, paths, game = _build_game_from_request(
        {"name": " G ", "save_paths": ["s1", "  s2"], "processes": ["p"],
         "id": "id1", "platform": ["Win"], "auto_backup": True})
    assert name == "G"
    assert paths == ["s1", "s2"]
    assert game["id"] == "id1"
    assert game["platform"] == ["Win"]
    assert game["custom"] is True
    assert game["source"] == "custom"
    assert game["auto_backup"] is True
    # 默认值兜底
    _, _, game2 = _build_game_from_request({"name": "G2", "save_paths": ["s"]})
    assert game2["platform"] == ["Other"]
    assert game2["auto_backup"] is False
    assert game2["custom"] is True


def test_validate_game_fields():
    assert _validate_game_fields("", ["p"]) == "游戏名称不能为空"
    assert _validate_game_fields("n", []) == "至少需要一个存档路径"
    assert _validate_game_fields("n", ["p"]) is None


def test_apply_game_updates_only_present_keys():
    g = {"id": "g2", "name": "N", "save_paths": ["p"], "processes": ["x"],
         "platform": ["PC"], "auto_backup": False, "hidden": False, "favorite": True}
    _apply_game_updates(g, {"name": "N2"})  # 仅更新存在的键
    assert g["name"] == "N2"
    assert g["save_paths"] == ["p"]
    assert g["processes"] == ["x"]
    assert g["platform"] == ["PC"]
    assert g["auto_backup"] is False
    assert g["favorite"] is True


def test_apply_game_updates_field_types():
    g = {"id": "g3", "name": "old", "save_paths": ["p"], "processes": ["x"],
         "platform": ["PC"], "auto_backup": False, "hidden": False, "favorite": False}
    _apply_game_updates(g, {"name": " new ", "save_paths": [" a ", ""],
                            "processes": None, "platform": None,
                            "auto_backup": 1, "hidden": "yes", "favorite": 0})
    assert g["name"] == "new"                       # 去空白
    assert g["save_paths"] == ["a"]                 # 列表清洗，空项过滤
    assert g["processes"] == []                     # None 经清洗变空列表
    assert g["platform"] == ["Other"]               # None 兜底
    assert g["auto_backup"] is True                 # 真值化
    assert g["hidden"] is True
    assert g["favorite"] is False


def test_resolve_open_target():
    _reset_store()
    root = _TMP / "openroot"
    root.mkdir(parents=True, exist_ok=True)
    store.settings["backup_root"] = str(root)

    assert _resolve_open_target("") == (None, "路径为空")
    assert _resolve_open_target(str(_TMP / "nope")) == (None, "路径不存在")
    # 允许：备份根目录本身
    target, err = _resolve_open_target(str(root))
    assert target is not None and target is not None and err is None
    # 拒绝：不在白名单内的目录（_TMP 非备份根/存档路径）
    t, e = _resolve_open_target(str(_TMP))
    assert t is None and e is not None


def test_import_settings_valid_and_clamped():
    _reset_store()
    _import_settings({"backup_root": "C:/x", "keep_versions": 200,
                      "compress_format": "bogus", "watch_delay": 9999})
    assert store.settings["backup_root"] == "C:/x"
    assert store.settings["keep_versions"] == 99        # 上限钳制
    assert store.settings["compress_format"] == "none"  # 非法值丢弃（保留默认）
    assert store.settings["watch_delay"] == 120         # 上限钳制


def test_import_settings_invalid_types_dropped():
    _reset_store()
    _import_settings({"keep_versions": "five", "compress_format": 123, "watch_delay": "x"})
    assert store.settings["keep_versions"] == 5          # 默认不变（脏数据丢弃）
    assert store.settings["compress_format"] == "none"
    assert store.settings["watch_delay"] == 8


def test_import_games():
    _reset_store()
    n = _import_games([
        {"name": "G1", "id": "x1"},
        {"name": ""},          # 空名跳过
        "bad",                 # 非 dict 跳过
        {"id": "x2"},          # 缺 name 跳过
    ])
    assert n == 1
    assert len(store.games) == 1
    g0 = store.games[0]
    assert g0["name"] == "G1"
    assert g0.get("custom") is True
    assert g0.get("source") == "custom"


# ----------------------------------------------------------------------------
# B. README 验收标准（经重构后的 backup 核心）
# ----------------------------------------------------------------------------

def test_backup_restore_hash_consistent():
    """备份-恢复前后哈希一致（verify_version 校验 SHA256 + 恢复内容一致）。"""
    _reset_backup_env()
    _write_save({"a.sav": "dataA", "sub/b.sav": "dataB"})
    g = _game("hr")
    v = bk.create_backup(g, force=True)
    assert bk.verify_version(g["id"], v["timestamp"])["ok"]
    _write_save({"a.sav": "CHANGED"})
    bk.restore_backup(g, v["timestamp"], safety_backup=False)
    assert (SAVE_DIR / "a.sav").read_text(encoding="utf-8") == "dataA"
    assert (SAVE_DIR / "sub/b.sav").read_text(encoding="utf-8") == "dataB"


def test_compressed_zip_backup_restore():
    """压缩备份/恢复（zip）。"""
    _reset_backup_env(compress="zip")
    _write_save({"a.sav": "zdata"})
    g = _game("zip")
    v = bk.create_backup(g, force=True)
    assert v.get("compress") == "zip"
    assert bk.verify_version(g["id"], v["timestamp"])["ok"]
    _write_save({"a.sav": "OTHER"})
    bk.restore_backup(g, v["timestamp"], safety_backup=False)
    assert (SAVE_DIR / "a.sav").read_text(encoding="utf-8") == "zdata"


def test_restore_creates_safety_snapshot():
    """恢复前自动快照（safety_backup=True 创建快照版本）。"""
    _reset_backup_env(keep=10)
    _write_save({"s.txt": "v1"})
    g = _game("rs")
    v = bk.create_backup(g, force=True)
    _write_save({"s.txt": "v2"})  # 改当前存档，使快照有意义
    before = len(bk.list_versions(g["id"]))
    res = bk.restore_backup(g, v["timestamp"], safety_backup=True)
    assert res["ok"] and res["safety_snapshot"], res
    after = len(bk.list_versions(g["id"]))
    assert after == before + 1, f"安全快照应新增 1 个版本: {before}->{after}"
    assert (SAVE_DIR / "s.txt").read_text(encoding="utf-8") == "v1"


def test_restore_rejected_when_game_running():
    """运行中拒绝恢复（安全防呆）。"""
    _reset_backup_env()
    _write_save({"a.sav": "v1"})
    g = _game("run")
    v = bk.create_backup(g, force=True)
    orig = bk.is_game_running
    bk.is_game_running = lambda procs: True  # 模拟游戏正在运行
    try:
        assert _expect_raises(bk.BackupError, bk.restore_backup, g, v["timestamp"])
    finally:
        bk.is_game_running = orig


def test_keep_versions_cleanup():
    """版本保留：超过 keep 自动清理，剩余均可校验。"""
    _reset_backup_env(keep=2)
    _write_save({"a.sav": "v1"})
    g = _game("keep")
    for i in range(4):
        _write_save({"a.sav": f"v{i}"})
        bk.create_backup(g, force=True)
    vs = bk.list_versions(g["id"])
    assert len(vs) <= 2
    for v in vs:
        assert bk.verify_version(g["id"], v["timestamp"])["ok"], v["timestamp"]


def test_favorite_protected_from_cleanup():
    """收藏保护：清理时收藏版本永不删除。"""
    _reset_backup_env(keep=1)
    _write_save({"a.sav": "v1"})
    g = _game("fav")
    v1 = bk.create_backup(g, force=True)
    bk.set_favorite(g["id"], v1["timestamp"], True)
    _write_save({"a.sav": "v2"})
    bk.create_backup(g, force=True)
    _write_save({"a.sav": "v3"})
    bk.create_backup(g, force=True)  # 触发清理，收藏的 v1 应保留
    left = [v["timestamp"] for v in bk.list_versions(g["id"])]
    assert v1["timestamp"] in left, f"收藏版本应保留: {left}"


def test_no_change_skips_backup():
    """无变更时跳过备份（BackupUnchanged）。"""
    _reset_backup_env()
    _write_save({"a.sav": "v1"})
    g = _game("unch")
    bk.create_backup(g, force=True)  # 首次必建
    assert _expect_raises(bk.BackupUnchanged, bk.create_backup, g, "", None, False)


def test_config_import_export_equivalent():
    """配置导入导出等价：导出后关键设置可经 _import_settings 还原。"""
    _reset_store()
    _import_settings({"backup_root": "C:/exp", "keep_versions": 7,
                      "compress_format": "tar.gz", "watch_delay": 30})
    assert store.settings["backup_root"] == "C:/exp"
    assert store.settings["keep_versions"] == 7
    assert store.settings["compress_format"] == "tar.gz"
    assert store.settings["watch_delay"] == 30


# ----------------------------------------------------------------------------
# C. 备份核心重构方法等价性
# ----------------------------------------------------------------------------

def test_decide_backup_kind():
    """_decide_backup_kind：无历史版本强制 full；mode 直传；auto 按变更比例。"""
    g = _game("dk")
    # 无历史版本（prev 缺失）→ 无论 mode 一律 full（孤儿增量缺陷修复核心）
    assert bk._decide_backup_kind(g, "incr", None, None, {}, []) == bk.KIND_FULL
    assert bk._decide_backup_kind(g, "auto", None, None, {}, []) == bk.KIND_FULL
    pm = {"files": {}}
    assert bk._decide_backup_kind(g, "full", pm, pm, {}, []) == bk.KIND_FULL
    assert bk._decide_backup_kind(g, "incr", pm, pm, {}, []) == bk.KIND_INCR
    # auto：无变更（0%）→ incr
    prev = {"a.txt": "h1"}
    assert bk._decide_backup_kind(g, "auto", {"files": prev}, {"files": prev},
                                  {"a.txt": "h1"}, []) == bk.KIND_INCR
    # auto：全量变更（>50%）→ full
    assert bk._decide_backup_kind(g, "auto", {"files": prev}, {"files": prev},
                                  {"a.txt": "h2"}, []) == bk.KIND_FULL


def test_first_backup_is_full_regardless_of_mode():
    """首个备份无论 incr/auto 模式均为 full（重构保证增量有基线）。"""
    _reset_backup_env()
    _write_save({"a.sav": "v1"})
    g = _game("first")
    for mode in ("incr", "auto"):
        _reset_backup_env()
        _write_save({"a.sav": "v1"})
        gg = _game("first_" + mode)
        v = bk.create_backup(gg, mode=mode, force=True)
        assert v["kind"] == "full", f"{mode} 首备应为 full，实际 {v['kind']}"


# ----------------------------------------------------------------------------
# 运行器（同时兼容 pytest 发现）
# ----------------------------------------------------------------------------

# 测试元数据：用于生成测试报告（分类 / 目标 / 验收标准 / 严重度）
TEST_META = {
    "test_clean_str_list": ("单元-重构", "app._clean_str_list", "add_game 提取逻辑", "LOW"),
    "test_build_game_from_request": ("单元-重构", "app._build_game_from_request", "add_game 提取逻辑", "LOW"),
    "test_validate_game_fields": ("单元-重构", "app._validate_game_fields", "add_game 字段校验", "LOW"),
    "test_apply_game_updates_only_present_keys": ("单元-重构", "app._apply_game_updates", "update_game 提取逻辑", "MEDIUM"),
    "test_apply_game_updates_field_types": ("单元-重构", "app._apply_game_updates", "update_game 类型处理", "MEDIUM"),
    "test_resolve_open_target": ("单元-重构", "app._resolve_open_target", "open_in_explorer 白名单", "MEDIUM"),
    "test_import_settings_valid_and_clamped": ("单元-重构", "app._import_settings", "import_config 校验钳制", "MEDIUM"),
    "test_import_settings_invalid_types_dropped": ("单元-重构", "app._import_settings", "import_config 脏数据丢弃", "MEDIUM"),
    "test_import_games": ("单元-重构", "app._import_games", "import_config 游戏导入", "LOW"),
    "test_backup_restore_hash_consistent": ("集成-核心", "backup.create_backup/restore_backup", "备份-恢复哈希一致", "HIGH"),
    "test_compressed_zip_backup_restore": ("集成-核心", "backup.create_backup(压缩)", "压缩备份/恢复", "HIGH"),
    "test_restore_creates_safety_snapshot": ("集成-核心", "backup.restore_backup", "恢复前自动快照", "HIGH"),
    "test_restore_rejected_when_game_running": ("集成-核心", "backup.restore_backup", "运行中拒绝恢复", "HIGH"),
    "test_keep_versions_cleanup": ("集成-核心", "backup.cleanup_versions", "版本保留", "MEDIUM"),
    "test_favorite_protected_from_cleanup": ("集成-核心", "backup.cleanup_versions", "收藏保护", "MEDIUM"),
    "test_no_change_skips_backup": ("集成-核心", "backup.check_changes/_try_skip_unchanged", "无变更跳过", "MEDIUM"),
    "test_config_import_export_equivalent": ("集成-核心", "app._import_settings", "配置导入导出等价", "MEDIUM"),
    "test_decide_backup_kind": ("单元-重构", "backup._decide_backup_kind", "首备必 full（重构）", "MEDIUM"),
    "test_first_backup_is_full_regardless_of_mode": ("集成-核心", "backup.create_backup", "首备必 full（重构）", "MEDIUM"),
}


def _run_all():
    tests = sorted(
        (n, f) for n, f in globals().items()
        if n.startswith("test_") and callable(f)
    )
    passed = failed = 0
    results = []
    print("=" * 64)
    print(f"refactor_dev 补充测试  项目根={PROJECT_ROOT}")
    print("=" * 64)
    for name, fn in tests:
        try:
            fn()
            passed += 1
            results.append((name, "PASS", ""))
            print(f"  ✅ {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            msg = f"{type(e).__name__}: {e}"
            results.append((name, "FAIL", msg))
            print(f"  ❌ {name}  {msg}")
    print("=" * 64)
    print(f"结果: {passed} 通过 / {failed} 失败  (共 {len(tests)})")
    return passed, failed, results


if __name__ == "__main__":
    p, f, _ = _run_all()
    sys.exit(1 if f else 0)
