# 存档管理工具 v2.0beta 发布前全面代码审查报告

- 审查对象：`C:\Users\Dengz\WorkBuddy\存档管理工具`（分支 `Dev`，与 `main` 无差异）
- 审查时间：2026-08-12
- 代码规模：Python 约 3900 行（12 个 .py）+ 前端约 1620 行（HTML/CSS/JS）+ 测试 620 行
- 验证基线：`integration_test.py` 54 项全通过 ✅；全部 .py 编译通过 ✅；JS 语法检查通过 ✅

---

## 一、分类问题列表

### 1. 代码规范性（Naming / Comments / Structure）

| # | 级别 | 问题 | 位置 | 说明 |
|---|------|------|------|------|
| N1 | 🟢 建议 | 未使用的 import 共 14 处 | app.py / backup.py / automation.py / ludusavi_rules.py / service.py / utils.py | `json`、`shutil`、`psutil`(app.py L160)、`traceback`、`Path`、`is_subpath`、`expand_env_path`、`safe_name`、`datetime`、`time`、`threading`、`fmt_size` 等导入后从未使用，属死代码 |
| N2 | 🟢 建议 | `import shutil`、`import json` 在 app.py 中未使用 | app.py L10-11 | 同上，且 app.py L160 `import psutil` 是函数内导入且未使用 |
| N3 | 🟢 建议 | `_read_json`/`_write_json` 兼容别名 | backup.py L41-42 | 注释称"保留旧调用名"，但仓库无历史包袱（仅 2 条提交），别名无存在必要 |
| N4 | ⚪ 提示 | 模块命名混用单复数 | backend/ | `steam_search.py` 内部函数 `_strip_name` 用 `s` 变量，`game_db.py` 数据与函数混在 918 行文件中，数据量大时可拆 `game_data.py` |
| N5 | ⚪ 提示 | 测试硬编码本机绝对路径 | tests/integration_test.py L10, L14 | `sys.path.insert(0, r"C:\Users\Dengz\...")` 与 BASE 端口写死，换机器需改代码；建议用环境变量/相对路径 |

### 2. 代码质量（Duplication / Complexity / Error Handling）

| # | 级别 | 问题 | 位置 | 说明 |
|---|------|------|------|------|
| Q1 | 🟡 重要 | **check_changes 被重复调用，大存档哈希计算翻倍** | app.py L322-326 + backup.py L450-454 | `backup_game` 先手动调 `bk.check_changes(g)`，`create_backup` 内部又调一次 `check_changes`（L451），同一次请求对同一份存档全量 SHA256 算两遍。`backup_all` 同样：service.py L59 调一次 + create_backup 内再算一次。存档文件多/大时耗时翻倍 |
| Q2 | 🟡 重要 | `_compute_current_state` 每次备份全量哈希所有文件 | backup.py L191-216 | 即使增量备份，也要先对全部文件算 SHA256 判断变更，存档几 GB 时明显卡顿。可考虑用 mtime+size 快筛（首次全量哈希，后续变更检测用 mtime 快速路径） |
| Q3 | 🟢 建议 | `check_changes` 中 `changed = max(len(full_files)-len(prev_files), 1)` | backup.py L186-188 | 变更数量用"文件数差值"估算不准确（改 1 个文件但数量不变时显示 1，实际应算哈希差异数）；且 `max(,1)` 掩盖了"删除多于新增"的负数场景，仅影响提示文案，不影响逻辑 |
| Q4 | 🟢 建议 | `_make_watcher` 函数内定义 Handler 类 | automation.py L98 | 每次建立 watcher 都重新定义类对象，可提升到模块级常量类 |
| Q5 | 🟢 建议 | `_has_descendant_using` 与 `_first_descendant` 重复扫盘 | backup.py L563-590 | 两个函数都遍历 `bdir.iterdir()` 读 meta.json，可合并为一次扫描返回后代列表 |
| Q6 | 🟢 建议 | 错误处理总体良好 | 全项目 | `BackupError`/`BackupUnchanged` 异常体系统一；恢复有"运行检测→快照→重建→回滚"完整链路；个别 except 裸吞（如 utils.read_json）符合工具定位，可接受 |
| Q7 | ⚪ 提示 | `LineCountRotatingHandler._trim` 每次超限读全文件 | app.py L68-79 | max_lines=1000 时开销可忽略，属过度设计但无害 |

### 3. 架构设计（Coupling / Extensibility）

| # | 级别 | 问题 | 位置 | 说明 |
|---|------|------|------|------|
| A1 | 🟢 建议 | `app.py` 仍有业务逻辑未下沉到 service 层 | app.py L159-175 `_dir_size_human`、L409-449 打开白名单 | 文件管理器白名单逻辑放路由层，可移入 service 便于测试复用 |
| A2 | 🟢 建议 | `store` 全局单例 + 模块级缓存 `_versions_cache` | config.py L144 / backup.py L530 | 单例便于快速开发，但多实例/测试隔离性弱；当前规模可接受，若后续做多用户或 CLI 需重构为依赖注入 |
| A3 | ⚪ 提示 | 架构分层总体合理 | 全项目 | app.py（路由薄壳）→ service.py（业务编排）→ backup.py（领域核心）→ utils/config（基础设施），单向依赖无环；增量链重构（promote_to_full/reconstruct）设计扎实，`base_dir` 修复（用目录名而非时间戳）是正确的坑位修复 |
| A4 | ⚪ 提示 | 扩展点清晰 | backup.py | 新增备份类型只需扩展 `_decide_backup_kind` + manifest kind 字段；游戏规则库（内置/ludusavi/steam）三源合并设计良好 |

### 4. 安全性（Security）

| # | 级别 | 问题 | 位置 | 说明 |
|---|------|------|------|------|
| S1 | 🔴 严重 | **STEAM_APPIDS 数据错误：ASTLIBRA appid 写成了 Starfield 的 1716740** | game_db.py L799 | 已联网核实：神之天平 (ASTLIBRA Revision) 正确 appid 为 **1718570**，`1716740` 是 Starfield。会导致 ASTLIBRA 的图标错误显示为 Starfield 封面。发布前必须修正 |
| S2 | 🟡 重要 | 配置文件导入未做类型校验 | app.py L482-503 | `/api/config/import` 对 `settings` 仅白名单键名，未校验值类型（如 backup_root 传入数字会直接写入）；游戏对象也未校验必填字段类型。本地工具风险低，但导入损坏 JSON 可能产生脏配置 |
| S3 | 🟢 建议 | 打开白名单基于"解析后路径集合相等" | app.py L436 | `target_resolved not in allowed and target not in allowed` 逻辑正确，但 `_allowed_open_paths` 每次重新收集（性能可缓存）；同时注意 Windows 大小写/短路径（8.3）可能导致误判，实际影响极小 |
| S4 | ⚪ 提示 | 无 CSRF/认证（本地回环工具合理） | app.py | 仅绑定 127.0.0.1，无跨站风险面；`/api/init` 清空备份有前端双重确认，符合定位 |
| S5 | ⚪ 提示 | 防循环递归保护完整 | backup.py L397-417 | 备份目录/存档路径双向 `is_subpath` 检测 + 自动化跳过 + 保存设置警告，三层防护到位 |

### 5. 性能优化空间（Performance）

| # | 级别 | 问题 | 位置 | 说明 |
|---|------|------|------|------|
| P1 | 🟡 重要 | `_dir_size_human` 每次 GET /api/settings 全盘遍历备份目录 | app.py L159-175 | 备份目录上千文件时每次打开设置页都 os.walk 全量统计，可加 TTL 缓存（如 60s） |
| P2 | 🟢 建议 | `is_game_running` 每次遍历所有进程 | utils.py L46-63 | 恢复/备份时调用，进程多时数百次 psutil 查询；可缓存进程名集合（1-2s TTL） |
| P3 | 🟢 建议 | 前端 `selectGame` 每次都重新 GET /api/settings | app.js L245 | 每选一个游戏就拉一次设置（含目录大小统计），可缓存或仅在详情需要时拉取 |
| P4 | ✅ 已优化 | 版本列表 5s TTL 缓存 / 前端 8s 轮询 counts / ludusavi 逐行解析（避 50s 全量 YAML） | 各处 | 这些是已落地的优秀优化，保持 |
| P5 | ✅ 已优化 | 后台线程联网扫描不阻塞启动 | app.py L535-555 | 首次启动秒开，增强后到，体验正确 |

---

## 二、量化打分

| 维度 | 权重 | 得分 | 一句话依据 |
|------|------|------|-----------|
| 代码规范性 | 15% | **85** | 命名清晰、注释到位、目录规整；扣分：14 处未使用 import、兼容别名、测试硬编码路径 |
| 代码质量 | 25% | **82** | 异常体系/恢复链路优秀；扣分：check_changes 重复计算、全量哈希无快筛、重复扫盘 |
| 架构设计 | 25% | **90** | 分层单向依赖、增量链设计扎实、扩展点清晰；扣分：全局单例、少量业务滞留路由层 |
| 安全性 | 25% | **78** | 防递归/白名单/双重确认到位；扣分：**S1 图标数据错误**（发布阻断）、导入类型校验缺失 |
| 性能优化 | 10% | **85** | 缓存/并发/逐行解析等优化已落地；扣分：设置页全盘统计、进程检测无缓存 |

### 总分

> **综合评分 = Σ(维度分 × 权重) = 85×0.15 + 82×0.25 + 90×0.25 + 78×0.25 + 85×0.10 = 12.75 + 20.5 + 22.5 + 19.5 + 8.5 = 83.8 / 100**

**评级：🟡 有条件通过（Conditional Pass）** — 核心功能正确、架构健康，但存在 1 个发布阻断项（S1 数据错误）与 2 个应修复项（Q1 重复计算、S2 导入校验），修复后可发布。

---

## 三、量化评分标准说明

### 分级规则

| 评级 | 综合分 | 判定 |
|------|--------|------|
| 🟢 通过 | ≥ 90 | 无阻断项，可直接发布 |
| 🟡 有条件通过 | 80 - 89 | 无 Critical 阻断，但存在应修复项，修复后发布 |
| 🟠 暂缓发布 | 70 - 79 | 存在阻断项或架构/安全重大隐患 |
| 🔴 不通过 | < 70 | 存在数据丢失/安全漏洞/架构问题，必须重构 |

### 各维度评分标准（每维度 100 分）

**代码规范性（权重 15%）**
- 90+：命名一致、注释聚焦非显然逻辑、目录职责单一、无死代码
- 80-89：存在少量未使用 import / 冗余别名 / 硬编码，但不影响理解
- 70-79：命名混乱或注释误导或死代码较多
- <70：命名/结构明显随意，可读性受损

**代码质量（权重 25%）**
- 90+：无重复计算、复杂度受控、错误路径全覆盖
- 80-89：存在 1-3 处重复/冗余计算（如 check_changes 双算），但异常处理与边界条件到位
- 70-79：存在逻辑缺陷或错误处理漏洞
- <70：存在功能性 bug 或明显数据不一致风险

**架构设计（权重 25%）**
- 90+：分层清晰、依赖单向、扩展点明确、核心算法设计扎实
- 80-89：整体健康，存在全局单例/少量业务滞留等可接受瑕疵
- 70-79：存在循环依赖或模块职责模糊
- <70：耦合严重或扩展困难

**安全性（权重 25%）**
- 90+：输入校验完备、无数据错误、危险操作多重确认
- 80-89：有少量校验缺失，但无实际利用面
- 70-79：存在发布阻断级问题（数据错误/路径穿越/权限缺失）
- <70：存在可被利用的漏洞或数据损坏风险

**性能优化（权重 10%）**
- 90+：热点路径有缓存/并发/降级策略，无重复 I/O
- 80-89：主要热点已优化，存在少量可缓存的重复计算
- 70-79：存在明显性能瓶颈（如每次请求全盘扫描）
- <70：存在 N+1 或阻塞式全量操作无任何缓存

### 级别定义

- 🔴 **严重（Critical）**：发布阻断。数据错误 / 安全漏洞 / 功能不可用
- 🟡 **重要（Important）**：应修复。影响性能 / 可靠性 / 数据正确性
- 🟢 **建议（Suggestion）**：清理类改进，不阻断发布
- ⚪ **提示（Nit/FYI）**：可选优化，供后续迭代参考

---

## 四、发布前行动清单（建议）

**必须修复（发布阻断）：**
1. [ ] S1：game_db.py L799 「神之天平 (ASTLIBRA)」appid `1716740` → `1718570`

**强烈建议修复（发布前）：**
2. [ ] Q1：`backup_game`/`backup_all` 移除对 `check_changes` 的手动预调用（create_backup 内部已做无变更检测），消除大存档双重哈希
3. [ ] S2：`/api/config/import` 增加 settings 值类型校验（backup_root/keep_versions 等按类型强制）

**建议纳入 v2.1 迭代：**
4. [ ] N1/N2：清理 14 处未使用 import
5. [ ] P1：`_dir_size_human` 加 60s TTL 缓存
6. [ ] Q5：合并 `_has_descendant_using` + `_first_descendant` 为单次扫描
7. [ ] N5：测试脚本路径/端口改为环境变量可配

**可选优化（低优先级）：**
8. [ ] P2/P3：进程检测与前端设置拉取加缓存
9. [ ] Q4：Handler 类提升到模块级
10. [ ] N3/N4：删除兼容别名；game_db.py 数据拆分
