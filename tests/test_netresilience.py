"""网络栈抖动自愈回归测试（WinError 10022 / WSAEINVAL）。

缺陷场景：
    加速器（UU 加速器等）或代理类软件启用时会重建 Winsock 的 LSP 链，
    使**已经存在**的监听 socket 句柄失效，此后 accept() 持续抛出
    OSError(10022)。原生 waitress 的 handle_accept() 只记录一条 warning
    就 return，不恢复：监听 socket 仍留在 select 集合里且一直可读，于是
    陷入 CPU 忙循环 + 日志风暴，服务实际不可用。

修复：backend.netserver 在 accept 连续失败后重建监听 socket 与唤醒通道，
并做日志节流、失败退避与看门狗探活。

测试全部使用本地回环地址与系统分配的空闲端口，不访问外网、不触碰 data/。
"""
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import netserver
from backend.netserver import _port_candidates, create_resilient_server

WSAEINVAL = 10022


# ---------------- 测试脚手架 ----------------

def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _echo_app(environ, start_response):
    body = b"pong"
    start_response(
        "200 OK",
        [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))],
    )
    return [body]


def _poke(srv, timeout=0.5):
    """向监听地址建一次连接后立即关闭，只为让监听 socket 进入可读状态。"""
    try:
        socket.create_connection(
            ("127.0.0.1", int(srv.effective_port)), timeout=timeout
        ).close()
    except OSError:
        pass


class _RunningServer:
    """在后台线程运行一个 ResilientWSGIServer。"""

    def __init__(self, threads=2):
        self.port = _free_port()
        self.server = create_resilient_server(
            _echo_app, "127.0.0.1", self.port, threads
        )
        self._thread = threading.Thread(
            target=self.server.run, daemon=True, name="test-waitress"
        )
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.effective_port}"

    def get(self, timeout=3):
        with urllib.request.urlopen(self.url + "/ping", timeout=timeout) as resp:
            return resp.status, resp.read()

    def close(self):
        try:
            self.server.close()
        except Exception:
            pass
        try:
            self.server.stop_watchdog()
        except Exception:
            pass
        self._thread.join(timeout=3)


@pytest.fixture
def server():
    srv = _RunningServer()
    try:
        yield srv
    finally:
        srv.close()


def _wait_until(predicate, timeout=10.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _wait_trigger_ready(srv, timeout=10.0):
    """等待后台唤醒通道重建完成（重建期间服务仍可接受连接）。"""
    return _wait_until(lambda: not srv._trigger_rebuilding, timeout=timeout)


def _inject_accept_failures(srv, times):
    """让 srv.accept 抛 WSAEINVAL 若干次后恢复正常，返回 (真实方法, 状态)。"""
    real_accept = srv.accept
    state = {"remaining": times, "calls": 0}

    def failing_accept():
        state["calls"] += 1
        if state["remaining"] > 0:
            state["remaining"] -= 1
            raise OSError(WSAEINVAL, "提供了一个无效的参数。")
        return real_accept()

    srv.accept = failing_accept
    return real_accept, state


# ---------------- 基线 ----------------

def test_serves_request_normally(server):
    assert server.get() == (200, b"pong")


# ---------------- 核心：accept 失败后自愈 ----------------

def test_rebuilds_listen_socket_after_accept_failures(server, monkeypatch):
    """accept 连续抛 WSAEINVAL 达到阈值后，应重建监听 socket 并恢复服务。"""
    monkeypatch.setattr(netserver, "REBUILD_THRESHOLD", 3)
    monkeypatch.setattr(netserver, "MIN_REBUILD_INTERVAL", 0.0)

    srv = server.server
    # 注意：不要比较 fileno() —— 旧 socket 关闭后 fd 号会被新 socket 复用
    original_socket = srv.socket
    real_accept, state = _inject_accept_failures(srv, times=3)

    # 失败的 accept 不会取走积压连接，监听 socket 会持续可读；
    # 这里补连只是防止个别平台把失败连接清出 backlog 后就不再触发。
    deadline = time.time() + 10
    while time.time() < deadline and srv._rebuild_count == 0:
        if state["remaining"] == 0:
            state["remaining"] = 3
        _poke(srv)
        time.sleep(0.05)

    assert srv._rebuild_count >= 1, "accept 连续失败后应触发重建"
    assert srv.socket is not original_socket, "重建后应换成新的监听 socket 对象"
    assert srv.accepting is True, "重建后应重新进入监听状态"

    # 等注入的失败耗尽，accept 恢复真实实现后服务必须可用
    _wait_until(lambda: state["remaining"] == 0, timeout=5)
    srv.accept = real_accept
    _wait_trigger_ready(srv)  # 等后台唤醒通道重建完成，避免响应回写延迟
    assert server.get() == (200, b"pong")


def test_rebuild_keeps_serving_on_same_port(server, monkeypatch):
    """正常情况下重建应回到原端口，避免用户访问地址变化。"""
    monkeypatch.setattr(netserver, "REBUILD_THRESHOLD", 2)
    monkeypatch.setattr(netserver, "MIN_REBUILD_INTERVAL", 0.0)

    srv = server.server
    original_port = int(srv.effective_port)
    _inject_accept_failures(srv, times=2)

    deadline = time.time() + 10
    while time.time() < deadline and srv._rebuild_count == 0:
        _poke(srv)
        time.sleep(0.05)

    assert srv._rebuild_count >= 1
    assert int(srv.effective_port) == original_port


# ---------------- 日志节流 ----------------

def test_accept_error_log_is_throttled(server, monkeypatch):
    """连续同类错误不应逐条刷屏，后续次数应计入抑制计数。"""
    monkeypatch.setattr(netserver, "REBUILD_THRESHOLD", 999)  # 暂不重建
    monkeypatch.setattr(netserver, "LOG_THROTTLE_INTERVAL", 30.0)
    monkeypatch.setattr(netserver, "MAX_ACCEPT_BACKOFF", 0.0)

    srv = server.server
    _real, state = _inject_accept_failures(srv, times=999)

    # 失败的 accept 不会取走积压连接，监听 socket 会持续可读；
    # 这里补连只是防止个别平台把失败连接清出 backlog 后就不再触发。
    deadline = time.time() + 10
    while time.time() < deadline and state["calls"] < 5:
        _poke(srv)
        time.sleep(0.05)

    assert state["calls"] >= 3, f"应发生多次 accept 失败，实际 {state['calls']}"
    assert srv._suppressed_errors >= 1, "超出节流窗口的错误应被抑制计数"


# ---------------- 唤醒通道 trigger ----------------

def test_trigger_can_be_rebuilt(server):
    """Winsock 抖动后唤醒通道同样失效，重建后应能继续回写响应。"""
    srv = server.server
    old_trigger = srv.trigger

    assert srv._rebuild_trigger(force=True) is True
    assert srv.trigger is not old_trigger
    assert server.get() == (200, b"pong")


def test_pull_trigger_failure_spawns_background_rebuild(server):
    """唤醒通道失效时转入后台重建：调用不阻塞、重建后服务可用。"""
    srv = server.server
    old_trigger = srv.trigger

    class _BrokenTrigger:
        def pull_trigger(self):
            raise OSError(10022, "唤醒通道失效")

    srv.trigger = _BrokenTrigger()
    started = time.monotonic()
    srv.pull_trigger()
    elapsed = time.monotonic() - started
    assert elapsed < 2, f"pull_trigger 不应同步等待重建（耗时 {elapsed:.2f}s）"
    assert srv._trigger_rebuilding is True, "应已拉起后台重建"

    assert _wait_trigger_ready(srv, timeout=10), "后台重建应完成"
    assert srv.trigger is not old_trigger, "后台重建后应换用新的唤醒通道"
    assert server.get() == (200, b"pong")


# ---------------- 看门狗 ----------------

def test_probe_listen_succeeds_when_healthy(server):
    assert server.server._probe_listen() is True


def test_probe_listen_fails_when_socket_dead(server):
    srv = server.server
    srv.accepting = False
    srv.socket.close()
    assert srv._probe_listen() is False


def test_watchdog_rebuilds_after_repeated_probe_failures(server, monkeypatch):
    """监听 socket 静默僵死（不抛异常但连不上）时，看门狗应能救回来。"""
    monkeypatch.setattr(netserver, "WATCHDOG_FAIL_THRESHOLD", 2)
    monkeypatch.setattr(netserver, "MIN_REBUILD_INTERVAL", 0.0)

    srv = server.server
    srv.accepting = False
    srv.socket.close()  # 模拟句柄失效

    srv._watchdog_tick()
    srv._watchdog_tick()

    assert srv._rebuild_count >= 1, "连续探活失败后应触发重建"
    assert srv.accepting is True
    _wait_trigger_ready(srv)  # 等后台唤醒通道重建完成
    assert server.get() == (200, b"pong")


# ---------------- 端口候选 ----------------

def test_port_candidates_prefers_original_port():
    ports = _port_candidates(8765)
    assert ports[0] == 8765
    assert ports[1] == 8766
    assert len(ports) == 50


def test_port_candidates_without_preferred():
    assert _port_candidates(None) == [0]
