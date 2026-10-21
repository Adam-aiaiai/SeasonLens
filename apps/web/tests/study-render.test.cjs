const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const schema = JSON.parse(readFileSync(
  join(__dirname, "../../../extensions/seasonlens/data/formative_questionnaire_v3_1.json"), "utf8"));
const escaped = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");

class Element {
  constructor() {
    this.hidden = false;
    this.textContent = "";
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
  querySelectorAll(selector) { return selector === "span" ? this.spans : []; }
}

function fixture() {
  const elements = {
    "#study-app": new Element(),
    "#status": new Element(),
    "#study-progress": new Element(),
  };
  const context = vm.createContext({
    document: { querySelector: selector => elements[selector] || new Element() },
    fetch: async () => ({ ok: false, status: 401, json: async () => ({ error: "signed out" }) }),
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

test("all v3.1 A-E fields and B-D materials render with their authored shapes", () => {
  const f = fixture();
  for (const [sectionId, section] of Object.entries(schema.sections)) {
    for (const field of section.fields) {
      f.context.field = field;
      const html = f.run("questionField(field, {})");
      assert.match(html, new RegExp(`>${field.id}<`));
      assert.ok(html.includes(escaped(field.zh)));
      assert.ok(html.includes(escaped(field.en)));
      if (field.type === "choice") {
        assert.equal((html.match(/<option value=/g) || []).length, field.options.length + 1);
      }
      if (field.type === "confidence") {
        assert.equal((html.match(/<option value=/g) || []).length, 6);
      }
    }
    assert.ok(section.title.zh && section.title.en, `${sectionId} requires a bilingual title`);
  }

  for (const sectionId of ["B", "C", "D"]) {
    f.context.material = { images: schema.materials[sectionId] };
    f.context.sectionId = sectionId;
    const html = f.run("materialPanel(material, sectionId)");
    for (const image of schema.materials[sectionId]) {
      assert.ok(html.includes(image.image_path));
      assert.ok(html.includes(image.material_id));
    }
  }
});
