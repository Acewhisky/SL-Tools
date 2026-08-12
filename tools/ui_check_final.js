// 可移植：puppeteer-core 通过 NODE_PATH 或 PUPPETEER_PATH 环境变量指定
const puppeteer = require(process.env.PUPPETEER_PATH || "puppeteer-core");
const path = require("path");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    headless: "new",
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 850 });
  await page.setCacheEnabled(false);
  await page.goto("http://127.0.0.1:8765?v=" + Date.now(), { waitUntil: "networkidle0", timeout: 15000 });
  await page.waitForSelector(".game-item", { timeout: 8000 });
  // 点击第一个游戏（有备份数据的优先；这里选艾尔登法环）
  await page.click(".game-item");
  await new Promise(r => setTimeout(r, 600));

  // 检查 UI 元素
  const ui = await page.evaluate(() => {
    const scrollable = (() => {
      const l = document.querySelector("#game-list");
      return l && l.scrollHeight > l.clientHeight;
    })();
    return {
      scrollable,
      gameListCount: document.querySelectorAll(".game-item").length,
      hasOpenSource: !!document.querySelector("#btn-open-source"),
      hasOpenBackup: !!document.querySelector("#btn-open-backup"),
      hasBackupModeSelect: !!document.querySelector("#set-backup-mode"),
      versionCards: document.querySelectorAll(".tl-item").length,
      kindBadges: Array.from(document.querySelectorAll(".tl-badge"))
        .map(b => b.textContent.trim())
        .filter(t => t.includes("完整") || t.includes("增量")),
    };
  });
  console.log("UI:", JSON.stringify(ui, null, 2));

  await page.screenshot({ path: path.join(__dirname, "debug_ui_final.png") });

  // 测试滚动：尝试 scrollTo
  const scrollResult = await page.evaluate(() => {
    const l = document.querySelector("#game-list");
    const before = l.scrollTop;
    l.scrollTop = 9999;
    const after = l.scrollTop;
    return { before, after, max: l.scrollHeight };
  });
  console.log("Scroll:", JSON.stringify(scrollResult));

  await browser.close();
})().catch(e => { console.error("ERR:", e.message); process.exit(1); });
