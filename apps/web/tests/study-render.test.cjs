const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const schema = JSON.parse(readFileSync(
  join(__dirname, "../../../extensions/seasonlens/data/formative_questionnaire_v3_2.json"), "utf8"));
const escaped = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

class Element {
  constructor() {
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.listeners = {};
    this.classList = { toggle() {} };
    this._innerHTML = "";
    this.spans = [];
  }
  set innerHTML(value) {
    this._innerHTML = value;
    this.spans = [...value.matchAll(/data-stage="([^"]+)"/g)].map(match => ({
      dataset: { stage: match[1] },
      classList: { toggle() {} },
    }));
  }
  get innerHTML() { return this._innerHTML; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  querySelectorAll(selector) { return selector === "span" ? this.spans : []; }
  querySelector() { return null; }
}

function fixture(fetchImpl = async () => ({ ok: false, status: 401, json: async () => ({ error: "signed out" }) })) {
  const elements = {
    "#study-app": new Element(),
    "#status": new Element(),
    "#study-progress": new Element(),
  };
  const context = vm.createContext({
    document: { querySelector: selector => elements[selector] ||= new Element() },
    fetch: fetchImpl,
    setTimeout, clearTimeout, FormData: class {}, console,
  });
  const source = readFileSync(join(__dirname, "../study.js"), "utf8").replace(/\nresume\(\);\s*$/, "\n");
  vm.runInContext(source, context);
  return { context, elements, run: code => vm.runInContext(code, context) };
}

test("legacy progress response is initialized before the progress map call", () => {
  const f = fixture();
  f.run(`study = normalizeStudyResponse({
    study_id: "old-shape", stage: "A", study_mode: "self_guided",
    progress: { completed: [], current: "A" }
  }); updateProgress();`);
  assert.deepEqual(f.elements["#study-progress"].spans.map(span => span.dataset.stage),
    ["A", "B", "C", "D", "E"]);
});

test("all v3.2 A-E fields and B-D materials render with their authored shapes", () => {
  const f = fixture();
  for (const [sectionId, section] of Object.entries(schema.sections)) {
    for (const field of section.fields) {
      f.context.field = field;
      const html = f.run("questionField(field, {})");
      assert.match(html, new RegExp(`>${field.id}<`));
      assert.ok(html.includes(escaped(field.zh)));
      assert.ok(html.includes(escaped(field.en)));
      if (field.required) {
        assert.match(html, new RegExp(`>${field.id}<\\/span><span class="required-marker">必填 \\/ Required`));
        assert.match(html, /aria-required="true"/);
      } else {
        assert.match(html, /选答 \/ Optional/);
      }
      if (field.type === "choice") {
        assert.equal((html.match(/<option value=/g) || []).length, field.options.length + 1);
      }
      if (field.type === "confidence") {
        assert.equal((html.match(/<option value=/g) || []).length, 6);
        assert.match(html, />1 — 完全没把握 \/ No confidence</);
        assert.match(html, />2 — 把握较低 \/ Low confidence</);
        assert.match(html, />3 — 把握中等 \/ Moderate confidence</);
        assert.match(html, />4 — 把握较高 \/ High confidence</);
        assert.match(html, />5 — 很有把握 \/ Full confidence</);
      }
    }
    assert.ok(section.title.zh && section.title.en, `${sectionId} requires a bilingual title`);
  }

  for (const sectionId of ["B", "C", "D"]) {
    f.context.material = { images: schema.materials[sectionId] };
    f.context.sectionId = sectionId;
    const html = f.run("materialPanel(material, sectionId)");
    assert.match(html, /^<div class="material-column"><aside class="material-panel/);
    assert.match(html, /<\/aside><\/div>$/);
    for (const image of schema.materials[sectionId]) {
      assert.ok(html.includes(image.image_path));
      assert.ok(html.includes(image.material_id));
    }
  }
});

test("observation material and form share one section-height layout boundary", () => {
  const f = fixture();
  f.context.projection = {
    stage: "D",
    section: schema.sections.D,
    material: { images: schema.materials.D, material_id: schema.materials.D[0].material_id },
    draft: {},
    study_mode: "self_guided",
  };
  f.run("study = projection; renderSection()");
  const html = f.elements["#study-app"].innerHTML;
  assert.match(html, /<div class="questionnaire-layout"><div class="material-column"><aside[\s\S]*<\/aside><\/div>\s*<form id="section-form"/);
});

test("conditional follow-ups are hidden until their authored trigger applies", () => {
  const f = fixture();
  f.context.field = schema.sections.E.fields.find(field => field.id === "E3_WHY");
  assert.match(f.run("questionField(field, {})"), /^<label[^>]+ hidden>/);
  assert.doesNotMatch(f.run('questionField(field, {E3: "on_request"})'), /^<label[^>]+ hidden>/);
});

test("completion starts one fresh consent flow even when clicked repeatedly", async () => {
  let requests = 0;
  const config = { participant_notice: { zh: "新测试说明", en: "New study notice" } };
  const f = fixture(async (path, options) => {
    requests += 1;
    assert.equal(path, "/api/study-config");
    assert.equal(options.method, undefined);
    assert.equal(options.headers["Content-Type"], "application/json");
    return { ok: true, status: 200, json: async () => config };
  });
  f.run("renderComplete()");
  assert.match(f.elements["#study-app"].innerHTML, /开始新的测试 \/ Start New Study/);
  const button = f.elements["#start-new-study"];
  const event = { currentTarget: button };
  await Promise.all([button.listeners.click(event), button.listeners.click(event)]);
  assert.equal(requests, 1);
  assert.match(f.elements["#study-app"].innerHTML, /Welcome \/ 欢迎/);
  assert.match(f.elements["#study-app"].innerHTML, /新测试说明/);
  assert.ok(f.elements["#start-study-form"].listeners.submit);
});

test("new-study configuration failure restores the retained button after currentTarget clears", async () => {
  let finishRequest;
  const response = new Promise(resolve => { finishRequest = resolve; });
  const f = fixture(async () => response);
  f.run("renderComplete()");
  const button = f.elements["#start-new-study"];
  const event = { currentTarget: button };
  const click = button.listeners.click(event);
  event.currentTarget = null;
  finishRequest({ ok: false, status: 500, json: async () => ({ error: "configuration unavailable" }) });
  await click;
  assert.equal(button.disabled, false);
  assert.match(f.elements["#status"].textContent,
    /无法开始新的测试 \/ Unable to start a new study: configuration unavailable/);
});

test("consent page renders the official bilingual title and all four verbatim statements", () => {
  const f = fixture();
  f.context.config = { participant_notice: { zh: "参与者信息", en: "Participant information" } };
  f.run("renderWelcome(config)");
  const html = f.elements["#study-app"].innerHTML;
  assert.match(html, /Learning to See the Seasons: Designing Contingent AI Scaffolds for Independent Situated Ecological Observation/);
  assert.match(html, /学会观测四季：面向自主情境化生态观察的条件式 AI 支架设计/);
  assert.match(html, /Informed Consent Statements \/ 知情同意声明/);
  assert.equal((html.match(/class="consent-statement"/g) || []).length, 4);
  assert.equal((html.match(/type="checkbox" aria-required="true"/g) || []).length, 4);
  assert.doesNotMatch(html, /type="checkbox"[^>]*\schecked/);
  assert.match(html, /I confirm that I have read and have understood the information sheet dated Version 1\.0, 21 October 2026/);
  assert.match(html, /本人确认已阅读并充分理解上述研究参与者告知Version 1\.0, 21 October 2026相关内容。/);
  assert.match(html, /I understand that my participation is voluntary and that I am free to withdraw at any time/);
  assert.match(html, /本人理解，参与本研究完全出于自愿。/);
  assert.match(html, /as explained in section #13 of the Participant Information Sheet\./);
  assert.match(html, /按照《参与者告知书》第13条的说明/);
  assert.match(html, /I agree to take part in the above study\./);
  assert.match(html, /本人同意参与上述研究。/);
});

test("zero through three consent checks cannot create a study; all four can", async () => {
  let creates = 0;
  const projection = {
    study_id: "consented-study", participant_id: "F-CONSENT", stage: "A", version: 0,
    study_mode: "self_guided", progress: { completed: [], current: "A", stages: ["A", "B", "C", "D", "E"] },
    section: schema.sections.A, draft: {}, updated_at: "2026-10-21T00:00:00Z",
  };
  const f = fixture(async (path, options) => {
    creates += 1;
    assert.equal(path, "/api/studies");
    const payload = JSON.parse(options.body);
    assert.deepEqual(Object.values(payload.consent_statements), [true, true, true, true]);
    return { ok: true, status: 201, json: async () => projection };
  });
  f.context.config = { participant_notice: { zh: "说明", en: "Notice" } };
  f.run("renderWelcome(config)");
  f.elements["#participant-id"] = new Element();
  f.elements["#participant-id"].value = "F-CONSENT";
  const checkboxes = [1, 2, 3, 4].map(number => f.elements[`#consent-statement_${number}`]);
  const form = f.elements["#start-study-form"];
  const event = { preventDefault() {}, currentTarget: form };
  for (let checkedCount = 0; checkedCount < 4; checkedCount += 1) {
    checkboxes.forEach((checkbox, index) => { checkbox.checked = index < checkedCount; });
    await form.listeners.submit(event);
    assert.equal(creates, 0);
    assert.match(f.elements["#status"].textContent, /Please check all four informed consent statements/);
  }
  checkboxes.forEach(checkbox => { checkbox.checked = true; });
  await form.listeners.submit(event);
  assert.equal(creates, 1);
  assert.match(f.elements["#study-app"].innerHTML, /Section A/);
});

test("repeated welcome submission creates only one new study run", async () => {
  let creates = 0;
  const config = { participant_notice: { zh: "说明", en: "Notice" } };
  const projection = {
    study_id: "new-study-id", participant_id: "F-NEW", stage: "A", version: 0,
    study_mode: "self_guided", progress: { completed: [], current: "A", stages: ["A", "B", "C", "D", "E"] },
    section: schema.sections.A, draft: {}, updated_at: "2026-01-01T00:00:00Z",
  };
  const f = fixture(async path => {
    assert.equal(path, "/api/studies");
    creates += 1;
    return { ok: true, status: 201, json: async () => projection };
  });
  f.context.config = config;
  f.run("renderWelcome(config)");
  f.elements["#participant-id"] = new Element();
  f.elements["#participant-id"].value = "F-NEW";
  for (let number = 1; number <= 4; number += 1) {
    f.elements[`#consent-statement_${number}`].checked = true;
  }
  const form = f.elements["#start-study-form"];
  const event = { preventDefault() {}, currentTarget: form };
  await Promise.all([form.listeners.submit(event), form.listeners.submit(event)]);
  assert.equal(creates, 1);
  assert.match(f.elements["#study-app"].innerHTML, /Section A/);
});
