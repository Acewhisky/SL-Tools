"""自动化任务：定时备份 + 目录变化监听自动备份。

- 定时任务：按小时/天/周粒度，后台线程循环检查。
- 变化监听：watchdog 监听指定游戏存档目录，变化后防抖延迟自动备份。
"""
import json
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from .config import store
from .utils import log, expand_env_path, is_subpath

_scheduler_thread = None
_watchers = {}
_scheduler_stop = threading.Event()
_sync_lock = threading.Lock()  # 防止 sync_watchers 并发调用导致 watcher 重复建立


# ---------------- 任务执行 ----------------

def _run_backup(game_id: str, note: str = ""):
    """在后台线程执行一次备份，捕获异常写日志。"""
    try:
        from .backup import create_backup, BackupUnchanged
        game = store.get_game(game_id)
        if not game:
            log.warning("自动任务: 游戏不存在 %s", game_id)
            return
        v = create_backup(game, note=note)
        # 注意：成功/跳过日志由 backup.create_backup 内部打印（更具体，含游戏名与 kind）
    except BackupUnchanged:
        # 存档无变更，跳过自动备份（具体日志由 backup.check_changes 打印）
        pass
    except Exception as e:
        log.error("自动备份失败 [%s]: %s", game_id, e)


# ---------------- 定时任务 ----------------

def _scheduler_loop():
    log.info("定时任务调度器启动（间隔 %ss）", SCHEDULER_INTERVAL)
    while not _scheduler_stop.is_set():
        try:
            now = datetime.now()
            tasks = store.settings.get("auto_tasks", [])
            for task in tasks:
                if not task.get("enabled", True):
                    continue
                if task.get("kind") != "interval":
                    continue
                last = task.get("last_run_ts")
                interval = task.get("interval_seconds", 3600)
                game_id = task.get("game_id")
                if not game_id:
                    continue
                if last is None or (time.time() - last) >= interval:
                    task["last_run_ts"] = time.time()
                    _run_backup(game_id, note=f"定时任务: {task.get('name','')}")
            # 周期性重试：存档目录可能在游戏运行后才出现，需要重新尝试建立 watcher
            # （Bug 2 修复：sync_watchers 内部对路径不存在的游戏会跳过，每轮重试确保路径出现后立即接管）
            try:
                sync_watchers()
            except Exception as e:
                log.warning("watcher 同步异常（忽略）: %s", e)
        except Exception as e:
            log.error("调度器异常: %s", e)
        _scheduler_stop.wait(SCHEDULER_INTERVAL)


# 调度循环间隔（秒）：同时也用于 watcher 重试周期
SCHEDULER_INTERVAL = 10


def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler")
    _scheduler_thread.start()


def stop_scheduler():
    _scheduler_stop.set()


# ---------------- 变化监听 ----------------

def _make_watcher(game_id: str, path: str):
    """为一个游戏创建一个 watchdog 监听器。"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class Handler(FileSystemEventHandler):
            def __init__(self):
                self._debounce_timer = None
                self._lock = threading.Lock()

            def _schedule(self):
                with self._lock:
                    if self._debounce_timer:
                        self._debounce_timer.cancel()
                    delay = float(store.settings.get("watch_delay", 8))
                    self._debounce_timer = threading.Timer(delay, self._do_backup)
                    self._debounce_timer.daemon = True
                    self._debounce_timer.start()

            def _do_backup(self):
                log.info("检测到存档内容变化，自动备份 [%s] %s", game_id, path)
                _run_backup(game_id, note="存档变化自动备份")

            # 真实内容变更事件（opened/closed 不代表内容变化，Windows 下杀毒/索引/编辑器
            # 会周期性打开关闭文件，必须忽略，否则误触发无意义的"自动备份跳过"）
            _CONTENT_EVENTS = {"created", "modified", "deleted", "moved"}

            def on_any_event(self, event):
                if event.event_type not in self._CONTENT_EVENTS:
                    return
                self._schedule()

        observer = _make_observer(path)
        observer.schedule(Handler(), path, recursive=True)
        observer.start()
        return observer
    except Exception as e:
        log.warning("创建监听器失败 [%s] %s: %s", game_id, path, e)
        return None


def _make_observer(path: str):
    """按设置选择监听实现。

    - watch_interval=0（默认）：事件驱动 Observer——操作系统内核通知，
      无轮询、近乎零 CPU 占用，推荐。
    - watch_interval>0：PollingObserver——每 N 秒扫描目录树，
      用于个别文件系统不支持事件通知的场景，可自行权衡性能。
    """
    from watchdog.observers import Observer
    from watchdog.observers.polling import PollingObserver
    interval = float(store.settings.get("watch_interval", 0) or 0)
    if interval > 0:
        log.info("监听方式: 轮询（间隔 %ss） [%s]", interval, path)
        return PollingObserver(timeout=interval)
    return Observer()


def sync_watchers():
    """根据设置与游戏配置同步监听器。

    规则：仅对 auto_backup=True 的游戏建立监听（游戏详情页开关独立控制，
    默认关闭；无全局开关）。
    Bug 2 修复：首次建立 watcher 时主动备份一次（保险：覆盖"路径刚出现时
    修改事件未被捕获"的边缘场景，例如游戏首次运行生成存档）。
    并发安全：加锁防止 main() 启动与调度器线程同时调用导致重复建立 watcher
    （重复监听会使每个文件事件被多个 Handler 处理，日志与备份翻倍）。
    """
    global _watchers
    with _sync_lock:
        wanted = {}
        conflicts = {}
        from .backup import find_backup_root_conflicts
        for c in find_backup_root_conflicts():
            conflicts[c["game"]] = c["save"]
        for game in store.games:
            if not game.get("auto_backup"):
                continue
            for p in game.get("save_paths", []):
                if p and expand_env_path(p).exists():
                    pp = str(expand_env_path(p))
                    # 防循环递归：存档路径与备份根目录重叠时不监听（备份已被拦截，监听只会空转）
                    if game["id"] in conflicts or game.get("name") in conflicts:
                        log.warning("存档路径与备份目录重叠，跳过监听 [%s] %s（请在设置中更换备份位置）",
                                    game["id"], pp)
                        continue
                    wanted[game["id"]] = pp
                    break

        # 停止不再需要的
        for k in list(_watchers.keys()):
            if k not in wanted:
                try:
                    _watchers[k].stop()
                except Exception:
                    pass
                del _watchers[k]

        # 启动新的 + 路径刚出现时主动备份一次
        for gid, path in wanted.items():
            if gid in _watchers:
                continue
            obs = _make_watcher(gid, path)
            if obs:
                _watchers[gid] = obs
                # 保险：首次建立 watcher 时备份一次（不 force，无变更则跳过）
                log.info("监听器建立，主动备份一次 [%s] %s", gid, path)
                _run_backup(gid, note="监听器建立时的初始备份")


def stop_watchers():
    for k, obs in list(_watchers.items()):
        try:
            obs.stop()
        except Exception:
            pass
    _watchers.clear()
