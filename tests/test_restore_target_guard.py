"""restore 写入目标基线校验回归测试。

背景缺陷：
    restore 的写入目标取自版本元数据 `source_paths`（缺失则回退 `game["save_paths"]`），
    而这两者都可由上层 API 改写、且上层不做任何路径位置校验；链路终点
    `_apply_reconstruct_to_targets()` 会 `mkdir` + 覆盖写入，最后由 `_prune_extra()`
    递归删除目标目录中**所有不在备份里**的内容。也就是说，一旦目标被指到
    「混有大量无关内容的目录」，后果不是读取越权，而是批量删除。
    详见 docs/SECURITY_AUDIT_20260930.md 的 H2。

防护：
    `backup.validate_restore_target()` 做独立于配置的基线校验；
    `backup._reject_unsafe_targets()` 在 restore 创建安全快照之前 fail fast，
    避免为不合法的目标白做一轮快照与版本重建。

设计约定（修改前请先理解，别当成 bug 修掉）：
    * **刻意不做白名单**。用户自己的游戏目录合法且无法穷举（可能装在任何盘符、
      任何深度），白名单只会砸掉正常用法。这里只声明「绝不允许落到这些位置」，
      它们的共同点是：目录下混有大量与本存档无关的内容。
    * **Documents 本身放行**。不少游戏的存档路径就是 Documents（见
      `utils.expand_env_path` 的 %DOCUMENTS% 映射），禁止它会破坏真实用法。
    * **AppData 根禁止，其下 Local / LocalLow / Roaming 子目录放行** —— 后者正是
      主流引擎存放存档的标准位置。
    * **backup_root 内部禁止**：写进去会连带删掉既有版本（自噬）。

本测试不触碰用户真实配置，全部使用动态构造的路径。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import backup as bk  # noqa: E402
from backend.config import store  # noqa: E402
from backend.utils import expand_env_path  # noqa: E402

HOME = Path.home().resolve()
DRIVE_ROOT = Path(HOME.anchor)


@pytest.fixture
def backup_root(monkeypatch, tmp_path):
    """把备份根隔离到临时目录，避免测试依赖真实 backup_root。"""
    monkeypatch.setitem(store.settings, "backup_root", str(tmp_path))
    return tmp_path


def check(target) -> str:
    return bk.validate_restore_target(expand_env_path(target) if isinstance(target, str)
                                      else target)


# ---------------- 必须拒绝：会导致批量删除的位置 ----------------

@pytest.mark.parametrize("target", [
    DRIVE_ROOT,                                  # C:\
    DRIVE_ROOT / "Windows",
    DRIVE_ROOT / "Windows" / "System32",
    DRIVE_ROOT / "Program Files",
    DRIVE_ROOT / "Program Files (x86)" / "Steam",
    DRIVE_ROOT / "ProgramData",
    DRIVE_ROOT / "$Recycle.Bin",
    DRIVE_ROOT / "System Volume Information",
    DRIVE_ROOT / "PerfLogs",
    HOME,                                        # 用户目录根（桌面/文档/下载都在下面）
    HOME / "AppData",                            # AppData 根
    "relative/saves",                            # 相对路径
    "saves\\game",
])
def test_rejects_catastrophic_targets(target, backup_root):
    assert check(target), f"应拒绝却放行了: {target}"


def test_rejects_backup_root_itself(backup_root):
    """写进备份库会连带删掉既有版本（自噬），必须拦住。"""
    assert check(backup_root)
    assert check(backup_root / "some-game")


@pytest.mark.parametrize("case_sensitive", ["Windows", "WINDOWS", "windows"])
def test_system_dir_match_is_case_insensitive(case_sensitive, backup_root):
    assert check(DRIVE_ROOT / case_sensitive)


# ---------------- 必须放行：正常游戏存档位置一个都不能砸 ----------------

@pytest.mark.parametrize("target", [
    HOME / "Saved Games" / "SomeGame",
    HOME / "Saved Games" / "Deep" / "Nested" / "Dir",
    HOME / "AppData" / "LocalLow" / "Studio" / "Game",
    HOME / "AppData" / "Roaming" / "SomeGame",
    HOME / "AppData" / "Local" / "SomeGame",
    HOME / "Documents" / "My Games" / "SomeGame",
    HOME / "Documents",                          # 存档就在 Documents 的游戏要能跑
    Path("D:\\Games\\SomeGame\\saves"),          # 其他盘符
    Path("D:\\SteamLibrary\\steamapps\\common\\Game\\saves"),
])
def test_allows_legitimate_save_paths(target, backup_root):
    assert check(target) == "", f"正常存档路径被误伤: {target}"


def test_allows_path_expanding_from_env_placeholder(backup_root):
    """%DOCUMENTS% 等占位符展开后必须仍在允许范围内。"""
    assert check("%DOCUMENTS%") == ""
    assert check("%SAVED_GAMES%\\SomeGame") == ""


def test_backup_root_outside_paths_are_unaffected(backup_root):
    """隔离的 tmp backup_root 不应意外覆盖上述合法路径的判定。"""
    assert check(HOME / "Saved Games" / "X") == ""


# ---------------- fail fast ----------------

def test_reject_unsafe_targets_raises_before_any_write(backup_root):
    with pytest.raises(bk.BackupError) as exc:
        bk._reject_unsafe_targets([str(DRIVE_ROOT / "Windows")])
    assert "恢复目标不安全" in str(exc.value)


def test_reject_unsafe_targets_reports_every_bad_entry(backup_root):
    bad = [str(DRIVE_ROOT / "Windows"), str(DRIVE_ROOT / "ProgramData")]
    with pytest.raises(bk.BackupError) as exc:
        bk._reject_unsafe_targets(bad)
    message = str(exc.value)
    for item in bad:
        assert item in message


def test_reject_unsafe_targets_empty_list(backup_root):
    with pytest.raises(bk.BackupError) as exc:
        bk._reject_unsafe_targets([])
    assert "缺少存档来源路径" in str(exc.value)


def test_apply_reconstruct_to_targets_validates_first(backup_root, tmp_path):
    """纵深防御：即使绕过 restore_backup 直接调用，也会先校验。"""
    with pytest.raises(bk.BackupError):
        bk._apply_reconstruct_to_targets(tmp_path / "nonexistent",
                                         [str(DRIVE_ROOT / "Windows")])


# ---------------- 复用：/api/open 的白名单加固（报告 M1） ----------------

def test_open_blocked_even_when_allowlist_is_poisoned(monkeypatch):
    """`/api/open` 的白名单由 save_paths 推导而成，是「自证式」的。

    即使白名单被污染到包含系统目录，叠在上层的本校验也必须把它拦下来。
    """
    import app as appmod

    poisoned = DRIVE_ROOT / "Windows"
    monkeypatch.setattr(appmod, "_allowed_open_paths", lambda: {poisoned})
    resolved, err = appmod._resolve_open_target(str(poisoned))
    assert resolved is None, "被污染的白名单竟放行了系统目录"
    assert err


def test_open_allows_backup_root_but_restore_still_rejects_it(monkeypatch, backup_root):
    """两套语义的分水岭——这条是 CI 曾经红的回归用例，勿删。

    备份库内部对 **restore** 必须禁：写进去 `_prune_extra` 会删掉既有版本（自噬）。
    但对 **`/api/open`** 必须放行：打开不写不删，而且它就是 UI 上「打开备份目录」
    用的路径，白名单里本来就有。若两者共用一套校验，这里就会误伤成功能故障。
    """
    import app as appmod

    monkeypatch.setattr(appmod, "_allowed_open_paths", lambda: {backup_root})
    resolved, err = appmod._resolve_open_target(str(backup_root))
    assert resolved is not None, "打开备份目录被误拒（UI 的「打开备份目录」会失效）"
    assert err is None
    # 同一条路径，restore 仍然要拦住
    assert check(backup_root)


@pytest.mark.parametrize("target", [
    HOME,                       # 用户目录根：打开无风险
    HOME / "AppData",           # AppData 根
])
def test_open_allows_targets_that_only_restore_must_reject(target, monkeypatch):
    """同上：这几条禁令的理由是 prune 删文件，只约束写入，不约束打开。"""
    import app as appmod

    monkeypatch.setattr(appmod, "_allowed_open_paths", lambda: {target})
    if not target.exists():
        pytest.skip(f"{target} 在本机不存在")
    resolved, err = appmod._resolve_open_target(str(target))
    assert resolved is not None and err is None
    assert check(target), "restore 侧必须仍然拒绝"


@pytest.mark.parametrize("target", [
    DRIVE_ROOT,
    DRIVE_ROOT / "Windows",
    DRIVE_ROOT / "Program Files",
])
def test_open_target_keeps_dangerous_locations_blocked(target):
    """防放松用的对照：最小基线降低了限制，但磁盘根与系统目录仍必须拦下。

    这两条即便「只是打开」也有意义——系统目录里的 `.exe` 双击会直接执行。
    """
    assert bk.validate_open_target(target), f"打开目标漏放了危险位置: {target}"


def test_open_allows_normal_directory(monkeypatch, tmp_path):
    """配套用例：正常目录不该被这层校验误伤，避免防护过头砸掉功能。"""
    import app as appmod

    monkeypatch.setattr(appmod, "_allowed_open_paths", lambda: {tmp_path})
    resolved, err = appmod._resolve_open_target(str(tmp_path))
    assert resolved is not None
    assert err is None


def test_open_blocked_outside_allowlist(monkeypatch, tmp_path):
    """白名单之外的路径照旧被拒（原有行为未被本次加固破坏）。"""
    import app as appmod

    other = HOME / "Saved Games"
    monkeypatch.setattr(appmod, "_allowed_open_paths", lambda: {tmp_path})
    resolved, err = appmod._resolve_open_target(str(other))
    assert resolved is None
    assert err
