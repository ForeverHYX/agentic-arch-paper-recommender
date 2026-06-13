const profileStorageKey = "recommender_profile_override";

const profileEditor = document.getElementById("profileEditor");
const profileStatus = document.getElementById("profileStatus");
const profileSummary = document.getElementById("profileSummary");
const saveProfileButton = document.getElementById("saveProfileButton");
const downloadProfileLink = document.getElementById("downloadProfileLink");

const categoryLabels = {
  "cs.AR": "计算机体系结构",
  "cs.PF": "性能",
  "cs.DC": "分布式与并行计算",
  "cs.PL": "编程语言与编译器",
  "cs.AI": "人工智能",
  "cs.LG": "机器学习",
};

const sectionSummaries = {
  agentic_architecture: {
    title: "自动架构设计",
    signal: "关注用智能体、模拟器反馈和设计空间搜索自动提出并筛选微架构方案。",
  },
  full_stack_codesign: {
    title: "全栈软硬件协同设计",
    signal: "关注 ISA、编译器、运行时和专用加速器之间的联合优化。",
  },
  microarchitecture_simulators: {
    title: "微架构与模拟器",
    signal: "关注缓存、预取、分支预测、GPU 执行模型和周期级模拟工具。",
  },
  hpc_cross_over: {
    title: "HPC 交叉方向",
    signal: "关注高性能计算、并行运行时、性能可移植性和体系结构瓶颈分析。",
  },
};

const negativeRuleLabels = {
  "generic-ai-agent-noise": "泛 AI agent 或 Web/RAG benchmark",
  "generic-nas-noise": "缺少硬件上下文的泛 NAS 论文",
};

if (saveProfileButton) {
  saveProfileButton.addEventListener("click", saveProfileOverride);
}
if (profileEditor) {
  profileEditor.addEventListener("input", () => renderProfileExport(profileEditor.value));
}

loadProfile().catch((error) => {
  profileStatus.textContent = error.message;
});

async function loadProfile() {
  const stored = localStorage.getItem(profileStorageKey);
  if (stored) {
    profileEditor.value = formatProfileText(stored);
    profileStatus.textContent = "已加载本地画像覆盖。";
    renderProfileExport(profileEditor.value);
    return;
  }

  const response = await fetch("interests.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`画像文件加载失败：${response.status}`);
  }
  const profile = await response.json();
  profileEditor.value = JSON.stringify(profile, null, 2);
  profileStatus.textContent = "已加载当前 workflow 发布的画像。";
  renderProfileExport(profileEditor.value);
}

function saveProfileOverride() {
  let text = "";
  try {
    text = normalizedProfileText(profileEditor.value);
  } catch {
    profileStatus.textContent = "画像 JSON 无效。";
    return;
  }
  localStorage.setItem(profileStorageKey, text);
  profileEditor.value = text;
  profileStatus.textContent = "已保存本地画像覆盖。";
  renderProfileExport(text);
}

function renderProfileExport(text) {
  let profile = null;
  try {
    profile = JSON.parse(text);
  } catch {
    profileStatus.textContent = "画像 JSON 无效。";
    return;
  }
  const normalized = JSON.stringify(profile, null, 2);
  downloadProfileLink.download = "recommender-profile.json";
  downloadProfileLink.href = `data:application/json;charset=utf-8,${encodeURIComponent(normalized)}`;
  renderProfileSummary(profile);
}

function renderProfileSummary(profile) {
  if (!profileSummary) return;
  const sections = Array.isArray(profile.sections) ? profile.sections : [];
  const coreCategories = readableCategories(profile.core_categories).join("、") || "未设置";
  const expansionCategories = readableCategories(profile.expansion_categories).join("、") || "未设置";
  const sectionCards = sections.map(renderSectionSummary).join("");
  const negativeRules = readableNegativeRules(profile.negative_rules);

  profileSummary.innerHTML = `
    <h2>核心规则</h2>
    <p class="profile-summary-lede">${escapeHtml(profile.name || "未命名画像")}</p>
    <div class="profile-rule-grid">
      <div><strong>核心分类</strong><span>${escapeHtml(coreCategories)}</span></div>
      <div><strong>扩展分类</strong><span>${escapeHtml(expansionCategories)}</span></div>
      <div><strong>扩展门槛</strong><span>规则分达到 ${escapeHtml(profile.expansion_accept_score ?? 4)} 后进入候选池</span></div>
      <div><strong>降权噪声</strong><span>${escapeHtml(negativeRules || "未设置")}</span></div>
    </div>
    ${sectionCards ? `<div class="profile-section-summary">${sectionCards}</div>` : ""}
  `;
}

function renderSectionSummary(section) {
  const id = String(section.id || "");
  const summary = sectionSummaries[id] || {
    title: chineseOrDefault(section.label, "自定义规则"),
    signal: "根据自定义画像规则筛选相关论文，详细匹配词保留在下方 JSON 编辑器中。",
  };
  const weight = Number(section.weight || 0);
  return `
    <article>
      <strong>${escapeHtml(summary.title)}</strong>
      <span>权重 ${Number.isFinite(weight) ? weight : 0}</span>
      <p>${escapeHtml(summary.signal)}</p>
    </article>
  `;
}

function readableCategories(values) {
  if (!Array.isArray(values)) return [];
  return values.map((value) => {
    const code = String(value);
    const label = categoryLabels[code];
    return label ? `${label}（${code}）` : code;
  });
}

function readableNegativeRules(values) {
  if (!Array.isArray(values)) return "";
  return values.map((rule) => negativeRuleLabels[String(rule.id || "")] || "自定义降权规则").join("、");
}

function chineseOrDefault(value, fallback) {
  const text = String(value || "").trim();
  return /[\u4e00-\u9fff]/.test(text) ? text : fallback;
}

function normalizedProfileText(text) {
  return JSON.stringify(JSON.parse(text), null, 2);
}

function formatProfileText(text) {
  try {
    return normalizedProfileText(text);
  } catch {
    return text;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
