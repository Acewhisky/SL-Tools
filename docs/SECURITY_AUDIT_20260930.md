# 安全审计报告 — 存档管理工具

| 项 | 值 |
|---|---|
| 审计对象 | `存档管理工具`（Flask + waitress 本地游戏存档备份工具） |
| Source ref | `25a9241` — `chore(release): 版本号升至 v2.2.3`，worktree 含未提交改动（见文末） |
| 审计日期 | 2026-09-30 |
| 审计方式 | 静态源码审查（`security-audit` skill，guidance mode） |
| 覆盖声明 | **部分覆盖（partial）**。未执行目标代码、未对运行中的服务发起请求。 |

## 审计方法与限制

本报告**不包含**任何可直接复制的攻击载荷；只描述代码层面的事实与修复方向。

**为什么是静态审查**：`security-audit` skill 要求执行目标代码时必须有 OS 强制沙箱（禁外网、空环境、只读目标、资源上限）。本机为 Windows，无法满足该前提（且该 skill 附带的两个校验器在 win32 下因缺少 `O_NOFOLLOW`/`O_NONBLOCK` 而主动失败关闭）。按 skill 自身的 `Universal execution safety` 规则，控制项无法全部满足时**不得执行目标代码**，降级为只读源码审查。

因此本报告中：

- **confirmed** = 结论完全由源码事实支撑（缺失某段控制逻辑，属可直接核对的白盒事实）。
- **needs_validation** = 需要动态触发或运行环境信息才能定论，按 skill 规则**不给严重度**。

## 信任边界

| | 主体 |
|---|---|
| 低信任 | 用户浏览器访问到的**任意第三方网页**；本机其他非特权进程 |
| 高信任 | `127.0.0.1:<port>` 本地 HTTP 服务，及其对本机文件系统的读写能力 |

服务在 `app.py:main()` 中**硬编码 `host = "127.0.0.1"`**，仅监听回环，局域网不可达——这是本项目的关键正确决策，它把攻击面从「同网段任何人」收窄到「本机浏览器 / 本机进程」。

---

## 已确认发现

### H1 — 全部写操作路由无跨站请求防护（High）

**事实**：全部 26 个路由均无 CSRF token、无 `Origin`/`Referer` 校验，且不存在任何 `before_request` / `after_request` 钩子。

**放大的因素**：业务代码统一使用 `request.get_json(force=True, silent=True)`。`force=True` 会**忽略 Content-Type** 强制解析 body。这使得浏览器可以用「简单请求」（`text/plain` 携带 JSON body）发起写请求——简单请求不触发 CORS 预检，因此**不需要目标服务授予任何跨域许可**就能真实送达并生效。

**后果**：低信任主体（任意网页）可通过用户浏览器驱动本服务执行写操作。结合 H2，可达任意路径写入。

**修复状态**：**已修复**，见文末「修复内容」。

### H2 — `save_paths` 无路径校验，最终落到无校验的任意路径写入（High）

**事实**（逐环核对）：

| 环节 | 位置 | 校验情况 |
|---|---|---|
| 游戏字段校验 | `app.py` `_validate_game_fields` | 仅校验 `name` 非空、`paths` 非空，**不校验路径位置** |
| 列表清洗 | `app.py` `_clean_str_list` | 仅 `strip()` 去空白 |
| 配置导入 | `app.py` `_import_games` | 遍历后直接 `store.upsert_game(g)`，**零路径校验** |
| 恢复写入终点 | `backend/backup.py` `_apply_reconstruct_to_targets` | **完全无校验**：直接 `t.parent.mkdir(parents=True)` → `_merge_copy(src, t)` → `_prune_extra(src, t, removed)` |

`restore_backup` 的写入目标取自 `v.get("source_paths", game.get("save_paths", []))`，即版本元数据记录的来源路径，回退到当前 `save_paths`。

**后果**：`_prune_extra` 会**删除**目标目录中不存在于源的文件，因此这不只是越权写入，而是**破坏性**操作（可删除用户数据）。

**注**：本项与 H1 构成完整链条。H1 修复后，触发本项需要本机进程权限——而本机进程本就有同等文件权限，**不构成信任边界跨越**，故 H2 的独立可利用性大幅下降。但「写入目标缺少独立校验」本身仍是纵深防御缺口，建议按下方建议补齐。

**修复状态**：**已修复**——引入 `validate_restore_target()` 基线校验（详见「修复内容」）。

### M1 — `/api/open` 的路径白名单是「自证式」的（Medium）

**事实**：`app.py` `_allowed_open_paths()` 构造的允许列表 = `backup_root` + 各游戏 `save_paths` + 各游戏备份目录。而其中 `backup_root` 与 `save_paths` 本身可被未鉴权 API 改写（见 H2、M2）。

**结论**：该白名单由被保护对象自身推导而来，**不构成独立的信任边界**——它能表达「这是应用自己配置过的路径」，但不能表达「这是安全可打开的路径」。

**已确认的部分**：终端调用 `subprocess.Popen(["explorer.exe", str(path)])` 使用**列表形式、未使用 `shell=True`**，因此**不存在命令注入**。（补充：Windows 下 `explorer.exe` 若被指向 `.exe` 会执行该文件，故白名单的强度直接决定了此项的实际后果。）

**修复状态**：**已修复**——改为白名单 + `validate_restore_target()` 双重要件。

### M2 — `/api/settings` 的 `backup_root` 无路径校验（Medium）

**事实**：`app.py` `save_settings()` 的 `allowed` 集合包含 `backup_root`，赋值时**无任何路径合法性/位置校验**。其后所有备份写入、版本列举与清理（`cleanup_versions`）都以该值为根。

**修复状态**：未修复。

### L1 — 归档解压未校验成员路径（Low / hardening）

**事实**：`backend/backup.py` `_materialize_full()` 使用 `zf.extractall(dest)` 与 `tf.extractall(dest)`，未逐项校验成员路径，理论上存在 Zip Slip / Tar Slip 逃逸面。

**为什么只记 hardening note**：当前归档由应用自身在备份阶段创建，不是外部输入。按审计标准，缺少某一层防护但上层仍有效时只记 hardening note，不升格为漏洞。

**修复状态**：未修复，建议后续加成员路径校验。

---

## 未决事项（needs_validation，无严重度）

1. **H1 利用链的端到端动态验证未执行**。源码层面「无防护」是已确认事实，且修复后的拦截行为已实测（见下）；但「从真实浏览器跨源发起」这一末端环节按沙箱规则未复现。
2. **生产部署形态未知**。若实际以 exe 分发且经反向代理 / 端口转发暴露到非回环地址，H1、H2 的风险等级需重估。当前源码恒为 `127.0.0.1`，未见此类路径。
3. **现网配置已核对（本次补充）**：用本机真实 `games.json` 跑过 H2 基线——3 个游戏 / 3 条存档路径**全部放行（0 误伤）**，`backup_root` 也被正确识别为禁止目标。后续新增游戏或迁移备份目录时，建议重跑一遍该核对（脚本见 `tests/test_restore_target_guard.py` 的同源用例）。

---

## 修复内容（本次已实现）

三块修复，涉及 `app.py` 与 `backend/backup.py`，**均为纯新增，未修改任何既有逻辑**。

### H1 — 来源校验（app.py，+74 / -0）

新增 `_guard_local_origin()` 作为 `@app.before_request` 钩子，两层防护：

1. **Host 头必须为回环名**（`127.0.0.1` / `localhost` / `::1`）——阻止 DNS rebinding：攻击者域名解析到 `127.0.0.1` 时 Host 会是攻击者域名，直接拒绝。
2. **写方法（POST/PUT/DELETE/PATCH）必须来自本机页面**——校验 `Origin`，缺失时回退 `Referer`，阻止 CSRF。

设计要点：

- **刻意不校验端口**：端口会因占用（`_find_free_port`）或网络自愈（`_on_port_changed`）变化，硬编码端口会导致误拒。
- **无 `Origin`/`Referer` 时放行**：curl、本机脚本、E2E 测试的 Node fetch 等客户端视为本机直接调用——与之一致的是这些客户端本就有同等文件权限，不构成边界跨越。
- **归一化处理**：小写、去 FQDN 尾点（杜绝 `localhost.` 绕过）、剥离 userinfo、畸形多值头只取第一段、正确解析 `[IPv6]:port`。

### H2 — restore 写入目标基线校验（backup.py）

新增 `validate_restore_target()` / `_reject_unsafe_targets()`，在 `restore_backup` **创建安全快照之前** fail fast（避免在非法目标上白做一轮快照与版本重建），并在 `_apply_reconstruct_to_targets` 入口再校验一次作为纵深防御。

**刻意不做白名单**：用户自己的游戏目录合法且无法穷举（可能装在任何盘符、任何深度），白名单只会砸掉正常用法。改为声明「绝不允许落到这些位置」——它们的共同点是**该目录下混有大量与本存档无关的内容**，一旦落下去 `_prune_extra` 就会递归删光：

| 禁止位置 | 理由 |
|---|---|
| 磁盘根目录（`C:\`） | 全是无关数据 |
| `Windows` / `Program Files` / `Program Files (x86)` / `ProgramData` / `$Recycle.Bin` / `System Volume Information` / `PerfLogs` / `Recovery` | 系统目录，且 Windows 下 explorer 对 `.exe` 会直接执行 |
| 用户目录根（`C:\Users\<name>`） | 桌面/文档/下载都在其下 |
| `AppData` 根 | 其下 `Local` / `LocalLow` / `Roaming` **子目录**才放行 |
| `backup_root` 内部 | 写进去会连带删掉既有版本（自噬） |
| 非绝对路径 | 目标不明确 |

**保留的取舍**：`Documents` **本身放行**。不少游戏的存档路径就是 `Documents`（见 `utils.expand_env_path` 的 `%DOCUMENTS%` 映射），禁止它会破坏真实用法。这是「不砸正常功能」优先于极致收紧的主动选择。

### M1 — `/api/open` 叠加独立基线（app.py）

`_allowed_open_paths()` 的白名单由被保护对象自身推导，改为**白名单 + `validate_restore_target()` 双重要件**。即使白名单被污染到包含系统目录，上层基线仍会拦下。

### 验证结果

**H1 请求级**（探针路由 `/api/__probe__`，零副作用）：

| 用例 | 期望 | 实测 |
|---|---|---|
| 本机 GET（无 Origin） | 放行 | 200 ✅ |
| `Origin: https://evil.com` POST | 拦截 | 403 ✅ |
| `Host: evil.com` GET / POST | 拦截 | 403 ✅ |
| `Origin: null`（沙箱 iframe / `file://`） | 拦截 | 403 ✅ |
| 跨源 `Referer`（无 Origin） | 拦截 | 403 ✅ |
| `Host: 127.0.0.1.evil.com`（子域伪装） | 拦截 | 403 ✅ |
| 同源 `Origin` / `Referer`（`localhost`、`127.0.0.1`） | 放行 | 放行 ✅ |
| `[::1]:8765`、`localhost.` | 放行 | 200 ✅ |

**H2 / M1 路径级**——先看「不误伤」，这条最关键：

- 用本机**真实配置**验证：3 个游戏、3 条存档路径，被拒绝 **0 条**。
- 合法形态全部放行：`Saved Games\*`、`AppData\LocalLow\*`、`AppData\Roaming\*`、`AppData\Local\*`、`Documents\*`、`D:\Games\*`、深层嵌套、`%DOCUMENTS%` / `%SAVED_GAMES%` 占位符展开。
- 灾难形态全部拒绝：盘符根、`Windows`、`Windows\System32`、`Program Files`、`Program Files (x86)\Steam`、`ProgramData`、`$Recycle.Bin`、用户目录根、`AppData` 根、相对路径、`backup_root` 自身及其子目录。大小写变体（`WINDOWS` / `windows`）同样命中。
- `Supplement`：即使白名单被人为设成包含 `Windows`，`_resolve_open_target` 仍返回拒绝。

### 回归测试（已固化）

| 文件 | 覆盖 |
|---|---|
| `tests/test_origin_guard.py` | H1：跨源写入、Referer 回退、`null` origin、多种域名伪装、DNS rebinding、回环放行集合、`_host_of` 归一化解析 |
| `tests/test_restore_target_guard.py` | H2：灾难位置拒绝、合法路径放行、fail-fast 抛错、逐项报错、空列表；M1：白名单被污染仍拒绝 / 正常目录不误伤 / 白名单外照旧拒绝 |

两份测试的 docstring 都写明了**修改前必须理解的设计约定**（如「不校验端口」「Documents 放行」），防止后续把它们当 bug 修掉。

**回归结果**：`pytest tests/test_incr_cleanup_regression.py tests/test_netresilience.py tests/test_origin_guard.py tests/test_restore_target_guard.py` → **92 passed**。

> 说明：`test_netresilience.py::test_rebuilds_listen_socket_after_accept_failures` 在多次运行中偶发失败过 1 次。经核：该用例只 import `backend.netserver` 并使用自带的裸 WSGI `_echo_app`，**不加载 `app.py` 也不加载 `backend.backup`**，与本次改动无因果关系；连续重跑 5 次均通过，判定为环境时序 flaky（Winsock socket 重建竞态）。

---

## 后续建议（按性价比排序）

1. **`M2 — backup_root` 位置校验**（目前唯一未修的中危）。`/api/settings` POST 仍可直接改写 `backup_root` 且无任何校验；建议限定为绝对路径、排除盘符根与系统目录，并与 H2 同一套基线保持一致。
2. **`L1 — 归档解压加成员路径校验`**：`_materialize_full` 的 `extractall` 解压前逐项拒绝绝对路径、`..` 与符号链接成员。当前非外部输入，属 hardening。
3. **把 H2 的基线提升 forte 为显式确认**：对「合法但混有大量无关内容」的位置（如 `Documents` 根）可在 UI 增加二次确认，而不是一律放行。
4. 若未来需要远程访问，**必须**改为显式鉴权，而不是放宽回环绑定。

> 已完成项：H1（来源校验）、H2（restore 目标基线）、M1（`/api/open` 叠加基线）均已实现并固化回归测试，见上一节。

## 覆盖边界声明

本次为**部分覆盖**：仅对 `app.py` 与 `backend/*.py` 的静态源码做了定向审查，未覆盖 `static/` 前端脚本、`autoresearch/`、构建产物 `build/`、`dist/` 及第三方依赖。单次审查不等于穷尽，未列出的部分不代表已确认安全。
