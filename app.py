"""游戏存档管理工具 - Flask 后端入口。

启动方式：
    python app.py            # 默认端口 8765，自动打开浏览器

提供 REST API 与静态前端页面。
"""
import json
import logging
import os
import shutil
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from backend.config import store
from backend import backup as bk
from backend import detector
from backend import automation
from backend import steam_search
from backend import service
from backend.utils import log, expand_env_path

if getattr(sys, "frozen", False):
    # PyInstaller 打包：静态资源从解压目录读取，数据目录固定在 exe 同级
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "static"
    DATA_DIR = Path(sys.executable).resolve().parent / "data"
else:
    ROOT = Path(__file__).resolve().parent
    STATIC_DIR = ROOT / "static"
    DATA_DIR = ROOT / "data"
LOG_FILE = DATA_DIR / "log.txt"

# static_folder=None：禁用内置 static 路由，统一走自定义 static_files（可控缓存头）
app = Flask(__name__, static_folder=None)

# 允许上传大小（配置导入等，放宽）
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


# ---------------- 日志 ----------------

class LineCountRotatingHandler(logging.FileHandler):
    """按行数滚动的日志 Handler：超过 max_lines 条时，保留最近 max_lines 条。"""

    def __init__(self, filename: str, max_lines: int = 1000, encoding: str = "utf-8"):
        super().__init__(filename, encoding=encoding)
        self.max_lines = max_lines
        self._line_count = self._count_existing()

    def _count_existing(self) -> int:
        try:
            with open(self.baseFilename, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    def emit(self, record):
        super().emit(record)
        self._line_count += 1
        if self._line_count > self.max_lines:
            self._trim()

    def _trim(self):
        """保留文件末尾 max_lines 条日志。"""
        try:
            with open(self.baseFilename, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if len(lines) > self.max_lines:
                keep = lines[-self.max_lines:]
                with open(self.baseFilename, "w", encoding="utf-8") as f:
                    f.writelines(keep)
                self._line_count = len(keep)
        except OSError:
            pass


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # 追加写入文件，仅保留最近 1000 条（避免日志无限膨胀）
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fh = LineCountRotatingHandler(str(LOG_FILE), max_lines=1000)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger("savemgr").addHandler(fh)
    except Exception as e:
        print("日志文件初始化失败:", e)


_setup_logging()


# ---------------- 工具 ----------------

def _api_ok(data=None):
    return jsonify({"ok": True, "data": data})


def _api_err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def _game_dict(g) -> dict:
    """游戏配置转前端展示结构（委托 service 层）。"""
    return service.game_dict(g)


# ---------------- 页面 ----------------

_INDEX_CACHE = None  # 渲染后的 index.html 缓存（含版本号注入）


@app.route("/")
def index():
    """首页。动态注入版本号到资源 URL，强制浏览器加载最新 JS/CSS，
    避免缓存旧版前端导致功能异常（如实时刷新不生效）。"""
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        from backend.version import VERSION
        try:
            html = (Path(STATIC_DIR) / "index.html").read_text(encoding="utf-8")
            html = html.replace("/css/style.css", f"/css/style.css?v={VERSION}")
            html = html.replace("/js/app.js", f"/js/app.js?v={VERSION}")
            _INDEX_CACHE = html
        except OSError:
            _INDEX_CACHE = "index.html 加载失败"
    return _INDEX_CACHE


@app.route("/<path:path>")
def static_files(path):
    resp = send_from_directory(STATIC_DIR, path)
    # 前端资源禁用缓存：版本号已注入 URL，确保更新后必然加载新资源
    if path.endswith((".js", ".css", ".html")):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


# ---------------- 设置 ----------------

@app.route("/api/settings", methods=["GET"])
def get_settings():
    s = dict(store.settings)
    s["backup_root_exists"] = Path(s["backup_root"]).exists()
    s["backup_root_size"] = _dir_size_human(s["backup_root"])
    return _api_ok(s)


def _dir_size_human(path):
    import psutil
    try:
        p = Path(path)
        if not p.exists():
            return "0 B"
        total = 0
        for root, _d, files in os.walk(p):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    continue
        from backend.utils import fmt_size
        return fmt_size(total)
    except Exception:
        return "未知"


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json(force=True, silent=True) or {}
    allowed = {"backup_root", "keep_versions", "compress_format", "auto_open_browser",
               "watch_delay", "log_level", "auto_tasks", "backup_mode",
               "scan_online", "watch_interval", "rules_source"}
    for k, v in data.items():
        if k in allowed:
            store.settings[k] = v
    # 规则库源合法性约束
    if store.settings.get("rules_source") not in ("auto", "jsdelivr", "github"):
        store.settings["rules_source"] = "auto"
    # 类型约束
    try:
        store.settings["keep_versions"] = max(1, int(store.settings.get("keep_versions", 5)))
    except Exception:
        store.settings["keep_versions"] = 5
    try:
        store.settings["watch_interval"] = max(0, float(store.settings.get("watch_interval", 0)))
    except Exception:
        store.settings["watch_interval"] = 0
    store.save_settings()
    # 监听配置变化
    automation.sync_watchers()
    # 防循环递归：备份根目录与任一存档路径重叠时返回 warning（设置仍保存，备份时会拦截）
    warning = service.check_backup_root_conflict()
    result = dict(store.settings)
    if warning:
        result["warning"] = warning
    return _api_ok(result)


# ---------------- 游戏 ----------------

@app.route("/api/games", methods=["GET"])
def list_games():
    return _api_ok(service.list_games_sorted())


@app.route("/api/games/counts", methods=["GET"])
def games_counts():
    """轻量接口：返回 {id: {"count": n, "latest": ts}}，供前端轮询。

    latest = 最新版本时间戳：当版本数达到上限（新增删旧数量不变）时，
    前端仍能通过 latest 变化感知到时间线更新，触发刷新。
    """
    counts = {}
    for g in store.games:
        if g.get("hidden"):
            continue
        versions = bk.list_versions(g["id"])
        counts[g["id"]] = {
            "count": len(versions),
            "latest": versions[0]["timestamp"] if versions else "",
        }
    return _api_ok(counts)


@app.route("/api/games/hidden", methods=["GET"])
def list_hidden_games():
    """列出被隐藏的游戏（设置页用于管理取消隐藏）。"""
    games = [_game_dict(g) for g in store.games if g.get("hidden")]
    games.sort(key=lambda x: x["name"])
    return _api_ok(games)


@app.route("/api/games", methods=["POST"])
def add_game():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    paths = [p.strip() for p in (data.get("save_paths") or []) if p and p.strip()]
    if not name:
        return _api_err("游戏名称不能为空")
    if not paths:
        return _api_err("至少需要一个存档路径")
    game = {
        "id": data.get("id"),
        "name": name,
        "platform": data.get("platform") or ["Other"],
        "save_paths": paths,
        "processes": [p.strip() for p in (data.get("processes") or []) if p and p.strip()],
        "custom": True,
        "source": "custom",
        "auto_backup": bool(data.get("auto_backup", False)),
    }
    store.upsert_game(game)
    automation.sync_watchers()
    return _api_ok(_game_dict(game))


@app.route("/api/games/<game_id>", methods=["PUT"])
def update_game(game_id):
    g = store.get_game(game_id)
    if not g:
        return _api_err("游戏不存在", 404)
    data = request.get_json(force=True, silent=True) or {}
    if "name" in data:
        g["name"] = (data["name"] or "").strip()
    if "save_paths" in data:
        g["save_paths"] = [p.strip() for p in data["save_paths"] if p and p.strip()]
    if "processes" in data:
        g["processes"] = [p.strip() for p in data["processes"] if p and p.strip()]
    if "platform" in data:
        g["platform"] = data["platform"] or ["Other"]
    if "auto_backup" in data:
        g["auto_backup"] = bool(data["auto_backup"])
    if "hidden" in data:
        g["hidden"] = bool(data["hidden"])
    if "favorite" in data:
        g["favorite"] = bool(data["favorite"])
    store.upsert_game(g)
    automation.sync_watchers()
    return _api_ok(_game_dict(g))


@app.route("/api/games/<game_id>/hide", methods=["POST"])
def hide_game(game_id):
    """隐藏游戏（不出现在列表中，可在设置页取消）。"""
    g = store.get_game(game_id)
    if not g:
        return _api_err("游戏不存在", 404)
    g["hidden"] = True
    store.upsert_game(g)
    automation.sync_watchers()
    return _api_ok(_game_dict(g))


@app.route("/api/games/<game_id>", methods=["DELETE"])
def delete_game(game_id):
    if not store.remove_game(game_id):
        return _api_err("游戏不存在", 404)
    automation.sync_watchers()
    return _api_ok({"id": game_id})


@app.route("/api/games/<game_id>/backup", methods=["POST"])
def backup_game(game_id):
    g = store.get_game(game_id)
    if not g:
        return _api_err("游戏不存在", 404)
    data = request.get_json(force=True, silent=True) or {}
    force = bool(data.get("force", False))
    try:
        # create_backup 内部已做无变更检测（check_changes），这里不再重复预检，
        # 避免同一请求对存档做两次全量 SHA256（大存档耗时翻倍）
        v = bk.create_backup(g, note=data.get("note", ""), mode=data.get("mode"), force=force)
        return _api_ok(v)
    except bk.BackupUnchanged as e:
        # 补充 latest：供前端"无变更确认"弹窗展示最近备份时间
        latest = ""
        _vs = bk.list_versions(game_id)
        if _vs:
            latest = _vs[0]["timestamp"]
        return _api_ok({"unchanged": True, "reason": str(e),
                        "latest": latest, "game_id": game_id})
    except bk.BackupError as e:
        return _api_err(str(e))
    except Exception as e:
        log.error("备份异常: %s", e)
        return _api_err(f"备份异常: {e}", 500)


@app.route("/api/games/backup-all", methods=["POST"])
def backup_all_games():
    """备份所有游戏（无变更的游戏自动跳过，不弹确认）。"""
    data = request.get_json(force=True, silent=True) or {}
    result = service.backup_all(
        force=bool(data.get("force", False)),
        note=data.get("note", ""),
        mode=data.get("mode"),
    )
    return _api_ok(result)


@app.route("/api/games/<game_id>/restore", methods=["POST"])
def restore_game(game_id):
    g = store.get_game(game_id)
    if not g:
        return _api_err("游戏不存在", 404)
    data = request.get_json(force=True, silent=True) or {}
    ts = data.get("timestamp") or data.get("ts")
    if not ts:
        return _api_err("缺少版本时间戳")
    try:
        result = bk.restore_backup(g, ts, safety_backup=True)
        return _api_ok(result)
    except bk.BackupError as e:
        return _api_err(str(e))
    except Exception as e:
        log.error("恢复异常: %s", e)
        return _api_err(f"恢复异常: {e}", 500)


@app.route("/api/games/<game_id>/versions", methods=["GET"])
def versions(game_id):
    return _api_ok(bk.list_versions(game_id))


@app.route("/api/games/<game_id>/versions/<ts>/verify", methods=["POST"])
def verify_version(game_id, ts):
    try:
        result = bk.verify_version(game_id, ts)
        return _api_ok(result)
    except bk.BackupError as e:
        return _api_err(str(e))


@app.route("/api/games/<game_id>/versions/<ts>/favorite", methods=["POST"])
def favorite_version(game_id, ts):
    data = request.get_json(force=True, silent=True) or {}
    fav = bool(data.get("favorite", True))
    try:
        return _api_ok(bk.set_favorite(game_id, ts, fav))
    except bk.BackupError as e:
        return _api_err(str(e))


@app.route("/api/games/<game_id>/versions/<ts>", methods=["DELETE"])
def delete_version(game_id, ts):
    try:
        bk.delete_version(game_id, ts)
        return _api_ok({"deleted": ts})
    except bk.BackupError as e:
        return _api_err(str(e))


@app.route("/api/games/<game_id>/versions/cleanup", methods=["POST"])
def cleanup_versions(game_id):
    return _api_ok(bk.cleanup_versions(game_id))


# ---------------- 文件管理器 ----------------

def _allowed_open_paths():
    """收集所有允许打开的目录：备份根目录 + 每个游戏的存档路径 + 备份目录。"""
    allowed = {Path(store.settings["backup_root"]).resolve()}
    for g in store.games:
        allowed.add(bk.game_backup_dir(g.get("id", "")).resolve())
        for p in g.get("save_paths", []):
            ep = expand_env_path(p)
            if ep.exists():
                allowed.add(ep.resolve())
    return allowed


@app.route("/api/open", methods=["POST"])
def open_in_explorer():
    """在系统文件管理器中打开指定路径（仅允许白名单内路径）。"""
    data = request.get_json(force=True, silent=True) or {}
    raw = (data.get("path") or "").strip()
    if not raw:
        return _api_err("路径为空")
    target = Path(raw)
    if not target.exists():
        return _api_err("路径不存在")
    allowed = _allowed_open_paths()
    try:
        target_resolved = target.resolve()
    except Exception:
        target_resolved = target
    if target_resolved not in allowed and target not in allowed:
        return _api_err("此路径不在允许列表内，仅可打开游戏存档路径与备份目录")
    try:
        import subprocess
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", str(target_resolved)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target_resolved)])
        else:
            subprocess.Popen(["xdg-open", str(target_resolved)])
        log.info("已打开文件管理器: %s", target_resolved)
        return _api_ok({"path": str(target_resolved)})
    except Exception as e:
        return _api_err(f"打开失败: {e}")


# ---------------- 扫描 ----------------

@app.route("/api/scan", methods=["POST"])
def scan():
    """触发扫描：将内置检测到的游戏写入配置。联网时增强规则 + 匹配图标。"""
    result = detector.sync_builtin_to_store()
    # 联网状态下为新游戏匹配 Steam 图标（失败不影响扫描结果）
    if store.settings.get("scan_online", True):
        try:
            icon_result = steam_search.match_icons()
            result["icon_match"] = icon_result
        except Exception as e:
            log.warning("图标匹配失败（忽略）: %s", e)
    return _api_ok(result)


# ---------------- 配置导入导出 ----------------

@app.route("/api/config/export", methods=["GET"])
def export_config():
    payload = {
        "app": "game-save-manager",
        "version": 1,
        "exported_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "settings": store.settings,
        "games": store.games,
    }
    return _api_ok(payload)


@app.route("/api/config/import", methods=["POST"])
def import_config():
    data = request.get_json(force=True, silent=True) or {}
    if not isinstance(data, dict):
        return _api_err("无效的配置文件")
    # 兼容直接导入 {games:[...], settings:{...}}
    imported = 0
    if isinstance(data.get("games"), list):
        for g in data["games"]:
            if not isinstance(g, dict) or not g.get("name"):
                continue
            g.setdefault("custom", True)
            g.setdefault("source", "custom")
            store.upsert_game(g)
            imported += 1
    if isinstance(data.get("settings"), dict):
        # 类型校验（S2 修复）：只接受合法类型的值，脏配置直接丢弃
        src = data["settings"]
        if isinstance(src.get("backup_root"), str) and src["backup_root"].strip():
            store.settings["backup_root"] = src["backup_root"].strip()
        try:
            if isinstance(src.get("keep_versions"), int):
                store.settings["keep_versions"] = max(1, min(src["keep_versions"], 99))
        except Exception:
            pass
        if isinstance(src.get("compress_format"), str) and src["compress_format"] in ("none", "zip", "tar.gz"):
            store.settings["compress_format"] = src["compress_format"]
        try:
            if isinstance(src.get("watch_delay"), (int, float)):
                store.settings["watch_delay"] = max(1, min(float(src["watch_delay"]), 120))
        except Exception:
            pass
        store.save_settings()
    automation.sync_watchers()
    return _api_ok({"imported_games": imported, "total": len(store.games)})


# ---------------- 日志 ----------------

@app.route("/api/logs", methods=["GET"])
def get_logs():
    lines = []
    if LOG_FILE.exists():
        try:
            raw = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
            # 最新的日志在最前面（倒序）
            lines = raw.strip().splitlines()[-200:][::-1]
        except Exception:
            pass
    return _api_ok(lines)


@app.route("/api/version", methods=["GET"])
def get_version():
    from backend.version import VERSION, APP_NAME
    return _api_ok({"version": VERSION, "name": APP_NAME})


# ---------------- 初始化 ----------------

INIT_MARKER = DATA_DIR / ".initialized"

# 联网增强（Ludusavi + 图标）在后台线程执行，避免阻塞首次启动
_background_threads = []


def _background_online_scan():
    """后台线程：联网增强扫描（Ludusavi 规则库）+ 图标匹配。

    首次启动/初始化后调用，让服务先跑起来，增强结果后到。
    """
    try:
        if store.settings.get("scan_online", True):
            detector.sync_builtin_to_store(online=True)
            log.info("联网增强扫描完成，共 %d 个游戏", len(store.games))
            try:
                steam_search.match_icons()
            except Exception as e:
                log.warning("图标匹配失败（忽略）: %s", e)
    except Exception as e:
        log.warning("后台联网增强失败（忽略）: %s", e)


def _spawn_background_online_scan():
    t = threading.Thread(target=_background_online_scan, daemon=True)
    _background_threads.append(t)
    t.start()


def _perform_initialization(reset_backups: bool = False, rescan: bool = True) -> dict:
    """执行初始化：重置设置为默认、清空游戏列表、清空日志、（可选清空备份）后重新扫描。

    初始化内的扫描使用离线模式（秒级），联网增强由后台线程补充。
    """
    result = store.reset(reset_backups=reset_backups)
    # 清空日志
    try:
        if LOG_FILE.exists():
            LOG_FILE.write_text("", encoding="utf-8")
    except OSError:
        pass
    # 重新扫描（离线，快）
    if rescan:
        try:
            scan_result = detector.sync_builtin_to_store(online=False)
            result["scan"] = scan_result
        except Exception as e:
            log.warning("初始化后扫描失败: %s", e)
            result["scan_error"] = str(e)
    log.info("初始化完成: %s", result)
    return result


@app.route("/api/init", methods=["POST"])
def init_tool():
    """手动初始化（设置页红色按钮）。reset_backups=True 时清空默认备份数据。"""
    data = request.get_json(force=True, silent=True) or {}
    reset_backups = bool(data.get("reset_backups", False))
    result = _perform_initialization(reset_backups=reset_backups)
    automation.sync_watchers()
    # 联网增强后台补充
    _spawn_background_online_scan()
    return _api_ok(result)


# ---------------- 启动 ----------------

def _find_free_port(preferred: int) -> int:
    """在 preferred 附近找一个空闲端口（被占用时自动+1 尝试）。"""
    import socket
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def main():
    port = int(os.environ.get("SAVEMGR_PORT", "8765"))
    host = "127.0.0.1"

    # 端口被占用时自动换（避免与已有实例冲突导致启动失败）
    port = _find_free_port(port)
    os.environ["SAVEMGR_PORT"] = str(port)

    # 首次部署：自动执行初始化（重置默认备份路径、清空列表与日志后重新扫描）
    try:
        if not INIT_MARKER.exists():
            print("[初始化] 首次部署，正在初始化…（重置默认设置并扫描本机游戏，请稍候）")
            log.info("检测到首次部署，自动执行初始化…")
            _perform_initialization(reset_backups=False, rescan=True)
            INIT_MARKER.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    except Exception as e:
        log.warning("首次初始化失败（继续启动）: %s", e)

    # 启动时自动扫描一次（幂等：已存在的游戏跳过；离线模式秒级完成）
    try:
        detector.sync_builtin_to_store(online=False)
        log.info("扫描完成，共 %d 个游戏", len(store.games))
    except Exception as e:
        log.warning("启动扫描失败: %s", e)

    automation.start_scheduler()
    automation.sync_watchers()

    url = f"http://{host}:{port}"
    if store.settings.get("auto_open_browser", True):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    log.info("存档管理工具已启动: %s", url)
    log.info("备份目录: %s", store.settings["backup_root"])
    print(f"\n[就绪] 存档管理工具已启动: {url}")
    print(f"[就绪] 备份目录: {store.settings['backup_root']}")
    # 自动监听状态提示（仅启动时一次，总结一句话，不逐个游戏提醒）
    watching = sum(1 for g in store.games if g.get("auto_backup"))
    if store.games:
        if watching:
            log.info("自动备份监听已生效：%d 个游戏启用了「自动备份」", watching)
        else:
            log.info("提示：当前没有游戏开启「自动备份」，存档变化监听未生效。"
                     "在游戏详情页勾选「自动备份」即可启用。")
            print("[提示] 当前没有游戏开启「自动备份」，存档变化监听未生效。")
            print("[提示] 在网页游戏详情页勾选「自动备份」即可启用；也可在设置中添加定时任务。")
    print("[提示] 请用浏览器访问上方地址；关闭本窗口或按 Ctrl+C 退出。\n")

    # 服务起来后，后台线程做联网增强（Ludusavi + 图标），不阻塞使用
    _spawn_background_online_scan()

    from waitress import serve
    serve(app, host=host, port=port, threads=8)


if __name__ == "__main__":
    main()
