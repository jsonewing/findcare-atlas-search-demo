const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const suggestionMenuEl = document.querySelector("#suggestion-menu");
const resultsEl = document.querySelector("#results");
const resultCountEl = document.querySelector("#result-count");
const resultContextEl = document.querySelector("#result-context");
const queryDisplayEl = document.querySelector("#query-display");
const executionDisplayEl = document.querySelector("#execution-display");
const corpusDisplayEl = document.querySelector("#corpus-display");
const queryMetricsEl = document.querySelector("#query-metrics");
const facetSummaryEl = document.querySelector("#facet-summary");
const geoContextEl = document.querySelector("#geo-context");
const mapListEl = document.querySelector("#map-list");
const codeDialog = document.querySelector("#code-dialog");
const codeOutput = document.querySelector("#code-output");
const dialogTitle = document.querySelector("#dialog-title");
const dialogEyebrow = document.querySelector("#dialog-eyebrow");
const codeSummary = document.querySelector("#code-summary");
const codePanel = document.querySelector("#code-panel");
const codeLabel = document.querySelector("#code-label");
const architectureView = document.querySelector("#architecture-view");
const architectureCanvas = document.querySelector("#architecture-canvas");
const scoreExplainer = document.querySelector("#score-explainer");
const closeDialog = document.querySelector("#close-dialog");
const stageTimingsEl = document.querySelector("#stage-timings");
const paginationControlsEl = document.querySelector("#pagination-controls");
const previousPageButton = document.querySelector("#previous-page");
const nextPageButton = document.querySelector("#next-page");
const pageNumberEl = document.querySelector("#page-number");
const setupDialog = document.querySelector("#setup-dialog");
const setupForm = document.querySelector("#setup-form");
const setupOpenButton = document.querySelector("#setup-open");
const setupOpenLabel = document.querySelector("#setup-open-label");
const setupCloseButton = document.querySelector("#setup-close");
const setupSaveButton = document.querySelector("#setup-save");
const setupFeedback = document.querySelector("#setup-feedback");
const setupProgressBar = document.querySelector("#setup-progress-bar");
const setupAtlasInput = document.querySelector("#setup-atlas-uri");
const setupVoyageInput = document.querySelector("#setup-voyage-key");

let lastPayload = null;
let setupState = null;
let liveInitialized = false;
let originLookup = {};
let leafletMap = null;
let markerClusterGroup = null;
let originMarker = null;
let radiusCircle = null;
let providerMarkers = new Map();
let suggestionItems = [];
let activeSuggestionIndex = -1;
let suggestionAbortController = null;
let paginationState = { page: 1, tokens: [null] };

const isFilePreview =
  window.location.protocol === "file:" || new URLSearchParams(window.location.search).get("preview") === "static";
const staticOrigins = [
  { value: "downtown", label: "Downtown Austin", coordinates: [-97.7431, 30.2672] },
  { value: "north", label: "North Austin", coordinates: [-97.713, 30.392] },
  { value: "south", label: "South Austin", coordinates: [-97.8, 30.19] },
  { value: "round_rock", label: "Round Rock", coordinates: [-97.6789, 30.5083] },
  { value: "cedar_park", label: "Cedar Park", coordinates: [-97.8203, 30.5052] },
];
const staticFilters = {
  origins: staticOrigins,
  specialties: [
    { value: "Orthopedic Surgery", count: 1 },
    { value: "Cardiology", count: 1 },
    { value: "Dermatology", count: 1 },
    { value: "Physical Therapy", count: 1 },
    { value: "Urgent Care", count: 1 },
  ],
  networks: [
    { value: "Humana Choice PPO", count: 5 },
    { value: "Medicare Advantage", count: 4 },
    { value: "Commercial HMO", count: 3 },
  ],
  languages: [
    { value: "English", count: 8 },
    { value: "Spanish", count: 3 },
    { value: "Vietnamese", count: 1 },
  ],
};
const staticResults = [
  {
    provider_id: "fc-ortho-001",
    provider_name: "Northstar Orthopedic Institute",
    provider_type: "Facility",
    specialty_name: "Orthopedic Surgery",
    specialty_group: "Surgical",
    aliases: ["ortho", "orthopedics", "bone doctor", "sports medicine"],
    care_summary: "Orthopedic surgeons and sports medicine clinicians treating joint pain, fractures, ACL injuries, and arthritis with surgical and non-surgical care.",
    conditions: ["knee pain", "hip pain", "joint pain", "shoulder injury"],
    procedures: ["knee replacement", "ACL repair", "hip replacement", "rotator cuff repair"],
    insurance_networks: ["Humana Choice PPO", "Medicare Advantage"],
    address_line1: "120 Congress Avenue",
    phone: "(512) 555-0100",
    next_available: "Today, 3:20 PM",
    city: "Austin",
    state: "TX",
    zip: "78701",
    distance_from_origin_miles: 2.4,
    rating: 4.8,
    review_count: 214,
    accepting_new_patients: true,
    telehealth: false,
    languages: ["English", "Spanish"],
    score_type: "scoreDetails",
    score: 0.0178,
    fusion: {
      lexical: { rank: 1, contribution: 0.0098 },
      vector: { rank: 1, contribution: 0.008 },
    },
    location: { type: "Point", coordinates: [-97.7431, 30.2711] },
  },
  {
    provider_id: "fc-pt-003",
    provider_name: "Peak Motion Physical Therapy",
    provider_type: "Facility",
    specialty_name: "Physical Therapy",
    specialty_group: "Rehabilitation",
    aliases: ["PT", "physiotherapy", "rehab clinic"],
    care_summary: "Outpatient rehabilitation clinic supporting recovery after surgery, sports injuries, balance issues, and chronic back pain.",
    conditions: ["back pain", "knee injury", "post surgical rehab", "balance problems"],
    procedures: ["gait training", "manual therapy", "sports rehabilitation", "post-op therapy"],
    insurance_networks: ["Humana Choice PPO", "Medicare Advantage", "Commercial HMO"],
    address_line1: "339 South Lamar Boulevard",
    phone: "(512) 555-0103",
    next_available: "Monday, 10:30 AM",
    city: "Austin",
    state: "TX",
    zip: "78745",
    distance_from_origin_miles: 6.8,
    rating: 4.9,
    review_count: 301,
    accepting_new_patients: true,
    telehealth: false,
    languages: ["English", "Spanish"],
    score_type: "scoreDetails",
    score: 0.0155,
    fusion: {
      lexical: { rank: 2, contribution: 0.0089 },
      vector: { rank: 2, contribution: 0.0066 },
    },
    location: { type: "Point", coordinates: [-97.797, 30.2065] },
  },
  {
    provider_id: "fc-imaging-012",
    provider_name: "Metro Diagnostic Imaging",
    provider_type: "Facility",
    specialty_name: "Radiology",
    specialty_group: "Diagnostics",
    aliases: ["imaging center", "radiology", "MRI center", "xray"],
    care_summary: "Imaging center offering MRI, CT, ultrasound, and x-ray services for injury evaluation and physician referrals.",
    conditions: ["joint injury", "back pain", "abdominal pain", "fracture evaluation"],
    procedures: ["MRI", "CT scan", "ultrasound", "x-ray"],
    insurance_networks: ["Humana Choice PPO", "Commercial HMO"],
    address_line1: "923 East 7th Street",
    phone: "(512) 555-0111",
    next_available: "Tomorrow, 2:15 PM",
    city: "Austin",
    state: "TX",
    zip: "78723",
    distance_from_origin_miles: 5.9,
    rating: 4.5,
    review_count: 144,
    accepting_new_patients: true,
    telehealth: false,
    languages: ["English"],
    score_type: "vectorSearchScore",
    score: 0.0138,
    location: { type: "Point", coordinates: [-97.6848, 30.3072] },
  },
  {
    provider_id: "fc-card-002",
    provider_name: "Riverbend Heart and Vascular",
    provider_type: "Practice",
    specialty_name: "Cardiology",
    specialty_group: "Medical",
    aliases: ["cardio", "heart doctor", "cardiologist"],
    care_summary: "Cardiology group focused on preventive heart care, rhythm evaluation, blood pressure management, and diagnostic testing.",
    conditions: ["chest pain", "high blood pressure", "atrial fibrillation", "heart failure"],
    procedures: ["stress test", "echocardiogram", "EKG", "cardiac clearance"],
    insurance_networks: ["Humana Choice PPO", "Commercial HMO"],
    address_line1: "193 West 38th Street",
    phone: "(512) 555-0101",
    next_available: "Tomorrow, 9:40 AM",
    city: "Austin",
    state: "TX",
    zip: "78705",
    distance_from_origin_miles: 4.1,
    rating: 4.7,
    review_count: 189,
    accepting_new_patients: true,
    telehealth: true,
    languages: ["English"],
    score_type: "searchScore",
    score: 0.0121,
    location: { type: "Point", coordinates: [-97.7394, 30.293] },
  },
];

const staticPreviewStopWords = new Set(["a", "an", "and", "at", "by", "for", "from", "in", "me", "my", "near", "of", "on", "the", "to", "who", "with"]);

function staticPreviewMatches(payload) {
  const terms = [...new Set((payload.query.toLowerCase().match(/[a-z0-9]+/g) || []))]
    .filter((term) => !staticPreviewStopWords.has(term));
  const requiredMatches = Math.min(terms.length >= 4 && terms.length <= 5 ? 3 : 2, terms.length || 1);
  const filters = payload.filters || {};

  return staticResults
    .filter((result) => !filters.specialty || result.specialty_name.toLowerCase() === filters.specialty.toLowerCase())
    .filter((result) => !filters.network || result.insurance_networks.some((network) => network.toLowerCase() === filters.network.toLowerCase()))
    .filter((result) => !filters.language || result.languages.some((language) => language.toLowerCase() === filters.language.toLowerCase()))
    .filter((result) => !filters.accepting_new_patients || result.accepting_new_patients)
    .filter((result) => !filters.telehealth || result.telehealth)
    .filter((result) => !filters.min_rating || result.rating >= Number(filters.min_rating))
    .filter((result) => !filters.max_distance || result.distance_from_origin_miles <= Number(filters.max_distance))
    .map((result, index) => {
      const text = [
        result.provider_name,
        result.specialty_name,
        ...(result.aliases || []),
        ...(result.conditions || []),
        ...(result.procedures || []),
        result.care_summary,
      ].join(" ").toLowerCase();
      const termMatches = terms.filter((term) => text.includes(term)).length;
      return { ...result, score_type: "previewMatch", score: termMatches, _previewIndex: index };
    })
    .filter((result) => result.score >= requiredMatches)
    .sort((left, right) => right.score - left.score || left._previewIndex - right._previewIndex)
    .slice(0, payload.limit)
    .map(({ _previewIndex, ...result }) => result);
}

function staticPreviewFacets(results) {
  const counts = new Map();
  results.forEach((result) => counts.set(result.specialty_name, (counts.get(result.specialty_name) || 0) + 1));
  return [...counts.entries()].map(([value, count]) => ({ value, count }));
}

const staticCodeExamples = {
  vectorIndex: {
    fields: [
      { type: "vector", path: "embedding", numDimensions: 1024, similarity: "cosine", quantization: "scalar" },
      { type: "filter", path: "document_type" },
      { type: "filter", path: "specialty_filter" },
      { type: "filter", path: "networks_filter" },
      { type: "filter", path: "languages_filter" },
      { type: "filter", path: "accepting_new_patients" },
      { type: "filter", path: "telehealth" },
      { type: "filter", path: "rating" },
    ],
  },
  searchIndex: {
    analyzer: "lucene.standard",
    searchAnalyzer: "lucene.standard",
    mappings: {
      dynamic: false,
      fields: {
        document_type: { type: "token" },
        provider_id: { type: "token" },
        provider_name: { type: "string" },
        specialty_name: { type: "string" },
        aliases: { type: "string" },
        conditions: { type: "string" },
        procedures: { type: "string" },
        autocomplete_text: { type: "autocomplete", tokenization: "edgeGram" },
        specialty_filter: { type: "token", normalizer: "lowercase" },
        networks_filter: { type: "token", normalizer: "lowercase" },
        languages_filter: { type: "token", normalizer: "lowercase" },
        location: { type: "geo" },
        rating: { type: "number" },
        accepting_new_patients: { type: "boolean" },
        telehealth: { type: "boolean" },
      },
    },
    synonyms: [
      {
        name: "medical_synonyms",
        analyzer: "lucene.standard",
        source: { collection: "medical_synonyms" },
      },
    ],
  },
  sample: { documents: staticResults.slice(0, 3) },
  pipeline: {
    $rankFusion: {
      input: {
        pipelines: {
          lexicalPipeline: [{ $search: { index: "search_index", compound: { should: ["phrase", "fuzzy clinical text", "medical synonyms"] } } }, { $limit: 50 }],
          vectorPipeline: [{ $vectorSearch: { index: "vector_index", path: "embedding", queryVector: "<Voyage voyage-4 embedding>", numCandidates: 1000, limit: 50 } }],
        },
      },
      combination: { weights: { lexicalPipeline: 0.55, vectorPipeline: 0.45 } },
      scoreDetails: true,
    },
  },
  geo: {
    search_filter_example: {
      compound: {
        filter: [
          {
            geoWithin: {
              path: "location",
              circle: {
                center: "<selected origin GeoJSON Point>",
                radius: "<selected miles converted to meters>",
              },
            },
          },
        ],
      },
    },
    regular_geo_index: { location: "2dsphere" },
    preview_results: staticResults.map((result) => ({
      provider_name: result.provider_name,
      location: result.location,
      distance_from_origin_miles: result.distance_from_origin_miles,
    })),
  },
};

const setupStageOrder = ["atlas", "voyage", "data", "save", "portal"];

function updateConnectionButton() {
  const configured = Boolean(setupState?.configured);
  setupOpenButton.classList.toggle("connected", configured);
  setupOpenButton.classList.toggle("required", !configured);
  setupOpenLabel.textContent = configured ? "Connected" : "Set up connection";
  setupOpenButton.title = configured
    ? `Connected to ${setupState.atlas_target}. Select to change local settings.`
    : "Configure local Atlas and Voyage connections";
}

function resetSetupProgress() {
  document.querySelectorAll("[data-setup-stage]").forEach((row) => {
    row.className = "setup-stage";
    row.querySelector("small").textContent = row.dataset.setupStage === "data"
      ? "Waiting for Atlas"
      : row.dataset.setupStage === "save"
        ? "Not written yet"
        : row.dataset.setupStage === "portal"
          ? "Waiting for connections"
          : "Waiting to validate";
    row.querySelector("em").textContent = "Pending";
  });
  setupProgressBar.style.width = "0%";
}

function setSetupStage(stage, status, message) {
  const row = document.querySelector(`[data-setup-stage="${stage}"]`);
  if (!row) return;
  row.className = `setup-stage ${status}`;
  row.querySelector("small").textContent = message;
  row.querySelector("em").textContent = status === "running"
    ? "Checking"
    : status === "complete"
      ? "Ready"
      : status === "warning"
        ? "Review"
        : status === "error"
          ? "Failed"
          : "Pending";

  const progress = setupStageOrder.reduce((total, name) => {
    const state = document.querySelector(`[data-setup-stage="${name}"]`)?.className || "";
    if (state.includes("complete") || state.includes("warning")) return total + 1;
    if (state.includes("running")) return total + 0.45;
    return total;
  }, 0);
  setupProgressBar.style.width = `${Math.round((progress / setupStageOrder.length) * 100)}%`;
}

function openSetup(required = false) {
  setupDialog.dataset.required = String(required);
  setupCloseButton.disabled = required;
  setupAtlasInput.value = "";
  setupVoyageInput.value = "";
  setupAtlasInput.placeholder = setupState?.atlas_configured
    ? "Saved locally - enter a value only to replace it"
    : "mongodb+srv://username:password@cluster.mongodb.net/";
  setupVoyageInput.placeholder = setupState?.voyage_configured
    ? "Saved locally - enter a value only to replace it"
    : "pa-...";
  document.querySelector("#setup-database").value = setupState?.database || "findcare_demo";
  document.querySelector("#setup-collection").value = setupState?.collection || "care_providers";
  document.querySelector("#setup-show-values").checked = false;
  document.querySelector("#setup-install-data").checked = true;
  setupAtlasInput.type = "password";
  setupVoyageInput.type = "password";
  setupSaveButton.disabled = false;
  setupSaveButton.dataset.ready = "false";
  setupSaveButton.textContent = "Verify and save";
  setupFeedback.className = "setup-feedback";
  setupFeedback.textContent = required
    ? "Complete this one-time setup to activate live Atlas Search."
    : "Saved values stay hidden. Leave a credential blank to keep its current value.";
  document.querySelector("#setup-storage").textContent = setupState?.storage
    ? `Saved to ${setupState.storage}`
    : "Saved locally in this application folder";
  resetSetupProgress();
  if (!setupDialog.open) setupDialog.showModal();
}

function closeSetup() {
  if (setupDialog.dataset.required === "true") return;
  setupDialog.close();
}

function applySetupEvent(event) {
  if (event.stage === "atlas") {
    setSetupStage("atlas", event.status, event.message);
    if (event.status === "complete" && event.readiness) {
      const indexes = Object.values(event.readiness.indexes || {});
      const queryable = indexes.filter((index) => index.queryable).length;
      const message = `${event.readiness.documents} providers · ${queryable}/${indexes.length} search indexes ready`;
      setSetupStage("data", event.readiness.ready ? "complete" : "warning", message);
    }
  } else if (["voyage", "data", "save"].includes(event.stage)) {
    setSetupStage(event.stage, event.status, event.message);
  }
  if (event.status === "error") throw new Error(event.message || "Connection validation failed");
  return event.setup || null;
}

async function readSetupEvents(response) {
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Connection validation failed");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completedSetup = null;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      completedSetup = applySetupEvent(JSON.parse(line)) || completedSetup;
    }
    if (done) break;
  }
  if (buffer.trim()) completedSetup = applySetupEvent(JSON.parse(buffer)) || completedSetup;
  if (!completedSetup) throw new Error("Setup ended before readiness was confirmed");
  return completedSetup;
}

function formPayload({ page = 1, pageToken = null } = {}) {
  const data = new FormData(form);
  return {
    query: data.get("query").trim(),
    mode: data.get("mode"),
    rerank: data.get("rerank") === "on",
    limit: Number(data.get("limit") || 12),
    hybrid_profile: data.get("hybrid_profile") || "balanced",
    page,
    page_token: pageToken,
    filters: {
      origin: data.get("origin") || "downtown",
      sort: data.get("sort") || "relevance",
      specialty: data.get("specialty") || null,
      network: data.get("network") || null,
      language: data.get("language") || null,
      max_distance: data.get("max_distance") ? Number(data.get("max_distance")) : null,
      min_rating: data.get("min_rating") ? Number(data.get("min_rating")) : null,
      accepting_new_patients: data.get("accepting_new_patients") === "on",
      telehealth: data.get("telehealth") === "on",
    },
  };
}

function optionList(select, values) {
  for (const item of values || []) {
    const value = typeof item === "string" ? item : item.value;
    const count = typeof item === "string" ? null : item.count;
    const option = document.createElement("option");
    option.value = value;
    const label = displayFacetValue(value);
    option.textContent = count == null ? label : `${label} (${count})`;
    select.appendChild(option);
  }
}

function displayFacetValue(value) {
  return value
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bPpo\b/g, "PPO")
    .replace(/\bHmo\b/g, "HMO")
    .replace(/\bEpo\b/g, "EPO")
    .replace(/\bHsa\b/g, "HSA")
    .replace(/\bAetna\b/g, "AETNA");
}

function formatTiming(value) {
  if (value == null) return "--";
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Number(value).toFixed(1)} ms`;
}

function renderStageTimings(payload) {
  if (!stageTimingsEl) return;
  const stages = payload?.metrics?.stages;
  if (!stages) {
    stageTimingsEl.hidden = true;
    return;
  }

  const entries = [
    ["Embedding", payload.mode === "lexical" ? "Not used" : formatTiming(stages.embedding_ms), "Voyage query vector"],
    ["Atlas retrieval", formatTiming(stages.retrieval_ms), payload.execution?.replace(" + Voyage rerank", "") || "Search"],
    ["Facets", formatTiming(stages.facets_ms), "$searchMeta"],
    ["Rerank", payload.rerank ? formatTiming(stages.rerank_ms) : "Off", "Voyage rerank"],
    ["End to end", formatTiming(stages.total_ms), "Server timing"],
  ];
  stageTimingsEl.innerHTML = `
    <summary class="timing-summary">
      <span class="timing-summary-main">
        <span class="timing-summary-label">Execution trace <em>Demo only</em></span>
        <small>Demo telemetry · ${escapeHtml(formatTiming(stages.total_ms))} end to end</small>
      </span>
      <span class="timing-disclosure">
        <span class="timing-show">Show details</span>
        <span class="timing-hide">Hide details</span>
        <i aria-hidden="true"></i>
      </span>
    </summary>
    <div class="timing-grid">
      ${entries.map(([label, value, detail]) => `
        <div class="timing-stage">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
          <small>${escapeHtml(detail)}</small>
        </div>
      `).join("")}
      <p class="timing-disclaimer">
        <strong>Demo telemetry.</strong> Includes application orchestration, Voyage AI network time, and a separate facet request. Production latency varies with deployment topology, load, index design, candidate windows, connection reuse, and caching.
      </p>
    </div>
  `;
  stageTimingsEl.hidden = false;
}

function renderPagination(payload) {
  if (!paginationControlsEl) return;
  const pagination = payload?.pagination || {};
  const enabled = Boolean(pagination.enabled);
  const visible = enabled && (pagination.has_more || (pagination.page || 1) > 1);
  paginationControlsEl.hidden = !visible;
  if (!visible) return;

  paginationState.page = pagination.page || 1;
  if (pagination.next_token) paginationState.tokens[paginationState.page] = pagination.next_token;
  pageNumberEl.textContent = String(paginationState.page);
  previousPageButton.disabled = paginationState.page <= 1;
  nextPageButton.disabled = !pagination.has_more;
}

function formatScore(result) {
  if (result.reranked) return `Rerank ${Number(result.rerank_score).toFixed(3)}`;
  const score = typeof result.score === "number" ? result.score : result.score?.value;
  if (result.score_type === "previewMatch") return "Preview match";
  if (typeof score === "number" && result.score_type === "searchScore") return `Search ${score.toFixed(3)}`;
  if (typeof score === "number" && result.score_type === "vectorSearchScore") return `Vector ${score.toFixed(4)}`;
  if (typeof score === "number" && ["scoreDetails", "clientRRF"].includes(result.score_type)) return `RRF ${score.toFixed(5)}`;
  if (typeof score === "number") return `Score ${score.toFixed(4)}`;
  if (result.score_type === "scoreDetails") return "Rank fusion";
  return result.score_type || "Ranked";
}

function scoreExplanation(result) {
  if (result.reranked) return "Voyage relevance score after reranking the Atlas candidate set";
  if (result.score_type === "previewMatch") return "Offline preview based on local term overlap; not an Atlas score";
  if (result.score_type === "searchScore") return "Atlas Search relevance score";
  if (result.score_type === "vectorSearchScore") return "Atlas Vector Search similarity score";
  if (["scoreDetails", "clientRRF"].includes(result.score_type)) {
    return "Reciprocal Rank Fusion score: sum of weight × 1 / (60 + source rank)";
  }
  return "Retrieval score";
}

function distanceLabel(result) {
  const distance = result.distance_from_origin_miles ?? result.distance_miles;
  return distance == null ? "" : `${distance} miles`;
}

function specialtyTone(specialty) {
  if (/card/i.test(specialty)) return "heart";
  if (/derm|skin/i.test(specialty)) return "skin";
  if (/urgent/i.test(specialty)) return "urgent";
  if (/radiology|imaging/i.test(specialty)) return "image";
  if (/ortho|physical/i.test(specialty)) return "ortho";
  return "default";
}

function availabilityLabel(result) {
  if (result.accepting_new_patients && result.telehealth) return "New patients + virtual";
  if (result.accepting_new_patients) return "Accepting new patients";
  if (result.telehealth) return "Virtual care";
  return "Limited availability";
}

function memberAddress(result) {
  const locality = `${result.city || ""}, ${result.state || ""} ${result.zip || ""}`.trim();
  return result.address_line1 ? `${result.address_line1}, ${locality}` : locality;
}

function nextAvailability(result, index) {
  if (result.next_available) return result.next_available;
  if (!result.accepting_new_patients) return "Call for availability";
  return ["Today, 3:20 PM", "Tomorrow, 9:40 AM", "Tomorrow, 2:15 PM", "Monday, 10:30 AM"][index % 4];
}

function formatExecutionLabel(payload) {
  if (!payload) return "Ranked by the selected retrieval strategy";
  const mode = payload.mode === "lexical" ? "Full text" : payload.mode.charAt(0).toUpperCase() + payload.mode.slice(1);
  return `${mode} results using ${payload.execution}`;
}

function getExecutionDescription(mode, execution) {
  const descriptions = {
    "$search": "Keyword-based full-text search with BM25 relevance, phrase boosts, typo tolerance, and medical synonym expansion.",
    "$vectorSearch": "Semantic search using AI embeddings. Finds conceptually similar results even without exact keyword matches.",
    "$rankFusion": "Atlas combines bounded keyword and semantic result lists with weighted Reciprocal Rank Fusion and native score details.",
    "client-side RRF fallback": "Client-side hybrid search using keyword + semantic similarity. Similar to $rankFusion but runs in application (MongoDB <8.0 compatibility).",
    "Static preview": "Offline preview using representative provider results. Start the API with `make run` for live Atlas Search, Vector Search, and rankFusion queries.",
  };
  const baseExecution = execution?.replace(" + Voyage rerank", "");
  const description = descriptions[baseExecution] || descriptions["$search"];
  return execution?.includes("Voyage rerank")
    ? `${description} Voyage rerank then reorders the retrieved candidate set.`
    : description;
}

function getSearchModeInfo(mode) {
  const modeInfo = {
    "hybrid": {
      description: "Combining keyword matching with semantic similarity for best results",
      color: "#10b981"
    },
    "lexical": {
      description: "Exact keyword and phrase matching with fuzzy typo tolerance",
      color: "#f97316"
    },
    "vector": {
      description: "Semantic similarity using AI embeddings for concept-based search",
      color: "#8b5cf6"
    }
  };
  return modeInfo[mode] || modeInfo.hybrid;
}

function updateSearchInsights(payload) {
  // Update mode indicator
  const activeModeInput = document.querySelector('input[name="mode"]:checked');
  const activeMode = activeModeInput ? activeModeInput.value : "hybrid";
  const modeInfo = getSearchModeInfo(activeMode);

  // Update all mode badges and radio buttons
  document.querySelectorAll('.segmented-small input[type="radio"]').forEach(input => {
    input.checked = (input.value === activeMode);
  });

  // Update mode description
  const modeDescEl = document.querySelector('#mode-description');
  if (modeDescEl) {
    modeDescEl.textContent = modeInfo.description;
  }

  // Update execution strategy
  const executionLabel = payload?.execution || "Ready";
  const executionDescription = getExecutionDescription(activeMode, executionLabel);
  const executionBadgeEl = document.querySelector('#execution-badge');
  if (executionBadgeEl) {
    executionBadgeEl.querySelector('strong').textContent = executionLabel;
    executionBadgeEl.querySelector('small').textContent = executionDescription;
  }

  // Update score breakdown for hybrid/ranked results
  const fusionBreakdownEl = document.querySelector('#fusion-breakdown');
  if (payload?.features?.static_preview) {
    fusionBreakdownEl.innerHTML = `
      <div class="breakdown-item">
        <div class="breakdown-label">
          <div class="breakdown-label-icon lexical-signal">UI</div>
          <span>Offline preview</span>
        </div>
        <div class="breakdown-value">
          <small class="breakdown-rank">No Atlas score</small>
        </div>
      </div>
    `;
  } else if (payload && payload.results && payload.results.length > 0) {
    const firstResult = payload.results[0];
    if (firstResult.fusion && (firstResult.fusion.lexical || firstResult.fusion.vector)) {
      let html = '';
      if (firstResult.fusion.lexical) {
        const lexical = firstResult.fusion.lexical;
        html += `
          <div class="breakdown-item">
            <div class="breakdown-label">
              <div class="breakdown-label-icon lexical-signal">FT</div>
              <span>Full Text</span>
            </div>
            <div class="breakdown-value">
              <div>Rank #${lexical.rank}</div>
              <small class="breakdown-rank">${Math.round((lexical.weight ?? 0.55) * 100)}% · +${Number(lexical.contribution || 0).toFixed(5)}</small>
            </div>
          </div>
        `;
      }
      if (firstResult.fusion.vector) {
        const vector = firstResult.fusion.vector;
        html += `
          <div class="breakdown-item">
            <div class="breakdown-label">
              <div class="breakdown-label-icon vector-signal">VS</div>
              <span>Semantic</span>
            </div>
            <div class="breakdown-value">
              <div>Rank #${vector.rank}</div>
              <small class="breakdown-rank">${Math.round((vector.weight ?? 0.45) * 100)}% · +${Number(vector.contribution || 0).toFixed(5)}</small>
            </div>
          </div>
        `;
      }
      if (firstResult.reranked) {
        html += `
          <div class="breakdown-item rerank-breakdown">
            <div class="breakdown-label">
              <div class="breakdown-label-icon rerank-signal">RR</div>
              <span>Voyage rerank</span>
            </div>
            <div class="breakdown-value">
              <div>Final rank #1</div>
              <small class="breakdown-rank">${Number(firstResult.rerank_score).toFixed(3)} relevance</small>
            </div>
          </div>
        `;
      }
      if (html) {
        fusionBreakdownEl.innerHTML = html;
      }
    } else if (firstResult.reranked) {
      fusionBreakdownEl.innerHTML = `
        <div class="breakdown-item">
          <div class="breakdown-label">
            <div class="breakdown-label-icon rerank-signal">RR</div>
            <span>Reranked</span>
          </div>
          <div class="breakdown-value">
            <div>Final rank #1</div>
            <small class="breakdown-rank">${firstResult.rerank_score.toFixed(3)} relevance</small>
          </div>
        </div>
      `;
    } else if (activeMode === "hybrid") {
      // Show default hybrid fusion weights even if detailed breakdown unavailable
      const profileWeights = {
        balanced: [55, 45],
        precision: [75, 25],
        discovery: [35, 65],
      }[payload.hybrid_profile || "balanced"];
      fusionBreakdownEl.innerHTML = `
        <div class="breakdown-item">
          <div class="breakdown-label">
            <div class="breakdown-label-icon lexical-signal">FT</div>
            <span>Full Text</span>
          </div>
          <div class="breakdown-value">
            <small class="breakdown-rank">${profileWeights[0]}% weight</small>
          </div>
        </div>
        <div class="breakdown-item">
          <div class="breakdown-label">
            <div class="breakdown-label-icon vector-signal">VS</div>
            <span>Semantic</span>
          </div>
          <div class="breakdown-value">
            <small class="breakdown-rank">${profileWeights[1]}% weight</small>
          </div>
        </div>
      `;
    } else {
      const isLexical = activeMode === "lexical";
      const score = Number(firstResult.score || 0);
      fusionBreakdownEl.innerHTML = `
        <div class="breakdown-item">
          <div class="breakdown-label">
            <div class="breakdown-label-icon ${isLexical ? "lexical-signal" : "vector-signal"}">${isLexical ? "FT" : "VS"}</div>
            <span>${isLexical ? "Atlas Search" : "Vector similarity"}</span>
          </div>
          <div class="breakdown-value">
            <div>Rank #1</div>
            <small class="breakdown-rank">${score.toFixed(isLexical ? 3 : 4)} score</small>
          </div>
        </div>
      `;
    }
  }

  // Update active filters display
  const filters = payload?.filters || {};
  const activeFilters = Object.entries(filters)
    .filter(([key, value]) => (
      value
      && value !== null
      && value !== false
      && !(key === "origin" && value === "downtown")
      && !(key === "sort" && value === "relevance")
    ))
    .map(([key, value]) => {
      const labels = {
        specialty: "Specialty",
        network: "Insurance",
        language: "Language",
        max_distance: "Distance",
        min_rating: "Rating",
        accepting_new_patients: "New Patients",
        telehealth: "Telehealth",
      };
      return { label: labels[key] || key, value };
    });

  const filterCountEl = document.querySelector('#filter-count');
  const activeFiltersEl = document.querySelector('#active-filters');
  if (filterCountEl && activeFiltersEl) {
    if (activeFilters.length === 0) {
      filterCountEl.textContent = "None";
      activeFiltersEl.innerHTML = '<p class="no-filters">All providers shown</p>';
    } else {
      filterCountEl.textContent = `${activeFilters.length} applied`;
      activeFiltersEl.innerHTML = activeFilters.map(f => `
        <div class="filter-tag">
          <div class="filter-tag-icon">✓</div>
          <strong>${f.label}</strong>: ${f.value === true ? "Yes" : displayFacetValue(String(f.value))}
        </div>
      `).join('');
    }
  }
}

function scoreDetailsSummary(result) {
  const badges = [];
  if (result.reranked && result.original_rank) {
    badges.push(`Original rank #${result.original_rank}`);
  }
  if (result.fusion?.lexical) {
    badges.push(`Text rank #${result.fusion.lexical.rank}`);
  }
  if (result.fusion?.vector) {
    badges.push(`Semantic rank #${result.fusion.vector.rank}`);
  }
  if (result.score_type === "scoreDetails" && !result.fusion) {
    badges.push("Hybrid: Lexical + Semantic");
  }
  return badges;
}

function scoreDetailsBlock(result, index) {
  if (!result.score && !result.fusion && !result.reranked) return "";
  return `
    <details class="score-details">
      <summary>Score details</summary>
      <pre id="score-details-${index}"></pre>
    </details>
  `;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function highlightBlock(result) {
  const highlights = (result.highlights || []).slice(0, 3);
  if (!highlights.length) return "";
  const snippets = highlights.map((highlight) => {
    const text = (highlight.texts || []).map((part) => {
      const value = escapeHtml(part.value);
      return part.type === "hit" ? `<mark>${value}</mark>` : value;
    }).join("");
    return `<span><small>${escapeHtml(displayFacetValue(highlight.path.replaceAll("_", " ")))}</small>${text}</span>`;
  });
  return `<div class="match-evidence"><strong>Matched evidence</strong>${snippets.join("")}</div>`;
}

function retrievalEvidenceBlock(result, mode, features = {}) {
  if (features.static_preview) {
    return `
      <details class="retrieval-evidence">
        <summary>
          <span>Why this preview matched</span>
          <small>Local term overlap · Not Atlas-ranked</small>
        </summary>
        <div class="evidence-content">
          <p class="evidence-note">This offline card only previews the interface. Start the application and use the HTTP URL for Atlas Search scoring, highlights, synonyms, Vector Search, and rank fusion.</p>
        </div>
      </details>
    `;
  }
  const signals = [];
  if (mode === "lexical" || mode === "hybrid") {
    signals.push("BM25 + field boosts");
    if (features.synonym_mapping) signals.push("Synonym-aware query");
  }
  if (mode === "vector" || mode === "hybrid") signals.push("Voyage semantic intent");
  if (result.reranked) signals.push("Voyage reranked");

  const concepts = [...(result.conditions || []), ...(result.procedures || [])].slice(0, 5);
  const semanticEvidence = mode === "vector" || mode === "hybrid"
    ? `
      <div class="semantic-evidence">
        <strong>Semantic context</strong>
        <p>Voyage compares the member query with the provider profile embedding; these indexed concepts provide human-readable context.</p>
        <div>${concepts.map((concept) => `<span>${escapeHtml(concept)}</span>`).join("")}</div>
      </div>
    `
    : "";
  const lexicalEvidence = highlightBlock(result);

  return `
    <details class="retrieval-evidence">
      <summary>
        <span>Why this matched</span>
        <small>${escapeHtml(signals.join(" · "))}</small>
      </summary>
      <div class="evidence-content">
        <div class="evidence-signal-row">
          ${signals.map((signal) => `<span>${escapeHtml(signal)}</span>`).join("")}
        </div>
        ${lexicalEvidence || (mode === "lexical" ? '<p class="evidence-note">The result matched the weighted lexical query; Atlas returned no highlight fragment for this document.</p>' : "")}
        ${semanticEvidence}
      </div>
    </details>
  `;
}

function renderFacetSummary(facets) {
  if (!facetSummaryEl) return;
  const topSpecialties = (facets?.specialties || []).slice(0, 4);
  const selected = form.elements.specialty.value;
  facetSummaryEl.innerHTML = topSpecialties.length
    ? `<span class="facet-source">Atlas facets <button type="button" class="facet-help-button" title="Understand Atlas facets" aria-label="Understand Atlas facets" data-code="facets">?</button></span>${topSpecialties.map((facet) => (
        `<button type="button" class="facet-action${selected === facet.value ? " active" : ""}" data-facet="specialty" data-value="${escapeHtml(facet.value)}" aria-pressed="${selected === facet.value}">${escapeHtml(displayFacetValue(facet.value))}<strong>${facet.count}</strong></button>`
      )).join("")}`
    : "";
}

function renderResults(results, totalMatches = null, mode = "hybrid", features = {}) {
  resultsEl.innerHTML = "";
  if (mode === "lexical" && totalMatches != null) {
    resultCountEl.textContent = totalMatches > results.length
      ? `${results.length} of ${totalMatches} matches`
      : `${totalMatches} ${totalMatches === 1 ? "match" : "matches"}`;
  } else {
    resultCountEl.textContent = `${results.length} ranked ${results.length === 1 ? "result" : "results"}`;
  }

  if (!results.length) {
    resultsEl.innerHTML = '<p class="empty-state">No matching care options found.</p>';
    return;
  }

  for (const [index, result] of results.entries()) {
    const card = document.createElement("article");
    const tone = specialtyTone(result.specialty_name);
    card.className = `result-card ${tone}`;
    const scoreBadges = scoreDetailsSummary(result);
    const appointment = nextAvailability(result, index);
    const visitType = result.telehealth ? "In-person or video visit" : "In-person visit";
    const networkSummary = (result.insurance_networks || []).slice(0, 2).join(" · ") || "Contact for coverage";
    const languageSummary = (result.languages || []).join(", ") || "English";
    const displayRank = mode === "lexical" && result.original_rank ? result.original_rank : index + 1;

    card.innerHTML = `
      <div class="rank">${displayRank}</div>
      <div class="result-body">
        <div class="result-title-row">
          <div>
            <div class="specialty-kicker">${result.specialty_name}</div>
            <h3></h3>
            <p class="subhead"></p>
          </div>
          <span class="score-pill" title="${escapeHtml(scoreExplanation(result))}">${formatScore(result)}</span>
        </div>
        <div class="member-meta-row">
          <span>${escapeHtml(memberAddress(result))}</span>
          <span>${escapeHtml(result.phone || "(512) 555-0100")}</span>
          <span>${escapeHtml(languageSummary)}</span>
        </div>
        <div class="member-status-row">
          <span class="member-chip ${result.accepting_new_patients ? "available" : "limited"}">${escapeHtml(availabilityLabel(result))}</span>
          ${result.telehealth ? '<span class="member-chip virtual">Video visits</span>' : ""}
        </div>
        <div class="result-metrics">
          <span><strong>${distanceLabel(result)}</strong><small>from origin</small></span>
          <span><strong>${result.rating} / 5</strong><small>${result.review_count} reviews</small></span>
          <span><strong>${escapeHtml((result.insurance_networks || ["Coverage varies"])[0])}</strong><small>featured network</small></span>
        </div>
        <p class="summary"></p>
        ${scoreBadges.length ? `<div class="fusion-row">${scoreBadges.map((badge) => `<span>${badge}</span>`).join("")}</div>` : ""}
        ${retrievalEvidenceBlock(result, mode, features)}
        <details class="care-details">
          <summary>Coverage and care details</summary>
          <div class="detail-grid">
            <p><strong>Conditions</strong>${escapeHtml((result.conditions || []).slice(0, 4).join(", "))}</p>
            <p><strong>Procedures</strong>${escapeHtml((result.procedures || []).slice(0, 4).join(", "))}</p>
            <p><strong>Networks</strong>${escapeHtml(networkSummary)}</p>
            <p><strong>Languages</strong>${escapeHtml(languageSummary)}</p>
          </div>
        </details>
        ${scoreDetailsBlock(result, index)}
      </div>
      <aside class="result-appointment">
        <span class="appointment-label">Next available</span>
        <strong>${escapeHtml(appointment)}</strong>
        <small>${escapeHtml(visitType)}</small>
        <button type="button" class="member-primary" data-action="details">View care details</button>
        <button type="button" class="member-secondary" data-action="map" data-provider-id="${escapeHtml(result.provider_id)}">Show on map</button>
      </aside>
    `;
    card.querySelector("h3").textContent = result.provider_name;
    card.querySelector(".subhead").textContent = `${result.provider_type} · ${result.specialty_group}`;
    card.querySelector(".summary").textContent = result.care_summary;
    const scoreDetails = card.querySelector(`#score-details-${index}`);
    if (scoreDetails) {
      scoreDetails.textContent = JSON.stringify(
        {
          score_type: result.score_type,
          score: result.score,
          fusion: result.fusion,
          reranked: result.reranked,
          rerank_score: result.rerank_score,
          original_rank: result.original_rank,
        },
        null,
        2,
      );
    }
    const careDetails = card.querySelector(".care-details");
    const detailsButton = card.querySelector('[data-action="details"]');
    detailsButton?.addEventListener("click", () => {
      careDetails.open = !careDetails.open;
      detailsButton.textContent = careDetails.open ? "Hide care details" : "View care details";
      detailsButton.setAttribute("aria-expanded", String(careDetails.open));
    });
    card.querySelector('[data-action="map"]')?.addEventListener("click", () => {
      focusProviderOnMap(result.provider_id);
    });
    resultsEl.appendChild(card);
  }
}

async function runSearch({ page = 1, pageToken = null, preservePagination = false } = {}) {
  if (!isFilePreview && setupState && !setupState.configured) return;
  if (!preservePagination) paginationState = { page: 1, tokens: [null] };
  const payload = formPayload({ page, pageToken });
  if (!payload.query) return;

  hideSuggestions();
  queryDisplayEl.textContent = payload.query;
  executionDisplayEl.textContent = "Searching";
  resultsEl.innerHTML = "";

  if (isFilePreview) {
    const previewResults = staticPreviewMatches(payload);
    const body = {
      ...payload,
      execution: "Static preview",
      pipeline: staticCodeExamples.pipeline,
      results: previewResults,
      metrics: {
        elapsed_ms: null,
        returned: previewResults.length,
        requested: payload.limit,
      },
      facets: { count: previewResults.length, specialties: staticPreviewFacets(previewResults) },
      features: { static_preview: true, pagination: null },
      pagination: { enabled: false },
    };
    lastPayload = body;
    executionDisplayEl.textContent = body.execution;
    resultContextEl.textContent = "Offline interface preview. Run `make run` and use the HTTP URL for live Atlas retrieval.";
    queryMetricsEl.textContent = `Offline preview · ${body.metrics.returned} representative ${body.metrics.returned === 1 ? "match" : "matches"}`;
    renderFacetSummary(body.facets);
    renderResults(body.results, body.facets.count, body.mode, body.features);
    renderStageTimings(body);
    renderPagination(body);
    renderMap(body.results, body.filters);
    updateSearchInsights(body);
    return;
  }

  try {
    const response = await fetch("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Search failed");
    lastPayload = body;
    executionDisplayEl.textContent = body.execution;
    resultContextEl.textContent = formatExecutionLabel(body);
    const elapsed = body.metrics?.elapsed_ms;
    queryMetricsEl.textContent = `${elapsed == null ? "--" : elapsed >= 1000 ? `${(elapsed / 1000).toFixed(2)} s` : `${elapsed} ms`} · ${body.metrics?.returned ?? 0} results`;
    renderFacetSummary(body.facets);
    renderResults(body.results || [], body.facets?.count, body.mode, body.features);
    renderStageTimings(body);
    renderPagination(body);
    renderMap(body.results || [], body.filters || payload.filters);
    updateSearchInsights(body);
  } catch (error) {
    executionDisplayEl.textContent = "Error";
    resultContextEl.textContent = "Search failed";
    resultsEl.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
    resultCountEl.textContent = "0 matches";
    queryMetricsEl.textContent = "Query failed";
    stageTimingsEl.hidden = true;
    paginationControlsEl.hidden = true;
  }
}

async function loadFilters() {
  const filters = isFilePreview ? staticFilters : await fetch("/filters").then((response) => response.json());
  const originSelect = document.querySelector("#origin-filter");
  originSelect.innerHTML = "";
  originLookup = {};
  for (const origin of filters.origins || []) {
    originLookup[origin.value] = origin;
    const option = document.createElement("option");
    option.value = origin.value;
    option.textContent = origin.label;
    originSelect.appendChild(option);
  }
  for (const id of ["specialty-filter", "network-filter", "language-filter"]) {
    const select = document.querySelector(`#${id}`);
    while (select.options.length > 1) select.remove(1);
  }
  optionList(document.querySelector("#specialty-filter"), filters.specialties);
  optionList(document.querySelector("#network-filter"), filters.networks);
  optionList(document.querySelector("#language-filter"), filters.languages);
}

function pinPosition(point) {
  const [lon, lat] = point.coordinates;
  return [lat, lon];
}

function getMarkerColor(specialty) {
  const tone = specialtyTone(specialty);
  const colorMap = {
    heart: "#d34f4f",
    skin: "#8b5cf6",
    urgent: "#f97316",
    image: "#3b82f6",
    ortho: "#0f8f73",
    default: "#10b981"
  };
  return colorMap[tone] || colorMap.default;
}

function createMapMarker(lat, lon, index, result) {
  const color = getMarkerColor(result.specialty_name);
  const html = `
    <div class="custom-marker" style="
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: ${color};
      border: 3px solid white;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
      cursor: pointer;
    ">${index + 1}</div>
  `;

  const icon = L.divIcon({
    html: html,
    iconSize: [32, 32],
    className: "custom-marker-icon"
  });

  const marker = L.marker([lat, lon], { icon: icon });
  const distance = result.distance_from_origin_miles ?? result.distance_miles;
  const distanceText = distance ? ` · ${distance} miles` : "";

  marker.bindPopup(`
    <div style="font-size: 13px; min-width: 180px;">
      <strong>${result.provider_name}</strong><br/>
      <small>${result.specialty_name}${distanceText}</small><br/>
      <small>Rating: ${result.rating}/5 (${result.review_count})</small>
    </div>
  `, { closeButton: false });

  return marker;
}

function initializeMap() {
  if (typeof L === "undefined") {
    return false;
  }

  if (!leafletMap) {
    leafletMap = L.map("leaflet-map", {
      center: [30.2672, -97.7431],
      zoom: 12,
      zoomControl: true,
      scrollWheelZoom: true,
      dragging: true
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(leafletMap);

    markerClusterGroup = L.markerClusterGroup({
      maxClusterRadius: 50,
      disableClusteringAtZoom: 16
    });
    leafletMap.addLayer(markerClusterGroup);
  }

  return true;
}

function renderMap(results, filters) {
  if (!initializeMap()) {
    renderFallbackMap(results, filters);
    return;
  }

  leafletMap.invalidateSize({ pan: false });

  // Clear existing markers and layers
  markerClusterGroup.clearLayers();
  providerMarkers = new Map();
  if (radiusCircle) {
    leafletMap.removeLayer(radiusCircle);
    radiusCircle = null;
  }
  if (originMarker) {
    leafletMap.removeLayer(originMarker);
    originMarker = null;
  }

  // Update geo context
  const originOption = document.querySelector(`#origin-filter option[value="${filters.origin || "downtown"}"]`);
  const originLabel = originOption?.textContent || "Downtown Austin";
  geoContextEl.textContent = `${originLabel}${filters.max_distance ? ` · within ${filters.max_distance} miles` : ""}`;
  const origin = originLookup[filters.origin || "downtown"] || originLookup.downtown;

  // Add origin marker
  if (origin?.coordinates) {
    const [lon, lat] = origin.coordinates;
    const originIcon = L.divIcon({
      html: `<div style="
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: #06b6d4;
        border: 4px solid white;
        box-shadow: 0 0 0 8px rgba(6, 182, 212, 0.2), 0 2px 8px rgba(0, 0, 0, 0.25);
      "></div>`,
      iconSize: [24, 24],
      className: "origin-marker-icon"
    });

    originMarker = L.marker([lat, lon], { icon: originIcon, zIndexOffset: 1000 });
    originMarker.addTo(leafletMap);

    // Add radius circle
    if (filters.max_distance) {
      const radiusInMeters = filters.max_distance * 1609.34;
      radiusCircle = L.circle([lat, lon], {
        radius: radiusInMeters,
        fillColor: "rgba(16, 185, 129, 0.1)",
        color: "rgba(16, 185, 129, 0.3)",
        weight: 2,
        opacity: 0.6,
        fillOpacity: 0.1
      });
      radiusCircle.addTo(leafletMap);
    }
  }

  // Add result markers with clustering
  for (const [index, result] of results.entries()) {
    if (!result.location) continue;
    const [lon, lat] = result.location.coordinates;
    const marker = createMapMarker(lat, lon, index, result);
    markerClusterGroup.addLayer(marker);
    providerMarkers.set(result.provider_id, marker);
  }

  // Fit map bounds
  const fitMap = () => {
    leafletMap.invalidateSize({ pan: false });
    if (markerClusterGroup.getLayers().length > 0) {
      leafletMap.fitBounds(markerClusterGroup.getBounds().pad(0.1), { maxZoom: 14 });
    } else if (origin?.coordinates) {
      const [lon, lat] = origin.coordinates;
      leafletMap.setView([lat, lon], 12);
    }
  };
  fitMap();
  window.setTimeout(fitMap, 120);

  // Update map list
  mapListEl.innerHTML = "";
  for (const [index, result] of results.entries()) {
    if (index >= 5) break;
    if (!result.location) continue;

    const distance = result.distance_from_origin_miles ?? result.distance_miles;
    const item = document.createElement("button");
    item.type = "button";
    item.className = "map-list-item";
    item.innerHTML = `
      <span class="map-list-rank">${index + 1}</span>
      <span class="map-list-main">
        <strong>${result.provider_name}</strong>
        <small>${result.specialty_name} · ${distance ? distance + ' miles' : 'Distance N/A'}</small>
      </span>
    `;
    item.addEventListener("click", () => focusProviderOnMap(result.provider_id));
    mapListEl.appendChild(item);
  }

  if (!mapListEl.children.length) {
    mapListEl.innerHTML = '<p class="map-empty">No mapped providers in this result set.</p>';
  }
}

function focusProviderOnMap(providerId) {
  document.querySelector(".geo-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  const marker = providerMarkers.get(providerId);
  if (!marker || !leafletMap || !markerClusterGroup) return;
  window.setTimeout(() => {
    markerClusterGroup.zoomToShowLayer(marker, () => {
      leafletMap.setView(marker.getLatLng(), Math.max(leafletMap.getZoom(), 14));
      marker.openPopup();
    });
  }, 250);
}

function fallbackMapPosition(result) {
  const [lon, lat] = result.location.coordinates;
  const minLon = -97.86;
  const maxLon = -97.62;
  const minLat = 30.18;
  const maxLat = 30.37;
  const x = Math.max(4, Math.min(96, ((lon - minLon) / (maxLon - minLon)) * 100));
  const y = Math.max(8, Math.min(92, (1 - (lat - minLat) / (maxLat - minLat)) * 100));
  return { x, y };
}

function renderFallbackMap(results, filters) {
  const originOption = document.querySelector(`#origin-filter option[value="${filters.origin || "downtown"}"]`);
  const originLabel = originOption?.textContent || "Downtown Austin";
  geoContextEl.textContent = `${originLabel}${filters.max_distance ? ` · within ${filters.max_distance} miles` : ""}`;

  const mapEl = document.querySelector("#leaflet-map");
  if (mapEl) {
    const pins = results
      .filter((result) => result.location)
      .map((result, index) => {
        const { x, y } = fallbackMapPosition(result);
        return `<span class="fallback-pin ${specialtyTone(result.specialty_name)}" style="left:${x}%;top:${y}%">${index + 1}</span>`;
      })
      .join("");
    mapEl.className = "leaflet-map-container fallback-map";
    mapEl.innerHTML = `
      <img src="./austin-care-map.svg" alt="" />
      <div class="fallback-map-shade"></div>
      ${pins}
    `;
  }

  mapListEl.innerHTML = "";
  for (const [index, result] of results.entries()) {
    if (index >= 5) break;
    const distance = result.distance_from_origin_miles ?? result.distance_miles;
    const item = document.createElement("button");
    item.type = "button";
    item.className = "map-list-item";
    item.innerHTML = `
      <span class="map-list-rank">${index + 1}</span>
      <span class="map-list-main">
        <strong>${result.provider_name}</strong>
        <small>${result.specialty_name} · ${distance ? distance + " miles" : "Distance N/A"}</small>
      </span>
    `;
    mapListEl.appendChild(item);
  }

  if (!mapListEl.children.length) {
    mapListEl.innerHTML = '<p class="map-empty">No mapped providers in this result set.</p>';
  }
}

async function loadHealth() {
  if (isFilePreview) {
    corpusDisplayEl.textContent = "Static preview";
    return;
  }

  try {
    const response = await fetch("/health");
    const health = await response.json();
    if (health.configured === false) {
      corpusDisplayEl.textContent = "Setup required";
    } else if (health.ok === false) {
      corpusDisplayEl.textContent = "Atlas unavailable";
    } else {
      corpusDisplayEl.textContent = `${health.documents} providers`;
    }
  } catch {
    corpusDisplayEl.textContent = "Not connected";
  }
}

function hideSuggestions() {
  window.clearTimeout(queryInput.suggestTimer);
  suggestionAbortController?.abort();
  suggestionAbortController = null;
  suggestionMenuEl.hidden = true;
  suggestionMenuEl.innerHTML = "";
  queryInput.setAttribute("aria-expanded", "false");
  queryInput.removeAttribute("aria-activedescendant");
  suggestionItems = [];
  activeSuggestionIndex = -1;
}

function setActiveSuggestion(index) {
  if (!suggestionItems.length) return;
  activeSuggestionIndex = (index + suggestionItems.length) % suggestionItems.length;
  suggestionMenuEl.querySelectorAll('[role="option"]').forEach((option, optionIndex) => {
    const active = optionIndex === activeSuggestionIndex;
    option.classList.toggle("active", active);
    option.setAttribute("aria-selected", String(active));
    if (active) {
      queryInput.setAttribute("aria-activedescendant", option.id);
      option.scrollIntoView({ block: "nearest" });
    }
  });
}

function selectSuggestion(index) {
  const suggestion = suggestionItems[index];
  if (!suggestion) return;
  queryInput.value = suggestion.provider_name;
  hideSuggestions();
  runSearch();
}

function renderSuggestions(suggestions) {
  suggestionItems = suggestions || [];
  activeSuggestionIndex = -1;
  if (!suggestionItems.length) {
    hideSuggestions();
    return;
  }

  suggestionMenuEl.innerHTML = suggestionItems.map((suggestion, index) => `
    <button id="suggestion-option-${index}" type="button" role="option" aria-selected="false" data-suggestion-index="${index}">
      <span class="suggestion-icon" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
      <span class="suggestion-copy">
        <strong>${escapeHtml(suggestion.provider_name)}</strong>
        <small>${escapeHtml(suggestion.specialty_name)} · ${escapeHtml(suggestion.city)}, ${escapeHtml(suggestion.state)}</small>
      </span>
      <span class="suggestion-source">Atlas autocomplete</span>
    </button>
  `).join("");
  suggestionMenuEl.hidden = false;
  queryInput.setAttribute("aria-expanded", "true");
}

async function loadSuggestions() {
  if (!isFilePreview && setupState && !setupState.configured) return;
  const q = queryInput.value.trim();
  if (q.length < 2) {
    hideSuggestions();
    return;
  }

  if (isFilePreview) {
    const needle = q.toLowerCase();
    renderSuggestions(staticResults.filter((result) => (
      `${result.provider_name} ${result.specialty_name}`.toLowerCase().includes(needle)
    )).slice(0, 6));
    return;
  }

  suggestionAbortController?.abort();
  suggestionAbortController = new AbortController();
  try {
    const response = await fetch(`/suggest?q=${encodeURIComponent(q)}`, {
      signal: suggestionAbortController.signal,
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Suggestions unavailable");
    renderSuggestions(body.suggestions || []);
  } catch (error) {
    if (error.name !== "AbortError") hideSuggestions();
  }
}

function renderComparisonPane(element, modeData) {
  element.innerHTML = "";
  for (const [index, result] of (modeData?.results || []).entries()) {
    const item = document.createElement("article");
    item.className = "compare-result";
    const lexicalRank = result.ranks?.lexical;
    const vectorRank = result.ranks?.vector;
    const hybridRank = result.ranks?.hybrid;
    const rankSignals = [
      lexicalRank ? `<span class="lexical-rank">FT ${lexicalRank}</span>` : "",
      vectorRank ? `<span class="vector-rank">VS ${vectorRank}</span>` : "",
      hybridRank ? `<span class="hybrid-rank">HF ${hybridRank}</span>` : "",
    ].filter(Boolean).join("");
    item.innerHTML = `
      <span class="compare-rank">${result.rank || index + 1}</span>
      <div class="compare-result-copy">
        <strong>${escapeHtml(result.provider_name)}</strong>
        <small>${escapeHtml(result.specialty_name)}</small>
        <div class="compare-rank-signals">${rankSignals}</div>
      </div>
    `;
    element.appendChild(item);
  }
}

function renderComparison(data) {
  const panes = {
    lexical: document.querySelector("#compare-lexical"),
    vector: document.querySelector("#compare-vector"),
    hybrid: document.querySelector("#compare-hybrid"),
  };
  for (const mode of ["lexical", "vector", "hybrid"]) {
    renderComparisonPane(panes[mode], data.comparison?.find((item) => item.mode === mode));
  }
  const summaryEl = document.querySelector("#compare-summary");
  const summary = data.summary || {};
  summaryEl.hidden = false;
  summaryEl.innerHTML = `
    <span><strong>${summary.unique_results ?? "--"}</strong> unique candidates</span>
    <span><strong>${summary.shared_all_modes ?? "--"}</strong> shared across all modes</span>
    <span><strong>${summary.lexical_vector_overlap ?? "--"}</strong> lexical/vector overlap</span>
  `;
}

function staticComparison() {
  const orders = {
    lexical: [staticResults[0], staticResults[1], staticResults[3], staticResults[2]],
    vector: [staticResults[0], staticResults[2], staticResults[1], staticResults[3]],
    hybrid: [staticResults[0], staticResults[1], staticResults[2], staticResults[3]],
  };
  const ranks = Object.fromEntries(Object.entries(orders).map(([mode, results]) => [
    mode,
    Object.fromEntries(results.map((result, index) => [result.provider_id, index + 1])),
  ]));
  return {
    summary: { unique_results: 4, shared_all_modes: 4, lexical_vector_overlap: 4 },
    comparison: Object.entries(orders).map(([mode, results]) => ({
      mode,
      results: results.map((result, index) => ({
        ...result,
        rank: index + 1,
        ranks: Object.fromEntries(Object.entries(ranks).map(([name, values]) => [name, values[result.provider_id]])),
      })),
    })),
  };
}

function architectureFlow(mode) {
  const payload = formPayload();
  const resultLimit = payload.limit;
  const fusionWindow = Math.max(50, resultLimit * 5);
  const vectorCandidates = Math.min(10000, Math.max(100, resultLimit * 20));
  const hybridVectorCandidates = Math.min(10000, Math.max(100, fusionWindow * 20));
  const weights = {
    balanced: [55, 45],
    precision: [75, 25],
    discovery: [35, 65],
  }[payload.hybrid_profile] || [55, 45];

  const flows = {
    overview: {
      eyebrow: "Unified retrieval architecture",
      title: "One provider document powers the complete care journey",
      description: "Atlas keeps clinical content, operational filters, coordinates, and Voyage embeddings together so every search mode returns the same current provider record.",
      steps: [
        ["01", "Member intent", "Condition, symptom, procedure, specialty, or provider name", "query"],
        ["02", "Atlas document", "Clinical text, coverage, availability, location, and embedding", "data"],
        ["03", "Parallel retrieval", "$search for lexical precision and $vectorSearch for semantic recall", "split"],
        ["04", "Native fusion", "$rankFusion combines source ranks without score normalization", "fusion"],
        ["05", "Care experience", "Ranked providers, facets, evidence, coverage, availability, and map", "experience"],
      ],
    },
    lexical: {
      eyebrow: "Atlas Search flow",
      title: "Precise retrieval for known clinical language",
      description: "Best for provider names, specialties, procedures, common aliases, and typo-tolerant member searches.",
      steps: [
        ["01", "Member query", "Natural language or known medical terminology", "query"],
        ["02", "$search compound", "Phrase, text, fuzzy, and medical synonym operators", "lexical"],
        ["03", "Clinical boosts", "Provider and specialty 5x, phrase 8x, synonym expansion 2.5x", "tuning"],
        ["04", "Non-scoring filters", "Network, language, rating, availability, and geoWithin", "filter"],
        ["05", "Search response", "Atlas relevance score, highlights, and $searchMeta facets", "experience"],
      ],
    },
    vector: {
      eyebrow: "Atlas Vector Search flow",
      title: "Semantic retrieval for intent and symptom language",
      description: "Best when the member describes a need without using the same words stored in the provider profile.",
      steps: [
        ["01", "Member query", "Conversational symptom or care intent", "query"],
        ["02", "Voyage 4", "Generate one 1024-dimension query embedding", "voyage"],
        ["03", "$vectorSearch", `Cosine ANN over ${vectorCandidates} candidates for ${resultLimit} results`, "vector"],
        ["04", "Vector prefilters", "Provider type, network, language, rating, and availability", "filter"],
        ["05", "Semantic response", "Related providers ranked by vector similarity", "experience"],
      ],
    },
    hybrid: {
      eyebrow: "Native hybrid flow",
      title: "Lexical precision and semantic recall in one aggregation",
      description: `The current ${payload.hybrid_profile} profile weights Full Text ${weights[0]}% and Vector ${weights[1]}%.`,
      steps: [
        ["01", "Member query", "One query is sent down both retrieval paths", "query"],
        ["02", "Bounded pipelines", `$search and $vectorSearch each contribute up to ${fusionWindow} ranked candidates`, "split"],
        ["03", "Vector recall", `${hybridVectorCandidates} ANN candidates support the bounded semantic lane`, "vector"],
        ["04", "$rankFusion", `Weighted RRF: ${weights[0]} / ${weights[1]} with rank constant 60`, "fusion"],
        ["05", "Explainable results", "Native scoreDetails expose source rank, weight, and contribution", "experience"],
      ],
    },
    rerank: {
      eyebrow: "Voyage reranking flow",
      title: "A final relevance pass over Atlas candidates",
      description: "Atlas remains the retrieval system; Voyage only reorders the strongest candidates for the final member-facing list.",
      steps: [
        ["01", "Atlas retrieval", "Run Full Text, Vector, or Hybrid with all selected filters", "query"],
        ["02", "Candidate set", `Retain the top ${Math.max(resultLimit, 20)} Atlas results`, "data"],
        ["03", "Voyage rerank", "Score the query against provider summaries and clinical evidence", "voyage"],
        ["04", "Final ordering", `Return the best ${resultLimit} results and preserve original Atlas rank`, "fusion"],
        ["05", "Transparent UI", "Show Voyage relevance and the original retrieval evidence", "experience"],
      ],
    },
  };
  return flows[mode] || flows.overview;
}

function renderArchitecture(mode = "overview") {
  const flow = architectureFlow(mode);
  document.querySelectorAll("[data-architecture-mode]").forEach((button) => {
    const active = button.dataset.architectureMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  architectureCanvas.innerHTML = `
    <div class="architecture-intro">
      <span>${escapeHtml(flow.eyebrow)}</span>
      <h3>${escapeHtml(flow.title)}</h3>
      <p>${escapeHtml(flow.description)}</p>
    </div>
    <div class="architecture-flow">
      ${flow.steps.map(([number, title, detail, tone], index) => `
        <article class="architecture-node ${tone}">
          <span class="architecture-number">${number}</span>
          <div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></div>
        </article>
        ${index < flow.steps.length - 1 ? '<div class="architecture-connector" aria-hidden="true"></div>' : ""}
      `).join("")}
    </div>
    <div class="architecture-foundation">
      <span>MongoDB Atlas</span>
      <strong>Operational provider data and search indexes stay together</strong>
      <small>One security model · one data lifecycle · one aggregation API</small>
    </div>
  `;
}

function renderScoreExplainer() {
  const result = lastPayload?.results?.[0];
  const lexical = result?.fusion?.lexical;
  const vector = result?.fusion?.vector;
  const terms = [];
  if (lexical) terms.push(`${lexical.weight.toFixed(2)} / (60 + ${lexical.rank}) = ${lexical.contribution.toFixed(5)}`);
  if (vector) terms.push(`${vector.weight.toFixed(2)} / (60 + ${vector.rank}) = ${vector.contribution.toFixed(5)}`);
  const calculation = terms.length
    ? `${terms.join("  +  ")}  =  ${Number(result.score).toFixed(5)}`
    : "Run a Hybrid search to see a live rank-fusion calculation.";

  scoreExplainer.innerHTML = `
    <div class="score-guide-intro">
      <span>How to read relevance</span>
      <h3>Each score answers a different ranking question</h3>
      <p>Scores are meaningful within the same query and retrieval method. A Search score should not be compared numerically with a Vector, RRF, or rerank score.</p>
    </div>
    <div class="score-concept-grid">
      <article class="score-concept lexical">
        <span>Atlas Search</span><strong>Lexical relevance</strong>
        <p>Reflects term rarity, frequency, phrase proximity, fuzzy matches, and field boosts. It has no fixed range and is only comparable within this query.</p>
      </article>
      <article class="score-concept vector">
        <span>Vector Search</span><strong>Semantic similarity</strong>
        <p>For cosine similarity Atlas reports (1 + cosine) / 2 on a 0–1 scale. Filters affect eligibility, not this similarity score.</p>
      </article>
      <article class="score-concept hybrid">
        <span>$rankFusion</span><strong>Reciprocal rank fusion</strong>
        <p>Combines rank positions instead of incomparable raw score scales. Each lane contributes weight / (60 + rank), then Atlas sums the terms.</p>
      </article>
      <article class="score-concept rerank">
        <span>Voyage rerank</span><strong>Final relevance</strong>
        <p>Reorders the retrieved candidate set using query-to-document relevance. It is a ranking signal, not a probability.</p>
      </article>
    </div>
    <div class="score-example">
      <div><span>Current top result</span><strong>${escapeHtml(result?.provider_name || "Hybrid result")}</strong></div>
      <code>${escapeHtml(calculation)}</code>
    </div>
  `;
}

function renderDialogSummary(kind, content) {
  const mode = lastPayload?.mode || formPayload().mode;
  const resultWindow = lastPayload?.metrics?.requested || formPayload().limit;
  let eyebrow = "Atlas implementation";
  let label = "MongoDB aggregation pipeline";
  let facts = [];

  if (kind === "pipeline") {
    eyebrow = "Live query architecture";
    facts = [
      ["Mode", mode === "lexical" ? "Full Text" : mode === "vector" ? "Vector" : "Hybrid"],
      ["Execution", lastPayload?.execution || "$rankFusion"],
      ["Result window", `${resultWindow} providers`],
      ["Embedding", mode === "lexical" ? "Not required" : "Voyage 4 · 1024d"],
    ];
  } else if (kind === "search-index") {
    const fields = Object.keys(content?.mappings?.fields || {});
    eyebrow = "Atlas Search definition";
    label = "search_index.json";
    facts = [
      ["Mapping", "Explicit"],
      ["Indexed fields", String(fields.length)],
      ["Retrieval", "BM25 + fuzzy + phrase"],
      ["Capabilities", "Autocomplete · synonyms · facets · geo"],
    ];
  } else if (kind === "vector-index") {
    const fields = content?.fields || [];
    const vector = fields.find((field) => field.type === "vector") || {};
    eyebrow = "Atlas Vector Search definition";
    label = "vector_index.json";
    facts = [
      ["Dimensions", String(vector.numDimensions || 1024)],
      ["Similarity", vector.similarity || "cosine"],
      ["Quantization", vector.quantization || "scalar"],
      ["Prefilters", String(fields.filter((field) => field.type === "filter").length)],
    ];
  } else if (kind === "compare") {
    eyebrow = "Live retrieval comparison";
    facts = [
      ["Same query", "3 retrieval paths"],
      ["Window", `${content?.limit || resultWindow} per mode`],
      ["Fusion", "Native $rankFusion"],
      ["Evidence", "Rank movement + overlap"],
    ];
  } else if (kind === "geo") {
    eyebrow = "Location-aware retrieval";
    label = "Atlas Search geo filter";
    facts = [
      ["Shape", "GeoJSON point"],
      ["Operator", "geoWithin"],
      ["Placement", "$search compound.filter"],
      ["Map source", "Live provider documents"],
    ];
  } else if (kind === "sample") {
    eyebrow = "Unified care document";
    label = "Provider document sample";
    facts = [
      ["Documents", String(content?.documents?.length || 0)],
      ["Workload", "Search + vector + geo"],
      ["Filters", "Embedded operational fields"],
      ["Storage", "One Atlas collection"],
    ];
  } else if (kind === "architecture") {
    eyebrow = "Search system blueprint";
    facts = [
      ["Data model", "One provider document"],
      ["Retrieval", "3 native search modes"],
      ["Fusion", "$rankFusion"],
      ["Final stage", "Optional Voyage rerank"],
    ];
  } else if (kind === "scoring") {
    const profile = formPayload().hybrid_profile;
    eyebrow = "Relevance score guide";
    facts = [
      ["Search", "Term relevance"],
      ["Vector", "Cosine score · 0–1"],
      ["Hybrid", "Rank-based fusion"],
      ["Active blend", profile.replace(/^./, (value) => value.toUpperCase())],
    ];
  } else if (kind === "facets") {
    eyebrow = "Atlas Search navigation";
    label = "$searchMeta facet example";
    facts = [
      ["Stage", "$searchMeta"],
      ["Source", "Search index"],
      ["Counts", "Current query + filters"],
      ["Selection", "Non-scoring constraint"],
    ];
  }

  dialogEyebrow.textContent = eyebrow;
  codeLabel.textContent = label;
  codeSummary.innerHTML = facts
    .map(([factLabel, value]) => `<div><span>${escapeHtml(factLabel)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

async function openCode(kind) {
  let title = "Code";
  let content = lastPayload?.pipeline || [];
  const comparePanesEl = document.querySelector("#compare-panes");
  const compareSummaryEl = document.querySelector("#compare-summary");

  codeDialog.dataset.view = kind;
  codePanel.hidden = false;
  comparePanesEl.hidden = true;
  compareSummaryEl.hidden = true;
  architectureView.hidden = true;
  scoreExplainer.hidden = true;

  if (kind === "architecture" || kind === "scoring") {
    title = kind === "architecture" ? "Search Architecture" : "Understanding Search Scores";
    codePanel.hidden = true;
    if (kind === "architecture") {
      architectureView.hidden = false;
      renderArchitecture("overview");
    } else {
      scoreExplainer.hidden = false;
      renderScoreExplainer();
    }
    dialogTitle.textContent = title;
    renderDialogSummary(kind, lastPayload);
    codeDialog.showModal();
    return;
  }

  if (kind === "facets") {
    title = "Understanding Atlas Facets";
    content = {
      concept: "Atlas Search computes category buckets and counts from the same indexed query context used for retrieval.",
      interaction: "Selecting a specialty reruns the query with an equals filter in compound.filter, so the constraint changes eligibility without adding relevance score.",
      pipeline: {
        $searchMeta: {
          index: "search_index",
          facet: {
            operator: "same compound query and active filters",
            facets: {
              specialties: { type: "string", path: "specialty_filter", numBuckets: 100 },
            },
          },
          count: { type: "total" },
        },
      },
      current: lastPayload?.facets || "Run a search to populate live facet counts.",
    };
    dialogTitle.textContent = title;
    renderDialogSummary(kind, content);
    codeOutput.textContent = JSON.stringify(content, null, 2);
    codeDialog.showModal();
    return;
  }

  if (isFilePreview) {
    if (kind === "search-index") {
      title = "Full-Text Search Index";
      content = staticCodeExamples.searchIndex;
    } else if (kind === "vector-index") {
      title = "Vector Search Index";
      content = staticCodeExamples.vectorIndex;
    } else if (kind === "sample") {
      title = "Sample Provider Documents";
      content = staticCodeExamples.sample;
    } else if (kind === "compare") {
      title = "Search Strategy Comparison";
      content = staticComparison();
      codePanel.hidden = true;
      comparePanesEl.hidden = false;
      renderComparison(content);
    } else if (kind === "geo") {
      title = "Geo Search Pattern";
      content = staticCodeExamples.geo;
    } else {
      title = "Current Search Pipeline";
      content = lastPayload?.pipeline || staticCodeExamples.pipeline;
    }

    dialogTitle.textContent = title;
    renderDialogSummary(kind, content);
    if (kind !== "compare") {
      codeOutput.textContent = JSON.stringify(content, null, 2);
    }
    codeDialog.showModal();
    return;
  }

  if (kind === "search-index" || kind === "vector-index") {
    const response = await fetch("/indexes");
    const indexes = await response.json();
    if (kind === "search-index") {
      title = "Full-Text Search Index";
      content = indexes.fullText;
    } else {
      title = "Vector Search Index";
      content = indexes.vector;
    }
  } else if (kind === "sample") {
    title = "Sample Provider Documents";
    const response = await fetch("/sample-documents?limit=3");
    content = await response.json();
  } else if (kind === "compare") {
    title = "Search Strategy Comparison";
    const response = await fetch("/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload()),
    });
    const compareData = await response.json();
    content = compareData;
    codePanel.hidden = true;
    comparePanesEl.hidden = false;
    renderComparison(compareData);
  } else if (kind === "geo") {
    title = "Geo Search Pattern";
    const payload = formPayload();
    const response = await fetch("/map-providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    content = {
      search_filter_example: {
        compound: {
          filter: [
            {
              geoWithin: {
                path: "location",
                circle: {
                  center: "<selected origin GeoJSON Point>",
                  radius: "<selected miles converted to meters>",
                },
              },
            },
          ],
        },
      },
      regular_geo_index: { location: "2dsphere" },
      current_map_results: await response.json(),
    };
  } else if (!lastPayload) {
    title = "Hybrid Query Example";
    const response = await fetch("/query-example");
    content = (await response.json()).pipeline;
  } else {
    title = "Current Search Pipeline";
  }

  dialogTitle.textContent = title;
  renderDialogSummary(kind, content);
  if (kind !== "compare") {
    codeOutput.textContent = JSON.stringify(content, null, 2);
  }
  codeDialog.showModal();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runSearch();
});

queryInput.addEventListener("input", () => {
  window.clearTimeout(queryInput.suggestTimer);
  queryInput.suggestTimer = window.setTimeout(loadSuggestions, 180);
});

queryInput.addEventListener("keydown", (event) => {
  if (suggestionMenuEl.hidden || !suggestionItems.length) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    setActiveSuggestion(activeSuggestionIndex + 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    setActiveSuggestion(activeSuggestionIndex - 1);
  } else if (event.key === "Enter" && activeSuggestionIndex >= 0) {
    event.preventDefault();
    selectSuggestion(activeSuggestionIndex);
  } else if (event.key === "Escape") {
    hideSuggestions();
  }
});

suggestionMenuEl.addEventListener("click", (event) => {
  const option = event.target.closest("[data-suggestion-index]");
  if (option) selectSuggestion(Number(option.dataset.suggestionIndex));
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".query-combobox")) hideSuggestions();
});

facetSummaryEl?.addEventListener("click", (event) => {
  const help = event.target.closest('[data-code="facets"]');
  if (help) {
    openCode("facets");
    return;
  }
  const action = event.target.closest("[data-facet]");
  if (!action) return;
  const select = form.elements[action.dataset.facet];
  if (!select) return;
  select.value = action.getAttribute("aria-pressed") === "true" ? "" : action.dataset.value;
  runSearch();
});

previousPageButton?.addEventListener("click", () => {
  const targetPage = Math.max(1, paginationState.page - 1);
  runSearch({
    page: targetPage,
    pageToken: paginationState.tokens[targetPage - 1] || null,
    preservePagination: true,
  });
  document.querySelector(".results-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
});

nextPageButton?.addEventListener("click", () => {
  const targetPage = paginationState.page + 1;
  const pageToken = paginationState.tokens[paginationState.page];
  if (!pageToken) return;
  runSearch({ page: targetPage, pageToken, preservePagination: true });
  document.querySelector(".results-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
});

document.querySelectorAll("[data-code]").forEach((button) => {
  button.addEventListener("click", () => openCode(button.dataset.code));
});

document.querySelectorAll("[data-architecture-mode]").forEach((button) => {
  button.addEventListener("click", () => renderArchitecture(button.dataset.architectureMode));
});

document.querySelectorAll("[data-query]").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.query;
    for (const fieldName of ["specialty", "network", "language", "max_distance", "min_rating"]) {
      form.elements[fieldName].value = "";
    }
    form.elements.origin.value = "downtown";
    form.elements.sort.value = "relevance";
    form.elements.telehealth.checked = button.dataset.telehealth === "true";
    form.elements.accepting_new_patients.checked = button.dataset.accepting === "true";
    form.elements.rerank.checked = button.dataset.rerank === "true";
    form.elements.limit.value = button.dataset.limit || "12";
    if (button.dataset.mode) {
      const modeControl = form.querySelector(`input[name="mode"][value="${button.dataset.mode}"]`);
      if (modeControl) modeControl.checked = true;
    }
    document.querySelector("#hybrid-profile").value = button.dataset.profile || "balanced";
    const scenarioFilters = document.querySelector("#advanced-filters");
    const filterControl = document.querySelector(".filter-toggle");
    if (scenarioFilters) scenarioFilters.hidden = true;
    filterControl?.setAttribute("aria-expanded", "false");
    syncHybridProfile();
    runSearch();
  });
});

function syncHybridProfile() {
  const selectedMode = form.querySelector('input[name="mode"]:checked')?.value || "hybrid";
  const profile = document.querySelector("#hybrid-profile");
  if (!profile) return;
  profile.disabled = selectedMode !== "hybrid";
  profile.closest("label")?.classList.toggle("is-disabled", profile.disabled);
}

form.querySelectorAll('input[name="mode"], input[name="rerank"], select[name="hybrid_profile"], select[name="limit"]').forEach((control) => {
  control.addEventListener("change", () => {
    syncHybridProfile();
    runSearch();
  });
});

closeDialog.addEventListener("click", () => codeDialog.close());

setupOpenButton.addEventListener("click", () => openSetup(false));
setupCloseButton.addEventListener("click", closeSetup);
setupDialog.addEventListener("cancel", (event) => {
  if (setupDialog.dataset.required === "true") event.preventDefault();
});
setupDialog.addEventListener("close", () => {
  if (setupDialog.dataset.required === "true" && !setupState?.configured) {
    window.setTimeout(() => {
      if (!setupDialog.open) setupDialog.showModal();
    }, 0);
  }
});

document.querySelector("#setup-show-values").addEventListener("change", (event) => {
  const type = event.target.checked ? "text" : "password";
  setupAtlasInput.type = type;
  setupVoyageInput.type = type;
});

setupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (setupSaveButton.dataset.ready === "true") {
    setupDialog.dataset.required = "false";
    closeSetup();
    return;
  }

  resetSetupProgress();
  setupSaveButton.disabled = true;
  setupSaveButton.textContent = "Verifying...";
  setupFeedback.className = "setup-feedback checking";
  setupFeedback.textContent = "Running connection and readiness checks...";
  setSetupStage("atlas", "running", "Connecting to MongoDB Atlas");

  try {
    const response = await fetch("/api/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        atlas_uri: setupAtlasInput.value || null,
        voyage_api_key: setupVoyageInput.value || null,
        database: document.querySelector("#setup-database").value,
        collection: document.querySelector("#setup-collection").value,
        install_demo_data: document.querySelector("#setup-install-data").checked,
      }),
    });
    setupState = await readSetupEvents(response);
    updateConnectionButton();
    setupDialog.dataset.required = "false";
    setupCloseButton.disabled = false;
    setSetupStage("portal", "running", "Loading filters and the first live search");
    await initializeLive(true);
    setSetupStage("portal", "complete", "UI and APIs are ready");
    setupFeedback.className = setupState.readiness?.ready
      ? "setup-feedback success"
      : "setup-feedback warning";
    setupFeedback.textContent = setupState.message;
    setupSaveButton.dataset.ready = "true";
    setupSaveButton.textContent = "Open FindCare";
    setupSaveButton.disabled = false;
  } catch (error) {
    setupFeedback.className = "setup-feedback error";
    setupFeedback.textContent = error.message;
    setupSaveButton.disabled = false;
    setupSaveButton.textContent = "Verify and save";
  }
});

// Filter toggle functionality
const filterToggle = document.querySelector(".filter-toggle");
const filtersContainer = document.querySelector(".filters-container");
if (filterToggle && filtersContainer) {
  filterToggle.addEventListener("click", (e) => {
    e.preventDefault();
    const isHidden = filtersContainer.hidden;
    filtersContainer.hidden = !isHidden;
    filterToggle.setAttribute("aria-expanded", String(!isHidden));
  });
}

async function initializeLive(force = false) {
  if (liveInitialized && !force) return;
  try {
    await loadFilters();
  } catch {
    originLookup = { downtown: { label: "Downtown Austin", coordinates: [-97.7431, 30.2672] } };
  }
  syncHybridProfile();
  await loadHealth();
  await runSearch();
  liveInitialized = true;
}

async function init() {
  syncHybridProfile();
  if (isFilePreview) {
    setupState = { configured: true, atlas_target: "Static preview" };
    setupOpenButton.hidden = true;
    await initializeLive();
    return;
  }

  try {
    const response = await fetch("/api/setup", { headers: { Accept: "application/json" } });
    setupState = await response.json();
  } catch {
    setupState = { configured: false };
  }
  updateConnectionButton();
  if (!setupState.configured) {
    corpusDisplayEl.textContent = "Setup required";
    executionDisplayEl.textContent = "Waiting";
    queryMetricsEl.textContent = "Not connected";
    resultContextEl.textContent = "Complete local connection setup to activate live search.";
    resultsEl.innerHTML = '<p class="empty-state">Connect MongoDB Atlas and Voyage AI to begin.</p>';
    openSetup(true);
    return;
  }
  await initializeLive();
}

init();
