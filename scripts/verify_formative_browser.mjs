#!/usr/bin/env node

// Dependency-free Chrome DevTools Protocol smoke test for the served study UI.
// Start Chrome with --remote-debugging-port=9223 and the SeasonLens server first.

const baseUrl = process.env.SEASONLENS_E2E_URL || "http://127.0.0.1:8000";
const cdpUrl = process.env.SEASONLENS_CDP_URL || "http://127.0.0.1:9223";
const researcherUsername = process.env.SEASONLENS_E2E_RESEARCHER_USERNAME || "e2e_researcher";
const researcherPassword = process.env.SEASONLENS_E2E_RESEARCHER_PASSWORD || "e2e-password";
const legacyParticipant = process.env.SEASONLENS_E2E_LEGACY_PARTICIPANT || "E2E-LEGACY";
const requireLegacy = process.env.SEASONLENS_E2E_REQUIRE_LEGACY === "true";

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

async function completeRun(participantId, inspectMaterials) {
  await setValue("#participant-id", participantId);
  await setValue("#consent-acknowledged", true, true);
  await click('#start-study-form button[type="submit"]');
  await expectSection("A");
  const first = await currentStudy();
  assert(first.status === 200 && first.body.study_mode === "self_guided", "New study is not self-guided.");
  assert(first.body.progress.stages.join("") === "ABCDE", "New study progress contains an unexpected stage.");

  await submitSection("B");
  if (inspectMaterials) {
    const b = await evaluate(`({
      text: document.body.innerText,
      images: [...document.images].map(image => ({ path: new URL(image.src).pathname, complete: image.complete, width: image.naturalWidth, height: image.naturalHeight }))
    })`);
    assert(/seasonal changes/i.test(b.text) && /季节/.test(b.text), "Section B seasonal wording is not visible.");
    assert(b.images.length === 1 && b.images[0].path === "/assets/real/anemone_virginiana_001.jpg", "Section B does not show Prototype Item 1.");
    assert(b.images[0].complete && b.images[0].width > 0 && b.images[0].height > 0, "Section B image did not load.");
  }

  await submitSection("C");
  if (inspectMaterials) {
    const c = await evaluate(`({ text: document.body.innerText, images: [...document.images].map(image => ({ path: new URL(image.src).pathname, width: image.naturalWidth })) })`);
    assert(/seasonal changes/i.test(c.text) && /季节/.test(c.text), "Section C seasonal-comparison wording is not visible.");
    assert(JSON.stringify(c.images.map(image => image.path)) === JSON.stringify(["/assets/study/C_SAME_PLANT_T1_001.png", "/assets/study/C_SAME_PLANT_T2_001.png"]), "Section C comparison images changed.");
    assert(c.images.every(image => image.width > 0), "A Section C image did not load.");
  }

  await submitSection("D");
  if (inspectMaterials) {
    const d = await evaluate(`({ text: document.body.innerText, images: [...document.images].map(image => ({ path: new URL(image.src).pathname, width: image.naturalWidth })) })`);
    assert(/seasonal condition/i.test(d.text) && /季节/.test(d.text), "Section D seasonal wording is not visible.");
    assert(d.images.length === 1 && d.images[0].path === "/assets/real/solidago_canadensis_001.jpg", "Section D does not show Prototype Item 2.");
    assert(d.images[0].width > 0, "Section D image did not load.");
    assert(!/correct stage|hint level|diagnostic feedback|target region|expert cue/i.test(d.text), "Section D reveals answer or diagnostic content.");
  }

  await submitSection("E");
  const eText = await evaluate("document.body.innerText");
  assert(/Sections B, C, and D/.test(eText) && !/prototype experience/i.test(eText), "Section E does not reflect only B-D observations.");
  await submitSection("COMPLETE");
  const complete = await currentStudy();
  assert(complete.body.study_id === first.body.study_id && complete.body.stage === "COMPLETE", "Completed record is not recoverable.");
  return first.body.study_id;
}

try {
  await command("Page.enable");
  await command("Runtime.enable");
  await command("Network.enable");
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
  assert(inspected.current?.questionnaire_version === "3.1" && inspected.current?.study_mode === "self_guided", "Dashboard/API misreports v3.1 configuration.");
  if (requireLegacy || inspected.legacy) {
    assert(inspected.legacy?.questionnaire_version === 3 && inspected.legacy?.study_mode === "researcher_assisted", "Dashboard/API cannot open the seeded v3 record.");
  }
  assert(inspected.exports.every(item => item.status === 200 && item.size > 0), "A researcher export failed.");

  await evaluate(`document.querySelector('.open-study[data-id="${secondId}"]').click()`);
  await waitFor("document.querySelector('.reveal-grid') !== null", "v3.1 study detail");
  const detailText = await evaluate("document.querySelector('#researcher-app').innerText");
  assert(/Questionnaire\s+3\.1/.test(detailText) && /Study mode\s+self_guided/.test(detailText), "Rendered v3.1 detail omits version or mode.");

  console.log(JSON.stringify({
    ok: true,
    browser: await evaluate("navigator.userAgent"),
    firstStudyId: firstId,
    secondStudyId: secondId,
    legacyVerified: Boolean(inspected.legacy),
    verifiedStages: ["A", "B", "C", "D", "E", "COMPLETE"],
    imagePaths: {
      B: ["/assets/real/anemone_virginiana_001.jpg"],
      C: ["/assets/study/C_SAME_PLANT_T1_001.png", "/assets/study/C_SAME_PLANT_T2_001.png"],
      D: ["/assets/real/solidago_canadensis_001.jpg"]
    },
    exports: inspected.exports
  }, null, 2));
} finally {
  socket.close();
  await fetch(`${cdpUrl}/json/close/${target.id}`);
}
