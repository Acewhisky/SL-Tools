import json, urllib.request, urllib.parse, time, os, shutil

# N5 优化：端口/数据目录可用环境变量覆盖
BASE = "http://127.0.0.1:" + os.environ.get("SAVEMGR_TEST_PORT", "8933")
EXE_DATA_DIR = os.environ.get("SAVEMGR_TEST_ROOT",
                              r"C:\Users\Dengz\AppData\Local\Temp\savemgr_probe2")

def req(m, p, b=None):
    u = BASE + urllib.parse.quote(p, safe="/")
    d = json.dumps(b).encode() if b is not None else None
    r = urllib.request.Request(u, data=d, method=m, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return json.loads(raw)
        except Exception:
            return {"ok": False, "error": raw[:150]}

# 测试 1: 变更自动备份
save = os.path.join(EXE_DATA_DIR, "save_auto")
shutil.rmtree(save, ignore_errors=True)
os.makedirs(save)
with open(os.path.join(save, "x.sav"), "w") as f:
    f.write("v1")

r = req("POST", "/api/games", {"name": "exe自动备份测试", "save_paths": [save]})
gid = r["data"]["id"]
print("游戏:", gid)
req("POST", "/api/settings", {"watch_delay": 2})
req("PUT", "/api/games/" + gid, {"auto_backup": True})
time.sleep(3)

c0 = req("GET", "/api/games/counts")["data"].get(gid, 0)
print("初始 counts:", c0)

with open(os.path.join(save, "x.sav"), "w") as f:
    f.write("v2 changed " + str(time.time()))

print("等待变更自动备份（20s）...")
deadline = time.time() + 20
ok = False
while time.time() < deadline:
    time.sleep(1)
    c = req("GET", "/api/games/counts")["data"].get(gid, 0)
    if c > c0:
        print(f"  counts: {c0} -> {c} 触发!")
        ok = True
        break
print("变更自动备份:", "PASS" if ok else "FAIL")

# 检查 watcher 是否建立
print("日志最后 10 行:")
with open(os.path.join(EXE_DATA_DIR, "data", "app.log"), "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
for line in lines[-10:]:
    print("  " + line.strip()[:120])

# 清理
req("DELETE", "/api/games/" + gid)
shutil.rmtree(save, ignore_errors=True)
