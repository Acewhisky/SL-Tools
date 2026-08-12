// 最小复现：验证 DEFECT-UI-001 修复
const puppeteer = require("C:/Users/Dengz/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core");
const fs = require("fs");
const path = require("path");
const BASE = "http://127.0.0.1:8890";
const SAVE = path.join(process.env.TEMP || "/tmp", "qa_verify_fix");

(async () => {
  if (fs.existsSync(SAVE)) fs.rmSync(SAVE, { recursive: true, force: true });
  fs.mkdirSync(SAVE, { recursive: true });
  fs.writeFileSync(path.join(SAVE, "s.sav"), "v1");
  const browser = await puppeteer.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: "new" });
  const page = await browser.newPage();
  const errs = [];
  page.on("pageerror", e => errs.push("PAGEERROR: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("CONSOLE: " + m.text()); });

  const api = async (method, p, body) => {
    const r = await fetch(BASE + p, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const j = await r.json(); if (!j.ok) throw new Error(p + ": " + j.error); return j.data;
  };
  // 清理
  for (const g of await api("GET", "/api/games")) if (g.name === "VERIFY修复验证") await api("DELETE", "/api/games/" + g.id);

  const g = await api("POST", "/api/games", { name: "VERIFY修复验证", save_paths: [SAVE], processes: [] });
  await api("POST", "/api/games/" + g.id + "/backup", { force: true });
  await page.goto(BASE + "/?v=" + Date.now(), { waitUntil: "networkidle0", timeout: 15000 });
  await page.evaluate(async (id) => {
    await window.loadGames();
    const it = [...document.querySelectorAll(".game-item")].find(i => i.dataset.id === id);
    it.click();
  }, g.id);
  await new Promise(r => setTimeout(r, 1200));

  // 收藏
  const hasStar = await page.$(".tl-badge.fav-star") !== null;
  console.log("有收藏入口(☆):", hasStar);
  await page.evaluate(() => { const el = document.querySelector(".tl-badge.fav-star"); if (el) el.click(); });
  await new Promise(r => setTimeout(r, 1200));
  const favNow = await page.$(".tl-badge.fav") !== null;
  console.log("收藏后出现(★):", favNow);
  const favTs = await page.evaluate(() => { const el = document.querySelector(".tl-badge.fav"); return el ? el.dataset.ts : null; });
  console.log("★ 徽章 data-ts:", favTs);

  // 点击取消收藏
  await page.evaluate(() => { const el = document.querySelector(".tl-badge.fav"); if (el) el.click(); });
  await new Promise(r => setTimeout(r, 1500));
  const favGone = await page.$(".tl-badge.fav") === null;
  console.log("点击后★消失(取消收藏成功):", favGone);
  console.log("页面错误:", errs.length ? JSON.stringify(errs) : "无");
  await browser.close();
  process.exit(favGone ? 0 : 1);
})().catch(e => { console.error("异常:", e.message); process.exit(1); });
