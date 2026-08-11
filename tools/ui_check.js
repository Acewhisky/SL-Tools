const puppeteer = require("C:/Users/Dengz/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    headless: "new",
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto("http://127.0.0.1:8765", { waitUntil: "networkidle0", timeout: 15000 });
  await page.waitForSelector(".game-item", { timeout: 8000 });

  const result = await page.evaluate(() => {
    const list = document.querySelector("#game-list");
    const sidebar = document.querySelector(".sidebar");
    const layout = document.querySelector(".layout");
    const itemCount = document.querySelectorAll(".game-item").length;
    return {
      itemCount,
      listClientH: list ? list.clientHeight : 0,
      listScrollH: list ? list.scrollHeight : 0,
      canScroll: list ? list.scrollHeight > list.clientHeight : false,
      sidebarH: sidebar ? sidebar.clientHeight : 0,
      layoutH: layout ? layout.clientHeight : 0,
    };
  });
  console.log(JSON.stringify(result, null, 2));
  await page.screenshot({ path: "C:/Users/Dengz/WorkBuddy/存档管理工具/debug_ui_before.png" });
  await browser.close();
})().catch(e => { console.error("ERR:", e.message); process.exit(1); });
