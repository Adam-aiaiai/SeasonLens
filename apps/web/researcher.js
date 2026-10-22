const app = document.querySelector("#researcher-app");
const statusBox = document.querySelector("#researcher-status");
let csrf = "";
let currentStudy = null;
let listedStudies = [];
let deleting = false;

const escapeHtml = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}), ...(options.headers || {}) } });
  const body = await response.json();
  if (!response.ok) throw Object.assign(new Error(body.error || `Request failed (${response.status})`), { status: response.status });
  return body;
}

function status(message, error = false) { statusBox.textContent = message; statusBox.classList.toggle("error", error); }

function normalizeStudyDetail(value) {
  if (!value || typeof value !== "object" || typeof value.study_id !== "string") {
    throw new Error("The server returned an invalid study record.");
  }
  const config = value.config && typeof value.config === "object" ? value.config : null;
  const questionnaireVersion = value.questionnaire_version ?? config?.questionnaire_version ?? 3;
  const materialSetVersion = value.material_set_version ?? config?.material_set_version ?? 3;
  const studyMode = value.study_mode ?? config?.study_mode ?? "researcher_assisted";
  if (!Array.isArray(value.responses) || !Array.isArray(value.materials)
      || !Array.isArray(value.prototype_sessions) || !Array.isArray(value.events)) {
    throw new Error("The study record is incomplete. Restart the local server and try again.");
  }
  return {
    ...value,
    questionnaire_version: questionnaireVersion,
    material_set_version: materialSetVersion,
    study_mode: studyMode,
    config: {
      ...(config || {}),
      questionnaire_version: questionnaireVersion,
      material_set_version: materialSetVersion,
      study_mode: studyMode,
    },
  };
}

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
  try {
    const studies = await api("/api/researcher/studies");
    if (!Array.isArray(studies)) throw new Error("The server returned an invalid study list.");
    listedStudies = studies;
    app.innerHTML = `<div class="dashboard-heading"><div><p class="eyebrow">Study operations</p><h2>Participants and progress</h2><p id="study-count">${studies.length} study record${studies.length === 1 ? "" : "s"} / ${studies.length} 条研究记录</p></div><div><button id="refresh" class="quiet-button">Refresh</button> <button id="logout" class="quiet-button">Sign out</button></div></div>
      <div class="table-scroll"><table class="study-table"><thead><tr><th>Participant</th><th>Study</th><th>Stage</th><th>Prototype items</th><th>Updated (UTC)</th><th>Actions</th></tr></thead><tbody>${studies.map(row => `<tr><td>${escapeHtml(row.participant_id)}</td><td><code>${escapeHtml(row.study_id)}</code></td><td>${escapeHtml(row.stage)}</td><td>${escapeHtml(row.prototype_session_count)}</td><td>${escapeHtml(row.updated_at)}</td><td><div class="study-actions"><button class="open-study" data-id="${escapeHtml(row.study_id)}">Open</button><button class="delete-study danger-button" data-id="${escapeHtml(row.study_id)}">删除记录 / Delete Record</button></div></td></tr>`).join("") || '<tr><td colspan="6">No studies yet.</td></tr>'}</tbody></table></div>
      <dialog id="deletion-dialog" class="deletion-dialog" aria-labelledby="deletion-title">
        <form id="deletion-form" method="dialog"><p class="eyebrow">Permanent deletion / 永久删除</p><h2 id="deletion-title">删除研究记录 / Delete study record</h2><dl><dt>Participant ID</dt><dd id="delete-participant"></dd><dt>Study ID</dt><dd><code id="delete-study-id"></code></dd><dt>Status</dt><dd id="delete-stage"></dd></dl><p class="deletion-warning">确定要永久删除这条研究记录吗？此操作无法撤销。<br><span lang="en">Are you sure you want to permanently delete this study record? This action cannot be undone.</span></p><label for="delete-confirmation">输入 DELETE 或完整 Study ID 以确认 / Type DELETE or the full Study ID to confirm<input id="delete-confirmation" autocomplete="off"></label><div class="dialog-actions"><button id="cancel-delete" class="quiet-button" type="button">取消 / Cancel</button><button id="confirm-delete" class="danger-button" type="submit" disabled>确认永久删除 / Confirm Delete</button></div></form>
      </dialog>`;
    document.querySelector("#refresh").addEventListener("click", listStudies);
    document.querySelector("#logout").addEventListener("click", async () => {
      try { await api("/api/researcher/logout", { method: "POST", body: "{}" }); csrf = ""; login(); }
      catch (error) { status(`Unable to sign out: ${error.message}`, true); }
    });
    document.querySelectorAll(".open-study").forEach(button => button.addEventListener("click", () => openStudy(button.dataset.id)));
    document.querySelectorAll(".delete-study").forEach(button => button.addEventListener("click", () => openDeleteDialog(button.dataset.id)));
    document.querySelector("#cancel-delete").addEventListener("click", closeDeleteDialog);
    document.querySelector("#delete-confirmation").addEventListener("input", updateDeleteConfirmation);
    document.querySelector("#deletion-form").addEventListener("submit", confirmDelete);
  } catch (error) { status(`Unable to load studies: ${error.message}`, true); }
}

function openDeleteDialog(studyId) {
  const record = listedStudies.find(item => item.study_id === studyId);
  if (!record) return;
  const dialog = document.querySelector("#deletion-dialog");
  dialog.dataset.studyId = studyId;
  document.querySelector("#delete-participant").textContent = record.participant_id;
  document.querySelector("#delete-study-id").textContent = record.study_id;
  document.querySelector("#delete-stage").textContent = record.stage;
  document.querySelector("#delete-confirmation").value = "";
  document.querySelector("#confirm-delete").disabled = true;
  if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
  document.querySelector("#delete-confirmation").focus();
}

function closeDeleteDialog() {
  const dialog = document.querySelector("#deletion-dialog");
  if (dialog.close) dialog.close(); else dialog.removeAttribute("open");
}

function updateDeleteConfirmation(event) {
  const dialog = document.querySelector("#deletion-dialog");
  document.querySelector("#confirm-delete").disabled = deleting
    || !["DELETE", dialog.dataset.studyId].includes(event.target.value.trim());
}

async function confirmDelete(event) {
  event.preventDefault();
  if (deleting) return;
  const dialog = document.querySelector("#deletion-dialog");
  const studyId = dialog.dataset.studyId;
  const confirmation = document.querySelector("#delete-confirmation").value.trim();
  if (!["DELETE", studyId].includes(confirmation)) return;
  deleting = true;
  document.querySelector("#confirm-delete").disabled = true;
  try {
    await api(`/api/researcher/studies/${studyId}`, {
      method: "DELETE",
      body: JSON.stringify({ confirmation }),
    });
    if (currentStudy?.study_id === studyId) currentStudy = null;
    closeDeleteDialog();
    status("研究记录已永久删除。 / Study record permanently deleted.");
    await listStudies();
  } catch (error) {
    status(`删除失败，记录未更改。 / Deletion failed; the record was not changed: ${error.message}`, true);
    document.querySelector("#confirm-delete").disabled = false;
  } finally {
    deleting = false;
  }
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
  try {
    currentStudy = normalizeStudyDetail(await api(`/api/researcher/studies/${id}`));
    const canRelease = currentStudy.stage.startsWith("WAIT_");
    app.innerHTML = `<div class="dashboard-heading"><div><p class="eyebrow">${escapeHtml(currentStudy.participant_id)}</p><h2>Study record</h2><p><code>${escapeHtml(currentStudy.study_id)}</code></p></div><button id="back" class="quiet-button">Back</button></div>
      <div class="researcher-grid"><section><h3>Progress</h3><dl class="reveal-grid"><dt>Stage</dt><dd>${escapeHtml(currentStudy.stage)}</dd><dt>Record version</dt><dd>${escapeHtml(currentStudy.version)}</dd><dt>Questionnaire</dt><dd>${escapeHtml(currentStudy.questionnaire_version)}</dd><dt>Materials</dt><dd>${escapeHtml(currentStudy.material_set_version)}</dd><dt>Study mode</dt><dd>${escapeHtml(currentStudy.study_mode)}</dd><dt>Created UTC</dt><dd>${escapeHtml(currentStudy.created_at)}</dd><dt>Updated UTC</dt><dd>${escapeHtml(currentStudy.updated_at)}</dd></dl>${canRelease ? '<button id="release">Release next stage</button>' : ""}</section>
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
    status("");
  } catch (error) { status(`Unable to open study: ${error.message}`, true); }
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
