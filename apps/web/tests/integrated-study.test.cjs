const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { createHash } = require("node:crypto");

const root = join(__dirname, "../../..");
const schema = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/formative_questionnaire_v3_1.json"), "utf8"));
const legacySchema = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/formative_questionnaire_v3.json"), "utf8"));
const prototypeOne = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/demo_anemone_001.json"), "utf8"));
const prototypeTwo = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/demo_solidago_001.json"), "utf8"));
const studyJs = readFileSync(join(root, "apps/web/study.js"), "utf8");
const researcherJs = readFileSync(join(root, "apps/web/researcher.js"), "utf8");
const indexHtml = readFileSync(join(root, "apps/web/index.html"), "utf8");

test("questionnaire schema preserves A-E IDs and approved subordinate fields", () => {
  assert.deepEqual(Object.keys(schema.sections), ["A", "B", "C", "D", "E"]);
  assert.deepEqual(schema.sections.D.fields.map(field => field.id),
    ["D1", "D2", "D3", "D4", "D_CONFIDENCE", "D5", "D6"]);
  assert.ok(schema.sections.A.fields.some(field => field.id === "A6_INFO"));
  assert.ok(schema.sections.B.fields.some(field => field.id === "B5_CONFIDENCE"));
  assert.ok(schema.sections.E.fields.some(field => field.id === "E3_WHY"));
});

test("v3.1 uses prototype item 1 for B, item 2 for D, and preserves C", () => {
  assert.equal(schema.materials.B.length, 1);
  assert.equal(schema.materials.C.length, 2);
  assert.equal(schema.materials.D.length, 1);
  for (const section of ["B", "C", "D"]) {
    for (const material of schema.materials[section]) {
      assert.match(material.material_id, new RegExp(`^${section}_`));
      assert.match(material.sha256, /^[A-F0-9]{64}$/);
      const bytes = readFileSync(join(root, "apps/web", material.image_path));
      assert.equal(createHash("sha256").update(bytes).digest("hex").toUpperCase(), material.sha256);
    }
  }
  assert.equal(schema.materials.B[0].image_path, prototypeOne.image_path);
  assert.equal(schema.materials.D[0].image_path, prototypeTwo.image_path);
  assert.deepEqual(schema.materials.C, legacySchema.materials.C);
});

test("default participant flow is self-guided and hides prototype progress", () => {
  assert.equal(schema.version, "3.1");
  assert.equal(schema.study_defaults.study_mode, "self_guided");
  assert.equal(schema.study_defaults.enable_prototype_stage, false);
  assert.match(studyJs, /\/draft/);
  assert.match(studyJs, /next section begins immediately/);
  assert.doesNotMatch(indexHtml, /data-stage="PROTOTYPE"/);
  assert.doesNotMatch(indexHtml, /prototype\.html/);
  assert.match(studyJs, /\["A", "B", "C", "D", "E"\]/);
  assert.doesNotMatch(studyJs, /expert-region|diagnostic|correct_stage|hint-level/);
});

test("seasonal bilingual wording preserves observation-first uncertainty", () => {
  for (const section of ["B", "C", "D"]) {
    assert.match(schema.sections[section].instructions.zh, /季节/);
    assert.match(schema.sections[section].instructions.en, /seasonal/i);
    assert.match(schema.sections[section].instructions.en, /visible|describe/i);
  }
  assert.match(schema.sections.B.fields.find(field => field.id === "B1").en, /seasonal changes/i);
  assert.match(schema.sections.D.fields.find(field => field.id === "D1").en, /seasonal condition/i);
  assert.match(JSON.stringify(schema.sections), /不确定|reliable change|uncertain/);
  assert.doesNotMatch(JSON.stringify(schema.sections.E), /prototype experience|工具体验/);
});

test("researcher client uses authenticated session and CSRF rather than debug header", () => {
  assert.match(researcherJs, /\/api\/researcher\/login/);
  assert.match(researcherJs, /X-CSRF-Token/);
  assert.doesNotMatch(researcherJs, /X-SeasonLens-Researcher/);
  assert.match(researcherJs, /debug=1.*do not grant access/);
  assert.match(researcherJs, /export\.zip/);
});
