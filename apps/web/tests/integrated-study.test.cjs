const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { createHash } = require("node:crypto");

const root = join(__dirname, "../../..");
const schema = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/formative_questionnaire_v3.json"), "utf8"));
const studyJs = readFileSync(join(root, "apps/web/study.js"), "utf8");
const researcherJs = readFileSync(join(root, "apps/web/researcher.js"), "utf8");

test("questionnaire schema preserves A-E IDs and approved subordinate fields", () => {
  assert.deepEqual(Object.keys(schema.sections), ["A", "B", "C", "D", "E"]);
  assert.deepEqual(schema.sections.D.fields.map(field => field.id),
    ["D1", "D2", "D3", "D4", "D_CONFIDENCE", "D5", "D6"]);
  assert.ok(schema.sections.A.fields.some(field => field.id === "A6_INFO"));
  assert.ok(schema.sections.B.fields.some(field => field.id === "B5_CONFIDENCE"));
  assert.ok(schema.sections.E.fields.some(field => field.id === "E3_WHY"));
});

test("B-D use exactly the approved embedded-image counts and stable material IDs", () => {
  assert.equal(schema.materials.B.length, 1);
  assert.equal(schema.materials.C.length, 2);
  assert.equal(schema.materials.D.length, 1);
  for (const section of ["B", "C", "D"]) {
    for (const material of schema.materials[section]) {
      assert.match(material.material_id, new RegExp(`^${section}_`));
      assert.match(material.sha256, /^[A-F0-9]{64}$/);
      assert.equal(material.source.document, "SeasonLens_Formative_Participant_Questionnaire_v3_Bilingual.docx");
      const bytes = readFileSync(join(root, "apps/web", material.image_path));
      assert.equal(createHash("sha256").update(bytes).digest("hex").toUpperCase(), material.sha256);
    }
  }
});

test("participant client supports draft saving, release waits, prototype routing and E", () => {
  assert.match(studyJs, /\/draft/);
  assert.match(studyJs, /WAIT_/);
  assert.match(studyJs, /prototype_url/);
  assert.match(studyJs, /\["A", "B", "C", "D", "E"\]/);
  assert.doesNotMatch(studyJs, /expert-region|diagnostic|correct_stage|hint-level/);
});

test("researcher client uses authenticated session and CSRF rather than debug header", () => {
  assert.match(researcherJs, /\/api\/researcher\/login/);
  assert.match(researcherJs, /X-CSRF-Token/);
  assert.doesNotMatch(researcherJs, /X-SeasonLens-Researcher/);
  assert.match(researcherJs, /debug=1.*do not grant access/);
  assert.match(researcherJs, /export\.zip/);
});
