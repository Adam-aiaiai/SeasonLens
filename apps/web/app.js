const app = document.querySelector("#app");
const statusBox = document.querySelector("#status");
const debugPanel = document.querySelector("#debug-panel");
const debugOutput = document.querySelector("#debug-output");
let projection = null;
let selectedRegion = null;
let lastLog = null;
let commitDraft = null;
let items = [];
let busy = false;
const params = new URLSearchParams(location.search);
const debugMode = params.get("debug") === "1";
const integratedStudyId = params.get("study_id");
let researcherMode = false;
let researcherCsrf = "";
const modeLabels = { training: "Training", unaided_test: "Unaided test", transfer: "Transfer" };
const conditionLabels = {
  "answer-first": "Group A · Answer-first",
  "observation-first-yoked": "Group B · Yoked non-contingent guidance — planned / not fully implemented in current formative prototype",
  "observation-first-contingent": "Group C · Error-contingent adaptive guidance",
};
const diagnosisLabels = {
  REGION_MISS: "Wrong region",
  CUE_MISIDENTIFIED: "Relevant region, missed cue",
  INTERPRETATION_ERROR: "Correct cue, wrong interpretation",
  CORRECT: "Fully correct",
};

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(researcherCsrf ? { "X-CSRF-Token": researcherCsrf } : {}), ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `请求失败（${response.status}）`);
  return body;
}

function showIntroduction() {
  if (busy) return;
  projection = null;
  selectedRegion = null;
  commitDraft = null;
  document.querySelector(".progress").hidden = true;
  const remembered = localStorage.getItem("seasonlens-participant") || "F01";
  app.innerHTML = `<div class="introduction">
    <p class="eyebrow">形成性研究</p>
    <h2>SeasonLens 植物观察研究</h2>
    <p>本研究关注人们如何观察植物的视觉变化。</p>
    <p>你不需要具备植物学知识。我们评估的是系统设计，而不是你的个人能力。</p>
    <p>请描述你实际看到的内容；不确定时也可以如实表达。如果方便，请在完成任务时说出你的想法。</p>
    <p>在观察优先条件下，系统不会在你首次判断前显示正确答案。</p>
    <dl class="instruction-definitions">
      <dt>选择区域</dt><dd>在图片中框选最能支持你判断的证据区域。提交前可以重新绘制矩形。</dd>
      <dt>描述观察</dt><dd>只描述你能从图片中直接看到的特征。</dd>
      <dt>阶段判断</dt><dd>选择一个阶段，说明判断理由及主要依据，再评定信心并提交。</dd>
    </dl>
    <form id="session-start-form" class="participant-code-form">
      <label for="participant-id">匿名参与者编号</label>
      <input id="participant-id" type="text" value="${escapeHtml(remembered)}" placeholder="例如：F01" autocomplete="off" required>
      <p class="commit-note">请只填写研究人员分配的编号，不要填写姓名。</p>
      <button type="submit">开始观察任务</button>
    </form>
  </div>`;
  document.querySelector("#session-start-form").addEventListener("submit", event => {
    event.preventDefault();
    const participantId = document.querySelector("#participant-id").value.trim();
    if (!participantId) {
      setStatus("开始前请输入匿名参与者编号。");
      document.querySelector("#participant-id").focus();
      return;
    }
    startSession(participantId);
  });
  if (researcherMode) loadItemOptions();
}

async function loadItemOptions() {
  const select = document.querySelector("#study-item");
  if (!select) return;
  const previous = select.value;
  try {
    items = await api("/api/items");
    select.innerHTML = items.map(item =>
      `<option value="${escapeHtml(item.item_id)}">${escapeHtml(item.item_id)} · ${escapeHtml(item.plant_name)}</option>`
    ).join("");
    select.value = items.some(item => item.item_id === previous) ? previous : items[0].item_id;
  } catch (error) {
    showError(error);
  }
}

async function startSession(participantId) {
  if (busy) return;
  setStatus("");
  if (!participantId?.trim()) {
    showIntroduction();
    setStatus("开始前请输入匿名参与者编号。");
    return;
  }
  localStorage.setItem("seasonlens-participant", participantId.trim());
  busy = true;
  document.querySelectorAll("button").forEach(button => { button.disabled = true; });
  try {
    if (integratedStudyId) {
      projection = await api(`/api/studies/${integratedStudyId}/prototype-start`, { method: "POST", body: "{}" });
    } else {
      items = await api("/api/items");
      const selectedItem = researcherMode ? document.querySelector("#study-item")?.value : null;
      projection = await api("/api/sessions", {
        method: "POST",
        body: JSON.stringify({
          participant_id: participantId.trim(), item_id: selectedItem || items[0].item_id,
          study_mode: researcherMode ? document.querySelector("#study-mode").value : "training",
          condition: researcherMode ? document.querySelector("#study-condition").value : "observation-first-contingent",
        }),
      });
    }
    selectedRegion = null;
    commitDraft = null;
    lastLog = null;
    document.querySelector(".progress").hidden = false;
    render();
  } catch (error) {
    showError(error);
  } finally {
    busy = false;
    document.querySelectorAll("button").forEach(button => { button.disabled = false; });
    document.querySelector("#apply-hint").disabled = projection?.data.stage !== "HINT" || !projection?.data.hint;
  }
}

function setStatus(message) { statusBox.textContent = message; }
function showError(error) { setStatus(error instanceof Error ? error.message : String(error)); }

function imagePanel({ interactive = false, expertRegion = null } = {}) {
  const item = projection.data.item;
  const point = selectedRegion;
  const marker = point
    ? `<span class="selection-region" style="left:${point.x * 100}%;top:${point.y * 100}%;width:${point.width * 100}%;height:${point.height * 100}%" aria-label="你选择的区域"></span>`
    : "";
  const region = expertRegion
    ? `<span class="expert-region" style="left:${expertRegion.x * 100}%;top:${expertRegion.y * 100}%;width:${expertRegion.width * 100}%;height:${expertRegion.height * 100}%"></span>`
    : "";
  return `
    <div class="visual-panel">
      <div id="image-shell" class="image-shell ${interactive ? "" : "locked"}" data-interactive="${interactive}">
        <img class="plant-image" src="${escapeHtml(item.image_path)}" alt="用于观察的${escapeHtml(item.plant_name)}照片" draggable="false">
        ${marker}${region}
      </div>
       <p class="image-caption">${interactive ? "请选择最能包含支持你判断的视觉证据的区域。提交前可以再次拖动，重新绘制矩形。" : escapeHtml(item.plant_name) + " · 植物观察照片"}</p>
    </div>`;
}

function stageLabel(stageId) {
  const option = (projection?.data.item.stage_options || []).find(entry => entry.id === stageId);
  return option?.label || stageId || "";
}

function stageChoiceField(selectedStageId, legacyInterpretation) {
  const item = projection.data.item;
  if (!item.stage_options?.length) {
    return `<div class="field"><label for="interpretation">${escapeHtml(item.prompts.interpretation)}</label>
      <textarea id="interpretation" required>${escapeHtml(legacyInterpretation)}</textarea></div>`;
  }
  return `<fieldset class="stage-field"><legend>${escapeHtml(item.prompts.interpretation)}</legend>
    <div class="stage-options">${item.stage_options.map((option, index) =>
      `<label class="stage-option"><input type="radio" name="stage" value="${escapeHtml(option.id)}" ${option.id === selectedStageId ? "checked" : ""} ${index === 0 ? "required" : ""}><span>${escapeHtml(option.label)}</span></label>`
    ).join("")}</div></fieldset>`;
}

function observationForm(isRevision) {
  const initial = projection.data.initial_attempt;
  const latest = projection.data.revised_attempt || initial;
  const observation = isRevision ? latest.observation_text : (commitDraft?.observation_text || "");
  const interpretation = isRevision ? latest.interpretation_text : (commitDraft?.interpretation_text || "");
  const selectedStageId = isRevision ? latest.selected_stage_id : (commitDraft?.selected_stage_id || null);
  const visualEvidenceReason = isRevision ? "" : (commitDraft?.visual_evidence_reason || "");
  const judgementSource = isRevision ? null : (commitDraft?.judgement_source || null);
  const confidence = commitDraft?.confidence || initial?.confidence || 3;
  const unaided = projection.data.study_mode !== "training";
  const answerFirst = !isRevision && projection.data.condition === "answer-first" && projection.data.expert_reveal;
  return `
    <form id="observation-form" class="form-panel">
      <p class="eyebrow">${isRevision ? (unaided ? "最终独立作答" : "再次观察") : "观察"}</p>
      <h2>${isRevision ? "提交你的最终观察" : "你看到了什么？"}</h2>
      <p>${isRevision ? (unaided ? "请在没有提示或专家答案的情况下独立完成最终作答。" : "请结合提示再次查看图片，并另行提交修改后的回答。") : "请框选一个区域，描述所见并作出自己的判断。"}</p>
      ${answerFirst ? `<div class="answer-first-panel"><strong>答案优先：专家参考</strong><p>相关区域：${escapeHtml(projection.data.expert_reveal.relevant_region)}<br>诊断特征：${escapeHtml(projection.data.expert_reveal.diagnostic_cue)}<br>解释：${escapeHtml(projection.data.expert_reveal.interpretation)}</p></div>` : ""}
      <div class="field">
        <label for="observation">${escapeHtml(projection.data.item.prompts.observation)}</label>
        <textarea id="observation" required>${escapeHtml(observation)}</textarea>
        <p class="field-help">这里只描述图片中可见的特征，不要在这里填写植物阶段。</p>
      </div>
      ${stageChoiceField(selectedStageId, interpretation)}
      ${isRevision ? "" : `<div class="field">
        <label for="visual-evidence-reason">为什么你认为植物处于刚才选择的阶段？</label>
        <textarea id="visual-evidence-reason" required>${escapeHtml(visualEvidenceReason)}</textarea>
        <p class="field-help">请结合图片中的具体特征说明原因。如果不确定，也可以如实描述。</p>
      </div>
      <fieldset class="source-field"><legend>你的判断主要依据是什么？</legend>
        <div class="stage-options">${[
          ["image_evidence", "图片中直接看到的特征"],
          ["prior_experience", "以前观察植物的经验"],
          ["learned_knowledge", "课堂或书本中学过的知识"],
          ["guessing", "主要依靠猜测"],
          ["other", "其他"],
        ].map(([value, label], index) => `<label class="stage-option"><input type="radio" name="judgement-source" value="${value}" ${value === judgementSource ? "checked" : ""} ${index === 0 ? "required" : ""}><span>${label}</span></label>`).join("")}</div>
      </fieldset>`}
      ${isRevision ? "" : confidenceField(confidence)}
      <button type="submit">${isRevision ? "提交修改后的观察" : "检查后提交"}</button>
      ${isRevision ? '<p class="commit-note">你的首次回答会在研究日志中保持不变。</p>' : ""}
    </form>`;
}

function confidenceField(selected) {
  return `<fieldset><legend>信心程度 · 1（最低）–5（最高）</legend><div class="confidence">${[1, 2, 3, 4, 5].map((value) =>
    `<label><input type="radio" name="confidence" value="${value}" ${value === selected ? "checked" : ""}><span>${value}</span></label>`
  ).join("")}</div></fieldset>`;
}

function attemptSummary(attempt, title, showRegion = false) {
  return `<div class="attempt-summary"><h3>${title}</h3><dl>
    ${showRegion ? `<dt>选择区域</dt><dd>${escapeHtml(JSON.stringify(attempt.selected_region))}</dd>` : ""}
    <dt>观察描述</dt><dd>${escapeHtml(attempt.observation_text)}</dd>
    <dt>阶段判断</dt><dd>${escapeHtml(stageLabel(attempt.selected_stage_id) || attempt.interpretation_text)}</dd>
    ${attempt.visual_evidence_reason ? `<dt>判断理由</dt><dd>${escapeHtml(attempt.visual_evidence_reason)}</dd>` : ""}
    ${attempt.judgement_source ? `<dt>判断依据</dt><dd>${escapeHtml({image_evidence: "图片中直接看到的特征", prior_experience: "以前观察植物的经验", learned_knowledge: "课堂或书本中学过的知识", guessing: "主要依靠猜测", other: "其他"}[attempt.judgement_source] || attempt.judgement_source)}</dd>` : ""}
    ${attempt.confidence ? `<dt>信心程度</dt><dd>${escapeHtml(attempt.confidence)} / 5</dd>` : ""}
  </dl></div>`;
}

function render() {
  if (!projection) return;
  setStatus("");
  const stage = projection.data.stage;
  updateProgress(stage);
  if (stage === "OBSERVE") {
    selectedRegion = commitDraft?.selected_region || null;
    app.innerHTML = `<div class="study-layout">${imagePanel({ interactive: true })}${observationForm(false)}</div>`;
    bindImageSelection();
    bindObservationForm(false);
  } else if (stage === "POSITIVE_FEEDBACK") {
    selectedRegion = projection.data.initial_attempt.selected_region;
    app.innerHTML = `<div class="study-layout">${imagePanel()}
      <div class="form-panel"><p class="eyebrow">积极反馈</p><h2>回答已确认</h2>
        <div id="shown-feedback" class="positive-feedback"><p>${escapeHtml(projection.data.positive_feedback.text)}</p></div>
        ${attemptSummary(projection.data.initial_attempt, "首次观察 · 已提交")}
        <button id="reveal" type="button">查看专家线索</button>
      </div></div>`;
    document.querySelector("#reveal").addEventListener("click", () => mutate("reveal"));
  } else if (stage === "HINT") {
    selectedRegion = (projection.data.revised_attempt || projection.data.initial_attempt).selected_region;
    app.innerHTML = `<div class="study-layout">${imagePanel()}
      <div class="form-panel"><p class="eyebrow">预先编写的提示</p><h2>请再看一次</h2>
        <div id="shown-hint" class="hint-panel"><p class="hint-level">第 ${escapeHtml(projection.data.hint.hint_level)} 级提示</p><p>${escapeHtml(projection.data.hint.hint_text)}</p></div>
        ${attemptSummary(projection.data.revised_attempt || projection.data.initial_attempt, projection.data.revised_attempt ? "最近一次修改后的观察" : "首次观察 · 已提交")}
        <button id="reobserve" type="button">再次观察</button>
      </div></div>`;
    document.querySelector("#reobserve").addEventListener("click", () => mutate("reobserve"));
  } else if (stage === "REOBSERVE") {
    selectedRegion = (projection.data.revised_attempt || projection.data.initial_attempt).selected_region;
    app.innerHTML = `<div class="study-layout">${imagePanel({ interactive: true })}${observationForm(true)}</div>`;
    bindImageSelection();
    bindObservationForm(true);
  } else if (stage === "REVISED_COMMITTED") {
    selectedRegion = projection.data.revised_attempt.selected_region;
    const training = projection.data.study_mode === "training";
    const action = training ? "reveal" : "complete-unaided";
    app.innerHTML = `<div class="study-layout">${imagePanel()}
      <div class="form-panel"><p class="eyebrow">最终回答已提交</p><h2>${training ? "与专家线索比较" : "完成本题独立作答"}</h2>
        ${attemptSummary(projection.data.revised_attempt, "修改后的观察")}
        <button id="${action}" type="button">${training ? "查看专家线索" : "完成最终提交"}</button>
      </div></div>`;
    document.querySelector(`#${action}`).addEventListener("click", () => mutate(action));
  } else if (stage === "REVEAL") {
    renderReveal(false);
  } else if (stage === "REFLECTION") {
    renderReveal(true);
  } else if (stage === "COMPLETE") {
    app.innerHTML = `<div class="success"><p class="eyebrow">研究日志已保存</p><h2>观察任务已完成</h2>
      <p>谢谢参与。你的回答和${projection.data.study_mode === "training" ? "训练过程中的交互" : "独立作答完成情况"}已分别记录。</p>
      ${integratedStudyId ? '<button id="continue-study" type="button">继续 Section E / Continue to Section E</button>' : '<button id="another" type="button">开始新的会话</button>'}</div>`;
    document.querySelector("#another")?.addEventListener("click", showIntroduction);
    document.querySelector("#continue-study")?.addEventListener("click", () => { location.href = "/"; });
    if (projection.data.has_next_item) {
      const next = document.createElement("button");
      next.textContent = "下一题";
      next.id = "next-item";
      next.addEventListener("click", () => mutate("next-item"));
      document.querySelector(".success").append(next);
    }
  }
  if (!debugPanel.hidden) refreshLog();
}

function renderReveal(showReflection) {
  const expert = projection.data.expert_reveal;
  selectedRegion = (projection.data.revised_attempt || projection.data.initial_attempt).selected_region;
  const receivedHint = projection.data.hint_received;
  const hintLearningQuestion = receivedHint ? `
        <label for="hint-learning-reflection">提示是否帮助你注意到或理解了之前没有发现的植物特征？如果有，你学到了什么？</label>
        <textarea id="hint-learning-reflection" required></textarea>` : `
        <label for="reflection">刚才观察植物时，有没有什么地方让你觉得不确定？如果有，是什么？</label>
        <textarea id="reflection" required></textarea>`;
  app.innerHTML = `<div class="study-layout">${imagePanel({ expertRegion: expert.target_region })}
    <div class="form-panel"><p class="eyebrow">限定范围的专家揭示</p><h2>专家线索</h2>
      <dl class="reveal-grid">
        <dt>相关区域</dt><dd>${escapeHtml(expert.relevant_region)}</dd>
        <dt>诊断特征</dt><dd>${escapeHtml(expert.diagnostic_cue)}</dd>
        <dt>解释</dt><dd>${escapeHtml(expert.interpretation)}</dd>
      </dl>
      ${showReflection ? `<form id="reflection-form" class="attempt-summary">
        ${hintLearningQuestion}
        <label for="reflection-category">你的判断主要在哪方面发生了变化？（选填）</label>
        <select id="reflection-category"><option value="">请选择</option>${[["Where I looked", "我查看的位置"], ["What feature I noticed", "我注意到的特征"], ["What the feature meant", "我对特征含义的理解"], ["My confidence", "我的信心程度"], ["Other", "其他"]].map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select>
        <button type="submit">保存反思</button>
      </form>` : `<button id="begin-reflection" type="button">${receivedHint ? "反思你从提示中学到的内容" : "继续完成反思"}</button>`}
    </div></div>`;
  if (showReflection) {
    document.querySelector("#reflection-form").addEventListener("submit", submitReflection);
  } else {
    document.querySelector("#begin-reflection").addEventListener("click", () => mutate("reflection-stage"));
  }
}

function bindImageSelection() {
  const shell = document.querySelector("#image-shell");
  const image = shell.querySelector("img");
  let start = null;
  let previous = null;
  const position = event => {
    const bounds = image.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
      y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
    };
  };
  const draw = () => {
    shell.querySelector(".selection-region")?.remove();
    if (!selectedRegion) return;
    const marker = document.createElement("span");
    marker.className = "selection-region";
    marker.setAttribute("aria-label", "你选择的区域");
    for (const [key, value] of Object.entries(selectedRegion)) {
      marker.style[{x: "left", y: "top", width: "width", height: "height"}[key]] = `${value * 100}%`;
    }
    shell.append(marker);
  };
  const update = event => {
    const end = position(event);
    selectedRegion = {
      x: Math.min(start.x, end.x), y: Math.min(start.y, end.y),
      width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y),
    };
    draw();
  };
  shell.addEventListener("pointerdown", event => {
    if (!event.isPrimary || event.button !== 0 || busy) return;
    event.preventDefault();
    previous = selectedRegion;
    start = position(event);
    shell.setPointerCapture(event.pointerId);
    update(event);
  });
  shell.addEventListener("pointermove", event => { if (start) update(event); });
  shell.addEventListener("pointerup", event => {
    if (!start) return;
    update(event);
    if (selectedRegion.width < 0.005 || selectedRegion.height < 0.005) {
      selectedRegion = previous;
      draw();
      setStatus("请拖动绘制一个具有可见宽度和高度的矩形。");
    } else {
      setStatus("区域已选择。提交前可以再次拖动以重新绘制。");
    }
    start = null;
    shell.releasePointerCapture(event.pointerId);
  });
  shell.addEventListener("pointercancel", () => { start = null; selectedRegion = previous; draw(); });
}

function renderCommit(payload) {
  commitDraft = structuredClone(payload);
  updateProgress("COMMIT");
  app.innerHTML = `<div class="study-layout">${imagePanel()}
    <div class="form-panel"><p class="eyebrow">提交</p><h2>检查你的观察</h2>
      ${attemptSummary(payload, "你的首次回答")}
      <p>${projection.data.study_mode === "training" ? "提交后将获得反馈或提示。" : "提交后将继续完成最终独立作答。"}</p>
      <button id="commit-initial" type="button">确认提交观察</button>
      <button id="edit-initial" class="quiet-button" type="button">修改回答 / 重画区域</button>
    </div></div>`;
  document.querySelector("#commit-initial").addEventListener("click", () => mutate("initial-observation", commitDraft));
  document.querySelector("#edit-initial").addEventListener("click", render);
}

function bindObservationForm(isRevision) {
  document.querySelector("#observation-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedRegion || selectedRegion.width <= 0 || selectedRegion.height <= 0) {
      setStatus("提交前请在图片上拖动选择一个矩形区域。");
      return;
    }
    const selectedStage = document.querySelector('input[name="stage"]:checked');
    const judgementSource = isRevision ? null : document.querySelector('input[name="judgement-source"]:checked');
    const legacyInterpretation = document.querySelector("#interpretation");
    const payload = {
      selected_region: selectedRegion,
      observation_text: document.querySelector("#observation").value.trim(),
      selected_stage_id: selectedStage?.value || null,
      interpretation_text: selectedStage ? stageLabel(selectedStage.value) : (legacyInterpretation?.value.trim() || ""),
    };
    if (!isRevision) {
      payload.visual_evidence_reason = document.querySelector("#visual-evidence-reason").value.trim();
      payload.judgement_source = judgementSource?.value || null;
      payload.confidence = Number(new FormData(event.currentTarget).get("confidence"));
    }
    if (!payload.observation_text) {
      setStatus("请描述所选区域中可见的特征。");
      return;
    }
    if (!payload.selected_stage_id && !payload.interpretation_text) {
      setStatus("请选择植物所处的阶段。");
      return;
    }
    if (!isRevision && !payload.visual_evidence_reason) {
      setStatus("请说明你作出阶段判断的理由，也可以如实表达不确定。");
      document.querySelector("#visual-evidence-reason").focus();
      return;
    }
    if (!isRevision && !payload.judgement_source) {
      setStatus("请选择你的判断主要依据。");
      return;
    }
    if (isRevision) await mutate("revision", payload);
    else renderCommit(payload);
  });
}

async function submitReflection(event) {
  event.preventDefault();
  let hintLearningReflection = null;
  let reflectionText = null;
  if (projection.data.hint_received) {
    hintLearningReflection = document.querySelector("#hint-learning-reflection").value.trim();
    if (!hintLearningReflection) {
      setStatus("请描述你从提示中学到的内容。");
      return;
    }
  } else {
    reflectionText = document.querySelector("#reflection").value.trim();
    if (!reflectionText) {
      setStatus("请描述观察植物时让你觉得不确定的地方；如果没有，请说明没有。");
      return;
    }
  }
  await mutate("reflection", {
    reflection_text: reflectionText,
    hint_learning_reflection: hintLearningReflection,
    reflection_category: document.querySelector("#reflection-category").value || null,
  });
}

async function mutate(action, payload = {}) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach(button => { button.disabled = true; });
  setStatus("正在保存……");
  try {
    projection = await api(`/api/sessions/${projection.data.session_id}/${action}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (action === "researcher-notes") {
      const notes = document.querySelector("#researcher-notes");
      if (notes.value === payload.researcher_notes) notes.dataset.dirty = "0";
      await refreshLog();
      setStatus("Researcher notes saved.");
    } else {
      commitDraft = null;
      lastLog = null;
      render();
    }
  } catch (error) {
    showError(error);
  } finally {
    busy = false;
    document.querySelectorAll("button").forEach(button => { button.disabled = false; });
    document.querySelector("#apply-hint").disabled = projection.data.stage !== "HINT" || !projection.data.hint;
  }
}

function updateProgress(stage) {
  const unaided = projection?.data.study_mode !== "training";
  document.querySelector('[data-step="hint"]').textContent = unaided ? "3. 无提示" : "3. 提示";
  document.querySelector('[data-step="reveal"]').textContent = unaided ? "5. 完成" : "5. 揭示";
  const map = {
    OBSERVE: "observe", COMMIT: "commit", INITIAL_COMMITTED: "commit", HINT: "hint",
    POSITIVE_FEEDBACK: "reveal",
    REOBSERVE: "reobserve", REVISED_COMMITTED: "reobserve", REVEAL: "reveal",
    REFLECTION: "reflect", COMPLETE: "reflect",
  };
  const order = ["observe", "commit", "hint", "reobserve", "reveal", "reflect"];
  const index = order.indexOf(map[stage]);
  document.querySelectorAll(".progress span").forEach((element, elementIndex) => {
    const skipped = projection?.data.study_mode === "training" && !projection?.data.hint_received &&
      ["hint", "reobserve"].includes(order[elementIndex]);
    element.classList.toggle("active", elementIndex === index);
    element.classList.toggle("done", elementIndex < index && !skipped);
    element.classList.toggle("skipped", skipped && elementIndex <= index);
    if (elementIndex === index) element.setAttribute("aria-current", "step");
    else element.removeAttribute("aria-current");
  });
}

function regionOverlay(rect, className, label) {
  if (!rect) return "";
  return `<span class="${className}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}"
    style="left:${rect.x * 100}%;top:${rect.y * 100}%;width:${rect.width * 100}%;height:${rect.height * 100}%"></span>`;
}

function researcherRegionPanels(regions, log, item) {
  if (!debugMode || !regions?.target_region) return "";
  const target = regions.target_region;
  const distractors = regions.distractor_regions || [];
  const panels = ["initial", "revised"].map(prefix => {
    const diagnostic = (prefix === "initial" ? log.initial_diagnostic || log.diagnostic : log.revised_diagnostic) || {};
    return `<div class="attempt-summary"><h3>${prefix === "initial" ? "Initial" : "Revised"} region diagnosis</h3>
      <div class="researcher-image-shell image-shell locked">
        <img class="plant-image" src="${escapeHtml(item.image_path)}" alt="Researcher region overlay for ${escapeHtml(item.plant_name)}" draggable="false">
        ${regionOverlay(target.rect, "expert-region", `Expert target: ${target.label}`)}
        ${distractors.map(region => regionOverlay(region.rect, "distractor-region", `Authored distractor: ${region.label}`)).join("")}
        ${regionOverlay(log[`${prefix}_region`], "selection-region", "Participant selection")}
      </div>
      <dl><dt>Best-matching semantic region</dt><dd>${escapeHtml(diagnostic.selected_semantic_region)} / ${escapeHtml(diagnostic.selected_region_label)}</dd>
        <dt>Target IoU</dt><dd>${escapeHtml(diagnostic.target_iou)}</dd>
        <dt>Best distractor IoU</dt><dd>${escapeHtml(diagnostic.best_distractor_iou)}</dd>
        <dt>Primary error</dt><dd>${escapeHtml(diagnostic.primary_error)}</dd></dl>
    </div>`;
  }).join("");
  return `<p class="commit-note">Researcher overlays: orange = participant, gold = expert target, purple dashed = authored distractors.</p>
    <dl><dt>Target region (authored metadata)</dt><dd>${escapeHtml(target.id)} / ${escapeHtml(target.label)} / ${escapeHtml(JSON.stringify(target.rect))}</dd>
    <dt>Distractors (authored metadata)</dt><dd>${escapeHtml(distractors.map(region => `${region.id}: ${region.label}`).join("; "))}</dd></dl>
    <div class="response-comparison">${panels}</div>`;
}

async function refreshLog() {
  if (!projection || !debugMode) return;
  const sessionId = projection.data.session_id;
  const version = projection.state_version;
  try {
    const result = await api(`/api/sessions/${sessionId}/researcher`);
    if (projection.data.session_id !== sessionId || projection.state_version !== version) return;
    lastLog = result.log;
    debugOutput.textContent = JSON.stringify(lastLog, null, 2);
    const attempt = prefix => ({
      selected_region: lastLog[`${prefix}_region`], observation_text: lastLog[`${prefix}_observation`],
      interpretation_text: lastLog[`${prefix}_interpretation`], selected_stage_id: lastLog[`${prefix}_stage_id`],
      confidence: lastLog[`${prefix}_confidence`],
      visual_evidence_reason: lastLog[`${prefix}_visual_evidence_reason`],
      judgement_source: lastLog[`${prefix}_judgement_source`],
    });
    const automaticHint = result.hints.find(hint => hint.id === lastLog.automatic_hint_id);
    document.querySelector("#researcher-summary").innerHTML = `
      <dl><dt>Session / participant / item</dt><dd>${escapeHtml(lastLog.session_id)} / ${escapeHtml(lastLog.participant_id)} / ${escapeHtml(lastLog.item_id)}</dd>
      <dt>Study mode</dt><dd>${escapeHtml(modeLabels[lastLog.study_mode] || lastLog.study_mode)}</dd>
      <dt>Plant / cue family</dt><dd>${escapeHtml(lastLog.plant_name)} / ${escapeHtml(lastLog.cue_family)}</dd>
      <dt>Condition</dt><dd>${escapeHtml(conditionLabels[lastLog.condition] || lastLog.condition)}</dd>
      <dt>Current stage</dt><dd>${escapeHtml(lastLog.stage)}</dd>
      <dt>Initial diagnostic / correct</dt><dd>${escapeHtml(diagnosisLabels[lastLog.primary_error] || lastLog.primary_error)} / ${escapeHtml(lastLog.initial_correctness)}</dd>
      <dt>Participant path</dt><dd>${escapeHtml(lastLog.participant_path)}</dd>
      <dt>Region correct</dt><dd>${escapeHtml(lastLog.region_correct)}</dd>
      <dt>Cue correct</dt><dd>${escapeHtml(lastLog.cue_correct)}</dd>
      <dt>Initial selected stage</dt><dd>${escapeHtml(stageLabel(lastLog.initial_stage_id))} (${escapeHtml(lastLog.initial_stage_id)})</dd>
      <dt>Initial visual evidence reason</dt><dd>${escapeHtml(lastLog.initial_visual_evidence_reason)}</dd>
      <dt>Initial judgement source</dt><dd>${escapeHtml(lastLog.initial_judgement_source)}</dd>
      <dt>Revised selected stage</dt><dd>${escapeHtml(stageLabel(lastLog.revised_stage_id))} (${escapeHtml(lastLog.revised_stage_id)})</dd>
      <dt>Correct stage</dt><dd>${escapeHtml(lastLog.correct_stage_label)} (${escapeHtml(lastLog.correct_stage_id)})</dd>
      <dt>Initial / revised stage correct</dt><dd>${escapeHtml(lastLog.initial_stage_correct)} / ${escapeHtml(lastLog.revised_stage_correct)}</dd>
      <dt>Final diagnostic</dt><dd>${escapeHtml(diagnosisLabels[lastLog.revised_diagnostic?.primary_error] || lastLog.revised_diagnostic?.primary_error || diagnosisLabels[lastLog.primary_error] || lastLog.primary_error)}</dd>
      <dt>Final correctness</dt><dd>${escapeHtml(lastLog.final_correctness)}</dd>
      <dt>Hint received</dt><dd>${escapeHtml(lastLog.hint_received)}</dd>
      <dt>Guidance error type</dt><dd>${escapeHtml(lastLog.hint_error_type)}</dd>
      <dt>Reason guidance was triggered</dt><dd>${escapeHtml(lastLog.hint_trigger_reason || lastLog.diagnostic_reason)}</dd>
      <dt>Automatic hint selected</dt><dd>${escapeHtml(lastLog.automatic_hint_id)} / ${escapeHtml(automaticHint?.text)}</dd>
      <dt>Region hint source / ID</dt><dd>${escapeHtml(lastLog.region_hint_source)} / ${escapeHtml(lastLog.region_hint_id)}</dd>
      <dt>Hint type / level / provenance</dt><dd>${escapeHtml(lastLog.hint_type)} / ${escapeHtml(lastLog.hint_level)} / ${escapeHtml(lastLog.hint_provenance)}</dd>
      <dt>Actual hint text</dt><dd>${escapeHtml(lastLog.hint_text)}</dd>
      <dt>Positive feedback</dt><dd>${escapeHtml(lastLog.positive_feedback_shown)} / ${escapeHtml(lastLog.positive_feedback_text)}</dd>
      <dt>Manual override</dt><dd>${escapeHtml(lastLog.manual_override)}</dd>
      <dt>Self-corrected after hint</dt><dd>${escapeHtml(lastLog.self_corrected_after_hint)}</dd>
      <dt>Reflection type / text / category</dt><dd>${escapeHtml(lastLog.reflection_type)} / ${escapeHtml(lastLog.reflection_text)} / ${escapeHtml(lastLog.reflection_category)}</dd>
      <dt>Hint-learning reflection</dt><dd>${escapeHtml(lastLog.hint_learning_reflection)}</dd></dl>
      <div class="response-comparison">${attemptSummary(attempt("initial"), "Initial response", true)}${attemptSummary(attempt("revised"), "Revised response after guidance / final unaided response", true)}</div>
      ${researcherRegionPanels(result.regions, lastLog, projection.data.item)}`;
    const select = document.querySelector("#hint-override");
    const previousChoice = select.value;
    select.innerHTML = result.hints.map(hint => `<option value="${escapeHtml(hint.id)}">${escapeHtml(hint.category)}${hint.region_id ? " · " + escapeHtml(hint.region_id) : ""} · Level ${hint.level} · ${escapeHtml(hint.text)}</option>`).join("");
    select.value = result.hints.some(hint => hint.id === previousChoice) ? previousChoice : (lastLog.actual_hint_id || result.hints[0].id);
    select.disabled = lastLog.stage !== "HINT" || !lastLog.actual_hint_id;
    document.querySelector("#apply-hint").disabled = select.disabled;
    const notes = document.querySelector("#researcher-notes");
    if (notes.dataset.session !== sessionId || notes.dataset.dirty !== "1") {
      notes.value = lastLog.researcher_notes;
      notes.dataset.session = sessionId;
      notes.dataset.dirty = "0";
    }
    return lastLog;
  } catch (error) { showError(error); }
}

function download(content, type, extension, sessionId = projection.data.session_id) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `seasonlens-${sessionId}.${extension}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.querySelector("#new-session").addEventListener("click", showIntroduction);
document.querySelector("#refresh-log").addEventListener("click", refreshLog);
document.querySelector("#download-log").addEventListener("click", async () => {
  const currentLog = await refreshLog();
  if (currentLog) download(JSON.stringify(currentLog, null, 2), "application/json", "json", currentLog.session_id);
});
document.querySelector("#download-csv").addEventListener("click", async () => {
  try {
    const sessionId = projection.data.session_id;
    const response = await fetch(`/api/sessions/${sessionId}/log.csv`);
    if (!response.ok) throw new Error("Unable to export CSV.");
    download(await response.text(), "text/csv;charset=utf-8", "csv", sessionId);
  } catch (error) { showError(error); }
});
document.querySelector("#hint-override-form").addEventListener("submit", async event => {
  event.preventDefault();
  await mutate("hint-override", { hint_id: document.querySelector("#hint-override").value });
});
document.querySelector("#researcher-notes").addEventListener("input", event => { event.target.dataset.dirty = "1"; });
document.querySelector("#researcher-notes-form").addEventListener("submit", async event => {
  event.preventDefault();
  await mutate("researcher-notes", { researcher_notes: document.querySelector("#researcher-notes").value });
});
document.querySelector("#reset-item").addEventListener("click", () => mutate("reset"));

async function bootstrap() {
  if (integratedStudyId) {
    document.querySelector("#new-session").hidden = true;
    startSession("integrated-study");
  } else {
    showIntroduction();
  }
  if (debugMode) {
    try {
      const session = await api("/api/researcher/me");
      researcherMode = true;
      researcherCsrf = session.csrf_token;
      debugPanel.hidden = false;
      if (!integratedStudyId) loadItemOptions();
    } catch (_) {
      debugPanel.hidden = true;
    }
  }
}

bootstrap();
