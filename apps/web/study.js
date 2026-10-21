const app = document.querySelector("#study-app");
const statusBox = document.querySelector("#status");
const progress = document.querySelector("#study-progress");
let study = null;
let saveTimer = null;
let saving = false;

const escapeHtml = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const body = await response.json();
  if (!response.ok) throw Object.assign(new Error(body.error || `请求失败 (${response.status})`), { status: response.status });
  return body;
}

function setStatus(message, error = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", error);
}

function bilingual(value) {
  return `<span class="question-zh">${escapeHtml(value.zh)}</span><span class="question-en" lang="en">${escapeHtml(value.en)}</span>`;
}

function renderWelcome(config) {
  progress.hidden = true;
  app.innerHTML = `<div class="introduction bilingual-intro">
    <p class="eyebrow">Welcome / 欢迎</p><h2>SeasonLens 形成性研究</h2>
    <p>${escapeHtml(config.participant_notice.zh)}</p><p lang="en">${escapeHtml(config.participant_notice.en)}</p>
    <p class="privacy-note">本系统只收集研究员分配的匿名编号，请勿填写姓名、邮箱或其他身份信息。<br><span lang="en">Enter only the anonymous code assigned by the researcher; do not enter your name, email, or other identifying information.</span></p>
    <form id="start-study-form" class="participant-code-form">
      <label for="participant-id">参与者编号 / Participant ID</label>
      <input id="participant-id" maxlength="80" autocomplete="off" required>
      <label class="metadata-field checkbox-label"><input id="consent-acknowledged" type="checkbox" required> 我已阅读以上研究信息并同意开始。 / I have read the study information above and agree to begin.</label>
      <button type="submit">开始 / Begin</button>
    </form>
    <p><a href="/prototype.html">Standalone SeasonLens prototype / 独立原型</a></p>
  </div>`;
  document.querySelector("#start-study-form").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      setStatus("正在创建研究记录… / Creating study record…");
      study = await api("/api/studies", { method: "POST", body: JSON.stringify({ participant_id: document.querySelector("#participant-id").value.trim(), consent_acknowledged: document.querySelector("#consent-acknowledged").checked }) });
      render();
    } catch (error) { setStatus(error.message, true); }
  });
}

function updateProgress() {
  progress.hidden = false;
  const completed = new Set(study.progress.completed);
  const current = study.stage.startsWith("WAIT_") ? study.stage.replace("WAIT_", "") : study.stage;
  progress.querySelectorAll("span").forEach(element => {
    const stage = element.dataset.stage;
    element.classList.toggle("done", completed.has(stage));
    element.classList.toggle("current", stage === current || (study.stage === "COMPLETE" && stage === "E"));
  });
}

function materialPanel(material, section) {
  if (!material) return "";
  const images = material.images.map((image, index) => `<figure>
    <img src="${escapeHtml(image.image_path)}" alt="${section === "C" ? (index === 0 ? "较早时间点材料 / Earlier material" : "当前时间点材料 / Current material") : "研究植物材料 / Study plant material"}">
    <figcaption>${section === "C" ? (index === 0 ? "较早 / Earlier" : "当前 / Current") : "观察材料 / Observation material"} · ${escapeHtml(image.material_id)}</figcaption>
  </figure>`).join("");
  return `<aside class="material-panel ${section === "C" ? "comparison-materials" : ""}">${images}</aside>`;
}

function metadataFields(section, material, draft) {
  const hidden = (id, value) => `<input type="hidden" name="${id}" value="${escapeHtml(draft[id] ?? value ?? "")}">`;
  if (section === "A") return `<label class="metadata-field">研究员填写日期（选填） / Researcher-entered date (optional)<input name="STUDY_DATE_MANUAL" value="${escapeHtml(draft.STUDY_DATE_MANUAL || "")}"></label>`;
  if (section === "B") return hidden("B_STATION_ID", material.station_id) + `<label class="metadata-field">研究员填写开始时间（选填） / Manual start time (optional)<input name="B_START_TIME_MANUAL" value="${escapeHtml(draft.B_START_TIME_MANUAL || "")}"></label>`;
  if (section === "C") return hidden("C_EARLIER_MATERIAL_ID", material.earlier_material_id) + hidden("C_CURRENT_MATERIAL_ID", material.current_material_id) + hidden("C_PRESENTATION_ORDER", material.presentation_order);
  if (section === "D") return hidden("D_MATERIAL_ID", material.material_id) + `<label class="metadata-field">研究员填写开始时间（选填） / Manual start time (optional)<input name="D_START_TIME_MANUAL" value="${escapeHtml(draft.D_START_TIME_MANUAL || "")}"></label><label class="metadata-field checkbox-label"><input type="checkbox" name="D_FIELD_BASED" ${draft.D_FIELD_BASED ?? material.field_based ? "checked" : ""}> 现场 / Field-based</label>`;
  return "";
}

function questionField(field, draft) {
  const value = draft[field.id] ?? "";
  if (field.type === "text") return `<label class="question-field" for="${field.id}"><span class="question-id">${field.id}</span>${bilingual(field)}<textarea id="${field.id}" name="${field.id}" rows="3">${escapeHtml(value)}</textarea></label>`;
  if (field.type === "confidence") return `<label class="question-field" for="${field.id}"><span class="question-id">${field.id}</span>${bilingual(field)}<select id="${field.id}" name="${field.id}"><option value="">跳过 / Skip</option>${[1,2,3,4,5].map(number => `<option value="${number}" ${Number(value) === number ? "selected" : ""}>${number}${number === 1 ? " — 完全没把握 / Not at all confident" : number === 3 ? " — 一般 / Moderately confident" : number === 5 ? " — 很有把握 / Very confident" : ""}</option>`).join("")}</select></label>`;
  return `<label class="question-field" for="${field.id}"><span class="question-id">${field.id}</span>${bilingual(field)}<select id="${field.id}" name="${field.id}"><option value="">跳过 / Skip</option>${field.options.map(option => `<option value="${escapeHtml(option.value)}" ${value === option.value ? "selected" : ""}>${escapeHtml(option.zh)} / ${escapeHtml(option.en)}</option>`).join("")}</select></label>`;
}

function renderSection() {
  const sectionId = study.stage;
  const section = study.section;
  app.innerHTML = `<div class="section-heading"><p class="eyebrow">Section ${sectionId}</p><h2>${escapeHtml(section.title.zh)}</h2><p lang="en">${escapeHtml(section.title.en)}</p>
    ${section.instructions ? `<div class="instruction-panel">${bilingual(section.instructions)}</div>` : ""}</div>
    <div class="questionnaire-layout">${materialPanel(study.material, sectionId)}
      <form id="section-form" class="questionnaire-form" novalidate>
        ${metadataFields(sectionId, study.material, study.draft)}
        ${section.fields.map(field => questionField(field, study.draft)).join("")}
        ${section.closing ? `<div class="instruction-panel closing">${bilingual(section.closing)}</div>` : ""}
        <div class="form-actions"><button type="button" id="save-draft" class="quiet-button">保存草稿 / Save draft</button><button type="submit">提交本部分 / Submit section</button></div>
        <p class="commit-note">所有问题均可跳过。提交后由研究员释放下一观察阶段。 / Every question may be skipped. The researcher releases the next observation stage.</p>
      </form></div>`;
  const form = document.querySelector("#section-form");
  form.addEventListener("input", scheduleDraft);
  form.addEventListener("change", scheduleDraft);
  document.querySelector("#save-draft").addEventListener("click", () => saveDraft(true));
  form.addEventListener("submit", submitSection);
}

function valuesFromForm() {
  const form = document.querySelector("#section-form");
  const values = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    if (element.type === "checkbox") values[element.name] = element.checked;
    else if (element.tagName === "SELECT" && element.name.endsWith("CONFIDENCE") || element.name === "C5") values[element.name] = element.value ? Number(element.value) : null;
    else values[element.name] = element.value || null;
  }
  return values;
}

function scheduleDraft() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => saveDraft(false), 900);
}

async function saveDraft(announce) {
  if (saving || !document.querySelector("#section-form")) return;
  saving = true;
  clearTimeout(saveTimer);
  try {
    study = await api(`/api/studies/${study.study_id}/draft`, { method: "POST", body: JSON.stringify({ version: study.version, values: valuesFromForm() }) });
    if (announce) setStatus("草稿已保存 / Draft saved");
  } catch (error) { setStatus(error.message, true); }
  finally { saving = false; }
}

async function submitSection(event) {
  event.preventDefault();
  clearTimeout(saveTimer);
  while (saving) await new Promise(resolve => setTimeout(resolve, 50));
  try {
    setStatus("正在提交… / Submitting…");
    study = await api(`/api/studies/${study.study_id}/submit`, { method: "POST", body: JSON.stringify({ version: study.version, values: valuesFromForm() }) });
    render();
  } catch (error) { setStatus(error.message, true); }
}

function renderWaiting() {
  const target = study.stage.replace("WAIT_", "");
  const label = target === "PROTOTYPE" ? "SeasonLens 原型 / SeasonLens prototype" : `Section ${target}`;
  app.innerHTML = `<div class="success"><p class="eyebrow">回答已安全保存 / Responses saved</p><h2>等待研究员释放下一阶段</h2><p lang="en">Waiting for the researcher to release the next stage.</p><p>${label}</p><button id="check-release" type="button">检查状态 / Check status</button></div>`;
  document.querySelector("#check-release").addEventListener("click", resume);
  setTimeout(resume, 10000);
}

function renderPrototype() {
  app.innerHTML = `<div class="success"><p class="eyebrow">SeasonLens Prototype</p><h2>原型观察任务已释放</h2><p>接下来将按固定顺序完成三个 SeasonLens 观察任务。</p><p lang="en">Next, complete the three SeasonLens observation tasks in their fixed order.</p><a class="button-link" href="${escapeHtml(study.prototype_url)}">进入 SeasonLens / Open SeasonLens</a></div>`;
}

function renderComplete() {
  app.innerHTML = `<div class="success"><p class="eyebrow">Complete / 完成</p><h2>感谢您的参与！</h2><p lang="en">Thank you for your participation!</p><p>完整研究记录已安全保存。 / The complete study record has been saved.</p></div>`;
}

function render() {
  setStatus("");
  updateProgress();
  if (["A", "B", "C", "D", "E"].includes(study.stage)) renderSection();
  else if (study.stage.startsWith("WAIT_")) renderWaiting();
  else if (study.stage === "PROTOTYPE") renderPrototype();
  else renderComplete();
}

async function resume() {
  try {
    study = await api("/api/studies/current");
    render();
  } catch (error) {
    if (error.status === 401) {
      const config = await api("/api/study-config");
      renderWelcome(config);
    } else setStatus(error.message, true);
  }
}

resume();
