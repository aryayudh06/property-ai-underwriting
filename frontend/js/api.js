// Wrapper sederhana untuk memanggil REST API backend FastAPI.
const API_BASE = ""; // sama origin (FastAPI serve static + API)

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      detail = errJson.detail ? JSON.stringify(errJson.detail) : detail;
    } catch (e) { /* ignore parse errors */ }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

const Api = {
  health: () => apiRequest("/api/health"),

  // ---- Cases ----
  listCases: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/api/cases${qs ? "?" + qs : ""}`);
  },
  getCase: (caseId) => apiRequest(`/api/cases/${caseId}`),
  createCase: (payload) => apiRequest("/api/cases", { method: "POST", body: JSON.stringify(payload) }),
  updateCase: (caseId, payload) => apiRequest(`/api/cases/${caseId}`, { method: "PUT", body: JSON.stringify(payload) }),
  changeCaseStatus: (caseId, status) => apiRequest(`/api/cases/${caseId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  deleteCase: (caseId) => apiRequest(`/api/cases/${caseId}`, { method: "DELETE" }),
  getCaseHistory: (caseId) => apiRequest(`/api/cases/${caseId}/history`),

  // ---- Documents ----
  uploadDocuments: (caseId, formData) => apiRequest(`/api/cases/${caseId}/documents`, { method: "POST", body: formData }),
  listDocuments: (caseId) => apiRequest(`/api/cases/${caseId}/documents`),
  getDocument: (docId) => apiRequest(`/api/documents/${docId}`),
  getDocumentText: (docId) => apiRequest(`/api/documents/${docId}/text`),
  processDocument: (docId) => apiRequest(`/api/documents/${docId}/process`, { method: "POST" }),
  deleteDocument: (docId) => apiRequest(`/api/documents/${docId}`, { method: "DELETE" }),
  previewUrl: (docId) => `/api/documents/${docId}/preview`,

  // ---- Structured Data Extraction ----
  llmServiceHealth: () => apiRequest("/api/llm-service/health"),
  runExtraction: (caseId) => apiRequest(`/api/cases/${caseId}/extract`, { method: "POST" }),
  getLatestExtraction: (caseId) => apiRequest(`/api/cases/${caseId}/extraction`),
  listExtractionVersions: (caseId) => apiRequest(`/api/cases/${caseId}/extraction/versions`),
  saveExtractionEdit: (caseId, data) => apiRequest(`/api/cases/${caseId}/extraction`, { method: "PUT", body: JSON.stringify({ data }) }),
  submitMockRules: (caseId) => apiRequest(`/api/cases/${caseId}/mock-rules`, { method: "POST" }),
  getLatestMockRules: (caseId) => apiRequest(`/api/cases/${caseId}/mock-rules`),

  // ---- Fitur Lanjutan #1: Search Riwayat Klaim ----
  searchClaimsForCase: (caseId) => apiRequest(`/api/cases/${caseId}/claims-search`),
  searchClaims: (insuredName) => apiRequest(`/api/claims/search?${new URLSearchParams({ insured_name: insuredName })}`),

  // ---- Fitur Lanjutan #2: RAG Knowledge Base ----
  listKnowledgeCategories: () => apiRequest("/api/knowledge/categories"),
  listKnowledgeDocuments: () => apiRequest("/api/knowledge"),
  getKnowledgeDocument: (docId) => apiRequest(`/api/knowledge/${docId}`),
  uploadKnowledgeDocument: (formData) => apiRequest("/api/knowledge/upload", { method: "POST", body: formData }),
  deleteKnowledgeDocument: (docId) => apiRequest(`/api/knowledge/${docId}`, { method: "DELETE" }),
  searchKnowledge: (query, topK = 5) => apiRequest("/api/knowledge/search", { method: "POST", body: JSON.stringify({ query, top_k: topK }) }),
  askKnowledge: (query, topK = 5) => apiRequest("/api/knowledge/ask", { method: "POST", body: JSON.stringify({ query, top_k: topK }) }),

  // ---- Disposisi Underwriting ----
  generateDisposition: (caseId, overrides) => apiRequest(`/api/cases/${caseId}/disposition/generate`, { method: "POST", body: JSON.stringify({ overrides }) }),
  getLatestDisposition: (caseId) => apiRequest(`/api/cases/${caseId}/disposition`),
  listDispositionVersions: (caseId) => apiRequest(`/api/cases/${caseId}/disposition/versions`),
  saveDispositionEdit: (caseId, payload) => apiRequest(`/api/cases/${caseId}/disposition`, { method: "PUT", body: JSON.stringify(payload) }),
  generateDispositionNarrative: (caseId) => apiRequest(`/api/cases/${caseId}/disposition/narrative`, { method: "POST" }),

  // ---- Fitur Lanjutan #4: Analisis Kualitatif & Risiko Bencana Wilayah ----
  getRegionalDisasterRisk: (caseId, limit = 5) => apiRequest(`/api/cases/${caseId}/regional-risk?${new URLSearchParams({ limit })}`),
  getQualitativeAnalysis: (caseId) => apiRequest(`/api/cases/${caseId}/qualitative-analysis`),
};
