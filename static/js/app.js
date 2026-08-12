/* ============================================================
   游戏存档管理工具 - 前端逻辑
   ============================================================ */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  games: [],          // 游戏列表
  currentId: null,    // 当前选中游戏 id
  versions: [],       // 当前游戏版本列表
  platformFilter: "",
  search: "",
  settingsDraft: null,  // 设置页未保存草稿（任务添加/删除不会丢失）
};

/* ---------------- 工具 ---------------- */

function toast(msg, type = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  t.classList.remove("hidden");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 2600);
}

function setStatus(text, busy = false) {
  const el = $("#status-text");
  el.textContent = text;
  el.className = busy ? "busy" : "";
}

async function api(url, method = "GET", body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  const res = await fetch(url, opt);
  let data;
  try { data = await res.json(); } catch (e) { data = { ok: false, error: "响应解析失败" }; }
  if (!data.ok) throw new Error(data.error || "请求失败");
  return data.data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtSize(n) {
  if (n == null) return "—";
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
  return (n / 1073741824).toFixed(2) + " GB";
}

/* ---------------- 弹窗 ---------------- */

function openModal(title, bodyHtml, footHtml = "") {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = bodyHtml;
  $("#modal-foot").innerHTML = footHtml;
  $("#modal-mask").classList.remove("hidden");
}
function closeModal() { $("#modal-mask").classList.add("hidden"); }

function confirmDialog(title, message, opts = {}) {
  return new Promise((resolve) => {
    const btnOk = opts.okText || "确认";
    const btnDanger = opts.danger ? "btn-danger" : "btn-primary";
    const requireText = opts.requireText || null;
    let bodyHtml;
    if (requireText) {
      bodyHtml = `<p style="font-size:13.5px;color:var(--text-2);white-space:pre-line">${esc(message)}</p>
        <div class="form-group" style="margin-top:10px">
          <input id="confirm-text" class="form-control" placeholder="请输入 ${esc(requireText)}" autocomplete="off">
        </div>`;
    } else {
      bodyHtml = `<p style="font-size:13.5px;color:var(--text-2);white-space:pre-line">${esc(message)}</p>`;
    }
    openModal(title, bodyHtml,
      `<button class="btn btn-ghost" data-cancel>取消</button>
       <button class="btn ${btnDanger}" data-ok ${requireText ? "disabled" : ""}>${esc(btnOk)}</button>`
    );
    if (requireText) {
      const inp = $("#confirm-text");
      const okBtn = $("#modal-foot [data-ok]");
      inp.addEventListener("input", () => {
        okBtn.disabled = inp.value.trim() !== requireText;
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && inp.value.trim() === requireText) {
          closeModal(); resolve(true);
        }
      });
    }
    $("#modal-foot [data-ok]").onclick = () => { closeModal(); resolve(true); };
    $("#modal-foot [data-cancel]").onclick = () => { closeModal(); resolve(false); };
    $("#modal-mask [data-close]").onclick = () => { closeModal(); resolve(false); };
  });
}

$("#modal-mask").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeModal();
});
$("#modal-mask [data-close]").addEventListener("click", closeModal);

/* ---------------- 游戏列表 ---------------- */

async function loadGames() {
  state.games = await api("/api/games");
  renderGameList();
}

// 加载版本号（单一来源 backend/version.py -> /api/version）
(async () => {
  try {
    const v = await api("/api/version");
    const el = $("#status-version");
    if (el && v && v.version) el.textContent = "v" + v.version;
  } catch (e) { /* 离线/异常忽略 */ }
})();

function renderGameList() {
  const list = $("#game-list");
  const kw = state.search.trim().toLowerCase();
  const filtered = state.games.filter(g => {
    if (state.platformFilter && !(g.platform || []).includes(state.platformFilter)) return false;
    if (kw && !g.name.toLowerCase().includes(kw)) return false;
    return true;
  });
  if (!filtered.length) {
    list.innerHTML = `<div class="empty-list">${state.games.length ? "没有匹配的游戏" : "尚未发现游戏，点击「扫描游戏」"}</div>`;
    return;
  }
  list.innerHTML = filtered.map(g => {
    const dot = g.detected ? "dot-ok" : "dot-off";
    const active = g.id === state.currentId ? "active" : "";
    const plat = (g.platform || []).slice(0, 2).join("/") || "Other";
    // Steam 图标：在线加载，失败回退 emoji（离线环境自动回退）
    const avatar = g.icon_url
      ? `<div class="g-avatar"><img class="g-icon" src="${esc(g.icon_url)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><span style="display:none">🎮</span></div>`
      : `<div class="g-avatar">🎮</div>`;
    // .g-count 优先保留 DOM 当前值（轮询已更新的真实计数），避免 renderGameList 覆盖回旧值
    const existing = list.querySelector(`.game-item[data-id="${esc(g.id)}"]`);
    const countText = existing ? existing.querySelector(".g-count").textContent : String(g.version_count || 0);
    const latestTs = existing ? (existing.dataset.latestTs || "") : (g.last_backup_ts || "");
    return `
    <div class="game-item ${active}" data-id="${esc(g.id)}" data-latest-ts="${esc(latestTs)}">
      ${avatar}
      <div class="g-body">
        <div class="g-name">${esc(g.name)}</div>
        <div class="g-sub"><span class="dot ${dot}"></span>${esc(plat)}${g.auto_backup ? " · 自动备份" : ""}</div>
      </div>
      <span class="g-count">${countText}</span>
      <button class="game-fav-btn ${g.favorite ? "on" : ""}" data-fav="${esc(g.id)}" title="${g.favorite ? "取消收藏" : "收藏置顶（按最新备份排序）"}">${g.favorite ? "★" : "☆"}</button>
      <button class="game-hide-btn" data-hide="${esc(g.id)}" title="隐藏此游戏（设置中可恢复）">✕</button>
    </div>`;
  }).join("");
}

$("#game-list").addEventListener("click", async (e) => {
  // 收藏星标：切换收藏置顶
  const favBtn = e.target.closest(".game-fav-btn");
  if (favBtn) {
    e.stopPropagation();
    const fid = favBtn.dataset.fav;
    const g = state.games.find(x => x.id === fid);
    const next = !(g && g.favorite);
    try {
      await api(`/api/games/${encodeURIComponent(fid)}`, "PUT", { favorite: next });
      toast(next ? "已收藏置顶" : "已取消收藏", "success");
      await loadGames();  // 重新排序
    } catch (err) { toast(err.message, "error"); }
    return;
  }
  const hideBtn = e.target.closest(".game-hide-btn");
  if (hideBtn) {
    e.stopPropagation();
    const hid = hideBtn.dataset.hide;
    const g = state.games.find(x => x.id === hid);
    const ok = await confirmDialog("隐藏游戏",
      `确定隐藏「${g ? g.name : hid}」吗？\n隐藏后不会出现在列表中，可在「设置」中恢复。`,
      { okText: "隐藏" });
    if (!ok) return;
    try {
      await api(`/api/games/${encodeURIComponent(hid)}/hide`, "POST", {});
      toast("游戏已隐藏", "success");
      if (state.currentId === hid) {
        state.currentId = null;
        $("#game-detail").classList.add("hidden");
        $("#empty-state").classList.remove("hidden");
      }
      await loadGames();
    } catch (err) { toast(err.message, "error"); }
    return;
  }
  const item = e.target.closest(".game-item");
  if (!item) return;
  selectGame(item.dataset.id);
});

async function selectGame(id) {
  state.currentId = id;
  renderGameList();
  const g = state.games.find(x => x.id === id);
  if (!g) return;
  $("#empty-state").classList.add("hidden");
  $("#game-detail").classList.remove("hidden");
  $("#g-name").textContent = g.name;

  // 平台
  const plats = (g.platform || []).map(p => `<span class="tag">${esc(p)}</span>`).join("");
  $("#g-platform").innerHTML = plats || `<span class="tag">其他</span>`;
  $("#g-detected").textContent = g.detected ? "已检测到存档" : "未检测到存档";
  $("#g-detected").className = "tag " + (g.detected ? "tag-ok" : "tag-warn");
  // 自动备份开关（详情页直接切换，无需重添加游戏）
  const autoEl = $("#g-auto");
  if (autoEl) {
    autoEl.checked = !!g.auto_backup;
    autoEl.onchange = async () => {
      try {
        await api(`/api/games/${encodeURIComponent(id)}`, "PUT", { auto_backup: autoEl.checked });
        toast(autoEl.checked ? "已启用自动备份（存档变化时自动备份）" : "已关闭自动备份", "success");
        // 更新本地状态并刷新列表（不递归 selectGame）
        const local = state.games.find(x => x.id === id);
        if (local) local.auto_backup = autoEl.checked;
        renderGameList();
      } catch (err) { toast(err.message, "error"); }
    };
  }

  // 存档路径
  const paths = g.save_paths || [];
  $("#g-paths").innerHTML = paths.length
    ? paths.map(p => {
        const ok = p && p.length > 0;
        return `<div class="path-item"><span class="path-state">📄</span><span>${esc(p)}</span></div>`;
      }).join("")
    : `<div class="path-item"><span>暂无路径，请编辑添加</span></div>`;

  // 备份目录
  $("#g-backup-dir").textContent = g.backup_dir;

  // 保留信息（P3 优化：settings 会话内缓存，避免每次选游戏都请求含目录大小统计的设置接口）
  const settings = await getSettingsCached();
  $("#g-keep-info").textContent = `保留最近 ${settings.keep_versions} 个版本 · 压缩: ${compressName(settings.compress_format)}`;

  await loadVersions(id);
}

// settings 会话级缓存（P3）：openSettings 的草稿机制与详情页共用一份
let _settingsCache = null;
async function getSettingsCached(force = false) {
  if (!_settingsCache || force) _settingsCache = await api("/api/settings");
  return _settingsCache;
}

function compressName(fmt) {
  return { none: "不压缩", zip: "ZIP", "tar.gz": "TAR.GZ" }[fmt] || "不压缩";
}

/* ---------------- 版本时间线 ---------------- */

async function loadVersions(gameId) {
  state.versions = await api(`/api/games/${gameId}/versions`);
  const g = state.games.find(x => x.id === gameId);
  $("#g-count").textContent = `${state.versions.length} 个备份`;
  renderTimeline();
}

function renderTimeline() {
  const tl = $("#timeline");
  const vs = state.versions;
  if (!vs.length) {
    tl.innerHTML = `<div class="empty-list" style="padding:40px">还没有备份版本。点击「立即备份」创建第一个版本。</div>`;
    return;
  }
  tl.innerHTML = vs.map(v => {
    const favCls = v.favorite ? "tl-fav" : "";
    const errCls = v.status === "异常" ? "tl-err" : "";
    const badgeFav = v.favorite
      ? `<span class="tl-badge fav">★ 已收藏</span>`
      : `<span class="tl-badge fav-star" data-act="fav" data-ts="${esc(v.timestamp)}" title="收藏此版本，不会被自动清理">☆ 收藏</span>`;
    const badgeVer = v.verified
      ? `<span class="tl-badge ok">✅ 已校验</span>`
      : (v.status === "异常" ? `<span class="tl-badge err">⚠️ 校验异常</span>` : `<span class="tl-badge">未校验</span>`);
    const compressTag = v.compress && v.compress !== "none" ? `<span>📦 ${compressName(v.compress)}</span>` : "";
    const kindTag = v.kind === "incr"
      ? `<span class="tl-badge">📝 增量</span>`
      : `<span class="tl-badge">📦 完整</span>`;
    const incrDetail = v.kind === "incr"
      ? `<span>✏️ ${v.change_count||0} 改 / 🗑 ${v.delete_count||0} 删</span>`
      : "";
    return `
    <div class="tl-item ${favCls} ${errCls}">
      <div class="tl-card ${v.favorite ? "fav" : ""} ${v.status === "异常" ? "err" : ""}">
        <div class="tl-head">
          <span class="tl-time">🕐 ${esc(v.display)}</span>
          ${kindTag}${badgeFav}${badgeVer}
        </div>
        ${v.note ? `<div class="tl-note">📝 ${esc(v.note)}</div>` : ""}
        <div class="tl-meta">
          <span>📁 ${v.file_count} 个文件</span>
          <span>💾 ${fmtSize(v.size)}</span>
          ${compressTag}
          ${incrDetail}
        </div>
        <div class="tl-actions">
          <button class="btn btn-primary btn-sm" data-act="restore" data-ts="${esc(v.timestamp)}">↩️ 恢复此版本</button>
          <button class="btn btn-ghost btn-sm" data-act="verify" data-ts="${esc(v.timestamp)}">✅ 校验</button>
          <button class="btn btn-danger-ghost btn-sm" data-act="delete" data-ts="${esc(v.timestamp)}">🗑 删除</button>
        </div>
      </div>
    </div>`;
  }).join("");
}

$("#timeline").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const act = btn.dataset.act;
  const ts = btn.dataset.ts;
  const gid = state.currentId;
  if (!gid) return;

  if (act === "restore") {
    const v = state.versions.find(x => x.timestamp === ts);
    const ok = await confirmDialog("确认恢复",
      `将用备份版本「${v.display}」覆盖当前存档。\n\n⚠️ 恢复前会自动备份当前存档，且若游戏正在运行将拒绝执行。\n确定继续吗？`,
      { okText: "开始恢复", danger: false });
    if (!ok) return;
    try {
      setStatus("正在恢复存档…", true);
      const r = await api(`/api/games/${gid}/restore`, "POST", { timestamp: ts });
      toast(`恢复成功！已自动创建恢复前快照 ${r.safety_snapshot}`, "success");
      await refreshAfterChange();
    } catch (err) {
      toast(err.message, "error");
    } finally { setStatus("就绪"); }
  } else if (act === "verify") {
    try {
      setStatus("正在校验哈希…", true);
      const r = await api(`/api/games/${gid}/versions/${ts}/verify`, "POST");
      if (r.ok) toast("✅ 校验通过：所有文件哈希一致", "success");
      else toast(`❌ 校验失败：${r.mismatched.length} 个文件不一致（版本已标记为异常）`, "error");
      await loadVersions(gid);
    } catch (err) { toast(err.message, "error"); }
    finally { setStatus("就绪"); }
  } else if (act === "delete") {
    const ok = await confirmDialog("删除备份版本", `确定删除版本「${ts}」吗？该操作不可撤销。`, { okText: "删除", danger: true });
    if (!ok) return;
    try {
      await api(`/api/games/${gid}/versions/${ts}`, "DELETE");
      toast("版本已删除", "success");
      await refreshAfterChange();
    } catch (err) { toast(err.message, "error"); }
  } else if (act === "fav") {
    try {
      await api(`/api/games/${gid}/versions/${ts}/favorite`, "POST", { favorite: true });
      toast("已收藏，此版本不会被自动清理", "success");
      await loadVersions(gid);
    } catch (err) { toast(err.message, "error"); }
  }
});

// 收藏卡片上的取消收藏点击
$("#timeline").addEventListener("click", (e) => {
  const fav = e.target.closest(".tl-badge.fav");
  if (!fav) return;
  const gid = state.currentId;
  const ts = fav.dataset.ts;
  if (!gid || !ts) return;
  api(`/api/games/${gid}/versions/${ts}/favorite`, "POST", { favorite: false })
    .then(() => { toast("已取消收藏", "success"); loadVersions(gid); })
    .catch(err => toast(err.message, "error"));
});

async function refreshAfterChange() {
  await loadGames();
  if (state.currentId) {
    const still = state.games.find(g => g.id === state.currentId);
    if (still) { await loadVersions(state.currentId); }
    else { state.currentId = null; $("#game-detail").classList.add("hidden"); $("#empty-state").classList.remove("hidden"); }
  }
}

/* ---------------- 详情操作 ---------------- */

$("#btn-backup-now").addEventListener("click", async () => {
  const gid = state.currentId;
  if (!gid) return;
  openModal("立即备份",
    `<div class="form-group">
       <label>备份备注（可选）</label>
       <input id="backup-note" class="form-control" placeholder="例如：通关前存档 / 打完BOSS后">
       <div class="hint">备份将保存到当前游戏的备份目录，目录名为时间戳。</div>
     </div>`,
    `<button class="btn btn-ghost" data-cancel>取消</button>
     <button class="btn btn-success" id="backup-confirm">💾 开始备份</button>`
  );
  $("#backup-confirm").onclick = async () => {
    const note = $("#backup-note").value.trim();
    closeModal();
    try {
      setStatus("正在检查存档变化…", true);
      const r = await api(`/api/games/${gid}/backup`, "POST", { note });
      // 存档无变更：弹窗确认后才执行备份
      if (r.unchanged) {
        setStatus("就绪");
        const ok = await confirmDialog("备份确认",
          `存档无变更，是否需要备份？\n\n（最近备份：${r.latest || "无"}）`,
          { okText: "是，备份", danger: false });
        if (!ok) { toast("已取消备份", ""); return; }
        setStatus("正在备份…", true);
        const v2 = await api(`/api/games/${gid}/backup`, "POST", { note, force: true });
        toast(`备份成功：${v2.display}`, "success");
        await refreshAfterChange();
        setStatus("就绪");
        return;
      }
      toast(`备份成功：${r.display}`, "success");
      await refreshAfterChange();
    } catch (err) { toast(err.message, "error"); }
    finally { setStatus("就绪"); }
  };
  $("#modal-foot [data-cancel]").onclick = closeModal;
});

$("#btn-restore").addEventListener("click", async () => {
  const gid = state.currentId;
  if (!gid) return;
  const vs = state.versions;
  if (!vs.length) { toast("暂无备份可恢复", "error"); return; }
  const options = vs.map(v => `<option value="${esc(v.timestamp)}">${esc(v.display)}${v.note ? " · " + esc(v.note) : ""}（${v.file_count} 文件）</option>`).join("");
  openModal("一键恢复",
    `<div class="form-group">
       <label>选择要恢复的备份版本</label>
       <select id="restore-select" class="form-control">${options}</select>
       <div class="hint">⚠️ 恢复前将自动备份当前存档；若游戏正在运行将拒绝执行。</div>
     </div>`,
    `<button class="btn btn-ghost" data-cancel>取消</button>
     <button class="btn btn-primary" id="restore-confirm">↩️ 确认恢复</button>`
  );
  $("#restore-confirm").onclick = async () => {
    const ts = $("#restore-select").value;
    closeModal();
    try {
      setStatus("正在恢复存档…", true);
      const r = await api(`/api/games/${gid}/restore`, "POST", { timestamp: ts });
      toast(`恢复成功！已自动创建恢复前快照 ${r.safety_snapshot}`, "success");
      await refreshAfterChange();
    } catch (err) { toast(err.message, "error"); }
    finally { setStatus("就绪"); }
  };
  $("#modal-foot [data-cancel]").onclick = closeModal;
});

$("#btn-verify-all").addEventListener("click", async () => {
  const gid = state.currentId;
  if (!gid) return;
  const vs = state.versions;
  if (!vs.length) { toast("暂无备份可校验", "error"); return; }
  const ok = await confirmDialog("校验全部版本", `将对 ${vs.length} 个备份版本逐一计算 SHA256 哈希并对比。确定继续吗？`, { okText: "开始校验" });
  if (!ok) return;
  setStatus(`正在校验 ${vs.length} 个版本…`, true);
  let pass = 0, fail = 0;
  for (const v of vs) {
    try {
      const r = await api(`/api/games/${gid}/versions/${v.timestamp}/verify`, "POST");
      if (r.ok) pass++; else { fail++; toast(`版本 ${v.timestamp} 校验异常`, "error"); }
    } catch (err) { fail++; }
  }
  setStatus("就绪");
  toast(`校验完成：${pass} 个通过，${fail} 个异常`, fail ? "error" : "success");
  await loadVersions(gid);
});

$("#btn-cleanup").addEventListener("click", async () => {
  const gid = state.currentId;
  if (!gid) return;
  const settings = await getSettingsCached();
  const ok = await confirmDialog("清理过期备份",
    `将删除除「最近 ${settings.keep_versions} 个」之外的所有备份版本（收藏的版本永不删除）。\n确定继续吗？`,
    { okText: "清理", danger: true });
  if (!ok) return;
  try {
    const r = await api(`/api/games/${gid}/versions/cleanup`, "POST");
    toast(`清理完成：删除 ${r.deleted.length} 个，保留 ${r.kept} 个`, "success");
    await refreshAfterChange();
  } catch (err) { toast(err.message, "error"); }
});

$("#btn-edit-paths").addEventListener("click", () => {
  const gid = state.currentId;
  const g = state.games.find(x => x.id === gid);
  if (!g) return;
  openModal(`编辑「${esc(g.name)}」的存档路径`,
    `<div class="form-group">
       <label>存档路径（每行一个，支持 %APPDATA% %LOCALAPPDATA% %DOCUMENTS% %SAVED_GAMES% 等）</label>
       <textarea id="edit-paths" class="form-control" rows="${Math.max(3, (g.save_paths||[]).length)}">${esc((g.save_paths||[]).join("\n"))}</textarea>
     </div>
     <div class="form-group">
       <label>运行进程名（逗号分隔，用于检测游戏是否运行，如 eldenring.exe）</label>
       <input id="edit-procs" class="form-control" value="${esc((g.processes||[]).join(", "))}" placeholder="eldenring.exe">
     </div>`,
    `<button class="btn btn-ghost" data-cancel>取消</button>
     <button class="btn btn-primary" id="paths-save">保存</button>`
  );
  $("#paths-save").onclick = async () => {
    const paths = $("#edit-paths").value.split("\n").map(s => s.trim()).filter(Boolean);
    const processes = $("#edit-procs").value.split(",").map(s => s.trim()).filter(Boolean);
    closeModal();
    try {
      await api(`/api/games/${gid}`, "PUT", { save_paths: paths, processes });
      toast("已保存", "success");
      await loadGames();
      await selectGame(gid);
    } catch (err) { toast(err.message, "error"); }
  };
  $("#modal-foot [data-cancel]").onclick = closeModal;
});

/* ---------------- 在文件管理器中打开 ---------------- */
async function openFolderInExplorer(path) {
  if (!path) { toast("路径为空", "error"); return; }
  try {
    await api("/api/open", "POST", { path });
    toast("已在文件管理器中打开", "success");
  } catch (err) { toast(err.message, "error"); }
}
$("#btn-open-source").addEventListener("click", () => {
  const g = state.games.find(x => x.id === state.currentId);
  if (!g) return;
  // 打开第一个存在的存档路径
  const existing = (g.save_paths || []).find(p => p && p.length);
  if (!existing) { toast("尚未配置存档路径", "error"); return; }
  openFolderInExplorer(existing);
});
$("#btn-open-backup").addEventListener("click", () => {
  const g = state.games.find(x => x.id === state.currentId);
  if (!g) return;
  openFolderInExplorer(g.backup_dir);
});

/* ---------------- 手动添加游戏 ---------------- */

function openAddGame() {
  openModal("手动添加游戏",
    `<div class="form-group">
       <label>游戏名称 *</label>
       <input id="ag-name" class="form-control" placeholder="例如：我的世界">
     </div>
     <div class="form-group">
       <label>平台</label>
       <select id="ag-platform" class="form-control">
         <option>Steam</option><option>Epic</option><option>GOG</option>
         <option>Xbox</option><option>WeGame</option><option>Other</option>
       </select>
     </div>
     <div class="form-group">
       <label>存档路径 *（可多条）</label>
       <div id="ag-paths">
         <div class="path-edit-item"><input class="form-control" placeholder="例如：%APPDATA%/.minecraft/saves"><button class="btn-icon" data-del-path>✕</button></div>
       </div>
       <button class="btn btn-link btn-add-path" id="ag-add-path">＋ 添加路径</button>
     </div>
     <div class="form-group">
       <label>运行进程名（逗号分隔，可选）</label>
       <input id="ag-procs" class="form-control" placeholder="javaw.exe">
     </div>
     <div class="checkbox-row"><input type="checkbox" id="ag-auto"><span>启用自动备份（存档变化时自动备份）</span></div>`,
    `<button class="btn btn-ghost" data-cancel>取消</button>
     <button class="btn btn-primary" id="ag-save">保存</button>`
  );
  $("#ag-add-path").onclick = () => {
    const wrap = document.createElement("div");
    wrap.className = "path-edit-item";
    wrap.innerHTML = `<input class="form-control" placeholder="存档路径"><button class="btn-icon" data-del-path>✕</button>`;
    $("#ag-paths").appendChild(wrap);
  };
  $("#ag-paths").addEventListener("click", (e) => {
    if (e.target.closest("[data-del-path]")) e.target.closest(".path-edit-item").remove();
  });
  $("#ag-save").onclick = async () => {
    const name = $("#ag-name").value.trim();
    const paths = [...$$("#ag-paths .form-control")].map(i => i.value.trim()).filter(Boolean);
    const processes = $("#ag-procs").value.split(",").map(s => s.trim()).filter(Boolean);
    if (!name) { toast("请填写游戏名称", "error"); return; }
    if (!paths.length) { toast("请至少填写一个存档路径", "error"); return; }
    closeModal();
    try {
      const g = await api("/api/games", "POST", {
        name, platform: [$("#ag-platform").value], save_paths: paths,
        processes, auto_backup: $("#ag-auto").checked,
      });
      toast("游戏已添加", "success");
      await loadGames();
      await selectGame(g.id);
    } catch (err) { toast(err.message, "error"); }
  };
  $("#modal-foot [data-cancel]").onclick = closeModal;
}

$("#btn-add-game").addEventListener("click", openAddGame);

/* ---------------- 扫描 ---------------- */

async function doScan() {
  try {
    setStatus("正在扫描本机游戏…", true);
    const r = await api("/api/scan", "POST");
    const names = (r.added_names || []).slice(0, 8);
    const nameStr = names.length ? `：${names.join("、")}${r.added > names.length ? " 等" : ""}` : "";
    toast(`扫描完成：新增 ${r.added} 个游戏${nameStr}，当前共 ${r.total} 个`, "success");
    await loadGames();
    if (r.added && !state.currentId && state.games.length) selectGame(state.games[0].id);
  } catch (err) { toast(err.message, "error"); }
  finally { setStatus("就绪"); }
}
$("#btn-scan").addEventListener("click", doScan);
$("#btn-scan-empty").addEventListener("click", doScan);

/* ---------------- 备份所有游戏 ---------------- */
$("#btn-backup-all").addEventListener("click", async () => {
  if (!state.games.length) { toast("暂无游戏可备份", "error"); return; }
  const ok = await confirmDialog("备份全部游戏",
    `将对 ${state.games.length} 个游戏执行备份。\n存档无变更的游戏会自动跳过，不占用空间。\n确定继续吗？`,
    { okText: "开始备份" });
  if (!ok) return;
  const btn = $("#btn-backup-all");
  btn.disabled = true;
  try {
    setStatus("正在备份全部游戏…", true);
    const r = await api("/api/games/backup-all", "POST", {});
    const msg = `备份完成：成功 ${r.ok} 个，跳过 ${r.skipped} 个（无变更），失败 ${r.error} 个`;
    if (r.error) {
      const errNames = r.errors.map(e => `${e.name}：${e.reason}`).join("\n");
      await confirmDialog("部分备份失败", `${msg}\n\n${errNames}`, { okText: "知道了" });
    } else {
      toast(msg, "success");
    }
    await loadGames();
    if (state.currentId) await loadVersions(state.currentId);
  } catch (err) { toast(err.message, "error"); }
  finally { btn.disabled = false; setStatus("就绪"); }
});

/* ---------------- 搜索与筛选 ---------------- */

$("#game-search").addEventListener("input", (e) => {
  state.search = e.target.value;
  renderGameList();
});
$("#platform-filter").addEventListener("click", (e) => {
  const chip = e.target.closest(".pf-chip");
  if (!chip) return;
  $$(".pf-chip").forEach(c => c.classList.remove("active"));
  chip.classList.add("active");
  state.platformFilter = chip.dataset.pf;
  renderGameList();
});

/* ---------------- 设置 ---------------- */

async function openSettings() {
  // 复用未保存草稿（task-add/task-del 后不丢失），首次打开从缓存/API 拉
  if (!state.settingsDraft) state.settingsDraft = await getSettingsCached();
  const s = state.settingsDraft;
  const taskRows = (s.auto_tasks || []).map((t, i) => `
    <div class="task-item">
      <span class="task-name">${esc(t.name || "任务" + (i + 1))}</span>
      <span class="task-desc">${esc(taskDesc(t))}</span>
      <input type="checkbox" class="task-switch" data-task="${i}" ${t.enabled === false ? "" : "checked"}>
      <button class="btn-icon" data-task-del="${i}">✕</button>
    </div>`).join("") || `<div class="empty-list">暂无自动任务</div>`;

  openModal("设置",
    `<div class="setting-group">
       <h4>备份存储</h4>
       <div class="form-group">
         <label>备份根目录（所有游戏的备份都存放在此）</label>
         <input id="set-root" class="form-control" value="${esc(s.backup_root)}">
         <div class="hint">当前大小：${esc(s.backup_root_size || "未知")} · 可用手动修改路径</div>
       </div>
       <div class="form-row">
         <div class="form-group">
           <label>保留版本数量 N</label>
           <input id="set-keep" type="number" min="1" max="99" class="form-control" value="${s.keep_versions}">
           <div class="hint">超出后自动清理最旧的版本（收藏除外）</div>
         </div>
         <div class="form-group">
           <label>压缩格式</label>
           <select id="set-compress" class="form-control">
             <option value="none" ${s.compress_format === "none" ? "selected" : ""}>不压缩（速度最快）</option>
             <option value="zip" ${s.compress_format === "zip" ? "selected" : ""}>ZIP</option>
             <option value="tar.gz" ${s.compress_format === "tar.gz" ? "selected" : ""}>TAR.GZ</option>
           </select>
         </div>
       </div>
       <div class="form-group">
         <label>备份模式</label>
         <select id="set-backup-mode" class="form-control">
           <option value="full" ${(s.backup_mode||"full") === "full" ? "selected" : ""}>完整备份（每次存所有文件）</option>
           <option value="incr" ${s.backup_mode === "incr" ? "selected" : ""}>仅增量（只存变更的文件，节省空间）</option>
           <option value="auto" ${s.backup_mode === "auto" ? "selected" : ""}>自动（变化小则增量，大则完整）</option>
         </select>
         <div class="hint">增量模式：仅备份变更的文件，节省存储。恢复时自动沿版本链重建。</div>
       </div>
     </div>
     <div class="setting-group">
       <h4>自动备份</h4>
       <div class="hint" style="margin-bottom:8px">自动备份由每个游戏独立控制：在左侧选择游戏，详情页勾选「自动备份」即可。下方为全局的监听行为参数。</div>
       <div class="form-group">
        <label>变化后延迟备份（秒，防抖）</label>
        <input id="set-watch-delay" type="number" min="1" max="120" class="form-control" value="${s.watch_delay}">
      </div>
      <div class="form-group">
        <label>文件变更监听扫描间隔（秒）</label>
        <input id="set-watch-interval" type="number" min="0" max="3600" class="form-control" value="${s.watch_interval ?? 0}">
        <div class="hint">0 = 事件驱动监听（默认，由系统内核通知变化，几乎零 CPU 占用）；大于 0 = 每 N 秒轮询扫描目录（对个别不产生事件通知的文件系统可用，数值越大 CPU 占用越低、检测越迟钝）。</div>
      </div>
       <div class="form-group">
         <label>定时任务（需在游戏编辑中启用自动备份，此处配置周期）</label>
         <div id="task-list">${taskRows}</div>
       </div>
       <div class="form-row">
         <div class="form-group">
           <label>选择游戏</label>
           <select id="task-game" class="form-control">
             ${state.games.map(g => `<option value="${esc(g.id)}">${esc(g.name)}</option>`).join("")}
           </select>
         </div>
         <div class="form-group">
           <label>周期</label>
           <select id="task-interval" class="form-control">
             <option value="3600">每小时</option>
             <option value="86400" selected>每天</option>
             <option value="604800">每周</option>
           </select>
         </div>
       </div>
       <button class="btn btn-outline btn-block" id="task-add">＋ 添加定时任务</button>
     </div>
     <div class="setting-group">
       <h4>其他</h4>
       <div class="checkbox-row"><input type="checkbox" id="set-browser" ${s.auto_open_browser ? "checked" : ""}><span>启动时自动打开浏览器</span></div>
       <div class="checkbox-row"><input type="checkbox" id="set-scan-online" ${s.scan_online !== false ? "checked" : ""}><span>扫描时联网更新游戏规则库（Ludusavi，增强识别范围）</span></div>
       <div class="form-group">
         <label>规则库下载源</label>
         <select id="set-rules-source" class="form-control">
           <option value="auto" ${(s.rules_source||"auto") === "auto" ? "selected" : ""}>自动（多源回退：jsDelivr → GitHub，国内直连优先）</option>
           <option value="jsdelivr" ${s.rules_source === "jsdelivr" ? "selected" : ""}>仅 jsDelivr CDN（国内直连稳定）</option>
           <option value="github" ${s.rules_source === "github" ? "selected" : ""}>仅 GitHub 原站（外网源）</option>
         </select>
         <div class="hint">Ludusavi 规则库含 19000+ 游戏。默认"自动"会先走国内可达的 jsDelivr CDN，失败再回退 GitHub；若你网络对某源特别快，可手动固定。</div>
       </div>
     </div>
     <div class="setting-group">
       <h4>隐藏的游戏</h4>
       <div id="hidden-games-list">加载中…</div>
     </div>
     <div class="setting-group">
       <h4>危险操作</h4>
       <button id="btn-init" class="btn btn-danger" style="width:100%">⚠️ 初始化工具（重置所有数据）</button>
       <div class="hint">重置设置与游戏列表、清空日志并重新扫描。勾选下方选项可同时清空默认备份目录中的备份数据。</div>
       <div class="checkbox-row" style="margin-top:8px"><input type="checkbox" id="init-clear-backups"><span>同时清空默认备份目录下的所有备份数据（不可恢复！）</span></div>
     </div>`,
    `<button class="btn btn-ghost" data-cancel>取消</button>
     <button class="btn btn-primary" id="set-save">保存设置</button>`
  );

  // 加载隐藏的游戏列表
  (async () => {
    try {
      const hidden = await api("/api/games/hidden");
      const box = $("#hidden-games-list");
      if (!box) return;
      if (!hidden.length) {
        box.innerHTML = `<div class="empty-list">暂无隐藏的游戏</div>`;
        return;
      }
      box.innerHTML = hidden.map(g => `
        <div class="task-item">
          <span class="task-name">${esc(g.name)}</span>
          <span class="task-desc">${(g.platform || []).join("/") || "Other"}</span>
          <button class="btn btn-outline btn-sm" data-unhide="${esc(g.id)}">恢复显示</button>
        </div>`).join("");
      box.querySelectorAll("[data-unhide]").forEach(btn => {
        btn.onclick = async () => {
          try {
            await api(`/api/games/${encodeURIComponent(btn.dataset.unhide)}`, "PUT", { hidden: false });
            toast("已恢复显示", "success");
            openSettings();
          } catch (err) { toast(err.message, "error"); }
        };
      });
    } catch (err) {
      const box = $("#hidden-games-list");
      if (box) box.innerHTML = `<div class="empty-list">加载失败</div>`;
    }
  })();

  // 任务增删
  $("#task-add").onclick = async () => {
    const gameId = $("#task-game").value;
    const interval = parseInt($("#task-interval").value, 10);
    const g = state.games.find(x => x.id === gameId);
    if (!g) { toast("请选择游戏", "error"); return; }
    // 开启该游戏自动备份
    await api(`/api/games/${gameId}`, "PUT", { auto_backup: true });
    state.settingsDraft.auto_tasks = state.settingsDraft.auto_tasks || [];
    state.settingsDraft.auto_tasks.push({
      id: "task_" + Date.now(),
      name: `定时备份 ${g.name}`,
      game_id: gameId,
      kind: "interval",
      interval_seconds: interval,
      enabled: true,
      last_run_ts: null,
    });
    toast("任务已添加，保存后生效", "success");
    openSettings();  // 重渲染列表展示新任务
  };

  $("#task-list").addEventListener("click", async (e) => {
    const delBtn = e.target.closest("[data-task-del]");
    if (delBtn) {
      const i = parseInt(delBtn.dataset.taskDel, 10);
      state.settingsDraft.auto_tasks.splice(i, 1);
      toast("任务已移除，保存后生效", "success");
      openSettings();
      return;
    }
  });

  $("#set-save").onclick = async () => {
    const keep = parseInt($("#set-keep").value, 10) || 5;
    const draft = state.settingsDraft || {};
    const payload = {
      backup_root: $("#set-root").value.trim(),
      keep_versions: keep,
      compress_format: $("#set-compress").value,
      backup_mode: $("#set-backup-mode").value,
      watch_delay: parseInt($("#set-watch-delay").value, 10) || 8,
      watch_interval: parseFloat($("#set-watch-interval").value) || 0,
      auto_open_browser: $("#set-browser").checked,
      scan_online: $("#set-scan-online") ? $("#set-scan-online").checked : true,
      rules_source: $("#set-rules-source") ? $("#set-rules-source").value : "auto",
      auto_tasks: draft.auto_tasks || [],
    };
    closeModal();
    try {
      await api("/api/settings", "POST", payload);
      toast("设置已保存", "success");
      state.settingsDraft = null;  // 清草稿，下次重新拉取
      _settingsCache = null;       // P3：保存后缓存失效，下次强制刷新
      if (state.currentId) selectGame(state.currentId);
    } catch (err) { toast(err.message, "error"); }
  };
  $("#modal-foot [data-cancel]").onclick = closeModal;

  // 初始化（危险操作，双重确认）
  $("#btn-init").onclick = async () => {
    const clearBackups = $("#init-clear-backups").checked;
    // 第一重确认
    const ok1 = await confirmDialog("⚠️ 初始化工具",
      "将重置设置与游戏列表、清空日志，并重新扫描识别游戏。\n确定继续吗？",
      { okText: "继续", danger: true });
    if (!ok1) return;
    // 第二重确认（清空备份时警告更强烈）
    let ok2;
    if (clearBackups) {
      ok2 = await confirmDialog("⚠️⚠️ 双重确认：清空备份数据",
        "你选择了同时清空默认备份目录下的所有备份数据！\n\n此操作不可恢复，备份将被永久删除。\n请输入「确定初始化」继续：",
        { okText: "确定初始化", danger: true, requireText: "确定初始化" });
    } else {
      ok2 = await confirmDialog("再次确认初始化",
        "初始化将清除当前列表与设置。是否继续？",
        { okText: "是，初始化", danger: true });
    }
    if (!ok2) return;
    closeModal();
    try {
      setStatus("正在初始化…", true);
      const r = await api("/api/init", "POST", { reset_backups: clearBackups });
      toast("初始化完成", "success");
      await loadGames();
      state.currentId = null;
      $("#game-detail").classList.add("hidden");
      $("#empty-state").classList.remove("hidden");
    } catch (err) { toast(err.message, "error"); }
    finally { setStatus("就绪"); }
  };
}

function taskDesc(t) {
  const sec = t.interval_seconds || 86400;
  const unit = sec >= 604800 ? `${sec / 604800} 周` : sec >= 86400 ? `${sec / 86400} 天` : `${sec / 3600} 小时`;
  const g = state.games.find(x => x.id === t.game_id);
  return `${g ? g.name : t.game_id} · 每${unit}`;
}

$("#btn-settings").addEventListener("click", openSettings);

/* ---------------- 导入导出 ---------------- */

$("#btn-export").addEventListener("click", async () => {
  try {
    const res = await fetch("/api/config/export");
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    const date = new Date().toISOString().slice(0, 10);
    a.href = URL.createObjectURL(blob);
    a.download = `savemgr-config-${date}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("配置已导出", "success");
  } catch (err) { toast(err.message, "error"); }
});

$("#btn-import").addEventListener("click", () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json,application/json";
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const ok = await confirmDialog("导入配置", `将导入配置中的游戏列表与设置。\n确定继续吗？`, { okText: "导入" });
      if (!ok) return;
      const r = await api("/api/config/import", "POST", data);
      toast(`导入完成：新增 ${r.imported_games} 个游戏`, "success");
      await loadGames();
    } catch (err) { toast("导入失败：" + err.message, "error"); }
  };
  input.click();
});

/* ---------------- 日志 ---------------- */

$("#btn-logs").addEventListener("click", async () => {
  try {
    const lines = await api("/api/logs");
    openModal("运行日志", `<div class="log-viewer">${esc(lines.join("\n") || "(空)")}</div>`,
      `<button class="btn btn-primary" data-close>关闭</button>`);
    $("#modal-foot [data-close]").onclick = closeModal;
  } catch (err) { toast(err.message, "error"); }
});

/* ---------------- 初始化 ---------------- */

(async function init() {
  try {
    setStatus("加载中…", true);
    await loadGames();
    // 自动选中第一个有备份的游戏
    const withBackup = state.games.find(g => g.version_count > 0);
    if (withBackup) await selectGame(withBackup.id);
    else if (state.games.length) await selectGame(state.games[0].id);
    else $("#empty-state").classList.remove("hidden");
    setStatus("就绪");
  } catch (err) {
    setStatus("加载失败：" + err.message);
    toast("加载失败：" + err.message, "error");
  }
})();

/* ---------------- 自动备份后的实时刷新 ----------------
   定时备份 / 监听变化备份由后端后台线程触发，前端无法感知。
   每 8s 轮询轻量 counts 接口，仅更新列表数字；当前选中游戏的
   版本数变化时刷新其时间线（不重渲染列表，避免打断用户操作）。 */
const POLL_INTERVAL = 8000;

async function pollBackupCounts() {
  try {
    const counts = await api("/api/games/counts");
    if (!counts || typeof counts !== "object") return;
    let selectedChanged = false;
    document.querySelectorAll(".game-item").forEach(item => {
      const gid = item.dataset.id;
      const el = item.querySelector(".g-count");
      if (!el || counts[gid] === undefined) return;
      const c = counts[gid];  // {count, latest}
      const curCount = parseInt(el.textContent, 10) || 0;
      const curLatest = item.dataset.latestTs || "";
      // 数量变化（新增备份）或最新版本变化（数量已满、新增删旧）都视为有更新
      if (c.count !== curCount || (c.latest && c.latest !== curLatest)) {
        el.textContent = c.count;
        item.dataset.latestTs = c.latest || "";
        if (gid === state.currentId) selectedChanged = true;
      }
    });
    // 当前选中游戏有新备���：刷新时间线
    if (selectedChanged && state.currentId) {
      await loadVersions(state.currentId);
    }
  } catch (e) {
    /* 静默：网络抖动/服务重启时忽略 */
  }
}

setInterval(pollBackupCounts, POLL_INTERVAL);
