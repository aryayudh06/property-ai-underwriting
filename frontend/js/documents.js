// Logika untuk modul Document Processing (upload, list, preview, extracted text).

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function docStatusBadge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

async function handleUploadDocuments() {
  const input = document.getElementById("fileInput");
  const statusEl = document.getElementById("uploadStatus");

  if (!input.files || input.files.length === 0) {
    statusEl.innerHTML = `<span class="err">Pilih minimal satu file terlebih dahulu.</span>`;
    return;
  }

  const formData = new FormData();
  for (const file of input.files) {
    formData.append("files", file);
  }

  const btn = document.getElementById("btnUpload");
  btn.disabled = true;
  statusEl.innerHTML = `Mengunggah &amp; memproses ${input.files.length} file...`;

  try {
    const result = await Api.uploadDocuments(currentCaseId, formData);
    let msg = "";
    if (result.uploaded.length) {
      msg += `<span class="ok">${result.uploaded.length} dokumen berhasil diunggah &amp; diproses.</span><br/>`;
    }
    if (result.failed.length) {
      msg += result.failed.map(f => `<span class="err">Gagal: ${escapeHtml(f.filename)} - ${escapeHtml(f.error)}</span>`).join("<br/>");
    }
    statusEl.innerHTML = msg;
    input.value = "";
    await loadDocumentList(currentCaseId);
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    statusEl.innerHTML = `<span class="err">Upload gagal: ${escapeHtml(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}

async function loadDocumentList(caseId) {
  const tbody = document.getElementById("documentTableBody");
  tbody.innerHTML = `<tr><td colspan="8" class="empty-row">Memuat dokumen...</td></tr>`;

  try {
    const docs = await Api.listDocuments(caseId);
    if (docs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-row">Belum ada dokumen diunggah.</td></tr>`;
      return;
    }
    tbody.innerHTML = docs.map((d) => `
      <tr>
        <td>${escapeHtml(d.original_filename)}</td>
        <td>${escapeHtml(d.doc_type)}</td>
        <td>${d.file_format.toUpperCase()}</td>
        <td>${formatBytes(d.file_size)}</td>
        <td>${d.page_count}</td>
        <td>${docStatusBadge(d.processing_status)}</td>
        <td>${formatDateTime(d.uploaded_at)}</td>
        <td class="action-cell">
          <button class="btn btn-secondary btn-sm" onclick="openPreview('${d.id}', '${escapeHtml(d.original_filename)}', '${d.file_format}')">Preview</button>
          <button class="btn btn-secondary btn-sm" onclick="openExtractedText('${d.id}')">Teks</button>
          <button class="btn btn-secondary btn-sm" onclick="handleReprocess('${d.id}')">Proses Ulang</button>
          <button class="btn btn-danger btn-sm" onclick="handleDeleteDocument('${d.id}')">Hapus</button>
        </td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-row">Gagal memuat dokumen: ${escapeHtml(e.message)}</td></tr>`;
  }
}

async function handleReprocess(docId) {
  try {
    showToast("Memproses ulang dokumen...", "success");
    await Api.processDocument(docId);
    await loadDocumentList(currentCaseId);
    await loadCaseHistory(currentCaseId);
    showToast("Dokumen selesai diproses ulang", "success");
  } catch (e) {
    showToast("Gagal memproses dokumen: " + e.message, "error");
  }
}

async function handleDeleteDocument(docId) {
  if (!confirm("Hapus dokumen ini beserta hasil ekstraksinya?")) return;
  try {
    await Api.deleteDocument(docId);
    showToast("Dokumen dihapus", "success");
    await loadDocumentList(currentCaseId);
    await loadCaseHistory(currentCaseId);
  } catch (e) {
    showToast("Gagal menghapus dokumen: " + e.message, "error");
  }
}

function openPreview(docId, filename, fileFormat) {
  document.getElementById("previewModalTitle").textContent = `Preview - ${filename}`;
  const body = document.getElementById("previewModalBody");
  const url = Api.previewUrl(docId);

  if (fileFormat === "pdf") {
    body.innerHTML = `<iframe src="${url}" style="height:65vh;"></iframe>`;
  } else {
    body.innerHTML = `<img src="${url}" alt="${escapeHtml(filename)}" />`;
  }
  openModal("previewModal");
}

async function openExtractedText(docId) {
  openModal("textModal");
  const body = document.getElementById("textModalBody");
  body.innerHTML = "Memuat hasil ekstraksi...";

  try {
    const data = await Api.getDocumentText(docId);
    document.getElementById("textModalTitle").textContent =
      `Hasil Ekstraksi - ${data.document.original_filename} (${data.document.doc_type})`;

    if (data.pages.length === 0) {
      body.innerHTML = `<p>Dokumen belum diproses atau tidak menghasilkan teks.</p>`;
      return;
    }

    body.innerHTML = data.pages.map((p) => {
      const fact = data.facts.find(f => f.page_number === p.page_number);
      return `
        <div class="page-block">
          <h4>Halaman ${p.page_number} &middot; metode: ${p.extraction_method} &middot; ${p.char_count} karakter</h4>
          ${fact ? `<div><span class="fact-tag">Confidence: ${(fact.confidence_score * 100).toFixed(0)}%</span><span class="fact-tag">Fact ID: ${fact.id.slice(0,8)}</span></div>` : ""}
          <pre>${escapeHtml(p.extracted_text || "(tidak ada teks)")}</pre>
        </div>
      `;
    }).join("");
  } catch (e) {
    body.innerHTML = `<p class="err">Gagal memuat teks: ${escapeHtml(e.message)}</p>`;
  }
}
