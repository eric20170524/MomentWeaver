const state = {
  files: [],
  localUrls: [],
  serverImages: [],
  jobId: null,
  plan: null,
  activeShot: 0,
  musicPath: null,
  musicUrl: null,
  settings: {},
  videos: [],
  selectedVideo: null,
};

const $ = (id) => document.getElementById(id);

const sampleCaption = `创意时代，已经到来。

越往后走，独特的眼光与真实的行动力，都会变得比什么都重要。关注力越来越稀缺，真正有生命力的 IP，也会越来越珍贵。

衣食足而知礼节。对于 00 后、10 后而言，这是一个更加友好、更加丰富，也更加值得奔赴的时代。愿新一代都能策马扬鞭，奔向属于自己的辽阔天地与美好未来。

于是个人而言，何其有幸，乐在参与。`;

const settingKeys = [
  "MOMENTWEAVER_HOST",
  "MOMENTWEAVER_PORT",
  "MOMENTWEAVER_RELOAD",
  "MOMENTWEAVER_PYTHON",
  "NEBULA_API_KEY",
  "NEBULA_PROVIDER",
  "NEBULA_MODEL",
  "NEBULA_BASE_URL",
  "NEBULA_SDK_PATH",
  "SMART_ASSET_KIT_PATH",
  "SAK_PYTHON",
];

function setStatus(text, tone = "normal") {
  const node = $("status");
  node.textContent = text;
  node.style.borderColor = tone === "warn" ? "rgba(255,122,89,.45)" : "rgba(17,24,22,.12)";
  node.style.color = tone === "warn" ? "#a7472d" : "";
}

function revokeLocalUrls() {
  for (const url of state.localUrls) URL.revokeObjectURL(url);
  state.localUrls = [];
}

function setFiles(files) {
  revokeLocalUrls();
  state.files = files.slice(0, 12);
  state.localUrls = state.files.map((file) => URL.createObjectURL(file));
  state.serverImages = [];
  state.musicPath = null;
  state.musicUrl = null;
  renderThumbs();
  renderPreview();
}

async function loadSettings() {
  const response = await fetch("/api/settings");
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Settings load failed");
  state.settings = data.values || {};
  $("envPath").textContent = data.env_path || "";
  for (const key of settingKeys) {
    const field = document.querySelector(`[data-setting="${key}"]`);
    if (field) field.value = state.settings[key] || "";
  }
  return data;
}

async function openSettings() {
  try {
    await loadSettings();
    $("settingsMessage").textContent = "";
    $("settingsModal").classList.remove("hidden");
  } catch (error) {
    setStatus(error.message, "warn");
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const values = {};
  for (const key of settingKeys) {
    const field = document.querySelector(`[data-setting="${key}"]`);
    if (field) values[key] = field.value;
  }
  $("settingsMessage").textContent = "Saving...";
  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Settings save failed");
    state.settings = data.values || {};
    $("settingsMessage").textContent = `Saved to ${data.env_path}. Host, port, reload and Python settings take effect after restart.`;
    setStatus("Settings saved");
  } catch (error) {
    $("settingsMessage").textContent = error.message;
    setStatus(error.message, "warn");
  }
}

function renderThumbs() {
  const grid = $("thumbGrid");
  grid.innerHTML = "";
  state.localUrls.forEach((url, index) => {
    const item = document.createElement("div");
    item.className = "thumb";
    item.innerHTML = `<img src="${url}" alt="素材 ${index + 1}"><span>${index + 1}</span>`;
    grid.appendChild(item);
  });
}

async function loadExamples() {
  try {
    const response = await fetch("/api/examples");
    const data = await response.json();
    const box = $("examples");
    box.innerHTML = "";
    for (const item of data.examples || []) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "example-thumb";
      button.innerHTML = `<img src="${item.url}" alt="${item.filename}">`;
      button.addEventListener("click", async () => {
        const img = await fetch(item.url);
        const blob = await img.blob();
        const file = new File([blob], item.filename, { type: blob.type || "image/png" });
        setFiles([...state.files, file]);
      });
      box.appendChild(button);
    }
  } catch {
    $("examples").innerHTML = "";
  }
}

function imageUrlFor(index) {
  const server = state.serverImages[index];
  if (server) return server.url;
  return state.localUrls[index] || "";
}

function renderPreview() {
  const preview = $("reelPreview");
  const plan = state.plan;
  if (!plan || !plan.shots || plan.shots.length === 0) {
    const firstImage = state.localUrls[0];
    if (firstImage) {
      preview.innerHTML = `
        <img class="preview-bg" src="${firstImage}" alt="">
        <img class="preview-image" src="${firstImage}" alt="">
        <div class="preview-copy">
          <small>00:00</small>
          <strong>素材</strong>
          <p>${state.files.length} 张图片</p>
        </div>`;
    } else {
      preview.innerHTML = `
        <div class="empty-preview">
          <div><strong>预览</strong><span>00:00</span></div>
        </div>`;
    }
    $("shotDots").innerHTML = "";
    return;
  }

  const shot = plan.shots[state.activeShot] || plan.shots[0];
  const imageUrl = imageUrlFor(shot.image_index || 0);
  preview.innerHTML = `
    ${imageUrl ? `<img class="preview-bg" src="${imageUrl}" alt="">` : ""}
    ${imageUrl ? `<img class="preview-image" src="${imageUrl}" alt="">` : ""}
    <div class="preview-copy">
      <small>${String(state.activeShot + 1).padStart(2, "0")} / ${plan.shots.length}</small>
      <strong>${escapeHtml(shot.title)}</strong>
      <p>${escapeHtml(shot.caption)}</p>
    </div>`;

  const dots = $("shotDots");
  dots.innerHTML = "";
  plan.shots.forEach((_, index) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = index === state.activeShot ? "active" : "";
    dot.title = `镜头 ${index + 1}`;
    dot.addEventListener("click", () => {
      state.activeShot = index;
      renderPreview();
      renderShotList();
    });
    dots.appendChild(dot);
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (!value) return "";
  const minute = Math.floor(value / 60);
  const second = Math.round(value % 60);
  return `${minute}:${String(second).padStart(2, "0")}`;
}

function renderPlan() {
  const plan = state.plan;
  if (!plan) return;
  $("llmBadge").textContent = "已生成";
  $("planSummary").innerHTML = `
    <strong>${escapeHtml(plan.title)}</strong>
    <span>${escapeHtml(plan.hook)}</span>
    <span>${escapeHtml(plan.weishi_caption || "")}</span>`;
  $("musicPrompt").value = plan.music_query || "";
  state.musicPath = null;
  state.musicUrl = null;
  $("musicDownloadBox").innerHTML = "";
  $("renderBtn").disabled = false;
  renderShotList();
  renderPreview();
  autoMusicPromptAndSearch();
}

function renderShotList() {
  const list = $("shotList");
  list.innerHTML = "";
  if (!state.plan) return;
  state.plan.shots.forEach((shot, index) => {
    const card = document.createElement("article");
    card.className = `shot-card ${index === state.activeShot ? "active" : ""}`;
    card.dataset.index = String(index);
    card.innerHTML = `
      <div class="shot-card-header">
        <span>${index + 1}</span>
        <input data-field="title" value="${escapeHtml(shot.title)}" />
        <input data-field="duration" type="number" min="1.5" max="8" step="0.5" value="${shot.duration}" />
      </div>
      <select data-field="image_index">
        ${imageOptions(shot.image_index)}
      </select>
      <textarea data-field="caption">${escapeHtml(shot.caption)}</textarea>
      <textarea data-field="emphasis">${escapeHtml(shot.emphasis || "")}</textarea>
    `;
    card.addEventListener("click", () => {
      state.activeShot = index;
      renderPreview();
      renderShotList();
    });
    card.addEventListener("input", syncPlanFromDom);
    list.appendChild(card);
  });
}

function imageOptions(selected) {
  const count = Math.max(state.serverImages.length, state.localUrls.length, 1);
  return Array.from({ length: count }, (_, index) => {
    const active = Number(selected) === index ? "selected" : "";
    return `<option value="${index}" ${active}>图片 ${index + 1}</option>`;
  }).join("");
}

function syncPlanFromDom() {
  if (!state.plan) return;
  document.querySelectorAll(".shot-card").forEach((card) => {
    const index = Number(card.dataset.index);
    const shot = state.plan.shots[index];
    if (!shot) return;
    card.querySelectorAll("[data-field]").forEach((field) => {
      const key = field.dataset.field;
      let value = field.value;
      if (key === "duration") value = Number(value);
      if (key === "image_index") value = Number(value);
      shot[key] = value;
    });
  });
  state.plan.music_query = $("musicPrompt").value.trim();
  state.plan.duration_seconds = state.plan.shots.reduce((sum, shot) => sum + Number(shot.duration || 0), 0);
  renderPreview();
}

async function analyze() {
  const caption = $("caption").value.trim();
  if (!caption) {
    setStatus("Missing caption", "warn");
    return;
  }
  if (state.files.length === 0) {
    setStatus("Add at least one image", "warn");
    return;
  }
  setStatus("Planning...");
  $("analyzeBtn").disabled = true;
  const body = new FormData();
  body.append("caption", caption);
  body.append("tone", $("tone").value);
  body.append("duration_seconds", $("duration").value);
  for (const file of state.files) body.append("images", file);

  try {
    const response = await fetch("/api/analyze", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Analyze failed");
    state.jobId = data.job_id;
    state.serverImages = data.images || [];
    state.plan = data.plan;
    state.activeShot = 0;
    state.musicPath = null;
    state.musicUrl = null;
    $("llmBadge").textContent = data.used_llm ? "Nebula" : "本地";
    renderPlan();
    setStatus(data.warning ? "Fallback plan" : "Plan ready", data.warning ? "warn" : "normal");
  } catch (error) {
    setStatus(error.message, "warn");
  } finally {
    $("analyzeBtn").disabled = false;
  }
}

async function autoMusicPromptAndSearch() {
  if (!state.plan) return;
  setStatus("Music prompt...");
  try {
    const response = await fetch("/api/music/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: state.plan,
        caption: $("caption").value.trim(),
        mood: $("tone").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Music prompt failed");
    $("musicPrompt").value = data.prompt || state.plan.music_query || "";
    state.plan.music_query = $("musicPrompt").value.trim();
    await searchMusic({ quiet: true });
    setStatus("Music ready");
  } catch (error) {
    setStatus(error.message, "warn");
  }
}

async function searchMusic(options = {}) {
  return searchMusicWithOptions(options);
}

async function searchMusicWithOptions(options = {}) {
  const query = $("musicPrompt").value.trim() || state.plan?.music_query || "";
  if (!options.quiet) setStatus("Searching music...");
  try {
    const response = await fetch("/api/music/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        mood: $("tone").value,
        duration_seconds: Number($("duration").value),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Music search failed");
    const box = $("musicCandidates");
    box.innerHTML = "";
    for (const candidate of data.candidates || []) {
      const item = document.createElement("article");
      item.className = "music-candidate";
      item.innerHTML = `
        <div class="music-candidate-main">
          <button type="button" data-action="pick">
            <strong>${escapeHtml(candidate.title)}</strong>
            <span>${escapeHtml(candidate.prompt)}</span>
            <span>${escapeHtml(candidate.status)} · ${escapeHtml(candidate.note || "")}</span>
          </button>
        </div>
        <button type="button" class="download-music-button" data-action="download" ${candidate.can_download ? "" : "disabled"}>下载</button>`;
      item.querySelector('[data-action="pick"]').addEventListener("click", () => {
        $("musicPrompt").value = candidate.prompt;
        if (state.plan) state.plan.music_query = candidate.prompt;
      });
      item.querySelector('[data-action="download"]').addEventListener("click", () => {
        $("musicPrompt").value = candidate.prompt;
        if (state.plan) state.plan.music_query = candidate.prompt;
        downloadMusic(candidate.prompt);
      });
      box.appendChild(item);
    }
    if (!options.quiet) setStatus("Music searched");
  } catch (error) {
    setStatus(error.message, "warn");
  }
}

async function downloadMusic(prompt) {
  if (!state.jobId || !state.plan) {
    setStatus("Generate storyboard first", "warn");
    return;
  }
  setStatus("Downloading music...");
  $("musicDownloadBox").innerHTML = `<div class="toast">Downloading music...</div>`;
  try {
    const response = await fetch("/api/music/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: state.jobId,
        prompt,
        duration_seconds: state.plan.duration_seconds || Number($("duration").value),
        seamless: true,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Music download failed");
    state.musicPath = data.path;
    state.musicUrl = data.url;
    $("useSakMusic").checked = false;
    $("musicDownloadBox").innerHTML = `
      <div class="audio-chip">
        <span>配乐已下载</span>
        <a href="${data.url}" target="_blank" rel="noreferrer">试听</a>
      </div>
      ${data.warning ? `<div class="toast">${escapeHtml(data.warning)}</div>` : ""}`;
    setStatus("Music downloaded");
    await renderVideo({ auto: true });
  } catch (error) {
    $("musicDownloadBox").innerHTML = `<div class="toast">${escapeHtml(error.message)}</div>`;
    setStatus(error.message, "warn");
  }
}

async function renderVideo(options = {}) {
  if (!state.jobId || !state.plan) return;
  syncPlanFromDom();
  setStatus(options.auto ? "Composing video..." : "Rendering MP4...");
  $("renderBtn").disabled = true;
  if (!options.keepResult) $("resultBox").innerHTML = "";
  try {
    const response = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: state.jobId,
        plan: state.plan,
        music_path: state.musicPath,
        use_sak_music: $("useSakMusic").checked,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Render failed");
    $("resultBox").innerHTML = `
      <video src="${data.video_url}" controls playsinline></video>
      <a class="download-link" href="${data.video_url}" download>下载 MP4</a>
      ${data.music_warning ? `<div class="toast">${escapeHtml(data.music_warning)}</div>` : ""}`;
    setStatus("MP4 ready");
    await loadVideoHistory({ quiet: true, selectPath: data.video_path });
  } catch (error) {
    $("resultBox").innerHTML = `<div class="toast">${escapeHtml(error.message)}</div>`;
    setStatus(error.message, "warn");
  } finally {
    $("renderBtn").disabled = false;
  }
}

async function loadVideoHistory(options = {}) {
  if (!options.quiet) setStatus("Loading videos...");
  try {
    const response = await fetch("/api/videos?limit=80");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Video history failed");
    state.videos = data.videos || [];
    if (options.selectPath) {
      state.selectedVideo = state.videos.find((video) => video.video_path === options.selectPath) || state.videos[0] || null;
    } else if (state.selectedVideo) {
      state.selectedVideo = state.videos.find(
        (video) => video.job_id === state.selectedVideo.job_id && video.filename === state.selectedVideo.filename
      ) || state.videos[0] || null;
    } else {
      state.selectedVideo = state.videos[0] || null;
    }
    renderVideoHistory();
    if (!options.quiet) setStatus("Videos loaded");
  } catch (error) {
    $("videoHistory").innerHTML = `<div class="toast">${escapeHtml(error.message)}</div>`;
    setStatus(error.message, "warn");
  }
}

function renderVideoHistory() {
  const box = $("videoHistory");
  box.innerHTML = "";
  if (!state.videos.length) {
    box.innerHTML = `<div class="empty-history">暂无导出记录</div>`;
    renderSelectedVideo();
    return;
  }

  state.videos.forEach((video, index) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "video-record";
    if (state.selectedVideo?.job_id === video.job_id && state.selectedVideo?.filename === video.filename) {
      item.classList.add("active");
    }
    const spec = [video.width && video.height ? `${video.width}×${video.height}` : "", formatDuration(video.duration_seconds), formatSize(video.size_bytes)]
      .filter(Boolean)
      .join(" · ");
    item.innerHTML = `
      <span class="video-record-title">${escapeHtml(video.title || video.filename)}</span>
      <span>${escapeHtml(spec || video.filename)}</span>
      <span>${escapeHtml(video.created_at || "")}${video.publish_status === "ready" ? " · 已准备发布" : ""}</span>`;
    item.addEventListener("click", () => {
      state.selectedVideo = state.videos[index];
      renderVideoHistory();
    });
    box.appendChild(item);
  });
  renderSelectedVideo();
}

function renderSelectedVideo() {
  const box = $("publishBox");
  const video = state.selectedVideo;
  $("publishResult").innerHTML = "";
  if (!video) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  $("selectedVideoPlayer").src = video.video_url;
  const spec = [video.width && video.height ? `${video.width}×${video.height}` : "", formatDuration(video.duration_seconds), formatSize(video.size_bytes)]
    .filter(Boolean)
    .join(" · ");
  $("selectedVideoMeta").innerHTML = `
    <strong>${escapeHtml(video.title || video.filename)}</strong>
    <span>${escapeHtml(spec)}</span>
    <span>${escapeHtml(video.video_path)}</span>`;
  $("publishShortTitle").value = video.short_title || video.title || "";
  $("publishDescription").value = video.video_description || video.caption || "";
  $("publishWeishiBtn").disabled = false;
}

async function publishSelectedVideo() {
  const video = state.selectedVideo;
  if (!video) {
    setStatus("Select a video", "warn");
    return;
  }
  setStatus("Preparing Weishi publish...");
  $("publishWeishiBtn").disabled = true;
  try {
    const response = await fetch("/api/publish/weishi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: video.job_id,
        filename: video.filename,
        channel: "weishi",
        caption: $("publishDescription").value.trim() || video.caption || "",
        short_title: $("publishShortTitle").value.trim() || video.short_title || "",
        video_description: $("publishDescription").value.trim() || video.video_description || "",
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Publish prepare failed");
    state.selectedVideo = data.record;
    let copyMessage = "发布信息已准备";
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(data.publish_text);
        copyMessage = "发布信息已复制";
      } catch {
        copyMessage = "浏览器未允许自动复制";
      }
    }
    await loadVideoHistory({ quiet: true });
    $("publishResult").innerHTML = `
      <div class="publish-ready">
        <strong>${escapeHtml(data.message)}</strong>
        <span>${escapeHtml(copyMessage)}</span>
        <span>短标题：${escapeHtml(data.short_title)}</span>
        <span>视频描述：${escapeHtml(data.video_description)}</span>
        <span>${escapeHtml(data.record.video_path)}</span>
        <textarea class="publish-text" readonly>${escapeHtml(data.publish_text)}</textarea>
      </div>`;
    setStatus("Weishi publish ready");
  } catch (error) {
    $("publishResult").innerHTML = `<div class="toast">${escapeHtml(error.message)}</div>`;
    setStatus(error.message, "warn");
  } finally {
    $("publishWeishiBtn").disabled = false;
  }
}

$("imageInput").addEventListener("change", (event) => setFiles(Array.from(event.target.files || [])));
$("sampleCaptionBtn").addEventListener("click", () => {
  $("caption").value = sampleCaption;
});
$("analyzeBtn").addEventListener("click", analyze);
$("musicAutoBtn").addEventListener("click", autoMusicPromptAndSearch);
$("musicSearchBtn").addEventListener("click", () => searchMusicWithOptions({}));
$("renderBtn").addEventListener("click", renderVideo);
$("refreshVideosBtn").addEventListener("click", () => loadVideoHistory({}));
$("publishWeishiBtn").addEventListener("click", publishSelectedVideo);
$("settingsBtn").addEventListener("click", openSettings);
$("settingsCloseBtn").addEventListener("click", () => $("settingsModal").classList.add("hidden"));
$("settingsModal").addEventListener("click", (event) => {
  if (event.target === $("settingsModal")) $("settingsModal").classList.add("hidden");
});
$("settingsForm").addEventListener("submit", saveSettings);
$("musicPrompt").addEventListener("input", () => {
  if (state.plan) state.plan.music_query = $("musicPrompt").value.trim();
  state.musicPath = null;
  state.musicUrl = null;
});
$("prevShot").addEventListener("click", () => {
  if (!state.plan?.shots?.length) return;
  state.activeShot = (state.activeShot - 1 + state.plan.shots.length) % state.plan.shots.length;
  renderPreview();
  renderShotList();
});
$("nextShot").addEventListener("click", () => {
  if (!state.plan?.shots?.length) return;
  state.activeShot = (state.activeShot + 1) % state.plan.shots.length;
  renderPreview();
  renderShotList();
});

loadExamples();
loadSettings().catch(() => {});
loadVideoHistory({ quiet: true });
