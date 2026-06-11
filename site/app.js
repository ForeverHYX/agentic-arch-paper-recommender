async function loadRecommendations() {
  const response = await fetch("recommendations.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load recommendations: ${response.status}`);
  }
  return response.json();
}

function render(payload) {
  const container = document.getElementById("recommendations");
  const runDate = document.getElementById("runDate");
  runDate.textContent = payload.run_date ? `Run date: ${payload.run_date}` : "";
  renderSummaryStats(payload);

  if (!payload.recommendations || payload.recommendations.length === 0) {
    container.innerHTML = '<p class="empty">No matching papers for this run.</p>';
    renderSectionNav(new Map(), {});
    return;
  }

  const groups = new Map();
  const sectionLabels = payload.section_labels || {};
  payload.recommendations.forEach((paper) => {
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

function renderSummaryStats(payload) {
  const target = document.getElementById("summaryStats");
  const recommendations = payload.recommendations || [];
  const sectionCount = new Set(recommendations.map((paper) => paper.sections?.[0] || "exploratory")).size;
  const codeCount = recommendations.filter((paper) => Array.isArray(paper.code_urls) && paper.code_urls.length > 0).length;
  target.innerHTML = `
    <div><strong>${recommendations.length}</strong><span>papers</span></div>
    <div><strong>${sectionCount}</strong><span>sections</span></div>
    <div><strong>${codeCount}</strong><span>code links</span></div>
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
  return `
    <article class="paper" id="paper-${escapeAttr(paper.paper_id)}">
      <div class="paper-meta"><span>#${paper.rank}</span><span>score ${paper.score}</span><span>${escapeHtml(categories)}</span></div>
      <h3>${escapeHtml(paper.title)}</h3>
      <p class="authors">${escapeHtml(authors)}</p>
      ${paper.tldr ? `<p class="paper-tldr">${escapeHtml(paper.tldr)}</p>` : ""}
      <p class="abstract">${escapeHtml(paper.abstract || "")}</p>
      <div class="actions">
        <a class="link-button" href="${escapeAttr(paperUrl)}" target="_blank" rel="noreferrer">Paper</a>
        <a class="link-button" href="${escapeAttr(pdfUrl)}" target="_blank" rel="noreferrer">PDF</a>
        ${codeLinks.map((url) => `<a class="link-button" href="${escapeAttr(url)}" target="_blank" rel="noreferrer">Code</a>`).join("")}
        <a class="feedback-button like" href="${likeUrl}">Like</a>
        <a class="feedback-button dislike" href="${dislikeUrl}">Dislike</a>
      </div>
    </article>
  `;
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
