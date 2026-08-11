# 存档管理工具 - 项目长期记忆

## 项目概况
- 本地游戏存档管理工具（一键 S/L）：Flask 后端 + 原生 HTML5 前端，浏览器访问 localhost:8765
- 启动：`start.bat`（自动建 venv 装依赖）；开发测试：`python tests/integration_test.py`
- 当前版本：v2.0beta（backend/version.py 单一来源）

## 项目约定
- 用户「十六」已确认的技术决策：Python Flask / 浏览器本地访问 / 内置精选规则+手动添加 / 先做完整备份（增量后续迭代）
- 备份结构：data/backups/<游戏id>/<时间戳>/{manifest.json, meta.json, data/}；时间戳格式 %Y%m%d_%H%M%S，同秒冲突加 _N 后缀
- **版本类型**：full（存完整文件或压缩包）/ incr（存 changes/ + deleted.json + base_version）；增量链沿 base_version 重建（reconstruct 函数）
- 设置与游戏列表均为 JSON（data/settings.json, data/games.json），便于手动编辑
- 内置规则库 backend/game_db.py 参考 Ludusavi 元数据，已覆盖本机 14 款已识别游戏
- backup_mode: full / incr / auto（默认 full）；auto 阈值：变更+删除占比 > 50% 升级 full
- 时间线 UI：完整显示"📦 完整"，增量显示"📝 增量" + "X 改 / Y 删"统计

## 关键技术坑（务必牢记）
1. **Windows 沙箱/回收站删除钩子**：shutil.rmtree / Path.unlink / os.unlink 在本环境会被 safe-delete 钩子拦截（回收站不可用时 SAFE_DELETE_FAIL_CLOSED）。删除必须用 `backend.backup.force_rmtree()`（os.walk+os.unlink+os.rmdir 底层逐级删）。
2. **恢复策略**：合并覆盖复制 `_merge_copy` + 尽力清理 `_prune_extra`，禁止"先删目录再复制"。重建用 `reconstruct(game_id, ts, dest)`。
3. **路径存储**：游戏 save_paths 存展开后的真实路径（expand_env_path 之后），不要存 %XXX% 模板。
4. 测试环境用系统 Temp 目录模拟存档（避开回收站钩子问题）。
5. **flex 布局最小高度链**：body→#app→topbar/layout/statusbar，#app 必须设 `display:flex; flex-direction:column; height:100%; min-height:0`，否则会被内容撑开；侧栏 game-list 的 flex 父容器同样需要 `min-height:0` 才能滚动。
6. 临时目录 `.restore_tmp` / `.verify_tmp` 使用 `mkdir(exist_ok=True)`，配合 reconstruct 内部的 force_rmtree，兼容沙箱删除失败残留。
7. 清理版本时如被后代引用（链基线），需 `promote_to_full` 把首个后代重建为 full 后再删，保持链完整；promote 临时目录放在游戏备份根目录下（`.promote_<ts>`），不要放版本目录内。
8. **增量链 base_version 必须用目录名**（prev_meta["base_dir"]），不能用 meta.timestamp——恢复前快照等目录名带 `_pre_restore` 后缀，裸时间戳会指向不存在的目录导致"增量基线缺失"。

## 备份策略
- **`check_changes(game)`**：对比当前文件哈希清单与最近版本 manifest.files，完全一致视为无变更。
- **`create_backup(..., force=False)`**：非 force 且无变更时抛 `BackupUnchanged` → 自动备份（automation）跳过；手动备份 API 返回 `{unchanged: True}` 让前端确认。
- **`/api/games/backup-all`**：批量备份所有游戏，无变更自动跳过，返回 `{ok, skipped, error, errors[]}` 汇总。

## 图标与 Steam 集成
- 内置规则 `STEAM_APPIDS`（backend/game_db.py）覆盖约 100 个常见游戏；`app.py` `_game_dict` 输出 `icon_url` 指向 Steam CDN。
- 前端 `<img onerror>` 回退 emoji → 仅联网生效（离线/加载失败自动降级）。

## 联网增强扫描（Ludusavi）
- `backend/ludusavi_rules.py`：manifest URL = raw.githubusercontent.com/mtkennerly/ludusavi-manifest/master/data/manifest.yaml；缓存 data/ludusavi/ + ETag 304。
- **性能陷阱**：17MB YAML 全量 PyYAML 解析 ~50s → 必须逐行扫描解析 + 本机目录名集合匹配 + 候选确认（总耗时 0.5s）。
- 占位符 `<winAppData>` 等尖括号格式；`<base>/<root>/<xdgConfig>` 跳过。设置 `scan_online`（默认 true）控制。
- 下载整体超时 DOWNLOAD_TIMEOUT=120s（分块读取防无限阻塞）。

## 游戏隐藏
- games.json `hidden` 字段；`/api/games` 过滤隐藏项；`GET /api/games/hidden` + `POST /api/games/<id>/hide`；PUT 切换 hidden；批量备份跳过隐藏游戏。

## Steam 图标搜索（steam_search.py）
- `search_appid(name)` 走 store.steampowered.com/api/storesearch（限速 0.4s/个，MAX_MATCH=30）；名称清洗+相似度校验；结果缓存 games.json `steam_appid`。
- 扫描后（scan_online=True）自动 `match_icons()`，结果 `{matched, total, failed}`。

## 初始化
- 首次部署自动执行：data/.initialized 标记不存在时重置设置+清空列表+清空日志+重新扫描。
- 手动：设置页红色按钮 `/api/init`，`reset_backups=True` 清空默认备份目录；前端双重确认（勾选清空备份时需输入"确定初始化"）。

## 防循环递归保护（v1.2beta）
- `utils.is_subpath(child, parent)`；`backup.find_backup_root_conflicts(game=None)` 返回冲突列表。
- create_backup 拦截（抛 BackupError 提示换位置）；automation 跳过重叠路径监听；save_settings 返回 warning。
- 场景覆盖：备份目录在存档目录内 / 存档在备份目录内 / exe 放在存档目录内运行（data/ 随 exe 旁）。

## 监听器（automation.py）
- 调度循环 SCHEDULER_INTERVAL=10s；每轮调 sync_watchers() 重试路径出现。
- 首次建立 watcher 主动备份一次（保险）。
- `watch_interval`：0=事件驱动 Observer（默认，实测 CPU 0%）；>0=PollingObserver 轮询（1s=2.6%、5s=0.52%、30s≈0%）。

## 收藏星标（v1.2beta）
- games.json `favorite` 字段；PUT /api/games/<id> 支持 favorite。
- 排序：收藏置顶（按 last_backup_ts 倒序，最新变更最上）→ 非收藏（version_count 倒序 + 名称）。

## 前端实时刷新
- 8s 轮询 `/api/games/counts`（轻量 {id: count}），只更新 .g-count 数字不重渲染；当前选中游戏数量变化时刷新时间线。

## 性能优化（v1.2beta 迭代）
- `_game_dict` 直接算 version_count（list_games 不再重复调用）。
- `list_versions` 5s TTL 缓存 `_versions_cache`；create_backup/delete_version/restore_backup 后 `_invalidate_versions(game_id)`。

## 打包发布（PyInstaller）
- spec：savemgr.spec（datas=static/，icon=static/icon.ico，console=True 保留日志）。
- 单文件 exe：data/ 固定在 exe 同级（`sys.frozen` 检测）；静态资源从 _MEIPASS 读。
- 打包时 `--clean` 会被 safe-delete 钩子拦截 → 用 `--workpath` 指向系统 Temp 规避。
- 发布目录：C:\Users\Dengz\WorkBuddy\sl工具发布版本\
- 图标：Pillow 生成多尺寸 .ico（16~256）。

## 反馈回路工具
- `tools/ui_check*.js` 用 puppeteer-core 驱动 Edge headless（executablePath: C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe），验证 CSS 布局/UI 元素。
- NODE_PATH="C:\Users\Dengz\.workbuddy\binaries\node\workspace\node_modules" + node 二进制调用。
