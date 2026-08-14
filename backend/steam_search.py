"""Steam 图标匹配（扫描后联网执行）。

通过 Steam Store 搜索 API 按游戏名查找 appid，生成图标 URL。
匹配结果写入 games.json 的 steam_appid 字段（缓存，避免重复请求）。
仅在联网时生效；离线/超时/无结果时静默跳过（游戏无图标，前端回退 emoji）。
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from .config import store
from .utils import log

SEARCH_API = "https://store.steampowered.com/api/storesearch/?term={term}&l=english&cc=US"
ICON_TPL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

# 请求间隔（秒），避免触发 Steam 限流
REQUEST_DELAY = 0.4
# 单次扫描最多匹配多少个游戏（防止海量请求）
MAX_MATCH = 30
# 单请求连接超时（秒）
TIMEOUT = 8
# 单请求整体超时（秒）：含连接 + 读取，防止 read() 无限挂起
READ_TIMEOUT = 10
# 图标匹配整体时限（秒）：网络不可用时快速降级，不阻塞后台线程太久
MATCH_DEADLINE = 60


def _strip_name(name: str) -> str:
    """清洗游戏名用于搜索：去常见后缀/标点。"""
    s = re.sub(r"[\u4e00-\u9fff]", "", name)  # 去中文（Steam 搜索英文名更准）
    s = re.sub(r"[:\-'\"!@#$%^&*()\[\]{}.,;，。！？、]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # 去常见版本后缀
    for suf in ("directors cut", "game of the year", "goty edition", "complete edition", "definitive edition"):
        if s.lower().endswith(suf):
            s = s[: -len(suf)].strip()
    return s[:40]


def search_appid(game_name: str):
    """按游戏名在 Steam 搜索，返回 (appid, name) 或 None。

    整体限时 READ_TIMEOUT（连接 + 读取都受控），网络异常时快速返回 None。
    """
    term = _strip_name(game_name)
    if not term:
        return None
    url = SEARCH_API.format(term=urllib.parse.quote(term))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "savemgr/1.0"})
        # 分块读取并限制总时长：urlopen 的 timeout 只覆盖连接阶段，read() 可能无限挂起
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            deadline = time.monotonic() + READ_TIMEOUT
            chunks = []
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError("Steam 响应读取超时")
                chunk = resp.read(1 << 14)
                if not chunk:
                    break
                chunks.append(chunk)
            body = b"".join(chunks)
        data = json.loads(body.decode("utf-8", errors="ignore"))
        items = data.get("items") or []
        if not items:
            return None
        first = items[0]
        appid = first.get("id")
        # 名称相似度校验：避免张冠李戴
        result_name = first.get("name", "")
        if appid and _name_similar(game_name, result_name):
            return appid, result_name
        return None
    except Exception as e:
        log.debug("Steam 搜索失败 [%s]: %s", game_name, e)
        return None


def _name_similar(orig: str, found: str) -> bool:
    """名称相似度校验：Found 名包含 Orig 主词，或反之（容忍大小写/标点）。"""
    def norm(s):
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", s.lower())
    a, b = norm(orig), norm(found)
    if not a or not b:
        return False
    return a in b or b in a or (len(a) >= 4 and len(b) >= 4 and (a[:4] in b or b[:4] in a))


def icon_url_for(game: dict) -> str:
    """取游戏的图标 URL（优先 games.json 缓存的 steam_appid，其次内置映射）。"""
    appid = game.get("steam_appid")
    if not appid:
        from .game_db import get_steam_appid
        appid = get_steam_appid(game.get("name", ""))
    return ICON_TPL.format(appid=appid) if appid else None


def _collect_icon_candidates() -> list:
    """收集需要匹配图标的游戏（跳过已有 appid / 自定义 / 隐藏，可减少请求）。"""
    need = []
    for g in store.games:
        if g.get("steam_appid"):
            continue
        if g.get("custom") or g.get("hidden"):
            continue
        need.append(g)
    return need


def match_icons(force: bool = False) -> dict:
    """扫描后调用：为缺失 appid 的游戏联网匹配 Steam 图标，结果写回 games.json。

    并发限速：线程池并行 + 信号量控制请求速率，网络不佳时受整体时限保护。
    返回 {"matched": n, "total": m, "failed": k}
    """
    import concurrent.futures

    need = _collect_icon_candidates()
    if not need:
        return {"matched": 0, "total": 0, "failed": 0}

    total = len(need)
    matched = 0
    failed = 0
    start = time.monotonic()
    sem = threading.Semaphore(3)  # 最多 3 个并发请求，避免触发 Steam 限流
    _last_progress = [0]

    def _work(idx_game):
        i, g = idx_game
        # 整体时限：网络不可用时快速降级，避免后台线程长时间无日志（看似卡死）
        if time.monotonic() - start > MATCH_DEADLINE:
            return ("deadline", None)
        with sem:
            r = search_appid(g.get("name", ""))
        if r:
            g["steam_appid"] = r[0]
            return ("ok", None)
        return ("fail", None)

    candidates = [(i, g) for i, g in enumerate(need[:MAX_MATCH])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for status, _ in pool.map(_work, candidates):
            if status == "deadline":
                break
            if status == "ok":
                matched += 1
            else:
                failed += 1
            _last_progress[0] += 1
            # 进度日志：每 5 个输出一次，避免长时间无输出被误认为卡死
            if _last_progress[0] % 5 == 0:
                log.info("图标匹配进度: %d/%d (匹配 %d)", _last_progress[0], total, matched)

    if time.monotonic() - start > MATCH_DEADLINE:
        log.info("图标匹配达到时限 (%ss)，提前结束：已处理 %d/%d",
                 MATCH_DEADLINE, _last_progress[0], total)

    store.save_games()
    log.info("Steam 图标匹配: 匹配 %d / 总数 %d (未匹配 %d)", matched, total, failed)
    return {"matched": matched, "total": total, "failed": failed}
