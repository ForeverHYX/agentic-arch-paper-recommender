let activePayload = null;

const localFeedbackKey = "recommender_local_feedback_events";
const feedbackUiStateKey = "recommender_feedback_ui_state";
const uiState = {
  activeTab: "all",
  selectedKeywords: new Set(),
};
const typeKeywords = new Set(["paper", "repository"]);
const contentKeywordSeeds = [
  "agentic architecture",
  "architecture design space exploration",
  "hardware software co-design",
  "co-design",
  "microarchitecture",
  "branch predictor",
  "cache",
  "prefetcher",
  "simulator",
  "simulation",
  "gem5",
  "gpu",
  "cuda",
  "rocm",
  "hpc",
  "compiler",
  "runtime",
  "mlir",
  "triton",
  "risc-v",
  "fpga",
  "accelerator",
  "memory hierarchy",
  "repository",
];

async function loadRecommendations() {
  const response = await fetch("recommendations.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`推荐数据加载失败：${response.status}`);
  }
  return response.json();
}

async function loadStatus() {
  const response = await fetch("status.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`运行状态加载失败：${response.status}`);
  }
  return response.json();
}

function render(payload) {
  activePayload = payload;
  const runDate = document.getElementById("runDate");
  runDate.textContent = payload.run_date ? `运行日期：${payload.run_date}` : "";
  renderControls(payload);
  renderKeywordFilters(payload.recommendations || [], payload.section_labels || {});
  renderFeedbackStatus();
  renderFeedbackInsights(payload.feedback_summary?.metrics || {});
  renderRunHealth(payload, null);
  loadStatus().then((status) => {
    renderSubsystemStatus(status);
    renderRunHealth(payload, status);
  }).catch(() => {
    renderSubsystemStatus(null);
    renderRunHealth(payload, null);
  });
  applyControls();
}

function renderControls(payload) {
  const sectionFilter = document.getElementById("sectionFilter");
  if (!sectionFilter.dataset.ready) {
    const sectionLabels = payload.section_labels || {};
    const sections = Array.from(new Set((payload.recommendations || []).map((paper) => paper.sections?.[0] || "exploratory")));
    sectionFilter.innerHTML = '<option value="">全部栏目</option>' + sections.map((section) => {
      const label = sectionLabels[section] || "探索性相关";
      return `<option value="${escapeAttr(section)}">${escapeHtml(label)}</option>`;
    }).join("");
    ["searchInput", "sectionFilter", "minAiScore", "hasCodeFilter", "hasAffiliationFilter", "sortSelect"].forEach((id) => {
      const element = document.getElementById(id);
      element.addEventListener("input", applyControls);
      element.addEventListener("change", applyControls);
    });
    sectionFilter.dataset.ready = "true";
  }
  renderDomainTabs(payload);
  bindReaderTabs();
  bindKeywordFilters();
  updateTabPanels();
  const recommendations = document.getElementById("recommendations");
  if (recommendations && !recommendations.dataset.feedbackReady) {
    recommendations.addEventListener("click", handleFeedbackClick);
    recommendations.dataset.feedbackReady = "true";
  }
}

function renderDomainTabs(payload) {
  const tabsContainer = document.getElementById("readerTabs");
  if (!tabsContainer || tabsContainer.dataset.domainsReady) return;
  const sectionLabels = payload.section_labels || {};
  const sections = Array.from(new Set((payload.recommendations || [])
    .map((paper) => paper.sections?.[0] || "exploratory")
    .filter(Boolean)));
  const repoCount = (payload.recommendations || []).filter(isRepositoryItem).length;
  const domainTabs = sections.map((section) => ({
    tab: `section:${section}`,
    label: sectionLabels[section] || "探索性相关",
  }));
  const fixedTabs = [
    { tab: "all", label: "全部" },
    ...domainTabs,
  ];
  if (repoCount > 0) fixedTabs.push({ tab: "repository", label: "仓库" });
  fixedTabs.push({ tab: "profile", label: "画像与系统" });
  tabsContainer.innerHTML = fixedTabs.map((entry) => {
    const active = entry.tab === "all" ? " is-active" : "";
    return `<button type="button" class="nav-link reader-tab${active}" data-tab="${escapeAttr(entry.tab)}">${escapeHtml(entry.label)}</button>`;
  }).join("");
  tabsContainer.dataset.domainsReady = "true";
}

function bindReaderTabs() {
  const tabs = document.querySelectorAll?.("#readerTabs [data-tab]") || [];
  tabs.forEach((tab) => {
    if (tab.dataset.ready) return;
    tab.addEventListener("click", () => setActiveTab(tab.dataset.tab || "all"));
    tab.dataset.ready = "true";
  });
}

function setActiveTab(tab) {
  uiState.activeTab = tab || "all";
  updateTabPanels();
  applyControls();
}

function updateTabPanels() {
  const recommendationWorkspace = document.getElementById("recommendationWorkspace");
  const profileSystemWorkspace = document.getElementById("profileSystemWorkspace");
  const showProfile = uiState.activeTab === "profile";
  recommendationWorkspace?.classList.toggle?.("is-hidden", showProfile);
  recommendationWorkspace?.classList.toggle?.("is-active", !showProfile);
  profileSystemWorkspace?.classList.toggle?.("is-hidden", !showProfile);
  profileSystemWorkspace?.classList.toggle?.("is-active", showProfile);

  const tabs = document.querySelectorAll?.("#readerTabs [data-tab]") || [];
  tabs.forEach((tab) => {
    const active = (tab.dataset.tab || "all") === uiState.activeTab;
    tab.classList.toggle?.("is-active", active);
    tab.setAttribute?.("aria-selected", active ? "true" : "false");
  });
}

function bindKeywordFilters() {
  const target = document.getElementById("keywordFilters");
  if (!target || target.dataset.ready) return;
  target.addEventListener("click", (event) => {
    const button = event.target?.closest?.("[data-keyword-filter]");
    if (!button) return;
    toggleKeywordFilter(button.dataset.keywordFilter || "");
  });
  target.dataset.ready = "true";
}

function toggleKeywordFilter(keyword) {
  const key = normalizeKeyword(keyword);
  if (!key) return;
  if (uiState.selectedKeywords.has(key)) {
    uiState.selectedKeywords.delete(key);
  } else {
    uiState.selectedKeywords.add(key);
  }
  renderKeywordFilters(activePayload?.recommendations || [], activePayload?.section_labels || {});
  applyControls();
}

function applyControls() {
  if (!activePayload) return;
  const filtered = filteredRecommendations(activePayload.recommendations || [], collectFilterState());
  renderSummaryStats({ ...activePayload, recommendations: filtered });
  renderRecommendationGroups(filtered, activePayload.section_labels || {});
  const resultCount = document.getElementById("resultCount");
  resultCount.textContent = `当前显示 ${filtered.length} / ${(activePayload.recommendations || []).length} 篇`;
  highlightTargetPaper();
}

function renderRecommendationGroups(recommendations, sectionLabels) {
  const container = document.getElementById("recommendations");

  if (!recommendations || recommendations.length === 0) {
    container.innerHTML = '<p class="empty">当前筛选条件下没有匹配论文。</p>';
    renderSectionNav(new Map(), {});
    return;
  }

  const groups = new Map();
  recommendations.forEach((paper) => {
    const section = paper.sections?.[0] || "exploratory";
    if (!groups.has(section)) groups.set(section, []);
    groups.get(section).push(paper);
  });
  renderSectionNav(groups, sectionLabels);

  container.innerHTML = Array.from(groups.entries()).map(([section, papers]) => {
    const label = sectionLabels[section] || "探索性但可能相关";
    const items = papers.map(renderPaper).join("");
    return `<section class="section" id="section-${escapeAttr(section)}"><div class="section-heading"><h2>${escapeHtml(label)}</h2><span>${papers.length} 篇</span></div>${items}</section>`;
  }).join("");
}

function collectFilterState() {
  return {
    query: document.getElementById("searchInput").value.trim().toLowerCase(),
    section: document.getElementById("sectionFilter").value,
    minAiScore: Number(document.getElementById("minAiScore").value),
    hasCode: document.getElementById("hasCodeFilter").checked,
    hasAffiliation: document.getElementById("hasAffiliationFilter").checked,
    sort: document.getElementById("sortSelect").value,
    keywords: Array.from(uiState.selectedKeywords),
  };
}

function filteredRecommendations(recommendations, filters) {
  const minAiScore = Number.isFinite(filters.minAiScore) ? filters.minAiScore : 0;
  const hiddenPaperIds = hiddenPaperIdsForRun();
  const filtered = recommendations.filter((paper) => {
    const section = paper.sections?.[0] || "exploratory";
    if (hiddenPaperIds.has(String(paper.paper_id || ""))) return false;
    if (!typeMatchesActiveTab(paper)) return false;
    if (filters.section && section !== filters.section) return false;
    if (filters.hasCode && !(Array.isArray(paper.code_urls) && paper.code_urls.length > 0)) return false;
    if (filters.hasAffiliation && !(Array.isArray(paper.affiliations) && paper.affiliations.length > 0)) return false;
    if (minAiScore && aiScoreFor(paper) < minAiScore) return false;
    if (filters.query && !searchTextFor(paper).includes(filters.query)) return false;
    if (!matchesKeywordFilters(paper, filters.keywords || [])) return false;
    return true;
  });
  return filtered.sort((left, right) => sortPapers(left, right, filters.sort));
}

function typeMatchesActiveTab(paper) {
  const tab = uiState.activeTab;
  if (tab === "profile") return false;
  if (tab === "all") return true;
  if (tab === "repository") return isRepositoryItem(paper);
  if (tab === "paper") return !isRepositoryItem(paper);
  if (tab.startsWith("section:")) {
    const section = tab.slice("section:".length);
    return (paper.sections?.[0] || "exploratory") === section;
  }
  return true;
}

function matchesKeywordFilters(paper, keywords) {
  const selected = keywords.map(normalizeKeyword).filter(Boolean);
  if (!selected.length) return true;
  const selectedTypes = selected.filter((keyword) => typeKeywords.has(keyword));
  const selectedContent = selected.filter((keyword) => !typeKeywords.has(keyword));
  if (selectedTypes.length) {
    const itemType = isRepositoryItem(paper) ? "repository" : "paper";
    if (!selectedTypes.includes(itemType)) return false;
  }
  if (!selectedContent.length) return true;
  const text = normalizeKeyword(searchTextFor(paper));
  return selectedContent.every((keyword) => text.includes(keyword));
}

function renderKeywordFilters(recommendations, sectionLabels) {
  const typeTarget = document.getElementById("typeKeywordFilters");
  const contentTarget = document.getElementById("contentKeywordFilters");
  if (!typeTarget || !contentTarget) return;
  const facets = keywordFacetsFor(recommendations, sectionLabels);
  typeTarget.innerHTML = renderKeywordChips(facets.type);
  contentTarget.innerHTML = facets.content.length
    ? renderKeywordChips(facets.content)
    : '<span class="empty-nav">暂无内容关键词</span>';
}

function renderKeywordChips(items) {
  return items.map((item) => {
    const keyword = normalizeKeyword(item.keyword);
    const active = uiState.selectedKeywords.has(keyword);
    return `
      <button class="keyword-chip${active ? " is-active" : ""}" type="button" data-keyword-filter="${escapeDataAttr(keyword)}">
        <span>${escapeHtml(item.label || keyword)}</span><strong>${Number(item.count || 0)}</strong>
      </button>
    `;
  }).join("");
}

function keywordFacetsFor(recommendations, sectionLabels) {
  const items = Array.isArray(recommendations) ? recommendations : [];
  return {
    type: [
      { keyword: "paper", label: "paper", count: items.filter((item) => !isRepositoryItem(item)).length },
      { keyword: "repository", label: "repository", count: items.filter(isRepositoryItem).length },
    ],
    content: deriveContentKeywords(items, sectionLabels),
  };
}

function deriveContentKeywords(recommendations, sectionLabels) {
  const counts = new Map();
  recommendations.forEach((paper) => {
    contentKeywordCandidatesFor(paper, sectionLabels).forEach((keyword) => {
      const key = normalizeKeyword(keyword);
      if (!key || typeKeywords.has(key)) return;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
  });
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 36)
    .map(([keyword, count]) => ({ keyword, label: keyword, count }));
}

function contentKeywordCandidatesFor(paper, sectionLabels) {
  const candidates = [];
  const sections = stringList(paper.sections);
  sections.forEach((section) => {
    candidates.push(section);
    if (sectionLabels?.[section]) candidates.push(sectionLabels[section]);
  });
  candidates.push(...stringList(paper.categories));
  candidates.push(...stringList(paper.repository_topics));
  if (paper.repository_language) candidates.push(paper.repository_language);
  paperLinksFor(paper).forEach((link) => candidates.push(link.label));

  const text = normalizeKeyword(searchTextFor(paper));
  contentKeywordSeeds.forEach((keyword) => {
    const normalized = normalizeKeyword(keyword);
    if (normalized && text.includes(normalized)) candidates.push(normalized);
  });
  return uniqueStrings(candidates);
}

function sortPapers(left, right, mode) {
  if (mode === "ai") return aiScoreFor(right) - aiScoreFor(left) || left.rank - right.rank;
  if (mode === "rule") return Number(right.score || 0) - Number(left.score || 0) || left.rank - right.rank;
  if (mode === "title") return String(left.title || "").localeCompare(String(right.title || ""));
  return Number(left.rank || 0) - Number(right.rank || 0);
}

function aiScoreFor(paper) {
  return Number(paper.ai_judgement?.score ?? paper.ai_score ?? 0);
}

function searchTextFor(paper) {
  return [
    paper.title,
    paper.abstract,
    paper.tldr,
    paper.ai_judgement?.reason,
    paper.repository_full_name,
    paper.repository_language,
    paper.repository_url,
    ...(Array.isArray(paper.authors) ? paper.authors : []),
    ...(Array.isArray(paper.affiliations) ? paper.affiliations : []),
    ...(Array.isArray(paper.categories) ? paper.categories : []),
    ...(Array.isArray(paper.repository_topics) ? paper.repository_topics : []),
    ...paperLinksFor(paper).map((link) => `${link.label} ${link.url}`),
  ].join(" ").toLowerCase();
}

function renderSummaryStats(payload) {
  const target = document.getElementById("summaryStats");
  const recommendations = payload.recommendations || [];
  const repositoryCount = recommendations.filter(isRepositoryItem).length;
  const sectionCount = new Set(recommendations.map((paper) => paper.sections?.[0] || "exploratory")).size;
  const codeCount = recommendations.filter((paper) => (Array.isArray(paper.code_urls) && paper.code_urls.length > 0) || paper.code_search_url).length;
  const affiliationCount = recommendations.filter(hasAffiliations).length;
  target.innerHTML = `
    <div><strong>${recommendations.length}</strong><span>论文</span></div>
    <div><strong>${repositoryCount}</strong><span>仓库</span></div>
    <div><strong>${sectionCount}</strong><span>栏目</span></div>
    <div><strong>${codeCount}</strong><span>代码线索</span></div>
    <div><strong>${affiliationCount}</strong><span>有单位</span></div>
  `;
}

function renderFeedbackStatus() {
  const target = document.getElementById("feedbackStatus");
  if (!target) return;

  const config = window.RECOMMENDER_CONFIG || {};
  if (config.supabaseUrl && config.supabaseAnonKey) {
    target.innerHTML = `
      <strong>反馈</strong>
      <span>Supabase 已启用，喜欢/不喜欢会进入后续推荐学习。</span>
    `;
    return;
  }

  const count = localFeedbackCount();
  target.innerHTML = `
    <strong>反馈</strong>
    <span>仅本地保存：此浏览器已有 ${count} 条点击；配置 Supabase 后才会自动进入每日学习。</span>
  `;
}

function renderFeedbackInsights(metrics) {
  const target = document.getElementById("feedbackInsights");
  if (!target) return;

  const total = Number(metrics.total_events || 0);
  if (!total) {
    target.innerHTML = `
      <strong>学习画像</strong>
      <span>暂无可持久读取的反馈。</span>
    `;
    return;
  }

  const likeRate = Math.round(Number(metrics.like_rate || 0) * 100);
  const likedTopics = uniqueStrings([...(metrics.top_liked_keywords || []), ...(metrics.top_liked_toolchains || [])]).slice(0, 4);
  const dislikedTopics = uniqueStrings([...(metrics.top_disliked_keywords || []), ...(metrics.top_disliked_toolchains || [])]).slice(0, 4);
  target.innerHTML = `
    <strong>学习画像</strong>
    <span>${total} 条反馈，喜欢率 ${likeRate}%</span>
    ${likedTopics.length ? `<span>偏好：${escapeHtml(likedTopics.join(", "))}</span>` : ""}
    ${dislikedTopics.length ? `<span>降权：${escapeHtml(dislikedTopics.join(", "))}</span>` : ""}
  `;
}

function renderSubsystemStatus(status) {
  const target = document.getElementById("subsystemStatus");
  if (!target) return;

  if (!status) {
    target.innerHTML = `
      <strong>系统</strong>
      <span>状态暂不可用。</span>
    `;
    return;
  }

  const rows = [
    ["LLM", status.llm?.configured, status.llm?.model],
    ["邮件", status.smtp?.configured, ""],
    ["Supabase", status.supabase?.configured, ""],
    ["本地反馈", status.local_feedback?.configured, ""],
    ["画像覆盖", status.profile_override?.configured, ""],
  ];
  target.innerHTML = `
    <strong>系统</strong>
    ${rows.map(([label, configured, detail]) => renderStatusRow(label, configured, detail)).join("")}
  `;
}

function renderRunHealth(payload, status) {
  const target = document.getElementById("runHealth");
  if (!target) return;

  const recommendations = Array.isArray(payload?.recommendations) ? payload.recommendations : [];
  const total = recommendations.length;
  const judged = recommendations.filter((paper) => paper.ai_judgement || paper.ai_score !== undefined).length;
  const summarized = recommendations.filter((paper) => String(paper.tldr || "").trim()).length;
  const metrics = payload?.feedback_summary?.metrics || {};
  const persistedEvents = Number(metrics.total_events || 0);
  const supabaseActive = isSupabaseActive(status);
  const feedbackMode = supabaseActive ? "Supabase 已启用" : "仅本地保存";
  const learningState = supabaseActive
    ? `${persistedEvents} 条持久反馈`
    : "尚未持久化";
  const setup = supabaseActive
    ? ""
    : "<span>下一步配置：SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY</span>";

  target.innerHTML = `
    <strong>运行状态</strong>
    <span>AI：${judged}/${total} 已判断，${summarized}/${total} 有 TLDR</span>
    <span>反馈：${escapeHtml(feedbackMode)}</span>
    <span>学习：${escapeHtml(learningState)}</span>
    ${setup}
  `;
}

function isSupabaseActive(status) {
  const config = window.RECOMMENDER_CONFIG || {};
  return Boolean(
    status?.supabase?.configured ||
    (config.supabaseUrl && config.supabaseAnonKey)
  );
}

function renderStatusRow(label, configured, detail) {
  const state = configured ? "on" : "off";
  const stateLabel = configured ? "开" : "关";
  const detailText = detail ? ` <em>${escapeHtml(detail)}</em>` : "";
  return `<span><b class="status-${state}">${stateLabel}</b> ${escapeHtml(label)}${detailText}</span>`;
}

function renderSectionNav(groups, sectionLabels) {
  const target = document.getElementById("sectionNav");
  if (!groups.size) {
    target.innerHTML = '<span class="empty-nav">暂无栏目</span>';
    return;
  }
  target.innerHTML = Array.from(groups.entries()).map(([section, papers]) => {
    const label = sectionLabels[section] || "探索性相关";
    return `<a href="#section-${escapeAttr(section)}"><span>${escapeHtml(label)}</span><strong>${papers.length}</strong></a>`;
  }).join("");
}

function renderPaper(paper) {
  const section = paper.sections?.[0] || "";
  const authors = Array.isArray(paper.authors) ? paper.authors.join(", ") : "";
  const categories = Array.isArray(paper.categories) ? paper.categories.join(", ") : "";
  const isRepository = isRepositoryItem(paper);
  const paperUrl = isRepository ? (paper.repository_url || paper.url) : (paper.url || `https://arxiv.org/abs/${encodeURIComponent(paper.paper_id)}`);
  const pdfUrl = isRepository ? "" : (paper.pdf_url || `https://arxiv.org/pdf/${encodeURIComponent(paper.paper_id)}`);
  const codeLinks = Array.isArray(paper.code_urls) ? paper.code_urls : [];
  const codeSearchUrl = isRepository ? "" : (paper.code_search_url || githubSearchUrl(paper));
  const aiJudgement = paper.ai_judgement || null;
  const aiScore = aiJudgement?.score ?? paper.ai_score;
  const feedbackState = feedbackStateFor(paper.paper_id);
  const liked = feedbackState === "like";
  const affiliations = stringList(paper.affiliations);
  const authorIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  const affiliationIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/></svg>`;
  const tags = uniqueStrings([
    ...(isRepository ? [] : (Array.isArray(paper.categories) ? paper.categories : [])),
    ...(Array.isArray(paper.repository_topics) ? paper.repository_topics.slice(0, 4) : []),
  ]);
  const aiJudgementHtml = aiJudgement
    ? `<div class="paper-ai"><span class="ai-label">AI 判断</span>${escapeHtml(aiJudgement.reason || "")}</div>`
    : "";
  const tldrHtml = paper.tldr
    ? `<div class="paper-tldr"><span class="tldr-label">核心解读</span>${escapeHtml(paper.tldr)}</div>`
    : "";
  const repoTag = isRepository ? `<span class="tag-chip repo">GitHub 仓库</span>` : "";
  const repoTrendHtml = isRepository ? renderRepositoryMetaInline(paper) : "";
  const tagChipsHtml = tags.map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`).join("");
  const originalPaperHtml = renderOriginalPaperLinks(paper);
  return `
    <article class="paper${liked ? " is-liked" : ""}" id="paper-${escapeAttr(paper.paper_id)}" data-paper-id="${escapeAttr(paper.paper_id)}">
      ${liked ? '<div class="paper-favorite-star" aria-label="已喜欢" title="已喜欢">★</div>' : ""}
      <h3 class="paper-title"><a href="${escapeAttr(paperUrl)}" target="_blank" rel="noreferrer">${escapeHtml(paper.title)}</a></h3>
      <div class="paper-meta">
        <span class="meta-rank">#${paper.rank}</span>
        ${aiScore !== undefined ? `<span class="meta-score ai">AI ${escapeHtml(aiScore)}</span>` : ""}
        <span class="meta-score">规则 ${escapeHtml(paper.score)}</span>
        ${repoTag}${repoTrendHtml}
        ${authors ? `<span class="meta-line">${authorIcon}<span>${escapeHtml(authors)}</span></span>` : ""}
        ${renderAffiliationInline(affiliations, affiliationIcon)}
        <span class="paper-tag-list">${tagChipsHtml}</span>
      </div>
      ${originalPaperHtml}
      ${tldrHtml}
      ${aiJudgementHtml}
      <div class="paper-actions actions">
        <a class="link-button" href="${escapeAttr(paperUrl)}" target="_blank" rel="noreferrer">${isRepository ? "GitHub" : "arXiv"}</a>
        ${pdfUrl ? `<a class="link-button" href="${escapeAttr(pdfUrl)}" target="_blank" rel="noreferrer">PDF</a>` : ""}
        ${isRepository && paper.repository_homepage ? `<a class="link-button" href="${escapeAttr(paper.repository_homepage)}" target="_blank" rel="noreferrer">主页</a>` : ""}
        ${codeLinks.map((url) => `<a class="link-button" href="${escapeAttr(url)}" target="_blank" rel="noreferrer">代码</a>`).join("")}
        ${codeSearchUrl ? `<a class="link-button" href="${escapeAttr(codeSearchUrl)}" target="_blank" rel="noreferrer">搜代码</a>` : ""}
        <button class="feedback-button like" type="button" data-paper-id="${escapeAttr(paper.paper_id)}" data-feedback-rating="like" data-section="${escapeAttr(section)}">${liked ? "已喜欢" : "喜欢"}</button>
        <button class="feedback-button dislike" type="button" data-paper-id="${escapeAttr(paper.paper_id)}" data-feedback-rating="dislike" data-section="${escapeAttr(section)}">不喜欢</button>
      </div>
    </article>
  `;
}

function renderAffiliationInline(affiliations, iconHtml) {
  if (!affiliations.length) {
    return `<span class="paper-affiliations-inline is-missing">${iconHtml}<span>未解析到作者单位</span></span>`;
  }
  const text = affiliations.slice(0, 2).join("、") + (affiliations.length > 2 ? " 等" : "");
  return `<span class="paper-affiliations-inline" title="${escapeAttr(affiliations.join("; "))}">${iconHtml}<span>作者单位：${escapeHtml(text)}</span></span>`;
}

function renderRepositoryMetaInline(paper) {
  const parts = [];
  const starsToday = Number(paper.repository_stars_today || 0);
  const totalStars = Number(paper.repository_stars || 0);
  const forks = Number(paper.repository_forks || 0);
  const language = String(paper.repository_language || "").trim();
  if (starsToday) parts.push(`今日 +${starsToday}`);
  if (totalStars) parts.push(`★ ${totalStars}`);
  if (forks) parts.push(`fork ${forks}`);
  if (language) parts.push(language);
  return parts.map((part) => `<span class="tag-chip repo">${escapeHtml(part)}</span>`).join("");
}

async function handleFeedbackClick(event) {
  const button = event.target?.closest?.(".feedback-button");
  if (!button) return;
  const paperId = button.dataset.paperId || "";
  const rating = button.dataset.feedbackRating || "";
  if (!paperId || !["like", "dislike"].includes(rating)) return;
  event.preventDefault();
  button.disabled = true;
  try {
    const result = await recordInlineFeedback(paperId, rating);
    markFeedbackState(paperId, rating);
    applyControls();
    const actionText = rating === "like" ? "已标记喜欢" : "已移出今日推荐";
    showToast(`${actionText}，${result.remote ? "反馈已记录" : "反馈已本地保存"}`);
  } catch (error) {
    showToast(error.message || "反馈记录失败", "error");
  } finally {
    button.disabled = false;
  }
}

async function recordInlineFeedback(paperId, rating) {
  const paper = findActivePaper(paperId);
  if (!paper) {
    throw new Error("未找到这篇论文，无法记录反馈。");
  }
  const event = buildFeedbackEvent(paper, rating);
  try {
    await postFeedbackEvent(event);
    return { remote: true };
  } catch (error) {
    storeLocalFeedback(event);
    return { remote: false, error };
  }
}

function buildFeedbackEvent(paper, rating) {
  const sections = Array.isArray(paper.sections) ? paper.sections : [];
  return {
    paper_id: String(paper.paper_id || ""),
    rating,
    source: "page",
    section: String(sections[0] || ""),
    item_type: isRepositoryItem(paper) ? "repository" : "paper",
    title: String(paper.title || ""),
    abstract: String(paper.abstract || ""),
    authors: stringList(paper.authors),
    affiliations: stringList(paper.affiliations),
    categories: stringList(paper.categories),
    repository_url: String(paper.repository_url || ""),
    paper_links: paperLinksFor(paper),
    created_at: new Date().toISOString(),
  };
}

async function postFeedbackEvent(event) {
  const config = window.RECOMMENDER_CONFIG || {};
  if (!config.supabaseUrl || !config.supabaseAnonKey) {
    throw new Error("Supabase 未配置，使用本地反馈队列。");
  }
  const response = await postSupabaseFeedbackPayload(config, feedbackPayload(event));
  if (response.ok) {
    return;
  }
  if (event.item_type === "repository") {
    const legacyResponse = await postSupabaseFeedbackPayload(config, legacyFeedbackPayload(event));
    if (legacyResponse.ok) {
      return;
    }
  }
  throw new Error(`Supabase rejected feedback: ${response.status}`);
}

async function postSupabaseFeedbackPayload(config, payload) {
  return fetch(`${config.supabaseUrl.replace(/\/$/, "")}/rest/v1/feedback_events`, {
    method: "POST",
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${config.supabaseAnonKey}`,
      "Content-Type": "application/json",
      Prefer: "return=minimal",
    },
    body: JSON.stringify(payload),
  });
}

function feedbackPayload(event) {
  return {
    paper_id: event.paper_id,
    rating: event.rating,
    source: event.source,
    section: event.section || null,
    title: event.title,
    abstract: event.abstract,
    authors: event.authors,
    affiliations: event.affiliations,
    categories: event.categories,
    item_type: event.item_type,
    repository_url: event.repository_url || null,
    paper_links: event.paper_links,
  };
}

function legacyFeedbackPayload(event) {
  return {
    paper_id: event.paper_id,
    rating: event.rating,
    source: event.source,
    section: event.section || null,
    title: event.title,
    abstract: event.abstract,
    authors: event.authors,
    affiliations: event.affiliations,
    categories: event.categories,
  };
}

function storeLocalFeedback(event) {
  const existing = readJsonArray(localFeedbackKey);
  existing.push(event);
  localStorage.setItem(localFeedbackKey, JSON.stringify(existing));
}

function markFeedbackState(paperId, rating) {
  const runDate = currentRunDate();
  const state = readFeedbackUiState();
  state.likes[runDate] = state.likes[runDate] || [];
  state.hidden[runDate] = state.hidden[runDate] || [];
  state.likes[runDate] = state.likes[runDate].filter((value) => value !== paperId);
  state.hidden[runDate] = state.hidden[runDate].filter((value) => value !== paperId);
  if (rating === "like") {
    state.likes[runDate].push(paperId);
  }
  if (rating === "dislike") {
    state.hidden[runDate].push(paperId);
  }
  localStorage.setItem(feedbackUiStateKey, JSON.stringify(state));
}

function feedbackStateFor(paperId) {
  const runDate = currentRunDate();
  const state = readFeedbackUiState();
  if ((state.likes[runDate] || []).includes(String(paperId || ""))) return "like";
  if ((state.hidden[runDate] || []).includes(String(paperId || ""))) return "dislike";
  return "";
}

function hiddenPaperIdsForRun() {
  const state = readFeedbackUiState();
  return new Set(state.hidden[currentRunDate()] || []);
}

function readFeedbackUiState() {
  try {
    const state = JSON.parse(localStorage.getItem(feedbackUiStateKey) || "{}");
    return {
      likes: state && typeof state.likes === "object" && !Array.isArray(state.likes) ? state.likes : {},
      hidden: state && typeof state.hidden === "object" && !Array.isArray(state.hidden) ? state.hidden : {},
    };
  } catch {
    return { likes: {}, hidden: {} };
  }
}

function currentRunDate() {
  return String(activePayload?.run_date || "unknown");
}

function findActivePaper(paperId) {
  const targetId = String(paperId || "");
  return (activePayload?.recommendations || []).find((paper) => String(paper.paper_id || "") === targetId) || null;
}

function showToast(message, kind = "info") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  toast.className = `toast${kind === "error" ? " is-error" : ""}`;
  window.clearTimeout?.(showToast.timer);
  showToast.timer = window.setTimeout?.(() => {
    toast.hidden = true;
  }, 2600);
}

function highlightTargetPaper() {
  const paperId = new URLSearchParams(window.location.search).get("paper_id");
  if (!paperId) return;
  const target = document.getElementById(`paper-${escapeAttr(paperId)}`);
  if (!target) return;
  target.classList.add("is-target");
  target.scrollIntoView({ block: "center", behavior: "smooth" });
}

function renderAffiliationBlock(affiliations) {
  const values = stringList(affiliations);
  if (values.length === 0) {
    return '<div class="paper-affiliations is-missing"><strong>作者单位</strong><div><span>未解析到作者单位</span></div></div>';
  }
  const items = values.map((value) => `<span>${escapeHtml(value)}</span>`).join("");
  return `<div class="paper-affiliations"><strong>作者单位</strong><div>${items}</div></div>`;
}

function renderRepositoryMeta(paper) {
  const parts = ["GitHub 仓库"];
  const starsToday = Number(paper.repository_stars_today || 0);
  const totalStars = Number(paper.repository_stars || 0);
  const forks = Number(paper.repository_forks || 0);
  const language = String(paper.repository_language || "").trim();
  const topics = stringList(paper.repository_topics).slice(0, 6);
  if (starsToday) parts.push(`今日新增 star ${starsToday}`);
  if (totalStars) parts.push(`总 star ${totalStars}`);
  if (forks) parts.push(`fork ${forks}`);
  if (language) parts.push(language);
  if (topics.length) parts.push(topics.join(", "));
  return `<div class="repo-meta">${parts.map((part) => `<span>${escapeHtml(part)}</span>`).join("")}</div>`;
}

function renderOriginalPaperLinks(paper) {
  const links = paperLinksFor(paper);
  if (!links.length) return "";
  return `
    <div class="paper-links">
      <strong>原始论文</strong>
      <div>${links.map((link) => `<a href="${escapeAttr(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label)}</a>`).join("")}</div>
    </div>
  `;
}

function paperLinksFor(paper) {
  const rawLinks = Array.isArray(paper.paper_links) ? paper.paper_links : [];
  return rawLinks.map((link) => {
    if (link && typeof link === "object") {
      return {
        label: String(link.label || "Paper"),
        url: String(link.url || ""),
      };
    }
    return { label: "Paper", url: String(link || "") };
  }).filter((link) => link.url);
}

function isRepositoryItem(paper) {
  return String(paper?.item_type || "").toLowerCase() === "repository";
}

function hasAffiliations(paper) {
  return stringList(paper.affiliations).length > 0;
}

function stringList(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function uniqueStrings(values) {
  const seen = new Set();
  const result = [];
  values.forEach((value) => {
    const text = String(value).trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) return;
    seen.add(key);
    result.push(text);
  });
  return result;
}

function normalizeKeyword(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function localFeedbackCount() {
  return readJsonArray(localFeedbackKey).length;
}

function readJsonArray(key) {
  try {
    const events = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(events) ? events : [];
  } catch {
    return [];
  }
}

function githubSearchUrl(paper) {
  const query = paper.title || paper.paper_id || "";
  return query ? `https://github.com/search?q=${encodeURIComponent(query).replaceAll("%20", "+")}&type=repositories` : "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll(" ", "-");
}

function escapeDataAttr(value) {
  return escapeHtml(value);
}

loadRecommendations().then(render).catch((error) => {
  document.getElementById("runDate").textContent = "推荐数据加载失败";
  document.getElementById("recommendations").innerHTML = `<pre class="error">${escapeHtml(error.message)}</pre>`;
});
