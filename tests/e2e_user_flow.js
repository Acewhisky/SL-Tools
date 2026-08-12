// 用户全流程 E2E 测试（浏览器驱动）。
// 流程：启动服务 → 扫描游戏 → 选中游戏 → 开启自动备份 → 修改存档触发自动备份
//      → 检查前端实时刷新 → 替换存档（新文件）→ 恢复体验 → 结束。
// 所有等待都有最大超时中断（超时报 FAIL 而非无限挂起），避免"误以为卡死"。
// 可移植：puppeteer-core 通过 NODE_PATH 或 PUPPETEER_PATH 环境变量指定
const puppeteer = require(process.env.PUPPETEER_PATH || "puppeteer-core");
const fs = require("fs");
const path = require("path");

const BASE = process.env.E2E_BASE || "http://127.0.0.1:8765";
const SAVE_DIR = process.env.E2E_SAVE_DIR || path.join(process.env.TEMP || "/tmp", "savemgr_e2e");
const TIMEOUT_MS = Number(process.env.E2E_TIMEOUT || 60000);  // 最大等待：60s

let passed = 0, failed = 0;
function check(name, cond, detail = "") {
  if (cond) { passed++; console.log(`  ✅ ${name}`); }
  else { failed++; console.log(`  ❌ ${name} ${detail}`); }
}

// 带超时的等待器（核心：任何等待都不会无限挂起）
async function waitFor(desc, fn, timeout = TIMEOUT_MS) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      if (await fn()) return true;
    } catch (e) { /* 重试 */ }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`等待超时（${timeout / 1000}s）：${desc}`);
}

async function api(method, path, body) {
  const r = await fetch(BASE + path, {
    method, headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "API 失败: " + path);
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

  // 准备干净存档目录
  if (fs.existsSync(SAVE_DIR)) fs.rmSync(SAVE_DIR, { recursive: true, force: true });
  fs.mkdirSync(SAVE_DIR, { recursive: true });
  fs.writeFileSync(path.join(SAVE_DIR, "slot1.sav"), "seed v1");
  console.log("E2E 存档目录:", SAVE_DIR);

  // ---- 1. 服务启动检查 ----
  console.log("\n步骤 1: 服务启动");
  check("服务可达", await fetch(BASE + "/api/version").then(r => r.ok));

  // ---- 2. 打开首页 ----
  console.log("\n步骤 2: 打开首页");
  await page.goto(BASE + "/?v=" + Date.now(), { waitUntil: "networkidle0", timeout: 15000 });
  await waitFor("游戏列表加载", () => page.$(".game-item"));
  check("首页渲染游戏列表", true);

  // ---- 3. 添加并选中测试游戏 ----
  console.log("\n步骤 3: 添加游戏并选中");
  // 清理上次可能残留的同名测试游戏
  const before = await api("GET", "/api/games");
  for (const x of before) {
    if (x.name === "E2E流程测试") await api("DELETE", `/api/games/${x.id}`);
  }
  const g = await api("POST", "/api/games", {
    name: "E2E流程测试", save_paths: [SAVE_DIR], auto_backup: false,
  });
  check("游戏已添加", !!g.id);
  // 刷新前端列表使新游戏出现在 DOM，再点击选中
  await page.evaluate(async () => { if (window.loadGames) await window.loadGames(); });
  await waitFor("新游戏出现在列表", () => page.$(`.game-item[data-id="${g.id}"]`), 10000);
  await page.evaluate((id) => {
    const it = [...document.querySelectorAll(".game-item")].find(i => i.dataset.id === id);
    if (it) it.click();
  }, g.id);
  // 注意：DOM classList 必须在 evaluate 内访问（Node 侧拿不到）
  await waitFor("详情页显示", () =>
    page.evaluate(() => {
      const d = document.querySelector("#game-detail");
      return d && !d.classList.contains("hidden");
    }), 10000);
  await new Promise(r => setTimeout(r, 600));

  // ---- 4. 开启自动备份（详情页开关）----
  console.log("\n步骤 4: 详情页开启自动备份");
  const autoOn = await page.evaluate(() => {
    const el = document.querySelector("#g-auto");
    if (!el) return null;
    el.click();  // 触发 onchange
    return el.checked;
  });
  await new Promise(r => setTimeout(r, 1000));
  check("详情页自动备份开关存在且可点击", autoOn === true, "autoOn=" + autoOn);
  // 确认后端已保存
  const gAfter = await api("GET", "/api/games").then(list => list.find(x => x.id === g.id));
  check("后端 auto_backup 已保存为 true", gAfter && gAfter.auto_backup === true);

  // ---- 5. 修改存档 → 自动备份（事件监听）----
  console.log("\n步骤 5: 修改存档触发自动备份");
  const v0 = (await api("GET", `/api/games/${g.id}/versions`)).length;  // 基线版本数
  fs.writeFileSync(path.join(SAVE_DIR, "slot1.sav"), "seed v2 " + Date.now());
  // 防抖 8s + 备份耗时，等待版本数相对基线增加
  await waitFor("自动备份完成（版本数增加）", async () => {
    const v = await api("GET", `/api/games/${g.id}/versions`);
    return v.length > v0;
  }, 30000);
  check("自动备份已触发并生成新版本", true);

  // ---- 6. 前端实时刷新检查 ----
  console.log("\n步骤 6: 前端实时刷新（8s 轮询）");
  const countBefore = await page.evaluate((id) => {
    const it = [...document.querySelectorAll(".game-item")].find(i => i.dataset.id === id);
    return it ? it.querySelector(".g-count").textContent : "?";
  }, g.id);
  // 再触发一次备份，等待前端自动更新数字
  fs.writeFileSync(path.join(SAVE_DIR, "slot1.sav"), "seed v3 " + Date.now());
  await waitFor("前端数字自动更新（无需手动刷新）", async () => {
    const cur = await page.evaluate((id) => {
      const it = [...document.querySelectorAll(".game-item")].find(i => i.dataset.id === id);
      return it ? it.querySelector(".g-count").textContent : "?";
    }, g.id);
    return cur !== countBefore;
  }, 25000);  // 8s 轮询 + 自动备份 8s 防抖，给 25s 上限
  check("前端数字自动刷新", true);

  // ---- 7. 替换存档（新增文件）→ 自动备份 ----
  // 注意：防抖会合并短时间内的多次写入为一次备份，因此这里等待"版本数继续增加"
  //（相对步骤 5 基线 +1，而非绝对数），并确保与步骤 6 的写入间隔超过防抖窗口。
  console.log("\n步骤 7: 替换存档（新增 slot2 文件）");
  await new Promise(r => setTimeout(r, 10000));  // 等待步骤 6 的防抖窗口结束
  const v1 = (await api("GET", `/api/games/${g.id}/versions`)).length;
  fs.writeFileSync(path.join(SAVE_DIR, "slot2.sav"), "new save " + Date.now());
  await waitFor("新增文件触发自动备份", async () => {
    const v = await api("GET", `/api/games/${g.id}/versions`);
    return v.length > v1;
  }, 30000);
  check("替换存档触发自动备份", true);

  // ---- 8. 手动备份按钮 ----
  console.log("\n步骤 8: 手动备份");
  const mb = await api("POST", `/api/games/${g.id}/backup`, { force: true });
  check("手动备份成功", !!mb.timestamp);

  // ---- 9. 恢复体验 ----
  console.log("\n步骤 9: 恢复版本");
  // 改动存档后恢复到最新备份
  fs.writeFileSync(path.join(SAVE_DIR, "slot1.sav"), "corrupted! " + Date.now());
  const versions = await api("GET", `/api/games/${g.id}/versions`);
  const target = versions[0].timestamp;
  const rb = await api("POST", `/api/games/${g.id}/restore`, { timestamp: target });
  check("恢复成功", !!rb.ok);
  const content = fs.readFileSync(path.join(SAVE_DIR, "slot1.sav"), "utf-8");
  check("存档内容已恢复（非 corrupted）", !content.startsWith("corrupted!"));

  // ---- 10. 关闭自动备份 + 清理 ----
  console.log("\n步骤 10: 关闭自动备份（结束体验）");
  await api("PUT", `/api/games/${g.id}`, { auto_backup: false });
  const gEnd = await api("GET", "/api/games").then(l => l.find(x => x.id === g.id));
  check("自动备份已关闭", gEnd.auto_backup === false);

  // 清理测试游戏
  await api("DELETE", `/api/games/${g.id}`);
  fs.rmSync(SAVE_DIR, { recursive: true, force: true });

  // ---- 结果 ----
  console.log("\n==================================================");
  console.log(`E2E 结果: ${passed} 通过 / ${failed} 失败`);
  if (pageErrors.length) {
    console.log("页面错误:", JSON.stringify(pageErrors.slice(0, 5)));
    failed++;
  }
  console.log("==================================================");
  await browser.close();
  process.exit(failed ? 1 : 0);
})().catch(e => {
  console.error("E2E 异常中断:", e.message);
  process.exit(1);
});
