"""配置管理：settings.json（全局设置）与 games.json（游戏列表）。

文件均存储在项目 data/ 目录下，采用 JSON 格式，便于用户手动阅读修改。
"""
import json
import sys
import threading
import uuid
from pathlib import Path

from .utils import log

if getattr(sys, "frozen", False):
    # PyInstaller 单文件打包：数据目录固定在 exe 同级，避免写入临时解压目录
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # 源码运行：项目根目录（backend 的上级）
    BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_ROOT_DEFAULT = DATA_DIR / "backups"
SETTINGS_FILE = DATA_DIR / "settings.json"
GAMES_FILE = DATA_DIR / "games.json"

_lock = threading.RLock()

DEFAULT_SETTINGS = {
    "backup_root": str(BACKUP_ROOT_DEFAULT),   # 备份存档根目录（可手动配置）
    "keep_versions": 5,                        # 保留最近 N 个版本，N 手动配置
    "compress_format": "none",                 # none / zip / tar.gz
    "backup_mode": "full",                     # full / incr / auto
    "auto_open_browser": True,                 # 启动后自动打开浏览器
    "watch_delay": 8,                          # 变化后等待秒数再备份（防抖）
    "watch_interval": 0,                       # 文件变更监听扫描间隔（秒）；0=事件驱动（默认，零轮询开销）
    "scan_online": True,                       # 扫描时联网更新游戏规则库（Ludusavi）
    "rules_source": "auto",                    # 规则库下载源: auto(多源回退)/jsdelivr/github
    "log_level": "INFO",
    "auto_tasks": [],                          # [{id,name,game_id,kind:interval|watch,interval_seconds,enabled}]
}


class ConfigStore:
    def __init__(self, settings_file=None, games_file=None):
        self.settings_file = Path(settings_file) if settings_file else SETTINGS_FILE
        self.games_file = Path(games_file) if games_file else GAMES_FILE
        self.settings = dict(DEFAULT_SETTINGS)
        self.games = []          # 列表，元素为游戏 dict
        self._load_settings()
        self._load_games()

    # ---------- 读写 ----------
    def _load_settings(self):
        try:
            if self.settings_file.exists():
                data = json.loads(self.settings_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(data)
                    self.settings = merged
        except Exception as e:
            log.warning("读取 settings 失败，使用默认: %s", e)

    def save_settings(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(
            json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_games(self):
        try:
            if self.games_file.exists():
                data = json.loads(self.games_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.games = data.get("games", [])
                elif isinstance(data, list):
                    self.games = data
        except Exception as e:
            log.warning("读取 games 失败: %s", e)

    def save_games(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.games_file.write_text(
            json.dumps({"games": self.games}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------- 游戏操作 ----------
    def get_game(self, game_id):
        for g in self.games:
            if g.get("id") == game_id:
                return g
        return None

    def upsert_game(self, game: dict):
        """按 id 新增或更新游戏，返回该游戏。"""
        with _lock:
            if not game.get("id"):
                game["id"] = uuid.uuid4().hex[:12]
            for i, g in enumerate(self.games):
                if g.get("id") == game["id"]:
                    self.games[i] = game
                    self.save_games()
                    return game
            self.games.append(game)
            self.save_games()
            return game

    def remove_game(self, game_id) -> bool:
        with _lock:
            before = len(self.games)
            self.games = [g for g in self.games if g.get("id") != game_id]
            if len(self.games) != before:
                self.save_games()
                return True
            return False

    def reset(self, reset_backups: bool = False) -> dict:
        """初始化：重置设置为默认、清空游戏列表（可选清空备份数据）。

        返回清理统计。reset_backups=True 时会清空默认备份目录下的所有备份。
        """
        with _lock:
            self.settings = dict(DEFAULT_SETTINGS)
            self.save_settings()
            self.games = []
            self.save_games()

        removed_backups = 0
        if reset_backups:
            try:
                from .backup import force_rmtree
                root = Path(self.settings["backup_root"])
                if root.exists():
                    for child in root.iterdir():
                        if child.is_dir():
                            force_rmtree(child)
                            removed_backups += 1
            except Exception as e:
                log.warning("初始化清空备份目录异常: %s", e)

        return {"settings_reset": True, "games_cleared": True,
                "backup_dirs_removed": removed_backups}


# 全局实例
store = ConfigStore()
