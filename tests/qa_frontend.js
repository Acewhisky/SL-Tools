// 全流程前端 UI 测试（QA 专用）：覆盖用例文档 C/H/I/M 模块的 UI 交互。
// 复用 e2e_user_flow.js 模式：Edge headless + puppeteer-core，所有等待带超时。
const puppeteer = require("C:/Users/Dengz/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core");
const fs = require("fs");
const path = require("path");

const BASE = process.env.E2E_BASE || "http://127.0.0.1:8877";
const SAVE_DIR = process.env.E2E_SAVE_DIR || path.join(process.env.TEMP || "/tmp", "qa_frontend");
const TIMEOUT_MS = Number(process.env.E2E_TIMEOUT || 60000);

let passed = 0, failed = 0;
const results = [];
function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond });
  if (cond) { passed++; console.log(`  ✅ ${name}`); }
  else { failed++; console.log(`  ❌ ${name} ${detail}`); }
}
async function waitFor(desc, fn, timeout = TIMEOUT_MS) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try { if (await fn()) return true; } catch (e) {}
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`等待超时（${timeout / 1000}s）：${desc}`);
}
async function api(method, p, body) {
  const r = await fetch(BASE + p, {
    method, headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "API 失败: " + p);
  return j.data;
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    headless: "new",
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 850 });
  const pageErrors = [];
  page.on("pageerror", e => pageErrors.push(e.message));
  page.on("console", msg => { if (msg.type() === "error") pageErrors.push(msg.text()); });

  // 干净存档目录
  if (fs.existsSync(SAVE_DIR)) fs.rmSync(SAVE_DIR, { recursive: true, force: true });
  fs.mkdirSync(SAVE_DIR, { recursive: true });
  fs.writeFileSync(path.join(SAVE_DIR, "slot.sav"), "seed");
  console.log("前端测试存档:", SAVE_DIR);

  // ---- 清理残留测试游戏 ----
  const before = await api("GET", "/api/games");
  for (const x of before) {
    if (x.name.startsWith("QA前端")) await api("DELETE", `/api/games/${x.id}`);
  }

  console.log("\n=== C 游戏管理 UI ===");
  await page.goto(BASE + "/?v=" + Date.now(), { waitUntil: "networkidle0", timeout: 15000 });
  await waitFor("游戏列表加载", () => page.$(".game-item"));

  // TC-C-001 手动添加游戏（前端表单）
  await page.click("#btn-add-game");
  await page.type("#ag-name", "QA前端测试游戏");
  await page.type("#ag-paths .form-control", SAVE_DIR);
  await page.type("#ag-procs", "testproc.exe");
  await page.click("#ag-save");
  await waitFor("新游戏出现在列表", () =>
    page.evaluate(() => [...document.querySelectorAll(".g-name")].some(e => e.textContent === "QA前端测试游戏")), 10000);
  check("TC-C-001ui 手动添加游戏（前端）", true);
  const gid = (await api("GET", "/api/games")).find(g => g.name === "QA前端测试游戏").id;

  // 选中游戏 → 详情页显示
  await page.evaluate((id) => {
    const it = [...document.querySelectorAll(".game-item")].find(i => i.dataset.id === id);
    if (it) it.click();
  }, gid);
  await waitFor("详情页显示", () =>
    page.evaluate(() => {
      const d = document.querySelector("#game-detail");
      return d && !d.classList.contains("hidden");
    }), 10000);
  check("TC-C-001b 选中游戏详情显示", true);
  await new Promise(r => setTimeout(r, 600));

  // TC-C-012 详情页自动备份开关
  const autoOn = await page.evaluate(() => {
    const el = document.querySelector("#g-auto");
    if (!el) return null;
    el.click();
    return el.checked;
  });
  await new Promise(r => setTimeout(r, 800));
  check("TC-C-012ui 自动备份开关可切换", autoOn === true, "autoOn=" + autoOn);
  const gAfter = (await api("GET", "/api/games")).find(g => g.id === gid);
  check("TC-C-012b 后端 auto_backup 已保存", gAfter.auto_backup === true);

  // TC-C-009 搜索过滤
  await page.type("#game-search", "QA前端");
  await new Promise(r => setTimeout(r, 300));
  const visCount = await page.evaluate(() => document.querySelectorAll(".game-item").length);
  check("TC-C-009ui 搜索过滤生效", visCount >= 1 && visCount <= 3, "visible=" + visCount);
  await page.evaluate(() => { document.querySelector("#game-search").value = ""; document.querySelector("#game-search").dispatchEvent(new Event("input")); });

  // TC-C-007 收藏置顶（前端星标）
  await page.evaluate((id) => {
    const btn = document.querySelector(`.game-fav-btn[data-fav="${id}"]`);
    if (btn) btn.click();
  }, gid);
  await waitFor("收藏后置顶", async () => {
    return page.evaluate((id) => {
      const items = [...document.querySelectorAll(".game-item")];
      return items.length > 0 && items[0].dataset.id === id;
    }, gid);
  }, 8000);
  const favTop = await page.evaluate((id) => {
    const items = [...document.querySelectorAll(".game-item")];
    return items.length > 0 && items[0].dataset.id === id;
  }, gid);
  check("TC-C-007ui 收藏置顶", favTop);
  await api("PUT", `/api/games/${gid}`, { favorite: false });

  console.log("\n=== D 备份 UI ===");
  // 先关闭自动备份（避免监听器初始备份导致"无变更"干扰），并确保存档有变化
  await api("PUT", `/api/games/${gid}`, { auto_backup: false });
  fs.writeFileSync(path.join(SAVE_DIR, "slot.sav"), "changed-for-backup " + Date.now());
  // TC-D-001ui 立即备份（带备注）
  await page.click("#btn-backup-now");
  await page.type("#backup-note", "前端备份备注");
  await page.click("#backup-confirm");
  await waitFor("备份成功 toast", () =>
    page.evaluate(() => document.querySelector("#toast").textContent.includes("备份成功")), 15000);
  check("TC-D-001ui 立即备份（前端）", true);

  // TC-D-002ui 无变更二次确认
  await page.click("#btn-backup-now");
  await page.click("#backup-confirm");
  await waitFor("无变更确认弹窗", () =>
    page.evaluate(() => document.querySelector("#modal-title").textContent === "备份确认"), 10000);
  check("TC-D-002ui 无变更确认弹窗出现", true);
  // 点"是，备份"
  await page.evaluate(() => { document.querySelector("#modal-foot [data-ok]").click(); });
  await waitFor("force 备份完成", () =>
    page.evaluate(() => document.querySelector("#toast").textContent.includes("备份成功")), 15000);
  check("TC-D-003ui force 备份成功", true);

  console.log("\n=== E 版本时间线 UI ===");
  // TC-E-001 时间线渲染（收藏按钮存在）
  await waitFor("时间线渲染", () => page.$(".tl-item"), 10000);
  check("TC-E-001ui 时间线渲染版本卡片", true);
  const tlText = await page.evaluate(() => document.querySelector("#timeline").textContent);
  check("TC-E-001b 时间线含类型标记", tlText.includes("完整") || tlText.includes("增量"), tlText.slice(0, 60));

  // TC-E-002ui 收藏版本（时间线星标）
  const hasFavStar = await page.$(".tl-badge.fav-star") !== null;
  if (hasFavStar) {
    await page.click(".tl-badge.fav-star");
    // 等待徽章变为已收藏（fav 样式），不依赖 toast 时序
    await waitFor("收藏徽章出现", async () => (await page.$(".tl-badge.fav")) !== null, 8000);
    check("TC-E-002ui 时间线收藏版本", true);
    // 取消收藏（点击已收藏徽章）—— 修复后应可正常取消
    await page.evaluate(() => {
      const el = document.querySelector(".tl-badge.fav");
      if (el) el.click();
    });
    await waitFor("取消收藏后徽章消失", async () => (await page.$(".tl-badge.fav")) === null, 8000);
    check("TC-E-002b 点击已收藏徽章可取消收藏", true);
    // 通过 API 兜底清理收藏状态，保持环境干净（若上面未生效）
    const favTs = await page.evaluate(() => {
      const el = document.querySelector(".tl-badge.fav");
      return el ? el.dataset.ts : null;
    });
    if (favTs) await api("POST", `/api/games/${gid}/versions/${favTs}/favorite`, { favorite: false });
  } else {
    check("TC-E-002ui 时间线收藏版本", false, "无收藏入口");
  }

  console.log("\n=== G 校验 UI ===");
  // TC-G-005 全部校验按钮（先过确认弹窗）
  await page.click("#btn-verify-all");
  await waitFor("校验确认弹窗", () =>
    page.evaluate(() => document.querySelector("#modal-title").textContent.includes("校验")), 10000);
  await page.evaluate(() => {
    const ok = document.querySelector("#modal-foot [data-ok]");
    if (ok) ok.click();
  });
  await waitFor("校验完成 toast", () =>
    page.evaluate(() => document.querySelector("#toast").textContent.includes("校验完成")), 60000);
  check("TC-G-005ui 校验全部版本", true);

  console.log("\n=== I 设置 UI ===");
  // TC-I-005 设置草稿保持
  await page.click("#btn-settings");
  await waitFor("设置弹窗", () => page.$("#set-root"), 10000);
  // 添加一个定时任务（不保存）
  const taskBefore = await page.evaluate(() => document.querySelectorAll(".task-item").length);
  await page.click("#task-add");
  await new Promise(r => setTimeout(r, 600));
  const taskAfter = await page.evaluate(() => document.querySelectorAll(".task-item").length);
  check("TC-I-005ui 设置页添加任务（草稿）", taskAfter > taskBefore, `${taskBefore}->${taskAfter}`);
  // 关闭设置（取消）再打开，草稿保留
  await page.evaluate(() => { document.querySelector("#modal-foot [data-cancel]").click(); });
  await page.click("#btn-settings");
  await waitFor("设置弹窗重开", () => page.$("#set-root"), 10000);
  const taskReopen = await page.evaluate(() => document.querySelectorAll(".task-item").length);
  check("TC-I-005b 关闭重开草稿保留", taskReopen === taskAfter, `${taskAfter} vs ${taskReopen}`);
  // 取消本次修改（保持环境干净）
  await page.evaluate(() => { document.querySelector("#modal-foot [data-cancel]").click(); });

  // TC-I-006 保存设置后刷新（改 keep）
  await page.click("#btn-settings");
  await waitFor("设置弹窗", () => page.$("#set-root"), 10000);
  await page.evaluate(() => {
    const el = document.querySelector("#set-keep");
    el.value = "3";
    el.dispatchEvent(new Event("input"));
  });
  await page.click("#set-save");
  await new Promise(r => setTimeout(r, 800));
  const s = await api("GET", "/api/settings");
  check("TC-I-006ui 保存设置生效", s.keep_versions === 3, "keep=" + s.keep_versions);
  // 恢复 keep=5
  await api("POST", "/api/settings", { keep_versions: 5 });

  console.log("\n=== H 自动化 UI（8s 轮询） ===");
  // 重新开启自动备份（D 模块为排除干扰关闭了它）
  await api("PUT", `/api/games/${gid}`, { auto_backup: true });
  // 等待 watcher 建立（调度器 10s 周期内同步）
  await new Promise(r => setTimeout(r, 12000));
  // TC-H-009 前端实时刷新
  const v0 = (await api("GET", `/api/games/${gid}/versions`)).length;
  fs.writeFileSync(path.join(SAVE_DIR, "slot.sav"), "v2 " + Date.now());
  await waitFor("自动备份 + 前端轮询刷新", async () => {
    const v = await api("GET", `/api/games/${gid}/versions`);
    return v.length > v0;
  }, 40000);
  // 前端数字自动更新（轮询 8s）
  await waitFor("前端数字自动更新", async () => {
    const c = await page.evaluate((id) => {
      const it = [...document.querySelectorAll(".game-item")].find(i => i.dataset.id === id);
      return it ? it.querySelector(".g-count").textContent : "?";
    }, gid);
    return c !== String(v0);
  }, 25000);
  check("TC-H-009ui 前端 8s 轮询自动刷新", true);

  console.log("\n=== M 端到端（UI 精简旅程） ===");
  // TC-M-001 部分：恢复体验
  fs.writeFileSync(path.join(SAVE_DIR, "slot.sav"), "corrupted!");
  const vs = await api("GET", `/api/games/${gid}/versions`);
  await page.click("#btn-restore");
  await waitFor("恢复弹窗", () => page.$("#restore-select"), 10000);
  await page.click("#restore-confirm");
  await waitFor("恢复成功 toast", () =>
    page.evaluate(() => document.querySelector("#toast").textContent.includes("恢复成功")), 20000);
  check("TC-M-001ui 一键恢复（前端）", true);
  const content = fs.readFileSync(path.join(SAVE_DIR, "slot.sav"), "utf-8");
  check("TC-M-001b 恢复后内容正确", !content.startsWith("corrupted!"), content);

  // 关闭自动备份 + 清理
  await api("PUT", `/api/games/${gid}`, { auto_backup: false });
  await api("DELETE", `/api/games/${gid}`);
  fs.rmSync(SAVE_DIR, { recursive: true, force: true });

  console.log("\n==================================================");
  console.log(`前端 UI 结果: ${passed} 通过 / ${failed} 失败`);
  if (pageErrors.length) {
    console.log("页面错误:", JSON.stringify(pageErrors.slice(0, 5)));
    failed++;
  }
  console.log("==================================================");
  await browser.close();
  process.exit(failed ? 1 : 0);
})().catch(e => {
  console.error("前端测试异常中断:", e.message);
  process.exit(1);
});
