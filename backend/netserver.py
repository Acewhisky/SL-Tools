"""抗 Winsock 抖动的 waitress 服务器封装（Windows）。

背景
----
加速器 / 代理类软件（UU 加速器、各类 VPN、游戏加速器等）在启用时会安装或
重新排列 Winsock 的 LSP（Layered Service Provider）链。此时**已经存在**的
监听 socket 句柄会在新的 provider chain 下失效，此后对它调用 accept() 会
持续返回 WSAEINVAL（WinError 10022「提供了一个无效的参数」）。

waitress 自带的 handle_accept() 只记录一条 warning 就 return，不做任何恢复：
监听 socket 仍留在 asyncore 的 map 里且一直是可读状态，于是 select() 立刻
返回 → 再次 accept() → 再次失败，形成 CPU 100% 的忙循环与日志风暴，对外表现
就是"服务卡死"，只能重启程序。

本模块子类化 waitress 的 TcpWSGIServer 实现自愈：

1. accept() 连续失败达到阈值后重建监听 socket；
2. 同步重建唤醒通道 trigger（Windows 下是 loopback socket pair，同样会失效）；
3. 错误日志按时间窗口节流，避免刷屏；
4. 连续失败时短退避，抑制忙循环；
5. 后台看门狗定期探活，覆盖"监听 socket 静默僵死、但不再抛异常"的场景。

注意：新创建的 socket 不受影响（测试已验证 UU 运行期间新建 socket 正常），
所以"丢弃旧句柄、重建监听"是针对该问题的正确解法。
"""
import socket
import threading
import time

from .utils import log

try:
    from waitress.adjustments import Adjustments
    from waitress.server import TcpWSGIServer
    from waitress.task import ThreadedTaskDispatcher
except ImportError:  # pragma: no cover - waitress 缺失时由 serve_robust 回退
    Adjustments = None
    TcpWSGIServer = None
    ThreadedTaskDispatcher = None


# ---------------- 可调参数 ----------------

# 连续 accept() 失败达到该次数后重建监听 socket
REBUILD_THRESHOLD = 3
# 两次重建之间的最小间隔（秒），防止疯狂重试
MIN_REBUILD_INTERVAL = 2.0
# trigger 重建的最小间隔（秒）；它是响应回写的关键路径，冷却设得比监听更短
TRIGGER_REBUILD_INTERVAL = 1.0
# 连续 accept 失败时的退避上限（秒），抑制 CPU 忙循环
MAX_ACCEPT_BACKOFF = 0.5
# 同类 accept 错误的日志节流窗口（秒）
LOG_THROTTLE_INTERVAL = 30.0
# 看门狗探活间隔（秒）
WATCHDOG_INTERVAL = 30.0
# 连续探活失败多少次才重建（配合间隔即至少持续 1 分钟异常才动手）
WATCHDOG_FAIL_THRESHOLD = 2


def _port_candidates(preferred, span=50):
    """生成端口候选序列：优先原端口，其后依次 +1。"""
    if preferred is None:
        return [0]
    return [preferred] + list(range(preferred + 1, preferred + span))


class ResilientWSGIServer(TcpWSGIServer):
    """在 Winsock LSP 抖动后可自愈的 waitress 服务器。"""

    # ---------------- 事件处理 ----------------

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._accept_failures = 0
        self._rebuild_count = 0
        self._last_rebuild_at = 0.0
        self._last_trigger_rebuild_at = 0.0
        self._last_error_log_at = 0.0
        self._suppressed_errors = 0
        self._watchdog_failures = 0
        self._watchdog_stop = threading.Event()
        self._watchdog_thread = None
        self._on_port_change = None
        self._preferred_port = self._initial_port()

    def _initial_port(self):
        try:
            return int(self.sockinfo[3][1])
        except (TypeError, IndexError, ValueError):
            return None

    def handle_accept(self):
        """覆写父类：accept 失败不再只是记日志，而是触发自愈。"""
        try:
            v = self.accept()
        except OSError as exc:
            self._on_accept_failure(exc)
            return
        if v is None:
            self._accept_failures = 0
            return

        conn, addr = v
        try:
            self.set_socket_options(conn)
        except OSError as exc:
            # 设置失败只影响这一条连接，丢弃它即可，不必重建监听 socket
            try:
                conn.close()
            except OSError:
                pass
            self._log_accept_error(exc, "设置连接选项")
            return

        self._accept_failures = 0
        addr = self.fix_addr(addr)
        self.channel_class(self, conn, addr, self.adj, map=self._map)

    def _on_accept_failure(self, exc):
        self._accept_failures += 1
        self._log_accept_error(exc, "accept()")

        # 退避：失败越多睡得越久，避免 select() 立刻返回造成 CPU 忙循环。
        # 监听 socket 已失效，此时服务本身就不健康，短暂阻塞是可接受的。
        if self._accept_failures >= 2:
            time.sleep(min(0.05 * self._accept_failures, MAX_ACCEPT_BACKOFF))

        if self._accept_failures >= REBUILD_THRESHOLD and self._rebuild():
            self._accept_failures = 0

    def _log_accept_error(self, exc, context):
        """同类错误按时间窗口节流，避免日志风暴。"""
        now = time.monotonic()
        if now - self._last_error_log_at >= LOG_THROTTLE_INTERVAL:
            suppressed = self._suppressed_errors
            self._suppressed_errors = 0
            self._last_error_log_at = now
            extra = f"（期间已抑制 {suppressed} 条同类日志）" if suppressed else ""
            log.warning("[网络自愈] %s 失败: %s%s", context, exc, extra)
        else:
            self._suppressed_errors += 1

    # ---------------- 自愈 ----------------

    def _rebuild(self):
        """重建监听 socket 与唤醒通道。返回是否成功。"""
        now = time.monotonic()
        if now - self._last_rebuild_at < MIN_REBUILD_INTERVAL:
            return False
        self._last_rebuild_at = now
        self._rebuild_count += 1
        log.warning("[网络自愈] 监听 socket 失效，开始第 %d 次重建…", self._rebuild_count)

        self._rebuild_trigger(force=True)
        if not self._rebuild_listen_socket():
            return False
        log.warning(
            "[网络自愈] 监听已恢复: http://%s:%s",
            self.effective_host, self.effective_port,
        )
        return True

    def _rebuild_trigger(self, force=False):
        """重建 Windows 下的 loopback 唤醒通道。返回是否成功。"""
        now = time.monotonic()
        if not force and now - self._last_trigger_rebuild_at < TRIGGER_REBUILD_INTERVAL:
            return False
        self._last_trigger_rebuild_at = now

        from waitress import trigger as trigger_mod

        old = getattr(self, "trigger", None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        try:
            self.trigger = trigger_mod.trigger(self._map)
            return True
        except Exception as exc:
            log.warning("[网络自愈] 唤醒通道重建失败: %s", exc)
            return False

    def _resolve_preferred_port(self, sockaddr):
        """确定重建时优先使用的端口。"""
        if self._preferred_port is not None:
            return self._preferred_port
        if sockaddr and len(sockaddr) > 1:
            return sockaddr[1]
        return None

    def _apply_family_options(self, family):
        if family != socket.AF_INET6:
            return
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        except OSError:
            pass

    def _try_bind(self, family, socktype, host, port):
        """在指定端口建立监听。成功返回 None，失败返回异常对象。"""
        try:
            self.create_socket(family, socktype)
            self._apply_family_options(family)
            self.set_reuse_addr()
            self.bind((host, port))
            self.accept_connections()
        except OSError as exc:
            self._detach_listen_socket()
            return exc
        return None

    def _finalize_rebind(self, family, socktype, proto, host, port, preferred):
        """重建成功后更新 sockinfo / 对外地址，必要时通知端口变化。"""
        self.sockinfo = (family, socktype, proto, (host, port))
        self._refresh_effective_addr(port)
        if preferred is not None and port != preferred:
            log.warning("[网络自愈] 原端口 %s 不可用，改用 %s", preferred, port)
            self._notify_port_change(port)

    def _rebuild_listen_socket(self):
        """丢弃失效句柄并重新 bind + listen。返回是否成功。"""
        family, socktype, proto, sockaddr = self.sockinfo
        host = sockaddr[0] if sockaddr else None
        preferred = self._resolve_preferred_port(sockaddr)

        self._detach_listen_socket()

        last_exc = None
        for port in _port_candidates(preferred):
            last_exc = self._try_bind(family, socktype, host, port)
            if last_exc is None:
                self._finalize_rebind(
                    family, socktype, proto, host, port, preferred
                )
                return True

        log.error("[网络自愈] 监听 socket 重建失败: %s", last_exc)
        self._install_placeholder(family, socktype)
        return False

    def _detach_listen_socket(self):
        """把当前监听 socket 从 select map 摘除并关闭（清理半成品也走这里）。"""
        old = getattr(self, "socket", None)
        try:
            self.del_channel()
        except Exception:
            pass
        if old is not None:
            try:
                old.close()
            except OSError:
                pass

    def _refresh_effective_addr(self, port):
        try:
            self.effective_host, self.effective_port = self.getsockname()
        except OSError:
            self.effective_port = str(port)

    def _notify_port_change(self, port):
        if self._on_port_change is None:
            return
        try:
            self._on_port_change(self.effective_host, port)
        except Exception:
            log.exception("[网络自愈] 端口变更回调执行失败")

    def _install_placeholder(self, family, socktype):
        """重建彻底失败时留一个占位 socket。

        waitress 的事件循环条件是 `while map`，若 server 不在 map 里，循环会
        直接退出、程序静默结束。占位 socket 不 listen（accepting=False），
        因此不会被 select 轮询，后续交给看门狗继续重建。
        """
        try:
            self.create_socket(family, socktype)
            self.accepting = False
        except OSError as exc:
            log.error("[网络自愈] 占位 socket 创建失败: %s", exc)

    # ---------------- 唤醒通道 ----------------

    def pull_trigger(self):
        """覆写父类：唤醒通道失效时自动重建后重试。"""
        try:
            self.trigger.pull_trigger()
        except OSError as exc:
            self._log_accept_error(exc, "唤醒通道")
            if self._rebuild_trigger(force=True):
                try:
                    self.trigger.pull_trigger()
                except OSError as retry_exc:
                    self._log_accept_error(retry_exc, "唤醒通道（重建后）")

    # ---------------- 看门狗 ----------------

    def start_watchdog(self):
        if self._watchdog_thread is not None:
            return
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, name="net-watchdog", daemon=True
        )
        self._watchdog_thread.start()

    def stop_watchdog(self):
        self._watchdog_stop.set()
        thread = self._watchdog_thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=2)

    def _watchdog_loop(self):
        # Event.wait 返回 True 表示收到停止信号
        while not self._watchdog_stop.wait(WATCHDOG_INTERVAL):
            try:
                self._watchdog_tick()
            except Exception:
                log.exception("[网络自愈] 看门狗异常")

    def _watchdog_tick(self):
        if self.accepting and self._probe_listen():
            self._watchdog_failures = 0
            return
        self._watchdog_failures += 1
        log.warning(
            "[网络自愈] 探活失败（%d/%d）",
            self._watchdog_failures, WATCHDOG_FAIL_THRESHOLD,
        )
        if self._watchdog_failures >= WATCHDOG_FAIL_THRESHOLD and self._rebuild():
            self._watchdog_failures = 0

    def _probe_listen(self):
        """向自身监听地址建立一次 TCP 连接，验证 accept 链路仍可用。"""
        host = self.effective_host
        if host in ("0.0.0.0", "::", ""):
            host = "127.0.0.1"
        try:
            port = int(self.effective_port)
        except (TypeError, ValueError):
            return False
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            return False


# ---------------- 对外接口 ----------------

def create_resilient_server(app, host="127.0.0.1", port=8765, threads=8):
    """创建带自愈能力的 waitress 服务器（不启动事件循环）。"""
    adj = Adjustments(host=host, port=port, threads=threads)
    dispatcher = ThreadedTaskDispatcher()
    dispatcher.set_thread_count(adj.threads)
    server = ResilientWSGIServer(
        app, {}, dispatcher=dispatcher, adj=adj, sockinfo=adj.listen[0]
    )
    log.info("网络层自愈已启用（accept 失败重建 + 看门狗探活）")
    return server


def serve_robust(app, host="127.0.0.1", port=8765, threads=8, on_port_change=None):
    """启动带自愈能力的服务器，阻塞直到进程退出。

    waitress 内部结构不兼容时自动回退到原生 serve()，保证不会因本模块而
    导致程序起不来。
    """
    if TcpWSGIServer is None:  # pragma: no cover - 依赖缺失兜底
        from waitress import serve
        return serve(app, host=host, port=port, threads=threads)

    try:
        server = create_resilient_server(app, host=host, port=port, threads=threads)
    except Exception as exc:  # pragma: no cover - 版本不兼容兜底
        log.warning("[网络自愈] 初始化失败，回退原生 waitress: %s", exc)
        from waitress import serve
        return serve(app, host=host, port=port, threads=threads)

    server._on_port_change = on_port_change
    server.start_watchdog()
    try:
        server.run()
    finally:
        server.stop_watchdog()
