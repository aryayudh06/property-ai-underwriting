// Bootstrap aplikasi: navigasi antar-view, modal helper, toast, dan event bindings.

function showView(viewId) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  document.getElementById(viewId).classList.remove("hidden");
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}
function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

let toastTimer = null;
function showToast(message, type = "") {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function goToDashboard() {
  showView("view-dashboard");
  loadCaseList();
}

document.addEventListener("DOMContentLoaded", () => {
  // Nav
  document.getElementById("btnGoDashboard").addEventListener("click", goToDashboard);
  document.getElementById("btnBackToDashboard").addEventListener("click", goToDashboard);
  document.getElementById("btnCancelForm").addEventListener("click", goToDashboard);

  // Dashboard
  document.getElementById("btnNewCase").addEventListener("click", () => openCaseForm(null));
  document.getElementById("btnRefreshCases").addEventListener("click", loadCaseList);
  document.getElementById("searchInput").addEventListener("input", debounce(loadCaseList, 350));
  document.getElementById("statusFilter").addEventListener("change", loadCaseList);

  // Case form
  document.getElementById("caseForm").addEventListener("submit", handleCaseFormSubmit);

  // Case detail
  document.getElementById("btnEditCase").addEventListener("click", () => openCaseForm(window.__currentCase));
  document.getElementById("btnChangeStatus").addEventListener("click", handleChangeStatus);
  document.getElementById("btnRefreshDocs").addEventListener("click", () => loadDocumentList(currentCaseId));
  document.getElementById("btnUpload").addEventListener("click", handleUploadDocuments);

  // Structured Data Extraction
  document.getElementById("btnExtract").addEventListener("click", handleExtractClick);
  document.getElementById("btnReExtract").addEventListener("click", handleReExtractClick);
  document.getElementById("btnEditExtraction").addEventListener("click", handleEditExtractionClick);
  document.getElementById("btnCancelExtractionEdit").addEventListener("click", handleCancelExtractionEdit);
  document.getElementById("btnSaveDraft").addEventListener("click", handleSaveDraft);
  document.getElementById("btnSubmitMockRules").addEventListener("click", handleSubmitMockRules);

  // ---- Fitur Lanjutan ----
  document.getElementById("btnSearchClaims").addEventListener("click", handleSearchClaims);
  document.getElementById("btnRefreshKb").addEventListener("click", loadKnowledgeList);
  document.getElementById("kbUploadForm").addEventListener("submit", handleKbUploadSubmit);
  document.getElementById("btnKbSearch").addEventListener("click", handleKbSearch);
  document.getElementById("kbSearchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); handleKbSearch(); }
  });
  document.getElementById("btnGenerateDisposition").addEventListener("click", handleGenerateDisposition);
  document.getElementById("btnGenerateNarrative").addEventListener("click", handleGenerateNarrative);
  document.getElementById("btnSaveDisposition").addEventListener("click", handleSaveDisposition);
  document.getElementById("btnGenerateQualitativeAnalysis").addEventListener("click", handleGenerateQualitativeAnalysis);

  // Modals
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(btn.dataset.close));
  });
  document.querySelectorAll(".modal").forEach((modal) => {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.add("hidden");
    });
  });

  // Initial load
  checkOcrHealth();
  goToDashboard();
});

async function checkOcrHealth() {
  const badge = document.getElementById("ocrBadge");
  try {
    const health = await Api.health();
    if (health.ocr_available) {
      badge.textContent = "OCR: Aktif";
      badge.className = "badge badge-Completed";
    } else {
      badge.textContent = "OCR: Tidak Terpasang";
      badge.className = "badge badge-Failed";
    }
  } catch (e) {
    badge.textContent = "Server Offline";
    badge.className = "badge badge-Failed";
  }
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
