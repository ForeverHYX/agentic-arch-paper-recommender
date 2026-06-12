const params = new URLSearchParams(window.location.search);
const paperId = params.get("paper_id");
const rating = params.get("rating");
const source = params.get("source") || "page";
const titleEl = document.getElementById("statusTitle");
const detailEl = document.getElementById("statusDetail");

recordFeedback().catch((error) => {
  titleEl.textContent = "Feedback was not recorded";
  detailEl.textContent = error.message;
});

async function recordFeedback() {
  if (!paperId || !["like", "dislike"].includes(rating)) {
    throw new Error("Missing or invalid feedback parameters.");
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
    titleEl.textContent = "Feedback captured locally";
    detailEl.textContent = "This feedback was stored locally in this browser. Configure Supabase to use it in future daily recommendations.";
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

  titleEl.textContent = "Feedback recorded";
  detailEl.textContent = `Recorded ${rating} for ${paperId}.`;
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
  const key = "recommender_local_feedback_events";
  const existing = JSON.parse(localStorage.getItem(key) || "[]");
  existing.push(event);
  localStorage.setItem(key, JSON.stringify(existing));
}
