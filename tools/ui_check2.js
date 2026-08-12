// 可移植：puppeteer-core 通过 NODE_PATH 或 PUPPETEER_PATH 环境变量指定
const puppeteer = require(process.env.PUPPETEER_PATH || "puppeteer-core");
const path = require("path");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    headless: "new",
    args: ["--disable-http-cache"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  // 强制禁用缓存
  await page.setCacheEnabled(false);
  await page.goto("http://127.0.0.1:8765/?v=" + Date.now(), { waitUntil: "networkidle0", timeout: 15000 });
  await page.waitForSelector(".game-item", { timeout: 8000 });

  const result = await page.evaluate(() => {
    const list = document.querySelector("#game-list");
    const sidebar = document.querySelector(".sidebar");
    const layout = document.querySelector(".layout");
    const itemCount = document.querySelectorAll(".game-item").length;
    // 读取实际应用的 min-height
    const listMinH = list ? getComputedStyle(list).minHeight : "";
    const sbMinH = sidebar ? getComputedStyle(sidebar).minHeight : "";
    const sbOverflow = sidebar ? getComputedStyle(sidebar).overflow : "";
    return {
      itemCount,
      listClientH: list ? list.clientHeight : 0,
      listScrollH: list ? list.scrollHeight : 0,
      canScroll: list ? list.scrollHeight > list.clientHeight : false,
      sidebarH: sidebar ? sidebar.clientHeight : 0,
      layoutH: layout ? layout.clientHeight : 0,
      listMinH, sbMinH, sbOverflow,
    };
  });
  console.log(JSON.stringify(result, null, 2));
  await page.screenshot({ path: path.join(__dirname, "debug_ui_after.png") });
  await browser.close();
})().catch(e => { console.error("ERR:", e.message); process.exit(1); });
