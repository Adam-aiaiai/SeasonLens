// DOM event doubles exercise the shipped app's handlers without adding a browser dependency.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() {
    this.listeners = {}; this.style = {}; this.dataset = {}; this.attributes = {};
    this.children = []; this.value = ""; this.innerHTML = ""; this.disabled = false;
    this.classList = { toggle() {} };
  }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  append(child) { child.parent = this; this.children.push(child); }
  remove() { this.parent.children = this.parent.children.filter(child => child !== this); }
  querySelector(selector) {
    if (selector === "img") return this.image;
    return this.children.find(child => selector === `.${child.className}`) || null;
  }
  getBoundingClientRect() { return { left: 100, top: 100, width: 400, height: 300 }; }
  setPointerCapture(id) { this.captured = id; }
  releasePointerCapture() { this.captured = null; }
  focus() { this.focused = true; }
}

function fixture(debug = true) {
  const elements = new Map();
  const node = selector => {
    if (!elements.has(selector)) elements.set(selector, new Element());
    return elements.get(selector);
  };
  node("#image-shell").image = new Element();
  const progress = Array.from({ length: 6 }, () => new Element());
  const requests = [];
  const context = vm.createContext({
    document: {
      querySelector: node,
      querySelectorAll: selector => selector === ".progress span" ? progress : [],
      createElement: () => new Element(),
    },
    window: { prompt: () => null },
    location: { search: debug ? "?debug=1" : "" },
    localStorage: { getItem: () => null, setItem() {} },
    URLSearchParams, URL, Blob, setTimeout, structuredClone,
    FormData: class { get() { return "3"; } },
    fetch: async (path, options = {}) => {
      requests.push({ path, options });
      const body = path.endsWith("/researcher")
        ? { log: { session_id: "session-1", stage: "REOBSERVE", researcher_notes: "Saved note" },
            hints: [{ id: "hint-1", category: "REGION_MISS", level: 1, text: "Look again" }] }
        : vm.runInContext("projection", context);
      return { ok: true, json: async () => body };
    },
  });
  vm.runInContext(readFileSync(join(__dirname, "../app.js"), "utf8"), context);
  const run = source => vm.runInContext(source, context);
  run(`projection = { data: { session_id: "session-1", stage: "OBSERVE", item: {
    plant_name: "Demo", image_path: "/assets/real/anemone_virginiana_001.jpg", prompts: { observation: "Observe", interpretation: "Which stage?" },
    stage_options: [{id: "flower_buds_present", label: "Flower buds present"}, {id: "fruiting", label: "Fruiting"}]
  } } };`);
  requests.length = 0;
  return { node, progress, requests, run };
}

const pointer = (clientX, clientY) => ({ clientX, clientY, button: 0, isPrimary: true, pointerId: 1, preventDefault() {} });

test("formative introduction explains the task and requires an anonymous code", () => {
  const f = fixture(false);
  f.run("showIntroduction()");
  assert.match(f.node("#app").innerHTML, /SeasonLens Observation Study/);
  assert.match(f.node("#app").innerHTML, /best contains the visual evidence supporting your judgement/);
  assert.match(f.node("#app").innerHTML, /Describe only what you can directly see/);
  f.node("#participant-id").value = " ";
  f.node("#session-start-form").listeners.submit({ preventDefault() {} });
  assert.match(f.node("#status").textContent, /anonymous participant code/);
  assert.equal(f.requests.length, 0);
});

test("drag in either direction creates a normalized visible rectangle; redraw and cancel are safe", () => {
  const f = fixture();
  f.run("bindImageSelection()");
  const shell = f.node("#image-shell");
  shell.listeners.pointerdown(pointer(420, 340));
  shell.listeners.pointermove(pointer(180, 160));
  shell.listeners.pointerup(pointer(180, 160));
  const region = JSON.parse(f.run("JSON.stringify(selectedRegion)"));
  assert.deepEqual(region, { x: 0.2, y: 0.2, width: 0.6000000000000001, height: 0.6000000000000001 });
  assert.equal(shell.children.length, 1);
  assert.equal(shell.children[0].style.left, "20%");
  shell.listeners.pointerdown(pointer(100, 100));
  shell.listeners.pointerup(pointer(500, 400));
  assert.equal(f.run("selectedRegion.width"), 1);
  assert.equal(shell.children.length, 1);
  shell.listeners.pointerdown(pointer(200, 200));
  shell.listeners.pointercancel();
  assert.equal(f.run("selectedRegion.width"), 1);
  shell.listeners.pointerdown(pointer(200, 200));
  shell.listeners.pointerup(pointer(200, 200));
  assert.equal(f.run("selectedRegion.width"), 1);
  assert.match(f.node("#status").textContent, /Drag to draw/);
});

test("initial validation prevents empty region and whitespace responses", async () => {
  const f = fixture();
  f.run("bindObservationForm(false)");
  const form = f.node("#observation-form");
  const submit = () => form.listeners.submit({ preventDefault() {}, currentTarget: form });
  await submit();
  assert.match(f.node("#status").textContent, /select a rectangle/);
  f.run("selectedRegion = {x: 0.1, y: 0.1, width: 0.2, height: 0.2}");
  f.node("#observation").value = " ";
  f.node('input[name="stage"]:checked').value = "flower_buds_present";
  await submit();
  assert.match(f.node("#status").textContent, /visible features/);
  assert.equal(f.requests.length, 0);
});

test("commit review shows stage 2 and keeps the editable draft without internal coordinates", () => {
  const f = fixture();
  f.run(`selectedRegion = {x: 0.1, y: 0.1, width: 0.2, height: 0.2};
    renderCommit({ selected_region: selectedRegion, observation_text: "A branch", selected_stage_id: "flower_buds_present", interpretation_text: "Flower buds present", confidence: 3 });`);
  assert.equal(f.progress[1].attributes["aria-current"], "step");
  assert.match(f.node("#app").innerHTML, /selection-region/);
  assert.doesNotMatch(f.node("#app").innerHTML, /Selected region|&quot;x&quot;/);
  f.node("#edit-initial").listeners.click();
  assert.equal(f.progress[0].attributes["aria-current"], "step");
  assert.match(f.node("#app").innerHTML, /A branch/);
  assert.equal(f.run("selectedRegion.width"), 0.2);
  assert.equal(f.run("commitDraft.observation_text"), "A branch");
  assert.equal(f.run("commitDraft.selected_stage_id"), "flower_buds_present");
});

test("initial and revised forms render bounded vertical stage choices", () => {
  const f = fixture(false);
  const initial = f.run("observationForm(false)");
  assert.match(initial, /name="stage"/);
  assert.match(initial, /value="flower_buds_present"/);
  assert.match(initial, /Describe visible features only\. Do not choose the plant stage here\./);
  assert.doesNotMatch(initial, /id="interpretation"/);
  f.run(`projection.data.initial_attempt = {observation_text: "swollen bud", selected_stage_id: "flower_buds_present", interpretation_text: "Flower buds present", confidence: 4}`);
  const revised = f.run("observationForm(true)");
  assert.match(revised, /value="flower_buds_present" checked/);
  assert.match(revised, /Submit revised observation/);
});

test("saving a researcher note preserves unfinished participant fields and rectangle", async () => {
  const f = fixture();
  f.run(`projection.data.stage = "REOBSERVE"; selectedRegion = {x: 0.1, y: 0.1, width: 0.3, height: 0.3};`);
  f.node("#app").innerHTML = "Unfinished participant form";
  f.node("#observation").value = "Unsaved revision";
  await f.run('mutate("researcher-notes", {researcher_notes: "Saved note"})');
  assert.equal(f.node("#app").innerHTML, "Unfinished participant form");
  assert.equal(f.node("#observation").value, "Unsaved revision");
  assert.equal(f.run("selectedRegion.width"), 0.3);
  assert.equal(f.requests[0].options.headers["X-SeasonLens-Researcher"], "1");
});

test("researcher hint and participant response text is escaped", () => {
  const f = fixture();
  const summary = f.run('attemptSummary({observation_text: "<script>bad</script>", interpretation_text: "<img src=x>", selected_region: {}}, "Response")');
  assert.doesNotMatch(summary, /<script>|<img/);
  assert.match(summary, /&lt;script&gt;/);
});

test("fully correct feedback is rendered without a hint level", () => {
  const f = fixture(false);
  f.run(`projection.data.stage = "POSITIVE_FEEDBACK";
    projection.data.study_mode = "training";
    projection.data.condition = "observation-first-contingent";
    projection.data.initial_attempt = {selected_region: {x: 0.1, y: 0.1, width: 0.2, height: 0.2}, observation_text: "bud", selected_stage_id: "flower_buds_present", interpretation_text: "Flower buds present"};
    projection.data.hint = null;
    projection.data.positive_feedback = {text: "Good. Evidence matches the stage.", shown_at: "2026-09-22T00:00:00Z"};
    render();`);
  assert.match(f.node("#app").innerHTML, /Positive feedback/);
  assert.match(f.node("#app").innerHTML, /Good\. Evidence matches the stage\./);
  assert.doesNotMatch(f.node("#app").innerHTML, /Re-observe/);
  assert.doesNotMatch(f.node("#app").innerHTML, /hint-level|Level 1/);
});

test("reflection wording follows whether guidance was received", () => {
  const f = fixture(false);
  f.run(`projection.data.stage = "REFLECTION";
    projection.data.study_mode = "training";
    projection.data.initial_attempt = {selected_region: {x: 0.1, y: 0.1, width: 0.2, height: 0.2}, observation_text: "bud", selected_stage_id: "flower_buds_present", interpretation_text: "Flower buds present"};
    projection.data.revised_attempt = null;
    projection.data.expert_reveal = {target_region: {x: 0.1, y: 0.1, width: 0.2, height: 0.2}, relevant_region: "upper bud", diagnostic_cue: "closed bud", interpretation: "Flower buds present"};
    projection.data.hint_received = false;
    render();`);
  assert.match(f.node("#app").innerHTML, /What visual evidence was most important for your decision\?/);
  assert.doesNotMatch(f.node("#app").innerHTML, /after seeing the hint/);
  f.run("projection.data.hint_received = true; render();");
  assert.match(f.node("#app").innerHTML, /What did you notice after seeing the hint\?/);
});

const authoredRegions = {
  target_region: { id: "upper_bud_region", label: "upper bud", rect: {x: 0.31, y: 0.07, width: 0.11, height: 0.2} },
  distractor_regions: [{ id: "large_leaf_region", label: "large leaves", rect: {x: 0.25, y: 0.58, width: 0.5, height: 0.39} }],
};

test("researcher overlays show both attempts, target, distractor, IoUs and semantic labels", () => {
  const f = fixture();
  f.run(`researchRegions = ${JSON.stringify(authoredRegions)};
    researchLog = { initial_region: {x: 0.1, y: 0.1, width: 0.2, height: 0.2},
      revised_region: researchRegions.target_region.rect,
      initial_diagnostic: {selected_semantic_region: "large_leaf_region", selected_region_label: "large leaves", target_iou: 0, best_distractor_iou: 1, primary_error: "REGION_MISS"},
      revised_diagnostic: {selected_semantic_region: "upper_bud_region", selected_region_label: "upper bud", target_iou: 1, best_distractor_iou: 0, primary_error: "CORRECT"} };`);
  const html = f.run("researcherRegionPanels(researchRegions, researchLog, projection.data.item)");
  assert.equal((html.match(/class="expert-region"/g) || []).length, 2);
  assert.equal((html.match(/class="distractor-region"/g) || []).length, 2);
  assert.equal((html.match(/class="selection-region"/g) || []).length, 2);
  assert.match(html, /large_leaf_region/);
  assert.match(html, /upper_bud_region/);
  assert.match(html, /Target IoU/);
  assert.match(html, /Best distractor IoU/);
});

test("participant image and disabled researcher mode hide expert and distractor overlays before reveal", () => {
  const f = fixture(false);
  f.run(`researchRegions = ${JSON.stringify(authoredRegions)}; selectedRegion = researchRegions.distractor_regions[0].rect;`);
  const participant = f.run("imagePanel({interactive: true})");
  assert.match(participant, /selection-region/);
  assert.doesNotMatch(participant, /expert-region|distractor-region|upper_bud_region|large_leaf_region/);
  assert.equal(f.run("researcherRegionPanels(researchRegions, {}, projection.data.item)"), "");
  const reveal = f.run("imagePanel({expertRegion: researchRegions.target_region.rect})");
  assert.match(reveal, /expert-region/);
  assert.doesNotMatch(reveal, /distractor-region/);
});
