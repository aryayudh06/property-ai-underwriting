// Logika untuk modul Structured Data Extraction (LLM via Ollama + LLM Extraction Service).
// Tidak mengubah logika Case Management / Document Processing yang sudah ada.

const CATEGORY_LABELS = {
  insured: "Tertanggung",
  risk_location: "Lokasi Risiko",
  occupancy: "Okupasi & Aktivitas Usaha",
  building: "Bangunan",
  assets: "Nilai Aset & Sum Insured",
  fire_protection: "Proteksi Kebakaran",
  electrical_and_maintenance: "Kelistrikan & Maintenance",
  operations: "Proses Operasional",
  natural_perils: "Risiko Bencana Alam",
  loss_history: "Riwayat Klaim / Kerugian",
  coverage: "Coverage & Perluasan",
  survey: "Hasil Survey",
};

const FIELD_LABELS = {
  insured: {
    name: "Nama Tertanggung",
    business_activity: "Aktivitas Usaha",
    address_office: "Alamat Kantor",
    contact_person: "Contact Person",
  },
  risk_location: {
    address: "Alamat Lokasi Risiko",
    city: "Kota/Kabupaten",
    province: "Provinsi",
    postal_code: "Kode Pos",
  },
  occupancy: {
    occupation_type: "Jenis Okupasi",
    business_activity_detail: "Detail Aktivitas Usaha",
    operational_hours: "Jam Operasional",
    number_of_employees: "Jumlah Karyawan",
  },
  building: {
    construction_type: "Jenis Konstruksi",
    building_age_years: "Usia Bangunan (tahun)",
    floor_area_sqm: "Luas Lantai (m²)",
    number_of_floors: "Jumlah Lantai",
    building_condition: "Kondisi Bangunan",
  },
  assets: {
    building_value: "Nilai Bangunan",
    machinery_value: "Nilai Mesin",
    stock_value: "Nilai Stok",
    equipment_value: "Nilai Peralatan",
    sum_insured_total: "Total Sum Insured Aset",
  },
  fire_protection: {
    sprinkler: "Sprinkler",
    hydrant: "Hydrant",
    fire_alarm: "Fire Alarm",
    apar_fire_extinguisher: "APAR",
    fire_brigade_distance: "Jarak ke Pemadam Kebakaran",
  },
  electrical_and_maintenance: {
    electrical_condition: "Kondisi Kelistrikan",
    housekeeping_condition: "Kondisi Housekeeping",
    maintenance_program: "Program Maintenance",
    wiring_age: "Usia Instalasi Kabel",
  },
  operations: {
    process_description: "Deskripsi Proses",
    raw_materials: "Bahan Baku",
    hazardous_materials: "Bahan Berbahaya",
    operating_shift_pattern: "Pola Shift",
  },
  natural_perils: {
    flood_risk: "Risiko Banjir",
    earthquake_risk: "Risiko Gempa",
    windstorm_risk: "Risiko Angin Ribut/Badai",
    other_natural_hazards: "Bencana Alam Lain",
  },
  loss_history: {
    previous_claims: "Klaim Sebelumnya",
    loss_years: "Tahun Kejadian",
    total_loss_amount: "Total Nilai Kerugian",
    cause_of_loss: "Penyebab Kerugian",
  },
  coverage: {
    sum_insured: "Sum Insured",
    coverage_extensions: "Perluasan Jaminan",
    deductible: "Deductible",
    policy_period: "Periode Pertanggungan",
    currency: "Mata Uang",
  },
  survey: {
    surveyor_name: "Nama Surveyor",
    survey_date: "Tanggal Survey",
    key_findings: "Temuan Utama",
    recommendations: "Rekomendasi",
    overall_risk_grade: "Grade Risiko Keseluruhan",
  },
};

let extractionState = {
  version: null,       // versi terakhir dari server (source of truth tersimpan)
  data: null,           // data yang sedang ditampilkan/diedit (working copy)
  editMode: false,
};

function getExtractionElements() {
  return {
    meta: document.getElementById("extractionMeta"),
    formContainer: document.getElementById("extractionFormContainer"),
    warnings: document.getElementById("extractionWarnings"),
    mockRulesResult: document.getElementById("mockRulesResult"),
    btnExtract: document.getElementById("btnExtract"),
    btnEdit: document.getElementById("btnEditExtraction"),
    btnCancel: document.getElementById("btnCancelExtractionEdit"),
    btnSaveDraft: document.getElementById("btnSaveDraft"),
    btnSubmitMockRules: document.getElementById("btnSubmitMockRules"),
    btnReExtract: document.getElementById("btnReExtract"),
  };
}

function setExtractionButtons({ hasData, editMode }) {
  const el = getExtractionElements();
  el.btnExtract.classList.toggle("hidden", hasData);
  el.btnEdit.classList.toggle("hidden", !hasData || editMode);
  el.btnCancel.classList.toggle("hidden", !editMode);
  el.btnSaveDraft.classList.toggle("hidden", !editMode);
  el.btnSubmitMockRules.classList.toggle("hidden", !hasData || editMode);
  el.btnReExtract.classList.toggle("hidden", !hasData || editMode);
}

async function loadExtractionForCase(caseId) {
  const el = getExtractionElements();
  el.mockRulesResult.classList.add("hidden");
  el.warnings.classList.add("hidden");

  try {
    const version = await Api.getLatestExtraction(caseId);
    extractionState.version = version;
    extractionState.data = JSON.parse(JSON.stringify(version.data));
    extractionState.editMode = false;

    el.meta.textContent = `v${version.version_number} · sumber: ${version.source} · metode: ${version.method || "-"} · ${formatDateTime(version.created_at)}`;
    renderExtractionWarnings(version.warnings || []);
    renderExtractionForm(extractionState.data, false);
    setExtractionButtons({ hasData: true, editMode: false });

    // muat juga hasil mock rules terakhir jika ada
    try {
      const mockResult = await Api.getLatestMockRules(caseId);
      renderMockRulesResult(mockResult);
    } catch (e) {
      // belum ada hasil mock rules - biarkan tersembunyi
    }
  } catch (e) {
    extractionState.version = null;
    extractionState.data = null;
    el.meta.textContent = "";
    el.formContainer.innerHTML = `<p class="extraction-empty">Belum ada hasil ekstraksi. Klik "Extract Structured Data" untuk memulai (pastikan minimal satu dokumen sudah berstatus Processed).</p>`;
    setExtractionButtons({ hasData: false, editMode: false });
  }
}

function renderExtractionWarnings(warnings) {
  const el = document.getElementById("extractionWarnings");
  if (!warnings || warnings.length === 0) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }
  el.classList.remove("hidden");
  el.innerHTML = "⚠️ " + warnings.map(escapeHtml).join("<br/>⚠️ ");
}

function confidenceDotClass(confidence) {
  if (confidence >= 0.75) return "conf-high";
  if (confidence >= 0.4) return "conf-mid";
  return "conf-low";
}

function renderExtractionForm(data, editable) {
  const container = document.getElementById("extractionFormContainer");
  const sections = Object.keys(CATEGORY_LABELS).map((cat) => {
    const fields = data[cat] || {};
    const fieldRows = Object.keys(FIELD_LABELS[cat]).map((fieldKey) => {
      const fv = fields[fieldKey] || { value: "Not Found", confidence: 0 };
      const isNotFound = fv.value === null || fv.value === undefined || fv.value === "" || fv.value === "Not Found";
      const label = FIELD_LABELS[cat][fieldKey];
      const confPct = Math.round((fv.confidence || 0) * 100);

      const valueBlock = editable
        ? `<input type="text" data-cat="${cat}" data-field="${fieldKey}" class="extraction-input"
             value="${escapeHtml(isNotFound ? "" : fv.value)}" placeholder="Not Found" />`
        : `<div class="field-value-readonly ${isNotFound ? "not-found" : ""}">${escapeHtml(isNotFound ? "Not Found" : fv.value)}</div>`;

      const sourceInfo = fv.source_document
        ? `📄 ${escapeHtml(fv.source_document)}${fv.page ? " · hal. " + fv.page : ""}`
        : "";

      return `
        <div class="field-row">
          <div class="field-label">${escapeHtml(label)}</div>
          <div class="field-value-block">
            ${valueBlock}
            <div class="field-meta">
              ${sourceInfo ? `<span>${sourceInfo}</span>` : ""}
              <span class="conf-bar"><span class="conf-dot ${confidenceDotClass(fv.confidence || 0)}"></span>Confidence: ${confPct}%</span>
            </div>
            ${fv.evidence ? `<div class="field-evidence">"${escapeHtml(fv.evidence)}"</div>` : ""}
          </div>
        </div>
      `;
    }).join("");

    return `
      <details class="extraction-section" open>
        <summary>${CATEGORY_LABELS[cat]} <span class="section-hint">${Object.keys(FIELD_LABELS[cat]).length} field</span></summary>
        <div class="extraction-fields">${fieldRows}</div>
      </details>
    `;
  }).join("");

  const gapsBlock = (data.data_gaps && data.data_gaps.length)
    ? `<p class="hint">Data gaps (${data.data_gaps.length}): ${data.data_gaps.slice(0, 15).map(escapeHtml).join(", ")}${data.data_gaps.length > 15 ? ", ..." : ""}</p>`
    : "";
  const conflictsBlock = (data.conflicts && data.conflicts.length)
    ? `<p class="hint" style="color:var(--danger);">Konflik data: ${data.conflicts.map(escapeHtml).join("; ")}</p>`
    : "";

  container.innerHTML = `
    <p class="hint">Overall confidence: <strong>${Math.round((data.confidence || 0) * 100)}%</strong></p>
    ${gapsBlock}
    ${conflictsBlock}
    ${sections}
  `;
}

function collectExtractionFormData() {
  // Mulai dari data working copy (agar source_document/page/evidence/confidence tetap terjaga),
  // lalu timpa hanya "value" dari input yang diedit oleh underwriter.
  const data = JSON.parse(JSON.stringify(extractionState.data));
  document.querySelectorAll("#extractionFormContainer .extraction-input").forEach((input) => {
    const cat = input.dataset.cat;
    const field = input.dataset.field;
    const newValue = input.value.trim();
    if (!data[cat]) data[cat] = {};
    if (!data[cat][field]) data[cat][field] = { value: null, source_document: null, page: null, evidence: null, confidence: 0 };
    data[cat][field].value = newValue === "" ? "Not Found" : newValue;
    if (newValue !== "" && data[cat][field].confidence === 0) {
      data[cat][field].confidence = 1.0; // nilai manual underwriter dianggap yakin penuh
    }
  });
  return data;
}

// ---------------- Progress Modal ----------------

const PROGRESS_STEPS = ["preparing", "sending", "extracting", "validating", "completed"];

function resetProgressSteps() {
  document.querySelectorAll("#progressSteps li").forEach((li) => {
    li.classList.remove("active", "done", "error");
    li.querySelector(".step-icon").textContent = "○";
  });
  document.getElementById("extractionProgressError").textContent = "";
}

function setProgressStep(stepName, status) {
  const li = document.querySelector(`#progressSteps li[data-step="${stepName}"]`);
  if (!li) return;
  li.classList.remove("active", "done", "error");
  const icon = li.querySelector(".step-icon");
  if (status === "active") {
    li.classList.add("active");
    icon.textContent = "◐";
  } else if (status === "done") {
    li.classList.add("done");
    icon.textContent = "✓";
  } else if (status === "error") {
    li.classList.add("error");
    icon.textContent = "✕";
  }
}

async function runExtractionFlow() {
  resetProgressSteps();
  openModal("extractionProgressModal");

  setProgressStep("preparing", "active");
  await sleep(400);
  setProgressStep("preparing", "done");
  setProgressStep("sending", "active");

  try {
    // Panggilan nyata ke Main API -> LLM Extraction Service -> Ollama/mock berjalan di sini.
    const extractPromise = Api.runExtraction(currentCaseId);

    await sleep(500);
    setProgressStep("sending", "done");
    setProgressStep("extracting", "active");

    const version = await extractPromise;

    setProgressStep("extracting", "done");
    setProgressStep("validating", "active");
    await sleep(400);
    setProgressStep("validating", "done");
    setProgressStep("completed", "done");
    await sleep(350);

    closeModal("extractionProgressModal");

    extractionState.version = version;
    extractionState.data = JSON.parse(JSON.stringify(version.data));
    extractionState.editMode = false;

    document.getElementById("extractionMeta").textContent =
      `v${version.version_number} · sumber: ${version.source} · metode: ${version.method || "-"} · ${formatDateTime(version.created_at)}`;
    renderExtractionWarnings(version.warnings || []);
    renderExtractionForm(extractionState.data, false);
    setExtractionButtons({ hasData: true, editMode: false });
    document.getElementById("mockRulesResult").classList.add("hidden");

    showToast("Ekstraksi data terstruktur selesai", "success");
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    setProgressStep("sending", "error");
    document.getElementById("extractionProgressError").textContent = "Gagal: " + e.message;
    await sleep(1800);
    closeModal("extractionProgressModal");
    showToast("Ekstraksi gagal: " + e.message, "error");
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------- Action handlers ----------------

function handleExtractClick() {
  runExtractionFlow();
}

function handleReExtractClick() {
  if (!confirm("Menjalankan ekstraksi ulang akan membuat versi baru dari LLM. Perubahan yang belum disimpan akan hilang. Lanjutkan?")) return;
  runExtractionFlow();
}

function handleEditExtractionClick() {
  extractionState.editMode = true;
  renderExtractionForm(extractionState.data, true);
  setExtractionButtons({ hasData: true, editMode: true });
}

function handleCancelExtractionEdit() {
  extractionState.editMode = false;
  extractionState.data = JSON.parse(JSON.stringify(extractionState.version.data));
  renderExtractionForm(extractionState.data, false);
  setExtractionButtons({ hasData: true, editMode: false });
}

async function handleSaveDraft() {
  const data = collectExtractionFormData();
  try {
    const version = await Api.saveExtractionEdit(currentCaseId, data);
    extractionState.version = version;
    extractionState.data = JSON.parse(JSON.stringify(version.data));
    extractionState.editMode = false;

    document.getElementById("extractionMeta").textContent =
      `v${version.version_number} · sumber: ${version.source} · ${formatDateTime(version.created_at)}`;
    renderExtractionForm(extractionState.data, false);
    setExtractionButtons({ hasData: true, editMode: false });

    showToast("Draft berhasil disimpan (versi baru dibuat)", "success");
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    showToast("Gagal menyimpan draft: " + e.message, "error");
  }
}

async function handleSubmitMockRules() {
  try {
    // Jika sedang dalam mode edit, simpan dulu perubahan sebelum menjalankan rules.
    if (extractionState.editMode) {
      const data = collectExtractionFormData();
      const version = await Api.saveExtractionEdit(currentCaseId, data);
      extractionState.version = version;
      extractionState.data = JSON.parse(JSON.stringify(version.data));
      extractionState.editMode = false;
      renderExtractionForm(extractionState.data, false);
      setExtractionButtons({ hasData: true, editMode: false });
    }

    showToast("Menjalankan mock rule engine...", "success");
    const result = await Api.submitMockRules(currentCaseId);
    renderMockRulesResult(result);
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    showToast("Gagal menjalankan mock rules: " + e.message, "error");
  }
}

function renderMockRulesResult(result) {
  const el = document.getElementById("mockRulesResult");
  el.classList.remove("hidden");

  const flagsHtml = result.risk_flags.length
    ? `<ul>${result.risk_flags.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : `<p class="empty">Tidak ada risk flag terdeteksi.</p>`;

  const missingHtml = result.missing_critical_info.length
    ? `<ul>${result.missing_critical_info.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : `<p class="empty">Semua field kritikal terisi.</p>`;

  const inconsistHtml = result.data_inconsistencies.length
    ? `<ul>${result.data_inconsistencies.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : `<p class="empty">Tidak ada inkonsistensi data terdeteksi.</p>`;

  el.innerHTML = `
    <span class="risk-level-badge risk-${result.risk_level}">Risk Level: ${result.risk_level}</span>
    <div class="mock-rules-grid">
      <div><h4>Risk Flags</h4>${flagsHtml}</div>
      <div><h4>Missing Critical Information</h4>${missingHtml}</div>
      <div><h4>Data Inconsistency</h4>${inconsistHtml}</div>
      <div><h4>Recommended Next Action</h4><p>${escapeHtml(result.recommended_action)}</p></div>
      <div class="recommended-action-box">Dievaluasi pada ${formatDateTime(result.created_at)} terhadap extraction versi terkait. Rules bersifat mock/konfigurasi sederhana - bukan analisa underwriting final.</div>
    </div>
  `;
}
