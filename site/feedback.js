const params = new URLSearchParams(window.location.search);
const paperId = params.get("paper_id");
const rating = params.get("rating");
const source = params.get("source") || "page";
const titleEl = document.getElementById("statusTitle");
const detailEl = document.getElementById("statusDetail");
const localFeedbackKey = "recommender_local_feedback_events";

recordFeedback().catch((error) => {
  titleEl.textContent = "反馈未记录";
  detailEl.textContent = error.message;
});

async function recordFeedback() {
  if (!paperId || !["like", "dislike"].includes(rating)) {
    throw new Error("缺少或无效的反馈参数。");
  }

  const config = window.RECOMMENDER_CONFIG || {};
  if (!config.supabaseUrl || !config.supabaseAnonKey) {
    const paperMetadata = await findPaperMetadata(paperId);
    storeLocalFeedback({
      paper_id: paperId,
      rating,
      source,
      section: params.get("section") || null,
      title: paperMetadata.title,
      abstract: paperMetadata.abstract,
      authors: paperMetadata.authors,
      affiliations: paperMetadata.affiliations,
      categories: paperMetadata.categories,
      created_at: new Date().toISOString(),
    });
    renderLocalFeedbackExport();
    titleEl.textContent = "反馈已保存到本地";
    detailEl.textContent = "这条反馈已本地保存在当前浏览器。配置 Supabase 前，可以在下方导出 JSON 作为临时回灌。";
    return;
  }

  const paperMetadata = await findPaperMetadata(paperId);
  const response = await fetch(`${config.supabaseUrl.replace(/\/$/, "")}/rest/v1/feedback_events`, {
    method: "POST",
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${config.supabaseAnonKey}`,
      "Content-Type": "application/json",
      Prefer: "return=minimal",
    },
    body: JSON.stringify({
      paper_id: paperId,
      rating,
      source,
      section: params.get("section") || null,
      title: paperMetadata.title,
      abstract: paperMetadata.abstract,
      authors: paperMetadata.authors,
      affiliations: paperMetadata.affiliations,
      categories: paperMetadata.categories,
    }),
  });

  if (!response.ok) {
    throw new Error(`Supabase rejected feedback: ${response.status}`);
  }

  titleEl.textContent = "反馈已记录";
  detailEl.textContent = `已为 ${paperId} 记录“${rating === "like" ? "喜欢" : "不喜欢"}”。`;
}

async function findPaperMetadata(targetPaperId) {
  try {
    const response = await fetch("recommendations.json", { cache: "no-store" });
    if (!response.ok) return emptyPaperMetadata();
    const payload = await response.json();
    const paper = (payload.recommendations || []).find((item) => item.paper_id === targetPaperId);
    if (!paper) return emptyPaperMetadata();
    return {
      title: paper.title || "",
      abstract: paper.abstract || "",
      authors: Array.isArray(paper.authors) ? paper.authors : [],
      affiliations: Array.isArray(paper.affiliations) ? paper.affiliations : [],
      categories: Array.isArray(paper.categories) ? paper.categories : [],
    };
  } catch {
    return emptyPaperMetadata();
  }
}

function emptyPaperMetadata() {
  return {
    title: "",
    abstract: "",
    authors: [],
    affiliations: [],
    categories: [],
  };
}

function storeLocalFeedback(event) {
  const existing = readLocalFeedbackEvents();
  existing.push(event);
  localStorage.setItem(localFeedbackKey, JSON.stringify(existing));
}

function readLocalFeedbackEvents() {
  try {
    const events = JSON.parse(localStorage.getItem(localFeedbackKey) || "[]");
    return Array.isArray(events) ? events : [];
  } catch {
    return [];
  }
}

function renderLocalFeedbackExport() {
  const exportEl = document.getElementById("localFeedbackExport");
  const downloadEl = document.getElementById("localFeedbackDownload");
  if (!exportEl || !downloadEl) return;

  const json = JSON.stringify(readLocalFeedbackEvents(), null, 2);
  exportEl.hidden = false;
  exportEl.value = json;
  downloadEl.hidden = false;
  downloadEl.download = "recommender-local-feedback.json";
  downloadEl.href = `data:application/json;charset=utf-8,${encodeURIComponent(json)}`;
}
