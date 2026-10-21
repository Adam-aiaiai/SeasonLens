const app = document.querySelector("#researcher-app");
const statusBox = document.querySelector("#researcher-status");
let csrf = "";
let currentStudy = null;

const escapeHtml = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}), ...(options.headers || {}) } });
  const body = await response.json();
  if (!response.ok) throw Object.assign(new Error(body.error || `Request failed (${response.status})`), { status: response.status });
  return body;
}

function status(message, error = false) { statusBox.textContent = message; statusBox.classList.toggle("error", error); }

function login() {
  app.innerHTML = `<div class="login-panel"><p class="eyebrow">Secure access</p><h2>Researcher sign in</h2><form id="login-form"><label>Username<input id="username" autocomplete="username" required></label><label>Password<input id="password" type="password" autocomplete="current-password" required></label><button type="submit">Sign in</button></form><p class="commit-note">The legacy debug header and <code>?debug=1</code> do not grant access.</p></div>`;
  document.querySelector("#login-form").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const session = await api("/api/researcher/login", { method: "POST", body: JSON.stringify({ username: document.querySelector("#username").value, password: document.querySelector("#password").value }) });
      csrf = session.csrf_token; await listStudies();
    } catch (error) { status(error.message, true); }
  });
}

async function listStudies() {
  const studies = await api("/api/researcher/studies");
  app.innerHTML = `<div class="dashboard-heading"><div><p class="eyebrow">Study operations</p><h2>Participants and progress</h2></div><div><button id="refresh" class="quiet-button">Refresh</button> <button id="logout" class="quiet-button">Sign out</button></div></div>
    <div class="table-scroll"><table class="study-table"><thead><tr><th>Participant</th><th>Study</th><th>Stage</th><th>Prototype items</th><th>Updated (UTC)</th><th></th></tr></thead><tbody>${studies.map(row => `<tr><td>${escapeHtml(row.participant_id)}</td><td><code>${escapeHtml(row.study_id)}</code></td><td>${escapeHtml(row.stage)}</td><td>${escapeHtml(row.prototype_session_count)}</td><td>${escapeHtml(row.updated_at)}</td><td><button class="open-study" data-id="${escapeHtml(row.study_id)}">Open</button></td></tr>`).join("") || '<tr><td colspan="6">No studies yet.</td></tr>'}</tbody></table></div>`;
  document.querySelector("#refresh").addEventListener("click", listStudies);
  document.querySelector("#logout").addEventListener("click", async () => { await api("/api/researcher/logout", { method: "POST", body: "{}" }); csrf = ""; login(); });
  document.querySelectorAll(".open-study").forEach(button => button.addEventListener("click", () => openStudy(button.dataset.id)));
}

function responsePanels(study) {
  return study.responses.map(record => `<details class="response-panel"><summary>Section ${escapeHtml(record.section_id)} · ${record.submitted_at ? "submitted" : "draft"}</summary><p>Started UTC: ${escapeHtml(record.started_at)}<br>Submitted UTC: ${escapeHtml(record.submitted_at || "—")}</p><pre>${escapeHtml(JSON.stringify(record.response || record.draft, null, 2))}</pre></details>`).join("");
}

function materialPanels(study) {
  const order = ["A", "WAIT_B", "B", "WAIT_C", "C", "WAIT_D", "D", "WAIT_PROTOTYPE", "PROTOTYPE", "E", "COMPLETE"];
  return study.materials.map(record => {
    const editable = order.indexOf(study.stage) < order.indexOf(record.section_id);
    return `<form class="material-config response-panel" data-section="${escapeHtml(record.section_id)}"><h4>Section ${escapeHtml(record.section_id)}</h4><textarea name="config" ${editable ? "" : "disabled"}>${escapeHtml(JSON.stringify(record.config, null, 2))}</textarea>${editable ? '<button type="submit">Save material configuration</button>' : '<p class="commit-note">Locked after release.</p>'}</form>`;
  }).join("");
}

async function openStudy(id) {
  currentStudy = await api(`/api/researcher/studies/${id}`);
  const canRelease = currentStudy.stage.startsWith("WAIT_");
  app.innerHTML = `<div class="dashboard-heading"><div><p class="eyebrow">${escapeHtml(currentStudy.participant_id)}</p><h2>Study record</h2><p><code>${escapeHtml(currentStudy.study_id)}</code></p></div><button id="back" class="quiet-button">Back</button></div>
    <div class="researcher-grid"><section><h3>Progress</h3><dl class="reveal-grid"><dt>Stage</dt><dd>${escapeHtml(currentStudy.stage)}</dd><dt>Record version</dt><dd>${escapeHtml(currentStudy.version)}</dd><dt>Questionnaire</dt><dd>${escapeHtml(currentStudy.config.questionnaire_version)}</dd><dt>Materials</dt><dd>${escapeHtml(currentStudy.config.material_set_version)}</dd><dt>Study mode</dt><dd>${escapeHtml(currentStudy.config.study_mode)}</dd><dt>Created UTC</dt><dd>${escapeHtml(currentStudy.created_at)}</dd><dt>Updated UTC</dt><dd>${escapeHtml(currentStudy.updated_at)}</dd></dl>${canRelease ? '<button id="release">Release next stage</button>' : ""}</section>
    <section><h3>Study exports</h3><div class="export-links">${[["export.json","Combined JSON"],["export.csv","Combined CSV"],["export.xlsx","XLSX"],["export.zip","Complete ZIP"],["questionnaire.json","Questionnaire JSON"],["questionnaire.csv","Questionnaire CSV"]].map(([path,label]) => `<a class="button-link quiet" href="/api/researcher/studies/${escapeHtml(id)}/${path}">${label}</a>`).join("")}</div></section></div>
    <form id="metadata-form" class="attempt-summary"><h3>Researcher metadata</h3><label>Researcher ID<input name="researcher_id" value="${escapeHtml(currentStudy.researcher_metadata.researcher_id || "")}"></label><label>Manual study date<input name="study_date_manual" value="${escapeHtml(currentStudy.researcher_metadata.study_date_manual || "")}"></label><label>Notes<textarea name="notes">${escapeHtml(currentStudy.researcher_metadata.notes || "")}</textarea></label><button type="submit">Save metadata</button></form>
    <h3>Questionnaire responses</h3>${responsePanels(currentStudy)}
    <details class="response-panel"><summary>Material configuration and provenance</summary><p class="commit-note">Only project-controlled asset paths are accepted. Released materials are immutable.</p>${materialPanels(currentStudy)}</details>
    <details class="response-panel"><summary>Prototype sessions</summary><pre>${escapeHtml(JSON.stringify(currentStudy.prototype_sessions, null, 2))}</pre></details>
    <details class="response-panel"><summary>Study event history</summary><pre>${escapeHtml(JSON.stringify(currentStudy.events, null, 2))}</pre></details>`;
  document.querySelector("#back").addEventListener("click", listStudies);
  document.querySelector("#release")?.addEventListener("click", releaseStage);
  document.querySelector("#metadata-form").addEventListener("submit", saveMetadata);
  document.querySelectorAll(".material-config").forEach(form => form.addEventListener("submit", saveMaterial));
}

async function saveMaterial(event) {
  event.preventDefault();
  try {
    const section = event.currentTarget.dataset.section;
    const config = JSON.parse(event.currentTarget.elements.config.value);
    currentStudy = await api(`/api/researcher/studies/${currentStudy.study_id}/materials/${section}`, { method: "POST", body: JSON.stringify({ version: currentStudy.version, config }) });
    status(`Section ${section} material configuration saved.`); await openStudy(currentStudy.study_id);
  } catch (error) { status(error.message, true); }
}

async function releaseStage() {
  try { currentStudy = await api(`/api/researcher/studies/${currentStudy.study_id}/release`, { method: "POST", body: JSON.stringify({ version: currentStudy.version }) }); status("Stage released."); await openStudy(currentStudy.study_id); }
  catch (error) { status(error.message, true); }
}

async function saveMetadata(event) {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try { currentStudy = await api(`/api/researcher/studies/${currentStudy.study_id}/metadata`, { method: "POST", body: JSON.stringify({ version: currentStudy.version, metadata: values }) }); status("Researcher metadata saved."); await openStudy(currentStudy.study_id); }
  catch (error) { status(error.message, true); }
}

async function boot() {
  try { const session = await api("/api/researcher/me"); csrf = session.csrf_token; await listStudies(); }
  catch (error) { if (error.status === 401) login(); else status(error.message, true); }
}

boot();
