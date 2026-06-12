let activePayload = null;

async function loadRecommendations() {
  const response = await fetch("recommendations.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load recommendations: ${response.status}`);
  }
  return response.json();
}

function render(payload) {
  activePayload = payload;
  const runDate = document.getElementById("runDate");
  runDate.textContent = payload.run_date ? `Run date: ${payload.run_date}` : "";
  renderControls(payload);
  applyControls();
}

function renderControls(payload) {
  const sectionFilter = document.getElementById("sectionFilter");
  if (!sectionFilter.dataset.ready) {
    const sectionLabels = payload.section_labels || {};
    const sections = Array.from(new Set((payload.recommendations || []).map((paper) => paper.sections?.[0] || "exploratory")));
    sectionFilter.innerHTML = '<option value="">All sections</option>' + sections.map((section) => {
      const label = sectionLabels[section] || "Exploratory";
      return `<option value="${escapeAttr(section)}">${escapeHtml(label)}</option>`;
    }).join("");
    ["searchInput", "sectionFilter", "minAiScore", "hasCodeFilter", "hasAffiliationFilter", "sortSelect"].forEach((id) => {
      const element = document.getElementById(id);
      element.addEventListener("input", applyControls);
      element.addEventListener("change", applyControls);
    });
    sectionFilter.dataset.ready = "true";
  }
}

function applyControls() {
  if (!activePayload) return;
  const filtered = filteredRecommendations(activePayload.recommendations || [], collectFilterState());
  renderSummaryStats({ ...activePayload, recommendations: filtered });
  renderRecommendationGroups(filtered, activePayload.section_labels || {});
  const resultCount = document.getElementById("resultCount");
  resultCount.textContent = `${filtered.length} / ${(activePayload.recommendations || []).length} papers`;
}

function renderRecommendationGroups(recommendations, sectionLabels) {
  const container = document.getElementById("recommendations");

  if (!recommendations || recommendations.length === 0) {
    container.innerHTML = '<p class="empty">No matching papers for this run.</p>';
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
    const label = sectionLabels[section] || "Exploratory but Maybe Relevant";
    const items = papers.map(renderPaper).join("");
    return `<section class="section" id="section-${escapeAttr(section)}"><div class="section-heading"><h2>${escapeHtml(label)}</h2><span>${papers.length} papers</span></div>${items}</section>`;
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
  };
}

function filteredRecommendations(recommendations, filters) {
  const minAiScore = Number.isFinite(filters.minAiScore) ? filters.minAiScore : 0;
  const filtered = recommendations.filter((paper) => {
    const section = paper.sections?.[0] || "exploratory";
    if (filters.section && section !== filters.section) return false;
    if (filters.hasCode && !(Array.isArray(paper.code_urls) && paper.code_urls.length > 0)) return false;
    if (filters.hasAffiliation && !(Array.isArray(paper.affiliations) && paper.affiliations.length > 0)) return false;
    if (minAiScore && aiScoreFor(paper) < minAiScore) return false;
    if (filters.query && !searchTextFor(paper).includes(filters.query)) return false;
    return true;
  });
  return filtered.sort((left, right) => sortPapers(left, right, filters.sort));
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
    ...(Array.isArray(paper.authors) ? paper.authors : []),
    ...(Array.isArray(paper.affiliations) ? paper.affiliations : []),
    ...(Array.isArray(paper.categories) ? paper.categories : []),
  ].join(" ").toLowerCase();
}

function renderSummaryStats(payload) {
  const target = document.getElementById("summaryStats");
  const recommendations = payload.recommendations || [];
  const sectionCount = new Set(recommendations.map((paper) => paper.sections?.[0] || "exploratory")).size;
  const codeCount = recommendations.filter((paper) => (Array.isArray(paper.code_urls) && paper.code_urls.length > 0) || paper.code_search_url).length;
  const affiliationCount = recommendations.filter(hasAffiliations).length;
  target.innerHTML = `
    <div><strong>${recommendations.length}</strong><span>papers</span></div>
    <div><strong>${sectionCount}</strong><span>sections</span></div>
    <div><strong>${codeCount}</strong><span>code refs</span></div>
    <div><strong>${affiliationCount}</strong><span>with units</span></div>
  `;
}

function renderSectionNav(groups, sectionLabels) {
  const target = document.getElementById("sectionNav");
  if (!groups.size) {
    target.innerHTML = '<span class="empty-nav">No sections</span>';
    return;
  }
  target.innerHTML = Array.from(groups.entries()).map(([section, papers]) => {
    const label = sectionLabels[section] || "Exploratory";
    return `<a href="#section-${escapeAttr(section)}"><span>${escapeHtml(label)}</span><strong>${papers.length}</strong></a>`;
  }).join("");
}

function renderPaper(paper) {
  const feedbackBase = "feedback.html";
  const section = paper.sections?.[0] || "";
  const likeUrl = `${feedbackBase}?paper_id=${encodeURIComponent(paper.paper_id)}&rating=like&source=page&section=${encodeURIComponent(section)}`;
  const dislikeUrl = `${feedbackBase}?paper_id=${encodeURIComponent(paper.paper_id)}&rating=dislike&source=page&section=${encodeURIComponent(section)}`;
  const authors = Array.isArray(paper.authors) ? paper.authors.join(", ") : "";
  const categories = Array.isArray(paper.categories) ? paper.categories.join(", ") : "";
  const paperUrl = paper.url || `https://arxiv.org/abs/${encodeURIComponent(paper.paper_id)}`;
  const pdfUrl = paper.pdf_url || `https://arxiv.org/pdf/${encodeURIComponent(paper.paper_id)}`;
  const codeLinks = Array.isArray(paper.code_urls) ? paper.code_urls : [];
  const codeSearchUrl = paper.code_search_url || githubSearchUrl(paper);
  const aiJudgement = paper.ai_judgement || null;
  const aiScore = aiJudgement?.score ?? paper.ai_score;
  return `
    <article class="paper" id="paper-${escapeAttr(paper.paper_id)}">
      <div class="paper-meta"><span>#${paper.rank}</span><span>rule ${paper.score}</span>${aiScore !== undefined ? `<span>AI ${escapeHtml(aiScore)}</span>` : ""}<span>${escapeHtml(categories)}</span></div>
      <h3>${escapeHtml(paper.title)}</h3>
      <p class="authors">${escapeHtml(authors)}</p>
      ${renderAffiliationBlock(paper.affiliations)}
      ${paper.tldr ? `<div class="paper-tldr"><span>AI 总结</span><p>${escapeHtml(paper.tldr)}</p></div>` : ""}
      ${aiJudgement ? `<div class="ai-judgement"><span>AI 判断</span><p>${escapeHtml(aiJudgement.reason || "")}</p></div>` : ""}
      <p class="abstract">${escapeHtml(paper.abstract || "")}</p>
      <div class="actions">
        <a class="link-button" href="${escapeAttr(paperUrl)}" target="_blank" rel="noreferrer">Paper</a>
        <a class="link-button" href="${escapeAttr(pdfUrl)}" target="_blank" rel="noreferrer">PDF</a>
        ${codeLinks.map((url) => `<a class="link-button" href="${escapeAttr(url)}" target="_blank" rel="noreferrer">Code</a>`).join("")}
        ${codeSearchUrl ? `<a class="link-button" href="${escapeAttr(codeSearchUrl)}" target="_blank" rel="noreferrer">Code Search</a>` : ""}
        <a class="feedback-button like" href="${likeUrl}">Like</a>
        <a class="feedback-button dislike" href="${dislikeUrl}">Dislike</a>
      </div>
    </article>
  `;
}

function renderAffiliationBlock(affiliations) {
  const values = stringList(affiliations);
  if (values.length === 0) {
    return '<div class="paper-affiliations is-missing"><strong>单位</strong><div><span>未解析到作者单位</span></div></div>';
  }
  const items = values.map((value) => `<span>${escapeHtml(value)}</span>`).join("");
  return `<div class="paper-affiliations"><strong>单位</strong><div>${items}</div></div>`;
}

function hasAffiliations(paper) {
  return stringList(paper.affiliations).length > 0;
}

function stringList(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
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

loadRecommendations().then(render).catch((error) => {
  document.getElementById("runDate").textContent = "Failed to load recommendations";
  document.getElementById("recommendations").innerHTML = `<pre class="error">${escapeHtml(error.message)}</pre>`;
});
