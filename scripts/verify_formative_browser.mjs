#!/usr/bin/env node

// Dependency-free Chrome DevTools Protocol smoke test for the served study UI.
// Start Chrome with --remote-debugging-port=9223 and the SeasonLens server first.

const baseUrl = process.env.SEASONLENS_E2E_URL || "http://127.0.0.1:8000";
const cdpUrl = process.env.SEASONLENS_CDP_URL || "http://127.0.0.1:9223";
const researcherUsername = process.env.SEASONLENS_E2E_RESEARCHER_USERNAME || "e2e_researcher";
const researcherPassword = process.env.SEASONLENS_E2E_RESEARCHER_PASSWORD || "e2e-password";
const legacyParticipant = process.env.SEASONLENS_E2E_LEGACY_PARTICIPANT || "E2E-LEGACY";
const requireLegacy = process.env.SEASONLENS_E2E_REQUIRE_LEGACY === "true";
const deleteVerifiedRecord = process.env.SEASONLENS_E2E_DELETE === "true";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const targetResponse = await fetch(`${cdpUrl}/json/new?${encodeURIComponent(baseUrl)}`, { method: "PUT" });
assert(targetResponse.ok, `Unable to create Chrome target (${targetResponse.status}).`);
const target = await targetResponse.json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let commandId = 0;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolve(message.result);
});

function command(method, params = {}) {
  const id = ++commandId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await command("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || "Browser evaluation failed.");
  return result.result.value;
}

async function waitFor(expression, description, timeoutMs = 8000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out waiting for ${description}.`);
}

async function navigate(path) {
  await command("Page.navigate", { url: new URL(path, baseUrl).href });
  await waitFor("document.readyState === 'complete'", path);
}

async function setViewport(width, height, mobile = false) {
  await command("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
}

async function stickyPositionAt(questionId) {
  return evaluate(`(async () => {
    document.querySelector(${JSON.stringify(`#${questionId}`)}).scrollIntoView({ block: 'center' });
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const panel = document.querySelector('.material-panel');
    const stickyOffset = Number.parseFloat(getComputedStyle(panel).top) || 0;
    const initialTop = panel.getBoundingClientRect().top;
    if (initialTop > stickyOffset + 1) {
      scrollBy(0, initialTop - stickyOffset);
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }
    const column = document.querySelector('.material-column');
    const form = document.querySelector('#section-form');
    const card = document.querySelector('#study-app');
    const rect = panel.getBoundingClientRect();
    return {
      scrollY,
      top: rect.top,
      bottom: rect.bottom,
      height: rect.height,
      viewportHeight: innerHeight,
      cardOverflow: getComputedStyle(card).overflow,
      columnHeight: column.getBoundingClientRect().height,
      formHeight: form.getBoundingClientRect().height,
    };
  })()`);
}

async function click(selector) {
  const clicked = await evaluate(`(() => { const element = document.querySelector(${JSON.stringify(selector)}); if (!element) return false; element.click(); return true; })()`);
  assert(clicked, `Missing clickable element: ${selector}`);
}

async function setValue(selector, value, checked = false) {
  const updated = await evaluate(`(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) return false;
    ${checked ? `element.checked = ${Boolean(value)};` : `element.value = ${JSON.stringify(value)};`}
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
  assert(updated, `Missing form element: ${selector}`);
}

async function currentStudy() {
  return evaluate("fetch('/api/studies/current').then(async response => ({ status: response.status, body: await response.json() }))");
}

async function expectSection(section) {
  await waitFor(`document.querySelector('#study-app .eyebrow')?.textContent.trim() === 'Section ${section}'`, `Section ${section}`);
  const progress = await evaluate("[...document.querySelectorAll('#study-progress span')].map(node => node.textContent.trim())");
  assert(JSON.stringify(progress) === JSON.stringify(["A", "B", "C", "D", "E"]), `Unexpected progress: ${progress}`);
  const text = await evaluate("document.body.innerText");
  assert(!/Check status|Release Stage|SeasonLens Prototype/.test(text), `Prototype/release UI leaked into Section ${section}.`);
}

async function submitSection(next) {
  await click('#section-form button[type="submit"]');
  if (next === "COMPLETE") await waitFor("document.querySelector('#start-new-study') !== null", "Completion");
  else await expectSection(next);
}

async function fillRequiredSection(section) {
  const values = {
    A: { A1: "prefer_not_to_answer", A3: "not_sure" },
    B: { B1: "Not sure", B2: "Not sure", B3: "Not sure", B4: "Not sure", B4_CONFIDENCE: "3" },
    C: { C1: "Not sure", C2: "Not sure", C3: "Not sure", C4: "Not sure", C5: "3", C6: "Not sure" },
    D: { D1: "Not sure", D2: "Not sure", D3: "Not sure", D4: "Not sure", D_CONFIDENCE: "3", D5: "No help needed", D6: "No help needed" },
    E: { E1: "Not sure", E2: "No help needed", E3: "on_request", E3_WHY: "Preserves participant autonomy", E4: "Not sure" },
  }[section];
  for (const [id, value] of Object.entries(values)) await setValue(`#${id}`, value);
}

async function completeRun(participantId, inspectMaterials) {
  await setValue("#participant-id", participantId);
  await setValue("#consent-acknowledged", true, true);
  await click('#start-study-form button[type="submit"]');
  await expectSection("A");
  const first = await currentStudy();
  assert(first.status === 200 && first.body.study_mode === "self_guided", "New study is not self-guided.");
  assert(first.body.progress.stages.join("") === "ABCDE", "New study progress contains an unexpected stage.");

  if (inspectMaterials) {
    await click('#section-form button[type="submit"]');
    await waitFor("document.querySelector('.question-field.invalid') !== null", "required-field validation");
    const validation = await evaluate(`({
      stage: document.querySelector('#study-app .eyebrow')?.textContent.trim(),
      message: document.querySelector('#status')?.textContent,
      invalid: [...document.querySelectorAll('.question-field.invalid')].map(node => node.dataset.questionId),
      focused: document.activeElement?.id
    })`);
    assert(validation.stage === "Section A", "Empty Section A advanced unexpectedly.");
    assert(validation.message.includes("Please complete all required questions"), "Bilingual required message is missing.");
    assert(validation.invalid.includes("A1") && validation.invalid.includes("A3") && validation.focused === "A1", `Required fields were not marked and focused: ${JSON.stringify(validation)}`);
  }
  await fillRequiredSection("A");
  await submitSection("B");
  if (inspectMaterials) {
    const b = await evaluate(`({
      text: document.body.innerText,
      questions: [...document.querySelectorAll('.question-field')].map(field => ({
        id: field.dataset.questionId,
        text: field.innerText
      })),
      images: [...document.images].map(image => ({ path: new URL(image.src).pathname, complete: image.complete, width: image.naturalWidth, height: image.naturalHeight }))
    })`);
    assert(/seasonal changes/i.test(b.text) && /季节/.test(b.text), "Section B seasonal wording is not visible.");
    assert(JSON.stringify(b.questions.map(question => question.id)) === JSON.stringify(["B1", "B2", "B3", "B4", "B4_CONFIDENCE"]), `Section B rendered unexpected IDs: ${JSON.stringify(b.questions)}`);
    assert(b.questions[3].text.includes("Based on the visible evidence, what can you conclude about the plant’s seasonal condition or change, and what remains uncertain?"), "Section B does not render the v3.2 B4 wording.");
    assert(!/viewing distance|angle, or position/i.test(b.text), "The deleted v3.1 viewing-distance question is still visible in v3.2.");
    assert(b.images.length === 1 && b.images[0].path === "/assets/real/anemone_virginiana_001.jpg", "Section B does not show Prototype Item 1.");
    assert(b.images[0].complete && b.images[0].width > 0 && b.images[0].height > 0, "Section B image did not load.");
  }

  await fillRequiredSection("B");
  await submitSection("C");
  if (inspectMaterials) {
    const c = await evaluate(`({
      text: document.body.innerText,
      questions: Object.fromEntries([...document.querySelectorAll('.question-field')].map(field => [field.dataset.questionId, field.innerText])),
      images: [...document.images].map(image => ({ path: new URL(image.src).pathname, width: image.naturalWidth }))
    })`);
    assert(/seasonal changes/i.test(c.text) && /季节/.test(c.text), "Section C seasonal-comparison wording is not visible.");
    assert(c.questions.C2.includes("When comparing the two images, which parts of the plant did you focus on? What differences did you notice in those parts?"), "Section C does not render the exact v3.2 C2 wording.");
    assert(c.questions.C3.includes("When comparing the two images, was there anything you found difficult to judge or were unsure about? Why? If not, you may say so."), "Section C does not render the exact v3.2 C3 wording.");
    assert(c.questions.C4.includes("Based on the differences between the two images, what growth-related change do you think the plant might be undergoing? Why do you think so?"), "Section C does not render the exact v3.2 C4 wording.");
    assert(JSON.stringify(c.images.map(image => image.path)) === JSON.stringify(["/assets/study/C_SAME_PLANT_T1_001.png", "/assets/study/C_SAME_PLANT_T2_001.png"]), "Section C comparison images changed.");
    assert(c.images.every(image => image.width > 0), "A Section C image did not load.");
    await setViewport(390, 844, true);
    const mobileComparison = await evaluate(`(() => {
      const panel = document.querySelector('.comparison-materials');
      const figures = [...panel.querySelectorAll('figure')].map(figure => {
        const rect = figure.getBoundingClientRect();
        return { top: rect.top, left: rect.left, width: rect.width, height: rect.height };
      });
      return { display: getComputedStyle(panel).display, panelHeight: panel.getBoundingClientRect().height, figures };
    })()`);
    assert(mobileComparison.display === "flex" && mobileComparison.figures.length === 2, `Section C mobile comparison is not a two-image preview: ${JSON.stringify(mobileComparison)}`);
    assert(Math.abs(mobileComparison.figures[0].top - mobileComparison.figures[1].top) < 2, `Section C mobile images are not kept side by side: ${JSON.stringify(mobileComparison)}`);
    assert(mobileComparison.panelHeight <= 844 * 0.31, "Section C mobile preview is too tall.");
    await setViewport(1280, 800);
  }

  await fillRequiredSection("C");
  await submitSection("D");
  if (inspectMaterials) {
    const d = await evaluate(`({ text: document.body.innerText, images: [...document.images].map(image => ({ path: new URL(image.src).pathname, width: image.naturalWidth })) })`);
    assert(/seasonal condition/i.test(d.text) && /季节/.test(d.text), "Section D seasonal wording is not visible.");
    assert(d.images.length === 1 && d.images[0].path === "/assets/study/section-d-solidago.png", "Section D does not show the supplied Solidago image.");
    assert(d.images[0].width > 0, "Section D image did not load.");
    assert(!/correct stage|hint level|diagnostic feedback|target region|expert cue/i.test(d.text), "Section D reveals answer or diagnostic content.");

    await setViewport(1280, 800);
    const desktopStart = await stickyPositionAt("D1");
    const desktopEnd = await stickyPositionAt("D6");
    assert(desktopStart.cardOverflow === "visible", `Questionnaire card still blocks sticky positioning: ${desktopStart.cardOverflow}`);
    assert(desktopStart.columnHeight + 1 >= desktopStart.formHeight, "Desktop material column ends before the question form.");
    assert(desktopEnd.scrollY - desktopStart.scrollY > 400, "Desktop sticky test did not scroll through enough of Section D.");
    assert(Math.abs(desktopEnd.top - desktopStart.top) < 3, `Desktop image moved in the viewport (${desktopStart.top} to ${desktopEnd.top}).`);
    assert(desktopEnd.top >= 0 && desktopEnd.bottom <= desktopEnd.viewportHeight, "Desktop image is not fully visible at D6.");

    await setViewport(390, 844, true);
    const mobileStart = await stickyPositionAt("D1");
    const mobileEnd = await stickyPositionAt("D6");
    assert(mobileEnd.scrollY - mobileStart.scrollY > 400, "Mobile sticky test did not scroll through enough of Section D.");
    assert(Math.abs(mobileEnd.top - mobileStart.top) < 3, `Mobile image moved in the viewport (${mobileStart.top} to ${mobileEnd.top}).`);
    assert(mobileEnd.height <= mobileEnd.viewportHeight * 0.31, "Mobile sticky preview occupies too much of the viewport.");
    assert(mobileEnd.top >= 0 && mobileEnd.bottom <= mobileEnd.viewportHeight, "Mobile image is not fully visible at D6.");
    console.log(JSON.stringify({ stickyLayout: { desktopStart, desktopEnd, mobileStart, mobileEnd } }));
    await setViewport(1280, 800);
  }

  await fillRequiredSection("D");
  await submitSection("E");
  const eText = await evaluate("document.body.innerText");
  assert(/Sections B, C, and D/.test(eText) && !/prototype experience/i.test(eText), "Section E does not reflect only B-D observations.");
  await fillRequiredSection("E");
  await submitSection("COMPLETE");
  const complete = await currentStudy();
  assert(complete.body.study_id === first.body.study_id && complete.body.stage === "COMPLETE", "Completed record is not recoverable.");
  return first.body.study_id;
}

try {
  await command("Page.enable");
  await command("Runtime.enable");
  await command("Network.enable");
  await setViewport(1280, 800);
  await command("Network.clearBrowserCookies");
  await navigate("/");
  await waitFor("document.querySelector('#start-study-form') !== null", "Welcome / Consent");

  const firstId = await completeRun(`E2E-FIRST-${Date.now()}`, true);
  assert(await evaluate("document.querySelector('#start-new-study')?.textContent.includes('Start New Study')"), "Completion is missing Start New Study.");
  await click("#start-new-study");
  await waitFor("document.querySelector('#start-study-form') !== null", "fresh Welcome / Consent");
  const stillFirst = await currentStudy();
  assert(stillFirst.body.study_id === firstId, "Start New Study created a duplicate record before consent.");
  const secondId = await completeRun(`E2E-SECOND-${Date.now()}`, false);
  assert(secondId !== firstId, "Second run reused the first study identifier.");

  await navigate("/researcher.html");
  await waitFor("document.querySelector('#login-form') !== null", "researcher login");
  await setValue("#username", researcherUsername);
  await setValue("#password", researcherPassword);
  await click('#login-form button[type="submit"]');
  await waitFor("document.querySelector('.study-table') !== null", "researcher study list");
  const listed = await evaluate("[...document.querySelectorAll('.open-study')].map(button => button.dataset.id)");
  assert(listed.includes(firstId) && listed.includes(secondId), "Both completed studies are not preserved in the dashboard.");
  await evaluate(`document.querySelector('.delete-study[data-id="${secondId}"]').click()`);
  await waitFor("document.querySelector('#deletion-dialog')?.open === true", "delete confirmation dialog");
  const dialog = await evaluate(`({
    participant: document.querySelector('#delete-participant').textContent,
    studyId: document.querySelector('#delete-study-id').textContent,
    stage: document.querySelector('#delete-stage').textContent,
    disabled: document.querySelector('#confirm-delete').disabled,
    warning: document.querySelector('.deletion-warning').innerText
  })`);
  assert(dialog.studyId === secondId && dialog.stage === "COMPLETE" && dialog.disabled, "Delete dialog is missing its safeguards.");
  assert(/cannot be undone/i.test(dialog.warning), "Permanent-deletion warning is missing.");
  await click("#cancel-delete");
  assert(await evaluate(`document.querySelector('.open-study[data-id="${secondId}"]') !== null`), "Cancel removed the study record.");

  const inspected = await evaluate(`(async () => {
    const rows = await fetch('/api/researcher/studies').then(response => response.json());
    const details = await Promise.all(rows.map(row => fetch('/api/researcher/studies/' + row.study_id).then(response => response.json())));
    const current = details.find(detail => detail.study_id === ${JSON.stringify(secondId)});
    const legacy = details.find(detail => detail.participant_id === ${JSON.stringify(legacyParticipant)});
    const exports = await Promise.all(['export.json', 'export.csv', 'export.xlsx', 'export.zip'].map(async suffix => {
      const response = await fetch('/api/researcher/studies/' + ${JSON.stringify(secondId)} + '/' + suffix);
      return { suffix, status: response.status, size: (await response.arrayBuffer()).byteLength };
    }));
    return { current, legacy, exports };
  })()`);
  assert(inspected.current?.questionnaire_version === "3.2" && inspected.current?.study_mode === "self_guided", "Dashboard/API misreports v3.2 configuration.");
  if (requireLegacy || inspected.legacy) {
    assert(inspected.legacy?.questionnaire_version === 3 && inspected.legacy?.study_mode === "researcher_assisted", "Dashboard/API cannot open the seeded v3 record.");
  }
  assert(inspected.exports.every(item => item.status === 200 && item.size > 0), "A researcher export failed.");

  await evaluate(`document.querySelector('.open-study[data-id="${secondId}"]').click()`);
  await waitFor("document.querySelector('.reveal-grid') !== null", "v3.2 study detail");
  const detailText = await evaluate("document.querySelector('#researcher-app').innerText");
  assert(/Questionnaire\s+3\.2/.test(detailText) && /Study mode\s+self_guided/.test(detailText), "Rendered v3.2 detail omits version or mode.");

  let deletionVerified = false;
  if (deleteVerifiedRecord) {
    await navigate("/researcher.html");
    await waitFor("document.querySelector('.study-table') !== null", "authenticated researcher study list");
    await evaluate(`document.querySelector('.delete-study[data-id="${secondId}"]').click()`);
    await waitFor("document.querySelector('#deletion-dialog')?.open === true", "delete confirmation dialog");
    await setValue("#delete-confirmation", secondId);
    assert(await evaluate("document.querySelector('#confirm-delete').disabled === false"), "Exact study ID did not enable deletion.");
    await click("#confirm-delete");
    await waitFor(`document.querySelector('.open-study[data-id="${secondId}"]') === null`, "deleted row removal");
    const afterDelete = await evaluate(`Promise.all([
      fetch('/api/researcher/studies/${secondId}').then(response => response.status),
      fetch('/api/researcher/studies/${firstId}').then(response => response.status),
      fetch('/api/researcher/studies/${secondId}/export.json').then(response => response.status)
    ])`);
    assert(JSON.stringify(afterDelete) === JSON.stringify([404, 200, 404]), "Deletion or export isolation check failed.");
    deletionVerified = true;
  }

  console.log(JSON.stringify({
    ok: true,
    browser: await evaluate("navigator.userAgent"),
    firstStudyId: firstId,
    secondStudyId: secondId,
    legacyVerified: Boolean(inspected.legacy),
    deletionDialogCancelVerified: true,
    deletionVerified,
    verifiedStages: ["A", "B", "C", "D", "E", "COMPLETE"],
    imagePaths: {
      B: ["/assets/real/anemone_virginiana_001.jpg"],
      C: ["/assets/study/C_SAME_PLANT_T1_001.png", "/assets/study/C_SAME_PLANT_T2_001.png"],
      D: ["/assets/study/section-d-solidago.png"]
    },
    exports: inspected.exports
  }, null, 2));
} finally {
  socket.close();
  await fetch(`${cdpUrl}/json/close/${target.id}`);
}
