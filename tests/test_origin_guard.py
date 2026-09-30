"""本地服务来源校验回归测试（CSRF / DNS rebinding）。

背景缺陷：
    本服务的写操作路由全部没有 CSRF token，且业务代码统一使用
    `request.get_json(force=True, silent=True)` —— `force=True` 会忽略
    Content-Type 强制解析 body。浏览器因此可以用「简单请求」（text/plain 携带
    JSON body）发起写操作，而简单请求**不触发 CORS 预检**，不需要目标服务授予
    任何跨域许可。结论：任意第三方网页都能驱动本服务写入。
    详见 docs/SECURITY_AUDIT_20260930.md 的 H1。

防护：
    `app.py::_guard_local_origin()`（before_request 钩子）做两层校验：
      ① Host 头必须是回环地址 —— 挡 DNS rebinding（攻击者域名解析到 127.0.0.1
         时 Host 会是攻击者域名，其「同源」判定随之失效）；
      ② 写方法的 Origin（缺失时回退 Referer）必须是本机 —— 挡 CSRF。

设计约定（修改前请先理解，别当成 bug 修掉）：
    * **不校验端口**。端口会因被占用（`_find_free_port`）或网络自愈
      （`_on_port_changed`）而变化，硬编码会导致误拒。
    * **不带 Origin/Referer 时放行**。curl、本机脚本、E2E 的 Node fetch 本就有
      同等本机文件权限，把它们挡在外面只会误伤自己的工具链，却不提升安全性。

本测试全部使用回环地址与不可路由域名，不访问外网、不触碰 data/。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod  # noqa: E402

# 未注册的路由：钩子放行时不会落到任何 handler（405/404），钩子拦截时是 403。
# 用它做探针可以避免触发真实的备份/扫描/删除逻辑，保持本测试零副作用。
PROBE = "/api/__probe__"

LOCAL_BASE = "http://127.0.0.1:8765"


@pytest.fixture(scope="module")
def client():
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def _write(client, base_url=LOCAL_BASE, **headers):
    return client.post(PROBE, base_url=base_url, json={}, headers=headers or None)


def _read(client, base_url=LOCAL_BASE):
    return client.get("/api/version", base_url=base_url)


# ---------------- 拦截：跨站写入（H1 核心） ----------------

def test_blocks_cross_origin_write(client):
    r = _write(client, Origin="https://evil.example")
    assert r.status_code == 403, "跨源写入必须被拦截"


def test_blocks_cross_origin_referer_when_origin_absent(client):
    r = _write(client, Referer="https://evil.example/page")
    assert r.status_code == 403, "没有 Origin 时必须回退到 Referer 判定"


def test_blocks_null_origin(client):
    """沙箱 iframe / file:// 产生的 `Origin: null` 同样不可信。"""
    r = _write(client, Origin="null")
    assert r.status_code == 403


@pytest.mark.parametrize("origin", [
    "https://evil.example",
    "http://evil.example:8080",
    "http://attacker.local",
    "http://127.0.0.1.evil.example",  # 看起来像本机，实为攻击者域名
    "http://localhost.evil.example",
])
def test_blocks_origin_spoofing_variants(client, origin):
    assert _write(client, Origin=origin).status_code == 403


# ---------------- 拦截：DNS rebinding ----------------

@pytest.mark.parametrize("method", ["get", "post"])
def test_blocks_non_local_host(client, method):
    """Host 不是回环名时连读请求也要拦，否则 DNS rebinding 会让一切失效。"""
    r = getattr(client, method)(PROBE, base_url="http://evil.example",
                                json={} if method == "post" else None)
    assert r.status_code == 403


def test_blocks_localhost_subdomain_spoof(client):
    assert _read(client, base_url="http://127.0.0.1.evil.example").status_code == 403


def test_blocks_rebinding_from_page(client):
    """DNS rebinding 的完整形态：攻击者域名 + 指向本机的 Host。"""
    r = _write(client, base_url="http://evil.example", Origin="http://evil.example")
    assert r.status_code == 403


# ---------------- 放行：本机正常用法一个都不能误伤 ----------------

@pytest.mark.parametrize("base_url", [
    "http://127.0.0.1:8765",
    "http://127.0.0.1",           # 无端口
    "http://localhost:8765",
    "http://localhost",
    "http://localhost.",          # FQDN 尾点
    "http://LOCALHOST:8765",      # 大小写不定
    "http://[::1]:8765",          # IPv6 回环
])
def test_allows_loopback_hosts(client, base_url):
    assert _read(client, base_url=base_url).status_code == 200


@pytest.mark.parametrize("headers", [
    {},                                              # curl / 本机脚本
    {"Origin": "http://127.0.0.1:8765"},             # 同源前端 fetch
    {"Origin": "http://localhost:8765"},             # 用 localhost 访问的同一前端
    {"Referer": "http://127.0.0.1:8765/index.html"},
])
def test_allows_local_writes(client, headers):
    r = _write(client, **headers)
    assert r.status_code != 403, f"本机合法写入被误伤: {r.status_code}"


def test_get_never_blocked_by_origin(client):
    """读请求只看 Host；Origin 不参与，避免误伤跨域 GET（当前无此用例但预留）。"""
    r = client.get("/api/version", base_url=LOCAL_BASE,
                   headers={"Origin": "null"})
    assert r.status_code == 200


# ---------------- 主机名解析 ----------------

@pytest.mark.parametrize("value, expected_local", [
    ("127.0.0.1:8765", True),
    ("localhost", True),
    ("localhost.", True),
    ("LOCALHOST:1", True),
    ("[::1]:8765", True),
    ("::1", True),
    ("http://127.0.0.1:8765", True),
    ("user@127.0.0.1:8765", True),
    ("evil.example", False),
    ("https://evil.example/a?b=1", False),
    ("null", False),
    ("127.0.0.1.evil.example", False),
    ("127.0.0.1,evil.example", True),   # 畸形多值头：取首段，仍视为本机
    ("", False),
    (None, False),
])
def test_host_of(value, expected_local):
    assert appmod._is_local_host(value) is expected_local
