/* VeriLens Frontend */

const API = "";  // same origin

let currentImageBase64 = null;

// ========== NAVIGATION ==========
function showPage(name) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  const el = document.getElementById("page-" + name);
  if (el) el.classList.add("active");
  window.scrollTo(0, 0);

  if (name === "dashboard") loadDashboard();
  if (name === "history") loadHistory();
}

function switchTab(tab) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
  document.querySelector(`.tab[data-tab="${tab}"]`).classList.add("active");
  document.getElementById("tab-" + tab).classList.add("active");
}

// ========== IMAGE HANDLING ==========
function handleImage(e) {
  const file = e.target.files[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    alert("Image too large. Please keep under 5 MB.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    currentImageBase64 = reader.result;
    const preview = document.getElementById("image-preview");
    preview.innerHTML = `<img src="${currentImageBase64}" alt="Preview" />`;
    preview.classList.remove("hidden");
    document.getElementById("btn-image").disabled = false;
  };
  reader.readAsDataURL(file);
}

// ========== VERIFY ==========
async function verifyText() {
  const text = document.getElementById("text-input").value.trim();
  if (text.length < 10) {
    alert("Please enter a longer claim (at least 10 characters).");
    return;
  }
  await runVerify("/api/verify/text", { text }, "btn-text");
}

async function verifyUrl() {
  const url = document.getElementById("url-input").value.trim();
  if (!url.startsWith("http")) {
    alert("Please enter a valid URL starting with http or https.");
    return;
  }
  await runVerify("/api/verify/url", { url }, "btn-url");
}

async function verifyImage() {
  if (!currentImageBase64) {
    alert("Please select an image first.");
    return;
  }
  await runVerify("/api/verify/image", { image: currentImageBase64 }, "btn-image");
}

async function runVerify(endpoint, body, btnId) {
  const btn = document.getElementById(btnId);
  const loading = document.getElementById("loading");
  btn.disabled = true;
  loading.classList.remove("hidden");

  try {
    const res = await fetch(API + endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    showResults(data);
  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    btn.disabled = false;
    loading.classList.add("hidden");
  }
}

// ========== RESULTS ==========
function showResults(data) {
  showPage("results");
  const meta = document.getElementById("result-meta");
  meta.textContent = `Analysis ID: ${data.analysis_id?.slice(0, 8)}… · Type: ${data.input_type} · ${new Date(data.created_at).toLocaleString()}`;

  const container = document.getElementById("results-container");
  if (!data.claims || data.claims.length === 0) {
    container.innerHTML = `<div class="claim-card"><p>No factual claims could be extracted from the input.</p></div>`;
    return;
  }

  container.innerHTML = data.claims.map((c, i) => {
    const conf = Math.round((c.confidence || 0) * 100);
    const supporting = (c.supporting || []).map(e => evidenceHtml(e)).join("") || `<div class="evidence-item">None found in this prototype run.</div>`;
    const contradicting = (c.contradicting || []).map(e => evidenceHtml(e)).join("") || `<div class="evidence-item">None found.</div>`;

    return `
      <div class="claim-card">
        <div class="claim-header">
          <div class="claim-text">${escapeHtml(c.claim_text)}</div>
          <span class="verdict verdict-${c.verdict}">${formatVerdict(c.verdict)}</span>
        </div>
        <div class="confidence">Confidence: ${conf}%</div>
        <div class="explanation">${escapeHtml(c.explanation || "")}</div>
        <div class="evidence-section">
          <h4>✓ Supporting Evidence</h4>
          ${supporting}
        </div>
        <div class="evidence-section">
          <h4>✗ Contradicting / Context</h4>
          ${contradicting}
        </div>
      </div>
    `;
  }).join("");
}

function evidenceHtml(e) {
  const name = e.source_name || e.source || "Source";
  const url = e.source_url || e.url || "";
  const summary = e.evidence_summary || e.summary || "";
  const date = e.published_at || e.date || "";
  const link = url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(name)}</a>` : escapeHtml(name);
  return `
    <div class="evidence-item">
      <strong>${link}</strong>
      <div>${escapeHtml(summary)}</div>
      ${date ? `<div class="evidence-meta">${escapeHtml(date)}</div>` : ""}
    </div>
  `;
}

function formatVerdict(v) {
  return (v || "INCONCLUSIVE").replace(/_/g, " ");
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ========== DASHBOARD & HISTORY ==========
async function loadDashboard() {
  try {
    const res = await fetch(API + "/api/dashboard/stats");
    const data = await res.json();
    document.getElementById("stat-analyses").textContent = data.total_analyses ?? 0;
    document.getElementById("stat-claims").textContent = data.total_claims ?? 0;
    renderHistoryList(data.recent || [], "dash-recent");
  } catch (e) {
    console.error(e);
  }
}

async function loadHistory() {
  try {
    const res = await fetch(API + "/api/history");
    const data = await res.json();
    renderHistoryList(data.history || [], "history-list");
  } catch (e) {
    console.error(e);
  }
}

function renderHistoryList(items, containerId) {
  const el = document.getElementById(containerId);
  if (!items.length) {
    el.innerHTML = `<p style="color:var(--muted)">No analyses yet. Try verifying a claim!</p>`;
    return;
  }
  el.innerHTML = items.map(h => `
    <div class="history-item" onclick="openAnalysis('${h.analysis_id}')">
      <div class="history-preview">${escapeHtml(h.claim_preview || "—")}</div>
      <span class="verdict verdict-${h.verdict}">${formatVerdict(h.verdict)}</span>
      <div class="history-meta">${h.input_type} · ${new Date(h.created_at).toLocaleDateString()}</div>
    </div>
  `).join("");
}

async function openAnalysis(id) {
  try {
    const res = await fetch(API + "/api/analysis/" + id);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    showResults(data);
  } catch (e) {
    alert("Could not load analysis: " + e.message);
  }
}

// Init
document.addEventListener("DOMContentLoaded", () => {
  showPage("landing");
});
