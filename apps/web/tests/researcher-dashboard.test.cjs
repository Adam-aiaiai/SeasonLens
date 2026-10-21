const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() {
    this.innerHTML = "";
    this.textContent = "";
    this.listeners = {};
    this.dataset = {};
    this.classList = { toggle() {} };
  }
  addEventListener(name, handler) { this.listeners[name] = handler; }
}

function studyDetail(overrides = {}) {
  return {
    study_id: "study-1",
    participant_id: "F-001",
    stage: "B",
    version: 2,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:01:00Z",
    researcher_metadata: {},
    responses: [],
    materials: [],
    prototype_sessions: [],
    events: [],
    ...overrides,
  };
}

function fixture(response) {
  const app = new Element();
  const status = new Element();
  const nodes = new Map([
    ["#researcher-app", app], ["#researcher-status", status],
    ["#back", new Element()], ["#release", new Element()], ["#metadata-form", new Element()],
  ]);
  const context = vm.createContext({
    document: {
      querySelector: selector => nodes.get(selector) || new Element(),
      querySelectorAll: () => [],
    },
    fetch: async () => response instanceof Error
      ? { ok: false, status: 500, json: async () => ({ error: response.message }) }
      : { ok: true, status: 200, json: async () => response },
    FormData: class {}, console,
  });
  const source = readFileSync(join(__dirname, "../researcher.js"), "utf8")
    .replace(/\nboot\(\);\s*$/, "\n");
  vm.runInContext(source, context);
  return { app, status, run: code => vm.runInContext(code, context) };
}

test("researcher opens a legacy v3 detail response without a config object", async () => {
  const f = fixture(studyDetail({ stage: "WAIT_B" }));
  await f.run('openStudy("legacy")');
  assert.match(f.app.innerHTML, /<dt>Questionnaire<\/dt><dd>3<\/dd>/);
  assert.match(f.app.innerHTML, /<dt>Materials<\/dt><dd>3<\/dd>/);
  assert.match(f.app.innerHTML, /<dt>Study mode<\/dt><dd>researcher_assisted<\/dd>/);
  assert.match(f.app.innerHTML, /id="release"/);
  assert.equal(f.status.textContent, "");
});

test("researcher opens a v3.1 detail using the stable top-level contract", async () => {
  const f = fixture(studyDetail({
    questionnaire_version: "3.1",
    material_set_version: "3.1",
    study_mode: "self_guided",
    config: {
      questionnaire_version: "3.1",
      material_set_version: "3.1",
      study_mode: "self_guided",
      enable_prototype_stage: false,
    },
  }));
  await f.run('openStudy("current")');
  assert.match(f.app.innerHTML, /<dt>Questionnaire<\/dt><dd>3\.1<\/dd>/);
  assert.match(f.app.innerHTML, /<dt>Materials<\/dt><dd>3\.1<\/dd>/);
  assert.match(f.app.innerHTML, /<dt>Study mode<\/dt><dd>self_guided<\/dd>/);
  assert.doesNotMatch(f.app.innerHTML, /id="release"/);
  assert.equal(f.status.textContent, "");
});

test("researcher detail failures are shown instead of becoming unhandled rejections", async () => {
  const f = fixture(new Error("database unavailable"));
  await f.run('openStudy("broken")');
  assert.match(f.status.textContent, /Unable to open study: database unavailable/);
});
