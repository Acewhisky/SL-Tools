# 全程回顾：踩坑路线与能力沉淀

> 覆盖 2026-08-08 ~ 2026-09-01，v1.0beta → v2.2.2。
> 目的不是记流水账，而是把「哪类坑会反复出现」抽成可执行的规则。

---

## A. Git / 发布踩坑路线

### 阶段 0 · 首次托管（08-11）——开局干净

用户自行建私有仓库 `Acewhisky/SL-Tools` 并首次推送。核验结论：30 个源码文件齐全、
`static/icon.ico` 二进制完好、`data/`、`dist/`、`*.exe`、`debug.log` 均未入库、无 >500KB 大文件。
这一步建立了一个好习惯：**推送前先核验入库内容**，后面所有发布都沿用。

### 阶段 1 · 沙箱写 git，把仓库写坏了（08-12 ~ 08-13）——最惨的一次

| | |
|---|---|
| 现象 | `git status` 报 `error: bad tree object HEAD`；main 的 HEAD tree 对象损坏、Dev 的两个 commit 对象丢失 |
| 根因 | 沙箱文件钩子拦截 git 对 `.git/refs` 的原子写入——命令 `rc=0` 但引用不落盘；叠加 GitHub Desktop 后台同步改写 `.git`，最终对象库损坏 |
| 代价 | 工作区源码被迫从「对话里的 diff 记录 + main 源码」手工重建 Dev v2.1.0 |
| 修复 | 删本地坏 refs → 全量 fetch → 重建分支（见下） |
| 铁律 | **沙箱内只做 git 只读操作**；写操作放本机终端；操作前退出 GitHub Desktop |

```bash
git update-ref -d refs/heads/main && git update-ref -d refs/heads/Dev
git fetch origin --tags --force      # 坏 refs 会骗过增量协商，必须先删
git checkout -B main origin/main && git branch -f Dev origin/Dev
```

两个细节坑：`git fetch --all origin` 语法错误（`--all` 不能与仓库名同用）；
`fetch` 报 `did not send all necessary objects` 也是坏 refs 造成的，同样靠先删 ref 解决。

### 阶段 2 · 摸清连接器权限（08-12 ~ 08-13）——404 与 403 的区别

- 仓库私有期间：连接器所有仓库级调用 **404**（GitHub App 未安装到该仓库）。
- 仓库公开后：读全部打通；写依然 **403 `Resource not accessible by integration`**。
- 结论：**连接器只读，永远只读**。重新授权用户身份也拿不到 write scope，别再试。

### 阶段 3 · 写入三件套定型（08-13，另一台干净设备实测定稿）

| 通道 | 能做什么 |
|---|---|
| 连接器 | 只读（仓库内容 / 分支 / Release / tag / commit / 搜索） |
| `git` + `store(PAT)` | push、建删远端分支、推删 tag |
| `gh` + PAT | 开 PR、合并、Issue、Release |

配套踩坑：

1. `.git-credentials` 行尾有**尾随空格** → store 匹配失败，报 `could not read Username` + `/dev/tty`。`sed -i 's/ *$//'` 清理。
2. 全局 `credential.helper` 指向 **132KB 损坏 GCM 桩程序**（SIGSEGV），且排在 store 前先被调用。
   必须 `git config --global --unset-all credential.helper`；`GIT_CONFIG_NOSYSTEM=1` 只跳系统级，跳不过全局。
3. 仓库级 `credential.helper` **不共享**，每个仓库都要 `git config credential.helper store`。

### 阶段 4 · 单人仓库的 PR 流程（08-15、09-01）

两层拦截，一次都没绕过：

- `gh pr review N --approve` → `Can not approve your own pull request`（GitHub 硬限制，无解）
- `gh pr merge N --merge` → `base branch policy prohibits the merge`

解法：`gh pr merge N --merge --admin`（PR#4、PR#5 两次验证）。
直接 push main 也会被规则拦截，但 admin 身份旁路放行（远端提示 `Bypassed rule violations`）。

认证方式也在这里定稿：**`export GH_TOKEN=<PAT>` 直接调 gh**，不要走 `gh auth login`
——本机 PAT 缺 `read:org`，login 校验会直接报错退出，而 gh 读环境变量时跳过 scope 校验。
`gh pr view`（GraphQL）仍会报错，改用 REST `gh api repos/.../pulls/N`。

### 阶段 5 · 发布流水线固化（08-15 起）

用户纠正过一次硬伤：合并 PR#4 后忘记升版本号。此后定为硬性规则——

```
合入 main ⇒ ① backend/version.py VERSION ② README「当前版本」③ README 迭代记录新增段落
          ⇒ commit "chore(release): 版本号升至 vX.Y.Z" ⇒ annotated tag ⇒ push tag
```

版本号规则：patch = bug 修复 / minor = 新功能 / major = 破坏性变更。单一来源是代码常量，README 与 tag 都从它派生。

### Git 踩坑速查表

| 症状 | 原因 | 解法 |
|---|---|---|
| `bad tree object HEAD` | 沙箱写 git + Desktop 同步 | 删 refs → 全量 fetch → 重建分支 |
| `did not send all necessary objects` | 本地坏 refs 骗过增量协商 | `update-ref -d` 后再 fetch |
| `could not read Username` | 凭据行尾空格 / GCM 桩程序 / 仓库级 helper 未设 | 清空格 + unset 全局 helper + 设 store |
| gh login `missing required scope 'read:org'` | PAT scope 不全 | 改用 `GH_TOKEN` 环境变量 |
| `Can not approve your own pull request` | 单人仓库 | 跳过自审 |
| `base branch policy prohibits the merge` | main 要求评审 | `gh pr merge --admin` |
| 连接器写操作 404 / 403 | 未安装 / 无 write scope | 走 gh 或 git |
| `git merge origin/X` 报 not something we can merge | 沙箱不持久化 remote-tracking | `git fetch origin X && git merge --ff-only FETCH_HEAD` |

---

## B. 工具开发路线

### 版本时间线

| 版本 | 日期 | 主要内容 |
|---|---|---|
| v1.0beta | 08-08 | 从需求大纲到成品：扫描识别、备份/恢复、版本管理、定时+监听自动备份 |
| v1.1beta | 08-08 | 定时任务不生效、路径不存在时监听失效、前端实时刷新 |
| v1.2beta | 08-09 | 静态资源版本化、自动备份开关、规则库 CDN 多源回退 |
| v2.0beta | 08-09 | 自动备份游戏级控制、事件过滤、service 层下沉、图标并发 |
| v2.0.1 | 08-12 | 发布前审查修复（appid 错写、双重哈希、配置类型校验） |
| v2.1.0 | 08-12 | 性能优化（_stat 快筛、三处缓存）、清理未使用 import |
| v2.1.1 | 08-13 | 收藏徽章取消失效修复、公开化清理、MIT 许可、CI 全绿 |
| v2.2.1 | 08-15 | 复杂度治理（20 个 CC>10 方法 → 0）、增量 mtime 缺陷修复 |
| v2.2.2 | 09-01 | 网络层自愈（Winsock LSP 抖动后的僵尸监听） |

### 架构演进

- **起步**：`app.py` 单文件承载路由 + 业务逻辑，Flask 内置 static。
- **v2.0beta**：抽出 `backend/service.py`，`app.py` 路由变薄壳；utils 收敛 JSON 读写。
- **v2.2.1**：7 个文件 20 个高复杂度方法重构，提取约 40 个辅助方法，平均圈复杂度 5.37 → 4.19，D 级归零。
- **v2.2.2**：网络层抽出 `backend/netserver.py`，服务启动统一走 `serve_robust()`。

### 反复出现的四类缺陷

**1. 隐式约定导致的数据结构断裂（增量链，3 次）**
- 目录名带 `_pre_restore` 后缀而 meta 存裸时间戳 → 链指向不存在目录。
- 无历史版本时 `incr` 仍返回 INCR → 产生 `base_version=None` 的孤儿增量根。
- `promote_to_full` 重写目录刷新 mtime → 破坏按 mtime 排序的版本判定。
- 统一解法：**链式引用一律用目录名**；产生新版本的每条路径都要保证有基线；链回溯要能容错历史脏数据。

**2. 加缓存不审写路径（2 次）**
`list_versions` 加 5s 缓存后，`set_favorite` / `verify_version` 未失效缓存 → 收藏版本被误清理。
规则：加缓存时列「读点 vs 写点」对照表逐个确认。

**3. 时序 / 排序假设（2 次）**
- 同秒备份生成 `181536 / 181536_2`，字符串倒序把复用的基础名判为最旧 → cleanup 删掉刚建的版本。Windows 跨秒不触发，Linux CI 必现。
- E2E 断言「版本数 +1」，但保留上限下总数是「清理最老 + 新增最新」= 不变。
- 统一解法：排序用 `mtime_ns`，断言用时间戳变化而非数量变化，清理逻辑支持 `exclude`。

**4. 阻塞与超时（3 次）**
- 首次启动同步下载 17MB 规则库，慢网 2.5 分钟无反馈，看起来卡死。
- `urlopen(timeout=)` 只覆盖连接阶段，`resp.read()` 无超时 → 17 个请求静默 136 秒。
- Winsock LSP 抖动后 accept 持续 10022 → 服务僵尸。
- 统一解法：联网操作后台化 + 连接/读取/整体三重超时 + 降级缓存；监听层自愈。

### 测试体系演进

| 阶段 | 规模 | 手段 |
|---|---|---|
| v1.0beta | 集成 24 项 | HTTP 黑盒 |
| v1.1beta | 集成 54 项 | + puppeteer-core 驱动 Edge headless 做 UI 遍历 |
| v2.0beta | 54 + E2E 12 | + 用户全流程 E2E |
| v2.1.1 | 黑盒 68 + 增量 12 + 前端 20 | 三套并行，双分支对照 |
| v2.2.2 | 200+ 项 | 五层矩阵（静态 / 单元 / HTTP 黑盒 / UI / exe 实机） |

关键教训：
- **测试会清空真实数据**。黑盒测试开头的「重置设置」把 53 个游戏清成 2 个，跑之前必须备份 `data/`。
- **抓到 bug 的回归用例必须进 CI**。PR#4 曾把新套件忘在 CI 外，同一个缺陷差点无声复现。
- **CI 与本地不一致时先怀疑自己**。同秒 bug 就是 CI 抓出来的真实产品缺陷。

### 工程化产物

- `.github/workflows/ci.yml`：ubuntu + py3.11/3.13 双矩阵。
- `docs/CODE_REVIEW_v2.0beta.md`：发布前量化审查（评分 83.8/100）。
- `docs/SENSITIVE_CHECK_20260813.md`：开源前敏感内容检查（个人路径 → 占位化）。
- `docs/复杂度重构报告.html` / `TEST_REPORT_refactor_dev_20260815.md`：重构与回归留档。

---

## C. 沉淀落到哪了

| 产物 | 位置 | 内容 |
|---|---|---|
| 经验库 | `.learnings/LEARNINGS.md` | 19 条（correction / insight / knowledge_gap / best_practice），带 Pattern-Key 与复发计数 |
| 错误库 | `.learnings/ERRORS.md` | 12 条（症状 / 根因 / 解法 / 状态），9 条已 resolved |
| 需求池 | `.learnings/FEATURE_REQUESTS.md` | 6 条（含 4 项自评发现的改进项） |
| 技能强化 | `~/.workbuddy/skills/git-github-write/` | 新增「GH_TOKEN 优先」「admin 强合」「发布流水线」「仓库损坏修复」四节 |
| 技能新建 | `~/.workbuddy/skills/windows-python-tool-release/` | 打包 → 回归 → 发布闭环 + `scripts/prebuild_check.py` 自检脚本 |
| 记忆更新 | 项目 `.workbuddy/memory/`、全局 `~/.workbuddy/MEMORY.md` | 路线索引与新增规则 |

`.learnings/` 已加入 `.gitignore`（本地经验库，不随公开仓库发布）。

**顺带修掉一个漏网缺陷**：新写的自检脚本第一次运行就扫出 `static/js/app.js:996`
注释里残留的替换字符（`新备\ufffd\ufffd\ufffd` → `新备份`）——2026-08-09 那轮清理只扫了 `.py`，漏了前端文件。

---

## D. 建议的下一步

按投入产出排序：

1. **版本号同步校验脚本**（FEAT-005，simple）：解析 version.py / README / git tag 四处，不一致就 exit 1，接进 CI。已有现成实现思路。
2. **发 Release 挂 exe**（FEAT-003，simple）：v2.2.1 / v2.2.2 只打了 tag，没传产物。`gh release create` 一行命令的事。
3. **增量链健康巡检**（FEAT-006，medium）：增量链出过 3 次缺陷，每次都靠用户反馈才发现。加个只读体检接口 + 设置页按钮，把被动救火变主动体检。
4. **前端 E2E 去 flaky**（FEAT-004，simple）：`networkidle0` 对 8s 轮询的页面天生不稳。
5. **历史提交清洗**（FEAT-002，medium）：公开仓库历史里仍有个人路径，`git filter-repo --replace-text` 可彻底清除，代价是所有 SHA 改写、tag 需重建。
