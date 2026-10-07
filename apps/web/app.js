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
const debugMode = new URLSearchParams(location.search).get("debug") === "1";
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

if (debugMode) {
  debugPanel.hidden = false;
}

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(debugMode ? { "X-SeasonLens-Researcher": "1" } : {}), ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
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
    <p class="eyebrow">Formative study</p>
    <h2>SeasonLens Observation Study</h2>
    <p>This study is about how people observe visual changes in plants.</p>
    <p>You do not need botanical expertise. We are testing the design of the system, not testing you.</p>
    <p>If possible, please say what you are thinking while completing the task.</p>
    <dl class="instruction-definitions">
      <dt>Region selection</dt><dd>Select the region that best contains the visual evidence supporting your judgement. You can redraw it before submitting.</dd>
      <dt>Observation</dt><dd>Describe only what you can directly see.</dd>
      <dt>Stage judgement</dt><dd>Choose one stage from the options provided.</dd>
    </dl>
    <form id="session-start-form" class="participant-code-form">
      <label for="participant-id">Anonymous participant code</label>
      <input id="participant-id" type="text" value="${escapeHtml(remembered)}" placeholder="For example, F01" autocomplete="off" required>
      <p class="commit-note">Use the researcher-assigned code only; do not enter a name.</p>
      <button type="submit">Start observation task</button>
    </form>
  </div>`;
  document.querySelector("#session-start-form").addEventListener("submit", event => {
    event.preventDefault();
    const participantId = document.querySelector("#participant-id").value.trim();
    if (!participantId) {
      setStatus("Enter an anonymous participant code before starting.");
      document.querySelector("#participant-id").focus();
      return;
    }
    startSession(participantId);
  });
  if (debugMode) loadItemOptions();
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
    setStatus("Enter an anonymous participant code before starting.");
    return;
  }
  localStorage.setItem("seasonlens-participant", participantId.trim());
  busy = true;
  document.querySelectorAll("button").forEach(button => { button.disabled = true; });
  try {
    items = await api("/api/items");
    const selectedItem = debugMode ? document.querySelector("#study-item")?.value : null;
    projection = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        participant_id: participantId.trim(), item_id: selectedItem || items[0].item_id,
        study_mode: debugMode ? document.querySelector("#study-mode").value : "training",
        condition: debugMode ? document.querySelector("#study-condition").value : "observation-first-contingent",
      }),
    });
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
    ? `<span class="selection-region" style="left:${point.x * 100}%;top:${point.y * 100}%;width:${point.width * 100}%;height:${point.height * 100}%" aria-label="Your selected region"></span>`
    : "";
  const region = expertRegion
    ? `<span class="expert-region" style="left:${expertRegion.x * 100}%;top:${expertRegion.y * 100}%;width:${expertRegion.width * 100}%;height:${expertRegion.height * 100}%"></span>`
    : "";
  return `
    <div class="visual-panel">
      <div id="image-shell" class="image-shell ${interactive ? "" : "locked"}" data-interactive="${interactive}">
        <img class="plant-image" src="${escapeHtml(item.image_path)}" alt="${escapeHtml(item.plant_name)} plant photograph for observation" draggable="false">
        ${marker}${region}
      </div>
       <p class="image-caption">${interactive ? "Select the region that best contains the visual evidence supporting your judgement. Drag again to redraw it before committing." : escapeHtml(item.plant_name) + " · plant observation photograph"}</p>
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
  const confidence = commitDraft?.confidence || initial?.confidence || 3;
  const unaided = projection.data.study_mode !== "training";
  const answerFirst = !isRevision && projection.data.condition === "answer-first" && projection.data.expert_reveal;
  return `
    <form id="observation-form" class="form-panel">
      <p class="eyebrow">${isRevision ? (unaided ? "Final unaided response" : "Re-observe") : "Observe"}</p>
      <h2>${isRevision ? "Submit your final observation" : "What do you see?"}</h2>
      <p>${isRevision ? (unaided ? "Make a final independent response without guidance or an expert reveal." : "Inspect the image again using the guidance, then make a separate revised submission.") : "Select a region and commit your own observation."}</p>
      ${answerFirst ? `<div class="answer-first-panel"><strong>Answer-first expert reference</strong><p>Region: ${escapeHtml(projection.data.expert_reveal.relevant_region)}<br>Cue: ${escapeHtml(projection.data.expert_reveal.diagnostic_cue)}<br>Interpretation: ${escapeHtml(projection.data.expert_reveal.interpretation)}</p></div>` : ""}
      <div class="field">
        <label for="observation">${escapeHtml(projection.data.item.prompts.observation)}</label>
        <textarea id="observation" required>${escapeHtml(observation)}</textarea>
        <p class="field-help">Describe visible features only. Do not choose the plant stage here.</p>
      </div>
      ${stageChoiceField(selectedStageId, interpretation)}
      ${isRevision ? "" : confidenceField(confidence)}
      <button type="submit">${isRevision ? "Submit revised observation" : "Review and commit"}</button>
      ${isRevision ? '<p class="commit-note">Your initial attempt remains unchanged in the study log.</p>' : ""}
    </form>`;
}

function confidenceField(selected) {
  return `<fieldset><legend>Confidence · 1–5</legend><div class="confidence">${[1, 2, 3, 4, 5].map((value) =>
    `<label><input type="radio" name="confidence" value="${value}" ${value === selected ? "checked" : ""}><span>${value}</span></label>`
  ).join("")}</div></fieldset>`;
}

function attemptSummary(attempt, title, showRegion = false) {
  return `<div class="attempt-summary"><h3>${title}</h3><dl>
    ${showRegion ? `<dt>Selected region</dt><dd>${escapeHtml(JSON.stringify(attempt.selected_region))}</dd>` : ""}
    <dt>Observation</dt><dd>${escapeHtml(attempt.observation_text)}</dd>
    <dt>Stage judgement</dt><dd>${escapeHtml(stageLabel(attempt.selected_stage_id) || attempt.interpretation_text)}</dd>
    ${attempt.confidence ? `<dt>Confidence</dt><dd>${escapeHtml(attempt.confidence)} / 5</dd>` : ""}
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
      <div class="form-panel"><p class="eyebrow">Positive feedback</p><h2>Response confirmed</h2>
        <div id="shown-feedback" class="positive-feedback"><p>${escapeHtml(projection.data.positive_feedback.text)}</p></div>
        ${attemptSummary(projection.data.initial_attempt, "Initial observation · committed")}
        <button id="reveal" type="button">Reveal expert cue</button>
      </div></div>`;
    document.querySelector("#reveal").addEventListener("click", () => mutate("reveal"));
  } else if (stage === "HINT") {
    selectedRegion = (projection.data.revised_attempt || projection.data.initial_attempt).selected_region;
    app.innerHTML = `<div class="study-layout">${imagePanel()}
      <div class="form-panel"><p class="eyebrow">Authored hint</p><h2>Look once more</h2>
        <div id="shown-hint" class="hint-panel"><p class="hint-level">Level ${escapeHtml(projection.data.hint.hint_level)} hint</p><p>${escapeHtml(projection.data.hint.hint_text)}</p></div>
        ${attemptSummary(projection.data.revised_attempt || projection.data.initial_attempt, projection.data.revised_attempt ? "Latest revised observation" : "Initial observation · committed")}
        <button id="reobserve" type="button">Re-observe</button>
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
      <div class="form-panel"><p class="eyebrow">Final response committed</p><h2>${training ? "Compare with the expert cue" : "Complete this unaided item"}</h2>
        ${attemptSummary(projection.data.revised_attempt, "Revised observation")}
        <button id="${action}" type="button">${training ? "Reveal expert cue" : "Complete final submission"}</button>
      </div></div>`;
    document.querySelector(`#${action}`).addEventListener("click", () => mutate(action));
  } else if (stage === "REVEAL") {
    renderReveal(false);
  } else if (stage === "REFLECTION") {
    renderReveal(true);
  } else if (stage === "COMPLETE") {
    app.innerHTML = `<div class="success"><p class="eyebrow">Study log saved</p><h2>Observation complete</h2>
      <p>Thank you. Your responses and ${projection.data.study_mode === "training" ? "training interactions" : "unaided completion"} were recorded separately.</p>
      <button id="another" type="button">Start another session</button></div>`;
    document.querySelector("#another").addEventListener("click", showIntroduction);
    if (projection.data.has_next_item) {
      const next = document.createElement("button");
      next.textContent = "Next item";
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
  const reflectionPrompt = receivedHint
    ? "What did you notice after seeing the hint?"
    : "What visual evidence was most important for your decision?";
  app.innerHTML = `<div class="study-layout">${imagePanel({ expertRegion: expert.target_region })}
    <div class="form-panel"><p class="eyebrow">Bounded expert reveal</p><h2>Expert cue</h2>
      <dl class="reveal-grid">
        <dt>Relevant region</dt><dd>${escapeHtml(expert.relevant_region)}</dd>
        <dt>Diagnostic cue</dt><dd>${escapeHtml(expert.diagnostic_cue)}</dd>
        <dt>Interpretation</dt><dd>${escapeHtml(expert.interpretation)}</dd>
      </dl>
      ${showReflection ? `<form id="reflection-form" class="attempt-summary">
        <label for="reflection">${reflectionPrompt}</label>
        <textarea id="reflection" required></textarea>
        <label for="reflection-category">What changed most in your judgment? (optional)</label>
        <select id="reflection-category"><option value="">Choose an option</option>${["Where I looked", "What feature I noticed", "What the feature meant", "My confidence", "Other"].map(value => `<option>${value}</option>`).join("")}</select>
        <button type="submit">Save reflection</button>
      </form>` : `<button id="begin-reflection" type="button">${receivedHint ? "Reflect on what you noticed" : "Reflect on your visual evidence"}</button>`}
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
    marker.setAttribute("aria-label", "Your selected region");
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
      setStatus("Drag to draw a rectangle with visible width and height.");
    } else {
      setStatus("Region selected. Drag again to redraw it before committing.");
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
    <div class="form-panel"><p class="eyebrow">Commit</p><h2>Review your observation</h2>
      ${attemptSummary(payload, "Your initial response")}
      <p>${projection.data.study_mode === "training" ? "Commit this response to receive feedback or guidance." : "Commit this response to continue to the final unaided submission."}</p>
      <button id="commit-initial" type="button">Commit observation</button>
      <button id="edit-initial" class="quiet-button" type="button">Edit response / redraw</button>
    </div></div>`;
  document.querySelector("#commit-initial").addEventListener("click", () => mutate("initial-observation", commitDraft));
  document.querySelector("#edit-initial").addEventListener("click", render);
}

function bindObservationForm(isRevision) {
  document.querySelector("#observation-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedRegion || selectedRegion.width <= 0 || selectedRegion.height <= 0) {
      setStatus("Drag to select a rectangle on the image before submitting.");
      return;
    }
    const selectedStage = document.querySelector('input[name="stage"]:checked');
    const legacyInterpretation = document.querySelector("#interpretation");
    const payload = {
      selected_region: selectedRegion,
      observation_text: document.querySelector("#observation").value.trim(),
      selected_stage_id: selectedStage?.value || null,
      interpretation_text: selectedStage ? stageLabel(selectedStage.value) : (legacyInterpretation?.value.trim() || ""),
    };
    if (!isRevision) payload.confidence = Number(new FormData(event.currentTarget).get("confidence"));
    if (!payload.observation_text) {
      setStatus("Please describe the visible features in your selected region.");
      return;
    }
    if (!payload.selected_stage_id && !payload.interpretation_text) {
      setStatus("Please choose a plant stage.");
      return;
    }
    if (isRevision) await mutate("revision", payload);
    else renderCommit(payload);
  });
}

async function submitReflection(event) {
  event.preventDefault();
  if (!document.querySelector("#reflection").value.trim()) {
    setStatus("Please describe the visual evidence you noticed.");
    return;
  }
  await mutate("reflection", { reflection_text: document.querySelector("#reflection").value.trim(), reflection_category: document.querySelector("#reflection-category").value || null });
}

async function mutate(action, payload = {}) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach(button => { button.disabled = true; });
  setStatus("Saving…");
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
  document.querySelector('[data-step="hint"]').textContent = unaided ? "3. No guidance" : "3. Guidance";
  document.querySelector('[data-step="reveal"]').textContent = unaided ? "5. Finalize" : "5. Reveal";
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
      <dt>Reflection type / text / category</dt><dd>${escapeHtml(lastLog.reflection_type)} / ${escapeHtml(lastLog.reflection_text)} / ${escapeHtml(lastLog.reflection_category)}</dd></dl>
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
    const response = await fetch(`/api/sessions/${sessionId}/log.csv`, { headers: { "X-SeasonLens-Researcher": "1" } });
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

showIntroduction();
