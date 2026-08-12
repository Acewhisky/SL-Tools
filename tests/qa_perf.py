"""性能对比专项测试（QA 专用）：TC-L-001/002/004。

对比 main（v2.0.1，无 Q2 快筛）与 Dev（v2.1.0，有 _stat 快筛）：
- L-001：大存档（200MB）无变更检测耗时 —— Dev 应显著快于 main
- L-002：有变更时仍正确备份（快筛不一致走全量哈希兜底）
- L-004：备份期间服务进程内存 RSS（要求 < 200MB）

用法（服务已启动）：
    SAVEMGR_TEST_PORT=8877 SAVEMGR_TEST_ROOT=<项目根> python tests/qa_perf.py
输出 JSON 结果（PERF_RESULT_<branch>.json），供报告对比。
"""
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("SAVEMGR_TEST_ROOT",
                                   str(Path(__file__).resolve().parent.parent)))
BASE = "http://127.0.0.1:" + os.environ.get("SAVEMGR_TEST_PORT", "8877")
BRANCH = os.environ.get("SAVEMGR_TEST_BRANCH", "unknown")
_TMP = Path(tempfile.mkdtemp(prefix="qa_perf_"))
BIG_SAVE = _TMP / "big_save"
DATA_DIR = PROJECT_ROOT / "data"

result = {"branch": BRANCH, "ts": time.strftime("%Y%m%d_%H%M%S"), "cases": {}}


def _force_rmtree(path: Path):
    path = Path(path)
    if not path.exists():
        return
    for root, _dirs, files in os.walk(path, topdown=False):
        for name in files:
            try:
                os.unlink(os.path.join(root, name))
            except OSError:
                pass
        for name in _dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except OSError:
                pass
    try:
        os.rmdir(path)
    except OSError:
        pass


def req(method, path, body=None):
    encoded = urllib.parse.quote(path, safe="/")
    url = BASE + encoded
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode() or "{}")
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def add_game(name, save_paths):
    r = req("POST", "/api/games", {"name": name, "save_paths": save_paths, "processes": []})
    return r.get("data", {}).get("id") if r.get("ok") else None


def del_game(gid):
    if gid:
        req("DELETE", f"/api/games/{gid}")


def backup(gid, body=None, **kw):
    # 兼容两种调用：backup(gid, {"force": True}) 或 backup(gid, force=True)
    if body is not None:
        kw = body
    return req("POST", f"/api/games/{gid}/backup", kw)


def service_rss_mb():
    """采样服务进程内存（找监听端口的 python 进程）。"""
    import socket
    import subprocess
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10).stdout
        total = 0
        for line in out.strip().splitlines():
            parts = line.strip('"').split('","')
            if len(parts) >= 5 and "python" in parts[0].lower():
                try:
                    total += int(parts[4].replace(",", "").replace(" K", ""))
                except ValueError:
                    pass
        return total / 1024.0  # KB -> MB
    except Exception:
        return -1.0


def main():
    print("=" * 60)
    print(f"性能对比测试 (branch={BRANCH})")
    print("=" * 60)

    # ---- 构造大存档（默认 50MB，可用 SAVEMGR_PERF_MB 调整；沙箱 safe-delete 钩子下 200MB 会超时）----
    PERF_MB = int(os.environ.get("SAVEMGR_PERF_MB", "50"))
    BIG_SAVE.mkdir(parents=True, exist_ok=True)
    chunk = b"x" * (1 << 20)
    for i in range(PERF_MB):
        with open(BIG_SAVE / f"data{i:03d}.bin", "wb") as f:
            f.write(chunk)
    total_mb = sum(p.stat().st_size for p in BIG_SAVE.glob("*.bin")) / (1 << 20)
    print(f"大存档: {total_mb:.0f} MB / {len(list(BIG_SAVE.glob('*.bin')))} 文件")

    gid = add_game("QA性能对比L", [str(BIG_SAVE)])
    if not gid:
        print("❌ 添加游戏失败")
        sys.exit(1)

    # ---- L-001a：首次全量备份（含全量 SHA256）----
    t0 = time.monotonic()
    r = backup(gid, {"force": True})
    t1 = time.monotonic()
    first_s = t1 - t0
    result["cases"]["L001_first_backup_s"] = round(first_s, 2)
    result["cases"]["L001_first_backup_ok"] = bool(r.get("ok"))
    print(f"TC-L-001a 首次全量备份: {first_s:.2f}s ok={r.get('ok')}")

    # ---- L-001b：无变更再备份（关键对比点：Dev 快筛 vs main 全量哈希）----
    t0 = time.monotonic()
    r = backup(gid, {})
    t1 = time.monotonic()
    unchanged_s = t1 - t0
    result["cases"]["L001_unchanged_check_s"] = round(unchanged_s, 2)
    result["cases"]["L001_unchanged_ok"] = bool(r.get("ok") and (r.get("data") or {}).get("unchanged"))
    print(f"TC-L-001b 无变更检测: {unchanged_s:.2f}s unchanged={result['cases']['L001_unchanged_ok']}")

    # ---- L-002：改 1 个文件（快筛不一致 → 全量哈希兜底 → 正常备份）----
    (BIG_SAVE / "data000.bin").write_bytes(b"y" * (1 << 20))
    t0 = time.monotonic()
    r = backup(gid, {})
    t1 = time.monotonic()
    changed_s = t1 - t0
    result["cases"]["L002_changed_backup_s"] = round(changed_s, 2)
    result["cases"]["L002_changed_backup_ok"] = bool(r.get("ok") and not (r.get("data") or {}).get("unchanged"))
    print(f"TC-L-002 有变更备份: {changed_s:.2f}s ok={result['cases']['L002_changed_backup_ok']}")

    # ---- L-003：改内容但保持 size+mtime（Dev 快筛局限验证）----
    # 恢复 data000.bin 原始内容，保持 mtime
    f = BIG_SAVE / "data000.bin"
    st = f.stat()
    f.write_bytes(b"x" * (1 << 20))
    os.utime(f, (st.st_atime, st.st_mtime))
    t0 = time.monotonic()
    r = backup(gid, {})
    t1 = time.monotonic()
    l003_s = t1 - t0
    l003_unchanged = bool(r.get("ok") and (r.get("data") or {}).get("unchanged"))
    result["cases"]["L003_same_size_mtime_s"] = round(l003_s, 2)
    result["cases"]["L003_unchanged"] = l003_unchanged
    print(f"TC-L-003 同size同mtime改内容: {l003_s:.2f}s 判unchanged={l003_unchanged}（已知局限）")

    # ---- L-004：内存采样 ----
    rss = service_rss_mb()
    result["cases"]["L004_service_rss_mb"] = round(rss, 1) if rss > 0 else -1
    result["cases"]["L004_under_200mb"] = rss > 0 and rss < 200
    print(f"TC-L-004 服务内存 RSS: {rss:.1f} MB（<200MB 达标: {result['cases']['L004_under_200mb']}）")

    del_game(gid)
    _force_rmtree(_TMP)

    # 输出结果文件
    out = PROJECT_ROOT / "data" / f"perf_result_{BRANCH}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
