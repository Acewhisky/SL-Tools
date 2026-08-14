# refactor_dev 分支测试报告

- 分支：`refactor_dev`（commit `4b5a696` fix(backup): 恢复 promote_to_full 后的版本目录 mtime，修复 list_versions 排序）
- 执行时间：20260815
- Python：3.13.14
- 结论：✅ 全部通过，重构未引入回归

## 汇总

| 套件 | 用例数 | 通过 | 失败 |
|------|------|------|------|
| 补充套件 qa_refactor_dev | 19 | 19 | 0 |
| 增量清理回归(精简) qa_regression_incr | 12 | 12 | 0 |
| 增量清理回归 test_incr_cleanup_regression | 7 | 7 | 0 |
| **合计** | **38** | **38** | **0** |

## 逐用例明细

| 套件 | 用例 | 分类 | 覆盖的重构方法/验收标准 | 严重度 | 结果 |
|------|------|------|----------------------|--------|------|
| 补充套件 qa_refactor_dev | test_apply_game_updates_field_types | 单元-重构 | app._apply_game_updates / update_game 类型处理 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_apply_game_updates_only_present_keys | 单元-重构 | app._apply_game_updates / update_game 提取逻辑 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_backup_restore_hash_consistent | 集成-核心 | backup.create_backup/restore_backup / 备份-恢复哈希一致 | HIGH | ✅ |
| 补充套件 qa_refactor_dev | test_build_game_from_request | 单元-重构 | app._build_game_from_request / add_game 提取逻辑 | LOW | ✅ |
| 补充套件 qa_refactor_dev | test_clean_str_list | 单元-重构 | app._clean_str_list / add_game 提取逻辑 | LOW | ✅ |
| 补充套件 qa_refactor_dev | test_compressed_zip_backup_restore | 集成-核心 | backup.create_backup(压缩) / 压缩备份/恢复 | HIGH | ✅ |
| 补充套件 qa_refactor_dev | test_config_import_export_equivalent | 集成-核心 | app._import_settings / 配置导入导出等价 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_decide_backup_kind | 单元-重构 | backup._decide_backup_kind / 首备必 full（重构） | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_favorite_protected_from_cleanup | 集成-核心 | backup.cleanup_versions / 收藏保护 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_first_backup_is_full_regardless_of_mode | 集成-核心 | backup.create_backup / 首备必 full（重构） | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_import_games | 单元-重构 | app._import_games / import_config 游戏导入 | LOW | ✅ |
| 补充套件 qa_refactor_dev | test_import_settings_invalid_types_dropped | 单元-重构 | app._import_settings / import_config 脏数据丢弃 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_import_settings_valid_and_clamped | 单元-重构 | app._import_settings / import_config 校验钳制 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_keep_versions_cleanup | 集成-核心 | backup.cleanup_versions / 版本保留 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_no_change_skips_backup | 集成-核心 | backup.check_changes/_try_skip_unchanged / 无变更跳过 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_resolve_open_target | 单元-重构 | app._resolve_open_target / open_in_explorer 白名单 | MEDIUM | ✅ |
| 补充套件 qa_refactor_dev | test_restore_creates_safety_snapshot | 集成-核心 | backup.restore_backup / 恢复前自动快照 | HIGH | ✅ |
| 补充套件 qa_refactor_dev | test_restore_rejected_when_game_running | 集成-核心 | backup.restore_backup / 运行中拒绝恢复 | HIGH | ✅ |
| 补充套件 qa_refactor_dev | test_validate_game_fields | 单元-重构 | app._validate_game_fields / add_game 字段校验 | LOW | ✅ |
| 增量清理回归(精简) qa_regression_incr | 首备 | 回归-增量清理 | 首备 / 首备 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 备份满自动清理至 | 回归-增量清理 | 备份满自动清理至 / 备份满自动清理至 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 保留版本 | 回归-增量清理 | 保留版本 / 保留版本 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 保留版本 | 回归-增量清理 | 保留版本 / 保留版本 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 删除中间版本成功 | 回归-增量清理 | 删除中间版本成功 / 删除中间版本成功 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 删除基线后直接后代 | 回归-增量清理 | 删除基线后直接后代 / 删除基线后直接后代 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | promote | 回归-增量清理 | promote / promote | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | promote | 回归-增量清理 | promote / promote | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 孤儿链 | 回归-增量清理 | 孤儿链 / 孤儿链 | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | auto | 回归-增量清理 | auto / auto | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 增量链成环保护（应报错） | 回归-增量清理 | 增量链成环保护（应报错） / 增量链成环保护（应报错） | MEDIUM | ✅ |
| 增量清理回归(精简) qa_regression_incr | 孤儿链环境备份满清理正常 | 回归-增量清理 | 孤儿链环境备份满清理正常 / 孤儿链环境备份满清理正常 | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_first_backup_with_incr_mode_is_full | 回归-增量清理 | test_first_backup_with_incr_mode_is_full / test_first_backup_with_incr_mode_is_full | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_cleanup_orphan_chain | 回归-增量清理 | test_cleanup_orphan_chain / test_cleanup_orphan_chain | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_auto_cleanup_when_full | 回归-增量清理 | test_auto_cleanup_when_full / test_auto_cleanup_when_full | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_cleanup_normal_chain_promote | 回归-增量清理 | test_cleanup_normal_chain_promote / test_cleanup_normal_chain_promote | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_manual_delete_middle_version | 回归-增量清理 | test_manual_delete_middle_version / test_manual_delete_middle_version | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_reconstruct_orphan_chain | 回归-增量清理 | test_reconstruct_orphan_chain / test_reconstruct_orphan_chain | MEDIUM | ✅ |
| 增量清理回归 test_incr_cleanup_regression | test_auto_mode_first_backup_is_full | 回归-增量清理 | test_auto_mode_first_backup_is_full / test_auto_mode_first_backup_is_full | MEDIUM | ✅ |

## 范围说明

- 本次覆盖：refactor_dev 复杂度重构涉及的 app.py 提取纯函数、backup 核心方法，以及 README 测试验收标准（哈希一致 / 恢复前快照 / 运行中拒绝 / 收藏保护 / 压缩 / 无变更跳过 / 配置导入导出）。
- 已有回归套件（qa_regression_incr、test_incr_cleanup_regression）一并运行，验证重构未破坏增量链/清理逻辑。
- 未覆盖（本范围外）：detector.scan_games / ludusavi_rules 联网扫描、service 层、以及需启动 Flask 服务的端到端测试（integration_test.py / qa_blackbox.py 等），可另行启动服务补充。

## 缺陷修复说明（refactor_dev 分支）

- 本次修复（refactor_dev 分支，backend/backup.py · promote_to_full）：此前 test_incr_cleanup_regression.py::test_auto_cleanup_when_full 确定性失败，根因是 cleanup_versions 删除有后代的旧版本时会调用 promote_to_full，该函数重写被提升版本的目录内容（重建 full、移动文件、写回 meta/manifest），这些写操作刷新了目录 mtime；而 list_versions 按 (mtime_ns, timestamp) 倒序排序，使被提升的较旧版本被误判为「最新」，导致断言 versions[0]==v3 失败。该缺陷非重构引入（main 分支同样存在），且会影响 _load_latest_version 的增量基准选择。修复方式：promote_to_full 在重写前记录目录原始 mtime，操作完成后用 os.utime 恢复，使 promote 不改变版本的逻辑创建顺序；不影响 list_versions 的同秒复用兜底逻辑，与其他 promote 相关用例完全兼容。修复后该用例由 FAIL 转为 PASS，全量 38/38 通过。

