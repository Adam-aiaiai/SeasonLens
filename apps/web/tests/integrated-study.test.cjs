const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { createHash } = require("node:crypto");

const root = join(__dirname, "../../..");
const schema = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/formative_questionnaire_v3_2.json"), "utf8"));
const v31Schema = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/formative_questionnaire_v3_1.json"), "utf8"));
const legacySchema = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/formative_questionnaire_v3.json"), "utf8"));
const prototypeOne = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/demo_anemone_001.json"), "utf8"));
const prototypeTwo = JSON.parse(readFileSync(join(root, "extensions/seasonlens/data/demo_solidago_001.json"), "utf8"));
const studyJs = readFileSync(join(root, "apps/web/study.js"), "utf8");
const researcherJs = readFileSync(join(root, "apps/web/researcher.js"), "utf8");
const indexHtml = readFileSync(join(root, "apps/web/index.html"), "utf8");

test("v3.2 questionnaire preserves A-E and uses sequential Section B IDs", () => {
  assert.deepEqual(Object.keys(schema.sections), ["A", "B", "C", "D", "E"]);
  const fields = Object.values(schema.sections).flatMap(section => section.fields);
  assert.equal(fields.length, 30);
  assert.equal(fields.filter(field => field.required).length, 25);
  assert.deepEqual(schema.sections.B.fields.map(field => field.id),
    ["B1", "B2", "B3", "B4", "B4_CONFIDENCE"]);
  assert.deepEqual(schema.sections.D.fields.map(field => field.id),
    ["D1", "D2", "D3", "D4", "D_CONFIDENCE", "D5", "D6"]);
  assert.ok(schema.sections.A.fields.some(field => field.id === "A6_INFO"));
  assert.ok(schema.sections.B.fields.some(field => field.id === "B4_CONFIDENCE"));
  assert.ok(schema.sections.E.fields.some(field => field.id === "E3_WHY"));
});

test("v3.2 required and optional policy is explicit without changing preserved versions", () => {
  const required = Object.fromEntries(Object.entries(schema.sections).map(([section, value]) =>
    [section, value.fields.filter(field => field.required).map(field => field.id)]));
  assert.deepEqual(required, {
    A: ["A1", "A3"],
    B: ["B1", "B2", "B3", "B4", "B4_CONFIDENCE"],
    C: ["C1", "C2", "C3", "C4", "C5", "C6"],
    D: ["D1", "D2", "D3", "D4", "D_CONFIDENCE", "D5", "D6"],
    E: ["E1", "E2", "E3", "E3_WHY", "E4"],
  });
  assert.deepEqual(schema.sections.A.fields.filter(field => field.optional).map(field => field.id),
    ["A2", "A4", "A5", "A6", "A6_INFO"]);
  assert.ok(legacySchema.sections.A.fields.every(field => field.required === undefined));
  assert.deepEqual(v31Schema.sections.B.fields.map(field => field.id),
    ["B1", "B2", "B3", "B4", "B5", "B5_CONFIDENCE"]);
});

test("v3.2 preserves v3.1 materials and uses the supplied Solidago image for D", () => {
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
  assert.equal(schema.materials.D[0].image_path, "/assets/study/section-d-solidago.png");
  assert.notEqual(schema.materials.D[0].image_path, prototypeTwo.image_path);
  assert.deepEqual(schema.materials, v31Schema.materials);
});

test("v3.2 updates only the requested B and C questionnaire content", () => {
  const b4 = schema.sections.B.fields.find(field => field.id === "B4");
  assert.equal(b4.zh, "根据目前可见的证据，您能对植物的季节性状态或变化作出哪些判断？哪些地方仍不能确定？");
  assert.equal(b4.en, "Based on the visible evidence, what can you conclude about the plant’s seasonal condition or change, and what remains uncertain?");
  assert.equal(schema.sections.B.fields.find(field => field.id === "B4_CONFIDENCE").type, "confidence");
  assert.doesNotMatch(JSON.stringify(schema.sections.B), /观察距离|viewing distance/i);

  const expected = {
    C2: ["比较这两张图片时，您主要观察了植物的哪些部位？这些部位有什么不同？", "When comparing the two images, which parts of the plant did you focus on? What differences did you notice in those parts?"],
    C3: ["比较这两张图片时，有没有哪个地方让您觉得难以判断或不确定？为什么？如果没有，可以直接说明。", "When comparing the two images, was there anything you found difficult to judge or were unsure about? Why? If not, you may say so."],
    C4: ["根据两张图片中的变化，您认为这株植物可能正在经历什么生长变化？您为什么这样认为？", "Based on the differences between the two images, what growth-related change do you think the plant might be undergoing? Why do you think so?"],
  };
  for (const [id, [zh, en]] of Object.entries(expected)) {
    const field = schema.sections.C.fields.find(item => item.id === id);
    assert.deepEqual([field.zh, field.en, field.required], [zh, en, true]);
  }
  for (const id of ["C1", "C5", "C6"]) {
    assert.deepEqual(schema.sections.C.fields.find(field => field.id === id),
      v31Schema.sections.C.fields.find(field => field.id === id));
  }
});

test("questionnaire UI removes the non-scrolling overflow ancestor and gives sticky materials a section-height boundary", () => {
  const styles = readFileSync(join(root, "apps/web/styles.css"), "utf8");
  assert.match(styles, /\.study-card\.questionnaire-active \{ overflow: visible; \}/);
  assert.match(styles, /\.questionnaire-layout \{[^}]*align-items: stretch;/);
  assert.match(styles, /\.material-column \{[^}]*min-width: 0;/);
  assert.match(styles, /\.material-panel \{[^}]*position: sticky;/);
  assert.match(styles, /@media \(max-width: 740px\)[\s\S]*\.questionnaire-layout \{ display: block; \}/);
  assert.match(styles, /@media \(max-width: 740px\)[\s\S]*\.material-column \{ display: contents; \}/);
  assert.match(styles, /@media \(max-width: 740px\)[\s\S]*\.material-panel \{[^}]*max-height: 30vh;/);
  assert.match(styles, /\.required-marker \{ color: #78837d; \}/);
  assert.match(studyJs, /app\.classList\.toggle\("questionnaire-active", sectionIsActive\)/);
  for (const option of [
    '[1, "完全没把握", "No confidence"]',
    '[2, "把握较低", "Low confidence"]',
    '[3, "把握中等", "Moderate confidence"]',
    '[4, "把握较高", "High confidence"]',
    '[5, "很有把握", "Full confidence"]',
  ]) assert.ok(studyJs.includes(option), `missing confidence option: ${option}`);
});

test("default participant flow is v3.2, self-guided, and hides prototype progress", () => {
  assert.equal(schema.version, "3.2");
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
