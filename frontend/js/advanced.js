// Logika untuk Fitur Lanjutan:
//  1. Search Riwayat Klaim (database SQLite dummy)
//  2. RAG Knowledge Base (upload, indeks, search)
//  3. Disposisi Underwriting (generate, edit, simpan) - menggabungkan hasil
//     Subject To/Conditions Rule Engine + rujukan Knowledge Base + koordinasi cabang

const KNOWLEDGE_CATEGORY_LABELS = {
  "Pedoman Underwriting": "Pedoman Underwriting",
  "SOP": "SOP",
  "Risk Appetite": "Risk Appetite",
  "Manual Risiko": "Manual Risiko",
  "Ketentuan Produk": "Ketentuan Produk",
  "Template Disposisi": "Template Disposisi",
  "Lainnya": "Lainnya",
};

// ==================================================================
// 1. Search Riwayat Klaim
// ==================================================================

async function handleSearchClaims() {
  const container = document.getElementById("claimsResult");
  container.innerHTML = `<p class="empty">Mencari riwayat klaim...</p>`;
  try {
    const res = await Api.searchClaimsForCase(currentCaseId);
    renderClaimsResult(res);
  } catch (e) {
    container.innerHTML = `<p class="error-text">Gagal mencari riwayat klaim: ${escapeHtml(e.message)}</p>`;
  }
}

function renderClaimsResult(res) {
  const container = document.getElementById("claimsResult");
  if (res.count === 0) {
    container.innerHTML = `
      <p class="claims-summary">Query: "${escapeHtml(res.insured_name)}"</p>
      <p class="empty">Tidak ditemukan riwayat klaim pada database internal untuk Tertanggung ini.</p>
    `;
    return;
  }

  const rows = res.results.map((c) => `
    <tr>
      <td>${escapeHtml(c.loss_date || "-")}</td>
      <td>${escapeHtml(c.policy_no || "-")}</td>
      <td>${escapeHtml(c.class_of_business || "-")}</td>
      <td>${escapeHtml(c.cause_of_loss || "-")}</td>
      <td>${escapeHtml(c.claim_amount || "-")}</td>
      <td><span class="claim-status-badge claim-status-${escapeHtml(c.claim_status || "")}">${escapeHtml(c.claim_status || "-")}</span></td>
      <td>${escapeHtml(c.branch || "-")}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <p class="claims-summary">Query: "${escapeHtml(res.insured_name)}" &middot; ${res.count} riwayat klaim ditemukan di database internal (tabel <code>claim_history</code>).</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Tgl Kejadian</th><th>No. Polis</th><th>Class</th><th>Penyebab</th><th>Nilai Klaim</th><th>Status</th><th>Cabang</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// ==================================================================
// 2. RAG Knowledge Base
// ==================================================================

async function initKnowledgeCategorySelect() {
  const select = document.getElementById("kbCategory");
  if (!select || select.dataset.loaded) return;
  try {
    const { categories } = await Api.listKnowledgeCategories();
    select.innerHTML = categories.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(KNOWLEDGE_CATEGORY_LABELS[c] || c)}</option>`).join("");
    select.dataset.loaded = "1";
  } catch (e) {
    select.innerHTML = `<option value="Lainnya">Lainnya</option>`;
  }
}

async function loadKnowledgeList() {
  const tbody = document.getElementById("kbTableBody");
  tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Memuat data...</td></tr>`;
  try {
    const docs = await Api.listKnowledgeDocuments();
    if (docs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Belum ada dokumen Knowledge Base.</td></tr>`;
      return;
    }
    tbody.innerHTML = docs.map((d) => `
      <tr>
        <td>${escapeHtml(d.title)}</td>
        <td><span class="kb-category-badge">${escapeHtml(d.category)}</span></td>
        <td>${d.chunk_count}</td>
        <td>${formatDateTime(d.uploaded_at)}</td>
        <td class="action-cell">
          <button class="btn btn-danger btn-sm" onclick="handleDeleteKnowledgeDoc('${d.id}')">Hapus</button>
        </td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-row">Gagal memuat data: ${escapeHtml(e.message)}</td></tr>`;
  }
}

async function handleDeleteKnowledgeDoc(docId) {
  if (!confirm("Hapus dokumen Knowledge Base ini beserta seluruh chunk/embedding-nya?")) return;
  try {
    await Api.deleteKnowledgeDocument(docId);
    showToast("Dokumen Knowledge Base dihapus", "success");
    loadKnowledgeList();
  } catch (e) {
    showToast("Gagal menghapus dokumen: " + e.message, "error");
  }
}

async function handleKbUploadSubmit(evt) {
  evt.preventDefault();
  const errorEl = document.getElementById("kbUploadError");
  errorEl.textContent = "";

  const title = document.getElementById("kbTitle").value.trim();
  const category = document.getElementById("kbCategory").value;
  const fileInput = document.getElementById("kbFile");
  const textContent = document.getElementById("kbTextContent").value.trim();

  if (!title || !category) {
    errorEl.textContent = "Judul dan kategori wajib diisi.";
    return;
  }
  if (!fileInput.files.length && !textContent) {
    errorEl.textContent = "Sertakan file ATAU teks manual untuk diindeks.";
    return;
  }

  const formData = new FormData();
  formData.append("title", title);
  formData.append("category", category);
  if (fileInput.files.length) formData.append("file", fileInput.files[0]);
  if (textContent) formData.append("text_content", textContent);

  try {
    await Api.uploadKnowledgeDocument(formData);
    showToast("Dokumen berhasil diupload & diindeks", "success");
    document.getElementById("kbUploadForm").reset();
    await loadKnowledgeList();
  } catch (e) {
    errorEl.textContent = "Gagal mengupload dokumen: " + e.message;
  }
}

async function handleKbSearch() {
  const query = document.getElementById("kbSearchInput").value.trim();
  const mode = document.getElementById("kbSearchMode").value;
  const container = document.getElementById("kbSearchResult");
  if (!query) {
    container.innerHTML = `<p class="kb-empty">Masukkan kata kunci pencarian terlebih dahulu.</p>`;
    return;
  }

  if (mode === "ask") {
    container.innerHTML = `<p class="kb-empty">Mencari &amp; menyusun jawaban (retrieval → context injection → Gemini)...</p>`;
    try {
      const res = await Api.askKnowledge(query, 5);
      renderRagAnswer(container, res);
    } catch (e) {
      container.innerHTML = `<p class="error-text">Gagal memproses RAG answer: ${escapeHtml(e.message)}</p>`;
    }
    return;
  }

  container.innerHTML = `<p class="kb-empty">Mencari...</p>`;
  try {
    const res = await Api.searchKnowledge(query, 5);
    if (res.count === 0) {
      container.innerHTML = `<p class="kb-empty">Tidak ditemukan potongan Knowledge Base yang cukup relevan dengan query ini.</p>`;
      return;
    }
    container.innerHTML = res.results.map((r) => `
      <div class="kb-result-item">
        <div class="kb-result-header">
          <span><strong>${escapeHtml(r.document_title)}</strong> &middot; <span class="kb-category-badge">${escapeHtml(r.document_category)}</span></span>
          <span class="kb-score">skor: ${r.relevance_score}</span>
        </div>
        <div class="kb-text">${escapeHtml(r.text)}</div>
      </div>
    `).join("");
  } catch (e) {
    container.innerHTML = `<p class="error-text">Gagal mencari: ${escapeHtml(e.message)}</p>`;
  }
}

function renderRagAnswer(container, res) {
  const methodLabel = { gemini: "Gemini", ollama: "Ollama", mock: "Mock (tanpa LLM)", mock_fallback: "Mock fallback" }[res.method] || res.method;
  const sourcesHtml = res.context_used.length
    ? `<ul>${res.context_used.map((c) => `<li>${escapeHtml(c.document_title)} <span class="kb-category-badge">${escapeHtml(c.document_category)}</span> <span class="kb-score">(skor ${c.relevance_score})</span></li>`).join("")}</ul>`
    : `<p class="kb-empty">Tidak ada potongan Knowledge Base yang dipakai.</p>`;

  container.innerHTML = `
    <div class="rag-answer-box">
      <div class="rag-answer-meta">
        <span class="rag-badge">${res.grounded ? "✓ Grounded pada KB" : "⚠ Tidak ada rujukan KB"}</span>
        <span class="rag-badge rag-method">Generator: ${escapeHtml(methodLabel)}</span>
      </div>
      <div class="rag-answer-text">${escapeHtml(res.answer)}</div>
      <h4>Potongan Knowledge Base yang Dipakai (Context Injection)</h4>
      ${sourcesHtml}
    </div>
  `;
}

// ==================================================================
// 3. Disposisi Underwriting
// ==================================================================

let dispositionState = { latest: null };

function getDispositionOverridesFromForm() {
  const overrides = {};
  const toc = document.getElementById("dispToc").value.trim();
  const sharePlan = document.getElementById("dispSharePlan").value.trim();
  const leader = document.getElementById("dispLeader").value.trim();
  const participation = document.getElementById("dispParticipation").value.trim();
  const decision = document.getElementById("dispDecision").value.trim();
  const notes = document.getElementById("dispNotes").value.trim();

  if (toc) overrides.toc = toc;
  if (sharePlan) overrides.placement_share_plan = sharePlan;
  if (leader) overrides.placement_leader = leader;
  if (participation) overrides.placement_proposed_participation = participation;
  if (decision) overrides.uw_decision = decision;
  if (notes) overrides.underwriter_notes = notes;
  return overrides;
}

async function handleGenerateDisposition() {
  const btn = document.getElementById("btnGenerateDisposition");
  btn.disabled = true;
  btn.textContent = "Menyusun disposisi...";
  try {
    const overrides = getDispositionOverridesFromForm();
    const d = await Api.generateDisposition(currentCaseId, overrides);
    dispositionState.latest = d;
    renderDisposition(d);
    showToast("Disposisi berhasil disusun", "success");
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    showToast("Gagal menyusun disposisi: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Disposisi";
  }
}

async function loadDispositionForCase(caseId) {
  const meta = document.getElementById("dispositionMeta");
  const summary = document.getElementById("dispositionSummary");
  const textarea = document.getElementById("dispositionTextArea");
  const btnSave = document.getElementById("btnSaveDisposition");
  const btnNarrative = document.getElementById("btnGenerateNarrative");
  const narrativeResult = document.getElementById("narrativeResult");

  meta.textContent = "";
  summary.classList.add("hidden");
  textarea.classList.add("hidden");
  btnSave.classList.add("hidden");
  btnNarrative.classList.add("hidden");
  narrativeResult.classList.add("hidden");
  narrativeResult.innerHTML = "";

  try {
    const d = await Api.getLatestDisposition(caseId);
    dispositionState.latest = d;
    renderDisposition(d);
  } catch (e) {
    // belum ada disposisi untuk case ini - biarkan kosong sampai underwriter klik Generate
  }
}

function renderDisposition(d) {
  const meta = document.getElementById("dispositionMeta");
  const summary = document.getElementById("dispositionSummary");
  const textarea = document.getElementById("dispositionTextArea");
  const btnSave = document.getElementById("btnSaveDisposition");
  const btnNarrative = document.getElementById("btnGenerateNarrative");

  meta.textContent = `v${d.version_number} · sumber: ${d.source} · ${formatDateTime(d.created_at)}`;

  const kbRefsHtml = d.kb_references.length
    ? `<ul>${d.kb_references.map((r) => `<li>${escapeHtml(r.document_title)} <span class="kb-category-badge">${escapeHtml(r.document_category)}</span></li>`).join("")}</ul>`
    : `<p class="kb-empty">Tidak ada rujukan Knowledge Base yang terpakai pada versi ini.</p>`;

  const subjectToCount = d.subject_to.length;
  const coordinationHtml = (d.coordination_notes || "").startsWith("PERLU KOORDINASI")
    ? `<div class="coordination-alert">⚠️ ${escapeHtml(d.coordination_notes)}</div>`
    : `<div class="coordination-ok">✓ ${escapeHtml(d.coordination_notes || "")}</div>`;

  summary.classList.remove("hidden");
  summary.innerHTML = `
    <div class="disposition-summary-box">
      <h4>Ringkasan Subject To/Conditions (${subjectToCount} kondisi terpicu dari Rule Engine)</h4>
      <h4 style="margin-top:10px;">Referensi Knowledge Base yang Digunakan</h4>
      ${kbRefsHtml}
      ${coordinationHtml}
    </div>
  `;

  textarea.value = d.disposition_text;
  textarea.classList.remove("hidden");
  btnSave.classList.remove("hidden");
  if (subjectToCount > 0) btnNarrative.classList.remove("hidden");
}

async function handleGenerateNarrative() {
  const btn = document.getElementById("btnGenerateNarrative");
  const container = document.getElementById("narrativeResult");
  btn.disabled = true;
  btn.textContent = "Menyusun narasi (retrieval → context injection → Gemini)...";
  container.classList.remove("hidden");
  container.innerHTML = `<p class="kb-empty">Memproses...</p>`;
  try {
    const res = await Api.generateDispositionNarrative(currentCaseId);
    const methodLabel = { gemini: "Gemini", ollama: "Ollama", mock: "Mock (tanpa LLM)", mock_fallback: "Mock fallback" }[res.method] || res.method;
    container.innerHTML = `
      <div class="rag-answer-box">
        <div class="rag-answer-meta">
          <span class="rag-badge">${res.grounded ? "✓ Grounded pada rule engine + KB" : "⚠ Tanpa rujukan KB"}</span>
          <span class="rag-badge rag-method">Generator: ${escapeHtml(methodLabel)}</span>
        </div>
        <div class="rag-answer-text">${escapeHtml(res.narrative)}</div>
        <div class="extraction-actions" style="margin-top:10px;">
          <button class="btn btn-secondary btn-sm" id="btnInsertNarrative">Sisipkan ke Catatan Underwriter</button>
        </div>
      </div>
    `;
    document.getElementById("btnInsertNarrative").addEventListener("click", () => {
      const notesEl = document.getElementById("dispNotes");
      notesEl.value = (notesEl.value ? notesEl.value + "\n\n" : "") + res.narrative;
      showToast("Narasi disisipkan ke Catatan Khusus Underwriter - klik Generate Disposisi untuk memperbarui teks.", "success");
    });
  } catch (e) {
    container.innerHTML = `<p class="error-text">Gagal menyusun narasi: ${escapeHtml(e.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ Buat Ringkasan Naratif AI (RAG + Gemini)";
  }
}

async function handleSaveDisposition() {
  const text = document.getElementById("dispositionTextArea").value;
  const notes = document.getElementById("dispNotes").value.trim();
  try {
    const d = await Api.saveDispositionEdit(currentCaseId, {
      disposition_text: text,
      underwriter_notes: notes || undefined,
    });
    dispositionState.latest = d;
    renderDisposition(d);
    showToast("Perubahan teks disposisi berhasil disimpan (versi baru dibuat)", "success");
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    showToast("Gagal menyimpan disposisi: " + e.message, "error");
  }
}

// ==================================================================
// 4. Analisis Kualitatif (rangkuman disposisi + Risiko Bencana Wilayah)
// ==================================================================

function resetQualitativeAnalysisCard() {
  document.getElementById("qaMeta").textContent = "";
  document.getElementById("qualitativeAnalysisResult").innerHTML = "";
}

function formatRupiahEstimate(amount) {
  if (amount === null || amount === undefined) return "-";
  try {
    return "Rp " + Number(amount).toLocaleString("id-ID");
  } catch (e) {
    return String(amount);
  }
}

function renderRegionalDisasterRisk(risk) {
  const level = risk.risk_level || "Unknown";
  const levelClass = ["Low", "Medium", "High"].includes(level) ? `risk-${level}` : "risk-Low";
  const cats = (risk.risk_categories_detected || []);
  const catsHtml = cats.length
    ? cats.map((c) => `<span class="fact-tag">${escapeHtml(c)}</span>`).join("")
    : `<span class="kb-empty">Tidak ada kategori risiko terdeteksi dari berita yang ditemukan.</span>`;

  const newsHtml = (risk.news_items || []).length
    ? risk.news_items.map((n) => `
        <div class="kb-result-item">
          <div class="kb-result-header">
            <span><a href="${escapeHtml(n.url)}" target="_blank" rel="noopener">${escapeHtml(n.title)}</a></span>
            <span class="kb-score">${escapeHtml(n.pub_date || "")}</span>
          </div>
          <div class="kb-text">${escapeHtml(n.snippet || "")}</div>
          ${n.categories && n.categories.length ? `<div style="margin-top:6px;">${n.categories.map((c) => `<span class="fact-tag">${escapeHtml(c)}</span>`).join("")}</div>` : ""}
        </div>
      `).join("")
    : `<p class="kb-empty">Tidak ditemukan berita terkait wilayah ini pada Google News.</p>`;

  const warningHtml = risk.warning ? `<div class="coordination-alert">⚠️ ${escapeHtml(risk.warning)}</div>` : "";

  return `
    <div class="disposition-summary-box" style="margin-top:14px;">
      <h4>🌪️ Analisis Risiko Bencana Wilayah - ${escapeHtml(risk.wilayah || "-")}</h4>
      <span class="risk-level-badge ${levelClass}">Tingkat Risiko: ${escapeHtml(level)}</span>
      <div style="margin:8px 0;">${catsHtml}</div>
      ${warningHtml}
      <h4 style="margin-top:12px;">Berita Terkait (sumber: ${escapeHtml(risk.source || "Google News RSS")})</h4>
      ${newsHtml}
      <p class="hint" style="margin-top:10px;">${escapeHtml(risk.disclaimer || "")}</p>
    </div>
  `;
}

function renderQualitativeAnalysis(qa) {
  const meta = document.getElementById("qaMeta");
  const container = document.getElementById("qualitativeAnalysisResult");
  meta.textContent = `berdasarkan disposisi v${qa.disposition_version}`;

  const claims = qa.claims_summary;
  const subjectTo = qa.subject_to_summary || [];
  const subjectToHtml = subjectTo.length
    ? subjectTo.map((s) => `<li><strong>${escapeHtml(s.category)}</strong> &middot; ${s.count} kondisi</li>`).join("")
    : `<li class="empty">Tidak ada kondisi Subject To/Conditions yang terpicu.</li>`;

  const coordinationHtml = qa.coordination.flagged
    ? `<div class="coordination-alert">⚠️ ${escapeHtml(qa.coordination.note || "")}</div>`
    : `<div class="coordination-ok">✓ ${escapeHtml(qa.coordination.note || "")}</div>`;

  container.innerHTML = `
    <div class="disposition-summary-box">
      <h4>📌 Ringkasan Informasi Risiko</h4>
      <p style="margin:0 0 10px;font-size:13px;">
        <strong>${escapeHtml(qa.risk_summary.insured_name)}</strong> &middot; ${escapeHtml(qa.risk_summary.risk_location || "-")}<br/>
        TOC: ${escapeHtml(qa.risk_summary.toc || "-")} &middot; TSI: ${escapeHtml(qa.risk_summary.tsi || "-")} &middot; Loss Ratio: ${escapeHtml(qa.risk_summary.loss_ratio || "-")}<br/>
        Rekomendasi: <strong>${escapeHtml(qa.risk_summary.decision || "-")}</strong>
      </p>

      <h4>Ringkasan Riwayat Klaim</h4>
      <p style="margin:0 0 10px;font-size:13px;">
        ${claims.count} riwayat klaim ditemukan pada database internal
        ${claims.total_claim_amount_estimate !== null ? ` &middot; estimasi total nilai klaim: ${formatRupiahEstimate(claims.total_claim_amount_estimate)}` : ""}.
      </p>

      <h4>Ringkasan Subject To/Conditions (${subjectTo.reduce((a, s) => a + s.count, 0)} kondisi)</h4>
      <ul>${subjectToHtml}</ul>

      <h4>Koordinasi Kantor/Cabang Lain</h4>
      ${coordinationHtml}
    </div>

    ${renderRegionalDisasterRisk(qa.regional_disaster_risk)}

    <div class="rag-answer-box" style="margin-top:14px;">
      <h4 style="margin-top:0;">Kesimpulan Kualitatif</h4>
      <div class="rag-answer-text">${escapeHtml(qa.conclusion)}</div>
    </div>
  `;
}

async function handleGenerateQualitativeAnalysis() {
  const btn = document.getElementById("btnGenerateQualitativeAnalysis");
  const container = document.getElementById("qualitativeAnalysisResult");
  btn.disabled = true;
  btn.textContent = "Menyusun analisis (rangkuman disposisi + scraping berita wilayah)...";
  container.innerHTML = `<p class="kb-empty">Memproses...</p>`;
  try {
    const qa = await Api.getQualitativeAnalysis(currentCaseId);
    renderQualitativeAnalysis(qa);
  } catch (e) {
    container.innerHTML = `<p class="error-text">Gagal menyusun Analisis Kualitatif: ${escapeHtml(e.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Buat Analisis Kualitatif";
  }
}
