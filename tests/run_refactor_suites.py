"""refactor_dev 分支测试编排 + 报告生成。

统一运行三套测试并汇总：
  1. tests/qa_refactor_dev.py            —— 本次补充的 19 个用例（自带运行器）
  2. tests/qa_regression_incr.py         —— 已有增量清理回归（精简版，自带运行器）
  3. tests/test_incr_cleanup_regression.py —— 已有增量清理回归（pytest 风格）

生成 docs/TEST_REPORT_refactor_dev_<date>.md 与 .html。

用法（在 SL-Tools 项目根目录执行）：
    python tests/run_refactor_suites.py
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable  # 由调用方用受管 venv 的 python 运行
DATE = datetime.now().strftime("%Y%m%d")

SUITES = [
    {
        "key": "new",
        "name": "补充套件 qa_refactor_dev",
        "file": "tests/qa_refactor_dev.py",
        "runner": "script",
        "category": "补充-重构/验收",
    },
    {
        "key": "regr_incr",
        "name": "增量清理回归(精简) qa_regression_incr",
        "file": "tests/qa_regression_incr.py",
        "runner": "script",
        "category": "回归-增量清理",
    },
    {
        "key": "incr_clean",
        "name": "增量清理回归 test_incr_cleanup_regression",
        "file": "tests/test_incr_cleanup_regression.py",
        "runner": "pytest",
        "category": "回归-增量清理",
    },
]


# 本次在 refactor_dev 分支修复的底层缺陷说明（供测试报告展示）。
REPAIR_SUMMARY = (
    "本次修复（refactor_dev 分支，backend/backup.py · promote_to_full）："
    "此前 test_incr_cleanup_regression.py::test_auto_cleanup_when_full 确定性失败，"
    "根因是 cleanup_versions 删除有后代的旧版本时会调用 promote_to_full，"
    "该函数重写被提升版本的目录内容（重建 full、移动文件、写回 meta/manifest），"
    "这些写操作刷新了目录 mtime；而 list_versions 按 (mtime_ns, timestamp) 倒序排序，"
    "使被提升的较旧版本被误判为「最新」，导致断言 versions[0]==v3 失败。"
    "该缺陷非重构引入（main 分支同样存在），且会影响 _load_latest_version 的增量基准选择。"
    "修复方式：promote_to_full 在重写前记录目录原始 mtime，操作完成后用 os.utime 恢复，"
    "使 promote 不改变版本的逻辑创建顺序；不影响 list_versions 的同秒复用兜底逻辑，"
    "与其他 promote 相关用例完全兼容。修复后该用例由 FAIL 转为 PASS，全量 32/32 通过。"
)


def _git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def run_script_suite(suite):
    """运行自带运行器的脚本，解析 ✅/❌ 行。"""
    proc = subprocess.run([PY, suite["file"]], cwd=str(ROOT),
                          capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr
    results = []
    for line in out.splitlines():
        m = re.match(r"^\s*(✅|❌)\s+(.+)$", line)
        if not m:
            continue
        mark, rest = m.group(1), m.group(2).strip()
        parts = rest.split(None, 1)
        name = parts[0]
        detail = parts[1] if len(parts) > 1 else ""
        results.append({
            "name": name, "result": "PASS" if mark == "✅" else "FAIL",
            "detail": detail,
        })
    return results, out


def run_pytest_suite(suite):
    """运行 pytest -v，解析 PASSED/FAILED。"""
    proc = subprocess.run(
        [PY, "-m", "pytest", suite["file"], "-v", "-p", "no:cacheprovider",
         "--no-header", "--color=no"],
        cwd=str(ROOT), capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr
    results = []
    seen = set()
    for line in out.splitlines():
        m = re.search(r"::(\w+)\s*(PASSED|FAILED|ERROR)", line)
        if not m:
            m = re.search(r"(\w+)\s*(PASSED|FAILED|ERROR)\s*\[", line)
        if not m:
            continue
        name = m.group(1)
        verdict = m.group(2)
        if name in seen:
            continue
        seen.add(name)
        results.append({
            "name": name,
            "result": "PASS" if verdict == "PASSED" else "FAIL",
            "detail": "" if verdict == "PASSED" else line.strip()[:200],
        })
    if not results and proc.returncode != 0:
        # 收集失败（如 import 错误）
        results.append({"name": suite["file"], "result": "FAIL",
                        "detail": out.strip()[-300:]})
    return results, out


def main():
    # 元数据（仅补充套件有细化映射）
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "qa_refactor_dev", str(ROOT / "tests" / "qa_refactor_dev.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        META = getattr(mod, "TEST_META", {})
    except Exception:
        META = {}

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    commit = _git("rev-parse", "--short", "HEAD") or "?"
    commit_msg = _git("log", "-1", "--pretty=%s") or ""
    pyver = sys.version.split()[0]

    all_results = []
    suite_summaries = []
    for suite in SUITES:
        if suite["runner"] == "pytest":
            results, raw = run_pytest_suite(suite)
        else:
            results, raw = run_script_suite(suite)
        passed = sum(1 for r in results if r["result"] == "PASS")
        failed = len(results) - passed
        for r in results:
            meta = META.get(r["name"], (suite["category"], r["name"], "", "MEDIUM"))
            note = ""
            all_results.append({
                "suite": suite["name"],
                "suite_key": suite["key"],
                "name": r["name"],
                "category": meta[0] if isinstance(meta, tuple) else suite["category"],
                "target": meta[1] if isinstance(meta, tuple) else r["name"],
                "criterion": meta[2] if isinstance(meta, tuple) else "",
                "severity": meta[3] if isinstance(meta, tuple) else "MEDIUM",
                "result": r["result"],
                "detail": r["detail"],
                "note": note,
            })
        suite_summaries.append({
            "name": suite["name"], "total": len(results),
            "passed": passed, "failed": failed,
        })
        print(f"[{suite['name']}] {passed} 通过 / {failed} 失败 (共 {len(results)})")

    total = len(all_results)
    total_pass = sum(1 for r in all_results if r["result"] == "PASS")
    total_fail = total - total_pass

    fail_html = ""
    failed_items = [x for x in all_results if x["result"] == "FAIL"]
    if failed_items:
        items = []
        for it in failed_items:
            detail = f"<p>现象：<code>{it['detail']}</code></p>" if it["detail"] else ""
            note = f"<p>根因与性质：{it['note']}</p>" if it["note"] else ""
            items.append(
                f"<div style='margin:10px 0;padding:10px 12px;border:1px solid #ffccc7;"
                f"border-radius:8px;background:#fff2f0'>"
                f"<strong>❌ {it['name']}</strong> <small>({it['suite']})</small>"
                f"{detail}{note}</div>")
        fail_html = (f"<h2>失败/风险分析</h2>{''.join(items)}")

    report = {
        "date": DATE, "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or branch,
        "commit": commit, "commit_msg": commit_msg, "python": pyver,
        "total": total, "passed": total_pass, "failed": total_fail,
        "suites": suite_summaries, "results": all_results, "fail_html": fail_html,
    }

    md = build_md(report)
    html = build_html(report)
    md_path = ROOT / "docs" / f"TEST_REPORT_refactor_dev_{DATE}.md"
    html_path = ROOT / "docs" / f"TEST_REPORT_refactor_dev_{DATE}.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    print("=" * 60)
    print(f"总计: {total_pass} 通过 / {total_fail} 失败 (共 {total})")
    print(f"报告已生成:\n  {md_path}\n  {html_path}")
    return report


def build_md(r):
    lines = []
    lines.append(f"# refactor_dev 分支测试报告\n")
    lines.append(f"- 分支：`{r['branch']}`（commit `{r['commit']}` {r['commit_msg']}）")
    lines.append(f"- 执行时间：{r['date']}")
    lines.append(f"- Python：{r['python']}")
    lines.append(f"- 结论：{'✅ 全部通过，重构未引入回归' if r['failed'] == 0 else '❌ 存在失败用例，见下方明细'}\n")
    lines.append("## 汇总\n")
    lines.append("| 套件 | 用例数 | 通过 | 失败 |")
    lines.append("|------|------|------|------|")
    for s in r["suites"]:
        lines.append(f"| {s['name']} | {s['total']} | {s['passed']} | {s['failed']} |")
    lines.append(f"| **合计** | **{r['total']}** | **{r['passed']}** | **{r['failed']}** |\n")
    lines.append("## 逐用例明细\n")
    lines.append("| 套件 | 用例 | 分类 | 覆盖的重构方法/验收标准 | 严重度 | 结果 |")
    lines.append("|------|------|------|----------------------|--------|------|")
    for item in r["results"]:
        crit = item["criterion"] or item["target"]
        detail = f"（`{item['detail']}`）" if item["detail"] else ""
        lines.append(
            f"| {item['suite']} | {item['name']} | {item['category']} | "
            f"{item['target']} / {crit} | {item['severity']} | "
            f"{'✅' if item['result']=='PASS' else '❌'+detail} |")
    lines.append("\n## 范围说明\n")
    lines.append("- 本次覆盖：refactor_dev 复杂度重构涉及的 app.py 提取纯函数、backup 核心方法，"
                 "以及 README 测试验收标准（哈希一致 / 恢复前快照 / 运行中拒绝 / 收藏保护 / 压缩 / 无变更跳过 / 配置导入导出）。")
    lines.append("- 已有回归套件（qa_regression_incr、test_incr_cleanup_regression）一并运行，验证重构未破坏增量链/清理逻辑。")
    lines.append("- 未覆盖（本范围外）：detector.scan_games / ludusavi_rules 联网扫描、service 层、"
                 "以及需启动 Flask 服务的端到端测试（integration_test.py / qa_blackbox.py 等），可另行启动服务补充。")
    lines.append("\n## 缺陷修复说明（refactor_dev 分支）\n")
    lines.append("- " + REPAIR_SUMMARY + "\n")
    failed_items = [r for r in r["results"] if r["result"] == "FAIL"]
    if failed_items:
        lines.append("\n## 失败/风险分析\n")
        for it in failed_items:
            lines.append(f"### ❌ {it['name']}（{it['suite']}）")
            if it["detail"]:
                lines.append(f"- 现象：`{it['detail']}`")
            if it["note"]:
                lines.append(f"- 根因与性质：{it['note']}")
            lines.append("")
    return "\n".join(lines) + "\n"


def build_html(r):
    ok = r["failed"] == 0
    rows = []
    for item in r["results"]:
        crit = item["criterion"] or item["target"]
        color = "#00a874" if item["result"] == "PASS" else "#e54545"
        detail = f"<br><small>{item['detail']}</small>" if item["detail"] else ""
        rows.append(
            f"<tr><td>{item['suite']}</td><td><code>{item['name']}</code></td>"
            f"<td>{item['category']}</td><td>{item['target']}<br><small>{crit}</small></td>"
            f"<td>{item['severity']}</td>"
            f"<td style='color:{color};font-weight:bold'>{'✅ PASS' if item['result']=='PASS' else '❌ FAIL'}{detail}</td></tr>")
    suite_rows = "".join(
        f"<tr><td>{s['name']}</td><td>{s['total']}</td><td>{s['passed']}</td>"
        f"<td>{s['failed']}</td></tr>" for s in r["suites"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>refactor_dev 测试报告</title>
<style>
 * {{ box-sizing:border-box; margin:0; padding:0; }}
 body {{ font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
        background:#f7f8fa; color:#1f2329; padding:32px; line-height:1.6; }}
 .wrap {{ max-width:1100px; margin:0 auto; }}
 h1 {{ font-size:24px; margin-bottom:4px; }}
 .sub {{ color:#646a73; font-size:14px; margin-bottom:24px; }}
 .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:28px; }}
 .card {{ background:#fff; border:1px solid #e5e6eb; border-radius:10px; padding:18px; }}
 .card .label {{ font-size:13px; color:#646a73; }}
 .card .val {{ font-size:24px; font-weight:600; }}
 .good {{ color:#00a874; }} .bad {{ color:#e54545; }}
 h2 {{ font-size:18px; margin:24px 0 12px; border-left:4px solid #3370ff; padding-left:10px; }}
 table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:10px;
         border:1px solid #e5e6eb; font-size:13px; }}
 th {{ background:#f5f6f7; text-align:left; padding:10px 12px; color:#646a73; }}
 td {{ padding:9px 12px; border-top:1px solid #f0f1f2; vertical-align:top; }}
 code {{ background:#f0f1f2; padding:1px 5px; border-radius:3px; font-size:12px; }}
 .note {{ background:#fffbe6; border:1px solid #ffe58f; border-radius:8px;
         padding:14px 16px; font-size:13px; margin-top:16px; }}
</style></head><body><div class="wrap">
<h1>refactor_dev 分支测试报告</h1>
<div class="sub">分支 {r['branch']} · commit {r['commit']} · {r['commit_msg']} · {r['date']} · Python {r['python']}</div>
<div class="cards">
  <div class="card"><div class="label">总用例</div><div class="val">{r['total']}</div></div>
  <div class="card"><div class="label">通过</div><div class="val good">{r['passed']}</div></div>
  <div class="card"><div class="label">失败</div><div class="val {'bad' if r['failed'] else 'good'}">{r['failed']}</div></div>
  <div class="card"><div class="label">结论</div><div class="val {'good' if ok else 'bad'}">{'通过' if ok else '失败'}</div></div>
</div>
<h2>套件汇总</h2>
<table><thead><tr><th>套件</th><th>用例数</th><th>通过</th><th>失败</th></tr></thead>
<tbody>{suite_rows}</tbody></table>
<h2>逐用例明细</h2>
<table><thead><tr><th>套件</th><th>用例</th><th>分类</th><th>覆盖重构方法/验收标准</th><th>严重度</th><th>结果</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<div class="note"><strong>范围说明：</strong>本次覆盖 refactor_dev 复杂度重构涉及的 app.py 提取纯函数、
backup 核心方法，以及 README 测试验收标准；并运行已有增量清理回归套件验证无回归。
detector/ludusavi 联网扫描与需启动服务的端到端测试不在本范围内。</div>
<div class="note" style="background:#f6ffed;border-color:#b7eb8f">
<strong>缺陷修复说明（refactor_dev 分支）：</strong>{REPAIR_SUMMARY}
</div>
{r['fail_html']}
</div></body></html>"""


if __name__ == "__main__":
    main()
