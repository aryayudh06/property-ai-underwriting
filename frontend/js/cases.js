// Logika untuk modul Case Management (dashboard, form, detail info, history).

let currentCaseId = null;

function formatDateTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

function statusBadge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

// ---------------- Dashboard ----------------

async function loadCaseList() {
  const tbody = document.getElementById("caseTableBody");
  tbody.innerHTML = `<tr><td colspan="9" class="empty-row">Memuat data...</td></tr>`;

  const params = {};
  const status = document.getElementById("statusFilter").value;
  const search = document.getElementById("searchInput").value.trim();
  if (status) params.status = status;
  if (search) params.search = search;

  try {
    const cases = await Api.listCases(params);
    if (cases.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty-row">Belum ada case. Klik "New Case" untuk membuat.</td></tr>`;
      return;
    }
    tbody.innerHTML = cases.map((c) => `
      <tr>
        <td><span class="row-link" onclick="openCaseDetail('${c.id}')">${c.id}</span></td>
        <td>${escapeHtml(c.quotation_policy_no)}</td>
        <td>${escapeHtml(c.insured_name)}</td>
        <td>${escapeHtml(c.risk_location)}</td>
        <td>${escapeHtml(c.occupation_business)}</td>
        <td>${statusBadge(c.status)}</td>
        <td>${c.document_count}</td>
        <td>${formatDateTime(c.updated_at)}</td>
        <td class="action-cell">
          <button class="btn btn-secondary btn-sm" onclick="openCaseDetail('${c.id}')">Detail</button>
          <button class="btn btn-danger btn-sm" onclick="handleDeleteCase('${c.id}')">Hapus</button>
        </td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-row">Gagal memuat data: ${escapeHtml(e.message)}</td></tr>`;
  }
}

async function handleDeleteCase(caseId) {
  if (!confirm(`Hapus case ${caseId}? Seluruh dokumen terkait juga akan dihapus.`)) return;
  try {
    await Api.deleteCase(caseId);
    showToast("Case berhasil dihapus", "success");
    loadCaseList();
  } catch (e) {
    showToast("Gagal menghapus case: " + e.message, "error");
  }
}

// ---------------- Create / Edit Form ----------------

function openCaseForm(caseData = null) {
  document.getElementById("caseForm").reset();
  document.getElementById("formError").textContent = "";
  document.getElementById("formCaseId").value = "";
  document.getElementById("caseFormTitle").textContent = caseData ? `Edit Case ${caseData.id}` : "Buat Case Baru";

  if (caseData) {
    document.getElementById("formCaseId").value = caseData.id;
    document.getElementById("formQuotationNo").value = caseData.quotation_policy_no;
    document.getElementById("formInsuredName").value = caseData.insured_name;
    document.getElementById("formRiskLocation").value = caseData.risk_location;
    document.getElementById("formOccupation").value = caseData.occupation_business;
    document.getElementById("formStatus").value = caseData.status;
    document.getElementById("formPeriodStart").value = caseData.period_start || "";
    document.getElementById("formPeriodEnd").value = caseData.period_end || "";
    document.getElementById("formBranch").value = caseData.branch || "";
  } else {
    document.getElementById("formStatus").value = "Draft";
  }
  showView("view-case-form");
}

async function handleCaseFormSubmit(evt) {
  evt.preventDefault();
  const errorEl = document.getElementById("formError");
  errorEl.textContent = "";

  const payload = {
    quotation_policy_no: document.getElementById("formQuotationNo").value.trim(),
    insured_name: document.getElementById("formInsuredName").value.trim(),
    risk_location: document.getElementById("formRiskLocation").value.trim(),
    occupation_business: document.getElementById("formOccupation").value.trim(),
    period_start: document.getElementById("formPeriodStart").value || null,
    period_end: document.getElementById("formPeriodEnd").value || null,
    branch: document.getElementById("formBranch").value.trim() || null,
    status: document.getElementById("formStatus").value,
  };

  if (!payload.quotation_policy_no || !payload.insured_name || !payload.risk_location || !payload.occupation_business) {
    errorEl.textContent = "Mohon lengkapi seluruh field wajib (*).";
    return;
  }

  const existingId = document.getElementById("formCaseId").value;
  try {
    let saved;
    if (existingId) {
      saved = await Api.updateCase(existingId, payload);
    } else {
      saved = await Api.createCase(payload);
    }
    showToast("Case berhasil disimpan", "success");
    openCaseDetail(saved.id);
  } catch (e) {
    errorEl.textContent = "Gagal menyimpan case: " + e.message;
  }
}

// ---------------- Case Detail ----------------

async function openCaseDetail(caseId) {
  currentCaseId = caseId;
  showView("view-case-detail");
  document.getElementById("detailCaseId").textContent = `(${caseId})`;
  await refreshCaseDetail();
  await loadDocumentList(caseId);
  await loadExtractionForCase(caseId);

  // Fitur Lanjutan: reset & muat ulang tiap kali membuka case detail
  document.getElementById("claimsResult").innerHTML = `<p class="empty">Klik "Cari Riwayat Klaim PT" untuk memulai pencarian.</p>`;
  await initKnowledgeCategorySelect();
  await loadKnowledgeList();
  await loadDispositionForCase(caseId);
  resetQualitativeAnalysisCard();
}

async function refreshCaseDetail() {
  try {
    const c = await Api.getCase(currentCaseId);
    window.__currentCase = c;

    document.getElementById("detailStatusBadge").outerHTML =
      `<span id="detailStatusBadge" class="badge badge-${c.status}">${c.status}</span>`;

    document.getElementById("caseInfoList").innerHTML = `
      <dt>No. Quotation/Polis</dt><dd>${escapeHtml(c.quotation_policy_no)}</dd>
      <dt>Nama Tertanggung</dt><dd>${escapeHtml(c.insured_name)}</dd>
      <dt>Lokasi Risiko</dt><dd>${escapeHtml(c.risk_location)}</dd>
      <dt>Okupasi/Usaha</dt><dd>${escapeHtml(c.occupation_business)}</dd>
      <dt>Kantor/Cabang</dt><dd>${escapeHtml(c.branch || "-")}</dd>
      <dt>Periode</dt><dd>${c.period_start || "-"} s/d ${c.period_end || "-"}</dd>
      <dt>Dibuat</dt><dd>${formatDateTime(c.created_at)}</dd>
      <dt>Diperbarui</dt><dd>${formatDateTime(c.updated_at)}</dd>
    `;
    document.getElementById("statusSelect").value = c.status;

    await loadCaseHistory(currentCaseId);
  } catch (e) {
    showToast("Gagal memuat detail case: " + e.message, "error");
  }
}

async function handleChangeStatus() {
  const newStatus = document.getElementById("statusSelect").value;
  try {
    await Api.changeCaseStatus(currentCaseId, newStatus);
    showToast("Status case diperbarui", "success");
    refreshCaseDetail();
  } catch (e) {
    showToast("Gagal mengubah status: " + e.message, "error");
  }
}

async function loadCaseHistory(caseId) {
  const list = document.getElementById("historyList");
  list.innerHTML = `<li>Memuat histori...</li>`;
  try {
    const history = await Api.getCaseHistory(caseId);
    if (history.length === 0) {
      list.innerHTML = `<li>Belum ada histori.</li>`;
      return;
    }
    list.innerHTML = history.map((h) => `
      <li>
        <div class="h-action">${escapeHtml(h.action)}</div>
        <div class="h-desc">${escapeHtml(h.description || "")}</div>
        <div class="h-time">${formatDateTime(h.created_at)}</div>
      </li>
    `).join("");
  } catch (e) {
    list.innerHTML = `<li>Gagal memuat histori: ${escapeHtml(e.message)}</li>`;
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
