import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from seasonlens import (
    FormativeStudyService,
    PersistentRepository,
    QuestionnaireValidationError,
    ResearcherAuth,
    SeasonLensService,
)


class IntegratedStudyTests(unittest.TestCase):
    REQUIRED = {
        "A": {"A1": "prefer_not_to_answer", "A3": "not_sure"},
        "B": {"B1": "Not sure", "B2": "Not sure", "B3": "Not sure", "B4": "Not sure",
              "B4_CONFIDENCE": 3},
        "C": {"C1": "Not sure", "C2": "Not sure", "C3": "Not sure", "C4": "Not sure",
              "C5": 3, "C6": "Not sure"},
        "D": {"D1": "Not sure", "D2": "Not sure", "D3": "Not sure", "D4": "Not sure",
              "D_CONFIDENCE": 3, "D5": "No help needed", "D6": "No help needed"},
        "E": {"E1": "Not sure", "E2": "No help needed", "E3": "on_request",
              "E3_WHY": "Preserves autonomy", "E4": "Not sure"},
    }

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "study.db"
        self.repository = PersistentRepository(f"sqlite:///{self.db_path}")
        self.prototype = SeasonLensService(repository=self.repository)
        self.studies = FormativeStudyService(self.repository, self.prototype)

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def create(self, *, legacy=False):
        projection, token = self.studies.create("F-001", consent_acknowledged=True)
        if legacy:
            config = {
                "instrument_id": "SeasonLens_Formative_Participant_Questionnaire_v3_Bilingual",
                "questionnaire_version": 3,
                "material_set_version": 3,
                "study_mode": "researcher_assisted",
                "enable_prototype_stage": True,
            }
            with self.repository.transaction() as cursor:
                cursor.execute("UPDATE studies SET config_json=? WHERE study_id=?",
                               (json.dumps(config), projection["study_id"]))
            projection = self.studies.participant_projection(projection["study_id"], token)
        return projection["study_id"], token, projection

    def release_and_submit(self, study_id, token, section, values):
        waiting = self.studies.participant_projection(study_id, token)
        detail = self.studies.release(study_id, waiting["version"], "researcher")
        self.assertEqual(detail["stage"], section)
        current = self.studies.participant_projection(study_id, token)
        return self.studies.submit(study_id, token, current["version"], values)

    def test_authoritative_fields_and_backend_gating_hide_future_materials(self):
        study_id, token, projection = self.create()
        self.assertEqual(projection["stage"], "A")
        self.assertEqual([field["id"] for field in projection["section"]["fields"]],
                         ["A1", "A2", "A3", "A4", "A5", "A6", "A6_INFO"])
        b = self.studies.submit(study_id, token, projection["version"], self.REQUIRED["A"])
        self.assertEqual(b["stage"], "B")
        self.assertEqual(b["progress"]["stages"], ["A", "B", "C", "D", "E"])
        self.assertEqual(b["material"]["images"][0]["material_id"], "B_PROTO_ITEM_1_ANEMONE_001")
        self.assertEqual(b["material"]["images"][0]["image_path"], "/assets/real/anemone_virginiana_001.jpg")
        self.assertNotIn("sha256", b["material"]["images"][0])
        self.assertNotIn("source", b["material"]["images"][0])
        text = json.dumps(b, ensure_ascii=False).lower()
        for forbidden in ("hint", "diagnostic", "expert", "correct answer", "target_region"):
            self.assertNotIn(forbidden, text)

    def test_exact_b_d_fields_draft_resume_and_confidence_validation(self):
        study_id, token, projection = self.create()
        b = self.studies.submit(study_id, token, projection["version"], self.REQUIRED["A"])
        ids = [field["id"] for field in b["section"]["fields"]]
        self.assertEqual(ids, ["B1", "B2", "B3", "B4", "B4_CONFIDENCE"])
        saved = self.studies.save_draft(study_id, token, b["version"], {"B1": "紫色花序", "B4_CONFIDENCE": 3})
        self.assertEqual(saved["draft"]["B1"], "紫色花序")
        c = self.studies.submit(study_id, token, saved["version"], {**self.REQUIRED["B"], **saved["draft"]})
        self.assertEqual([image["material_id"] for image in c["material"]["images"]],
                         ["C_SAME_PLANT_T1_001", "C_SAME_PLANT_T2_001"])
        d = self.studies.submit(study_id, token, c["version"], {**self.REQUIRED["C"], "C5": 2})
        self.assertEqual(d["material"]["images"][0]["material_id"], "D_PROTO_ITEM_2_SOLIDAGO_001")
        self.assertEqual(d["material"]["images"][0]["image_path"], "/assets/study/section-d-solidago.png")
        self.assertEqual([field["id"] for field in d["section"]["fields"]],
                         ["D1", "D2", "D3", "D4", "D_CONFIDENCE", "D5", "D6"])
        with self.assertRaisesRegex(ValueError, "D_CONFIDENCE"):
            self.studies.save_draft(study_id, token, d["version"], {"D_CONFIDENCE": 6})

    def test_full_self_guided_sequence_without_prototype_and_exports(self):
        study_id, token, current = self.create()
        current = self.studies.submit(study_id, token, current["version"], {**self.REQUIRED["A"], "A6": "never"})
        current = self.studies.submit(study_id, token, current["version"], self.REQUIRED["B"])
        current = self.studies.submit(study_id, token, current["version"], self.REQUIRED["C"])
        e = self.studies.submit(study_id, token, current["version"], {**self.REQUIRED["D"], "D_CONFIDENCE": 2})
        self.assertEqual(e["stage"], "E")
        self.assertEqual([field["id"] for field in e["section"]["fields"]],
                         ["E1", "E2", "E3", "E3_WHY", "E4"])
        complete = self.studies.submit(study_id, token, e["version"], self.REQUIRED["E"])
        self.assertEqual(complete["stage"], "COMPLETE")
        combined = self.studies.combined_export(study_id)
        self.assertEqual(combined["questionnaire_version"], "3.2")
        self.assertEqual(combined["material_set_version"], "3.1")
        self.assertEqual(combined["study_mode"], "self_guided")
        self.assertEqual(combined["prototype_session_ids"], [])
        self.assertEqual(combined["prototype_sessions"], [])
        self.assertIn("D_CONFIDENCE", self.studies.export_csv(study_id))
        xlsx = self.studies.export_xlsx(study_id)
        self.assertTrue(xlsx.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(xlsx)) as workbook:
            xml = "\n".join(
                workbook.read(name).decode("utf-8")
                for name in workbook.namelist()
                if name.endswith(".xml")
            )
            self.assertIn("Questionnaire version", xml)
            self.assertIn("3.2", xml)
        with zipfile.ZipFile(io.BytesIO(self.studies.export_zip(study_id))) as archive:
            names = archive.namelist()
            self.assertIn("combined-study.json", names)
            self.assertIn("combined-study.xlsx", names)
            self.assertEqual(len([name for name in names if name.startswith("prototype/") and name.endswith(".json")]), 0)

    def test_self_guided_draft_persists_after_restart_and_duplicate_submit_is_rejected(self):
        study_id, token, current = self.create()
        current = self.studies.submit(study_id, token, current["version"], self.REQUIRED["A"])
        saved = self.studies.save_draft(study_id, token, current["version"], {"B1": "可见花蕾"})
        stale_version = saved["version"]
        self.repository.close()
        self.repository = PersistentRepository(f"sqlite:///{self.db_path}")
        self.prototype = SeasonLensService(repository=self.repository)
        self.studies = FormativeStudyService(self.repository, self.prototype)
        restored = self.studies.participant_projection(study_id, token)
        self.assertEqual(restored["draft"]["B1"], "可见花蕾")
        submitted = self.studies.submit(study_id, token, stale_version, {**self.REQUIRED["B"], **restored["draft"]})
        self.assertEqual(submitted["stage"], "C")
        with self.assertRaisesRegex(ValueError, "changed|cannot be submitted"):
            self.studies.submit(study_id, token, stale_version, self.REQUIRED["C"])

    def test_new_study_rejects_release_and_prototype_start(self):
        study_id, token, current = self.create()
        with self.assertRaisesRegex(ValueError, "do not require researcher release"):
            self.studies.release(study_id, current["version"], "researcher")
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.studies.start_prototype(study_id, token)

    def test_required_validation_blocks_each_section_but_allows_incomplete_drafts(self):
        study_id, token, current = self.create()
        for section in ("A", "B", "C", "D", "E"):
            self.assertEqual(current["stage"], section)
            before_version = current["version"]
            with self.assertRaises(QuestionnaireValidationError) as failure:
                self.studies.submit(study_id, token, before_version, {})
            self.assertTrue(failure.exception.errors)
            unchanged = self.studies.participant_projection(study_id, token)
            self.assertEqual(unchanged["stage"], section)
            self.assertEqual(unchanged["version"], before_version)
            draft = self.studies.save_draft(study_id, token, before_version, {})
            self.assertEqual(draft["stage"], section)
            current = self.studies.submit(study_id, token, draft["version"], self.REQUIRED[section])
        self.assertEqual(current["stage"], "COMPLETE")

    def test_partial_conditional_and_optional_validation(self):
        study_id, token, current = self.create()
        with self.assertRaises(QuestionnaireValidationError) as failure:
            self.studies.submit(study_id, token, current["version"], {"A1": "prefer_not_to_answer"})
        self.assertEqual([item["question_id"] for item in failure.exception.errors], ["A3"])
        current = self.studies.submit(study_id, token, current["version"], self.REQUIRED["A"])
        for section in ("B", "C", "D"):
            current = self.studies.submit(study_id, token, current["version"], self.REQUIRED[section])
        without_why = {key: value for key, value in self.REQUIRED["E"].items() if key != "E3_WHY"}
        with self.assertRaises(QuestionnaireValidationError) as failure:
            self.studies.submit(study_id, token, current["version"], without_why)
        self.assertEqual([item["question_id"] for item in failure.exception.errors], ["E3_WHY"])

    def test_hard_delete_removes_only_selected_study_and_keeps_minimal_audit(self):
        deleted_id, _, _ = self.create()
        kept_id, _, _ = self.create()
        prototype = self.prototype.create_session("F-001", "demo_anemone_001")
        session_id = prototype["data"]["session_id"]
        at = "2026-01-01T00:00:00+00:00"
        self.repository.add_prototype_session(
            deleted_id, 0, session_id, "demo_anemone_001", at,
            self.studies._event(deleted_id, "prototype.session-linked", "participant", {}, at))

        result = self.studies.delete_study(deleted_id, "lead", "DELETE")
        self.assertTrue(result["deleted"])
        self.assertIsNone(self.repository.get_study(deleted_id))
        self.assertIsNotNone(self.repository.get_study(kept_id))
        self.assertIsNone(self.repository.load_prototype_session(session_id))
        with self.repository.transaction() as cursor:
            cursor.execute("SELECT study_id, actor_id, child_counts_json FROM study_deletion_audit")
            audit = cursor.fetchone()
        self.assertEqual(audit[0], deleted_id)
        self.assertEqual(audit[1], "lead")
        self.assertNotIn("F-001", audit[2])

    def test_researcher_detail_has_stable_version_fields_for_v3_and_v3_2(self):
        current_id, _, _ = self.create()
        legacy_id, _, _ = self.create(legacy=True)
        current = self.studies.researcher_detail(current_id)
        legacy = self.studies.researcher_detail(legacy_id)
        self.assertEqual((current["questionnaire_version"], current["material_set_version"],
                          current["study_mode"]), ("3.2", "3.1", "self_guided"))
        self.assertEqual((legacy["questionnaire_version"], legacy["material_set_version"],
                          legacy["study_mode"]), (3, 3, "researcher_assisted"))
        self.assertEqual(current["config"]["questionnaire_version"], current["questionnaire_version"])
        self.assertEqual(legacy["config"]["questionnaire_version"], legacy["questionnaire_version"])

    def test_in_progress_v3_1_study_resumes_against_preserved_schema(self):
        v31_path = Path(__file__).resolve().parents[2] / "data" / "formative_questionnaire_v3_1.json"
        v31_service = FormativeStudyService(self.repository, self.prototype, schema_path=v31_path)
        projection, token = v31_service.create("F-V31", consent_acknowledged=True)
        study_id = projection["study_id"]
        projection = v31_service.submit(study_id, token, projection["version"], self.REQUIRED["A"])
        old_draft = {"B4": "Changed viewing angle", "B5": "Seasonal judgment", "B5_CONFIDENCE": 4}
        v31_service.save_draft(study_id, token, projection["version"], old_draft)

        active_v32_service = FormativeStudyService(self.repository, self.prototype)
        resumed = active_v32_service.participant_projection(study_id, token)
        self.assertEqual([field["id"] for field in resumed["section"]["fields"]],
                         ["B1", "B2", "B3", "B4", "B5", "B5_CONFIDENCE"])
        self.assertEqual(resumed["draft"], old_draft)
        v31_required = {"B1": "One", "B2": "Two", "B3": "Three", **old_draft}
        submitted = active_v32_service.submit(study_id, token, resumed["version"], v31_required)
        self.assertEqual(submitted["stage"], "C")
        exported = active_v32_service.combined_export(study_id)
        self.assertEqual(exported["questionnaire_version"], "3.1")
        self.assertEqual(exported["questionnaire"]["B"]["response"]["B4"], "Changed viewing angle")
        self.assertEqual(exported["questionnaire"]["B"]["response"]["B5"], "Seasonal judgment")
        self.assertIn("B5_CONFIDENCE", active_v32_service.export_csv(study_id))

    def test_unknown_questionnaire_version_exports_raw_ids_without_guessing(self):
        study_id, token, current = self.create()
        current = self.studies.submit(study_id, token, current["version"], self.REQUIRED["A"])
        saved = self.studies.save_draft(study_id, token, current["version"], {"B4": "Raw answer"})
        study = self.repository.get_study(study_id)
        config = {**study["config"], "questionnaire_version": "unknown-preserved"}
        with self.repository.transaction() as cursor:
            cursor.execute("UPDATE studies SET config_json=? WHERE study_id=?",
                           (json.dumps(config), study_id))
        exported = self.studies.combined_export(study_id)
        self.assertEqual(exported["questionnaire_version"], "unknown-preserved")
        self.assertEqual(exported["questionnaire"]["B"]["draft"]["B4"], "Raw answer")
        with self.assertRaisesRegex(ValueError, "Unsupported questionnaire version"):
            self.studies.participant_projection(study_id, token)

    def test_migration_marks_preexisting_study_as_legacy_without_changing_stage(self):
        legacy_path = Path(self.directory.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        connection.execute("""CREATE TABLE studies (
            study_id TEXT PRIMARY KEY, participant_id TEXT NOT NULL,
            resume_token_hash TEXT NOT NULL, stage TEXT NOT NULL,
            version INTEGER NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, completed_at TEXT,
            researcher_metadata_json TEXT NOT NULL)""")
        connection.execute("""INSERT INTO studies VALUES
            ('legacy-study', 'F-OLD', 'hash', 'WAIT_B', 7,
             '2025-01-01T00:00:00Z', '2025-01-01T00:10:00Z', NULL, '{}')""")
        connection.commit()
        connection.close()

        migrated = PersistentRepository(f"sqlite:///{legacy_path}")
        try:
            study = migrated.get_study("legacy-study")
            self.assertEqual(study["stage"], "WAIT_B")
            self.assertEqual(study["version"], 7)
            self.assertEqual(study["config"]["questionnaire_version"], 3)
            self.assertEqual(study["config"]["study_mode"], "researcher_assisted")
            self.assertTrue(study["config"]["enable_prototype_stage"])
        finally:
            migrated.close()

    def test_prototype_state_survives_repository_and_service_restart(self):
        study_id, token, current = self.create(legacy=True)
        current = self.studies.submit(study_id, token, current["version"], {})
        current = self.release_and_submit(study_id, token, "B", {})
        current = self.release_and_submit(study_id, token, "C", {})
        current = self.release_and_submit(study_id, token, "D", {})
        self.studies.release(study_id, current["version"], "researcher")
        projection = self.studies.start_prototype(study_id, token)
        session_id = projection["data"]["session_id"]
        self.repository.close()
        self.repository = PersistentRepository(f"sqlite:///{self.db_path}")
        restored = SeasonLensService(repository=self.repository)
        self.assertEqual(restored.participant_projection(session_id)["data"]["stage"], "OBSERVE")
        self.assertEqual(restored.export_study_log(session_id)["participant_id"], "F-001")


class ResearcherAuthTests(unittest.TestCase):
    def test_authentication_csrf_and_expiry_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = PersistentRepository(f"sqlite:///{Path(directory) / 'auth.db'}")
            try:
                auth = ResearcherAuth(repository, username="lead", development_password="secret-password")
                with self.assertRaises(PermissionError):
                    auth.login("lead", "wrong")
                token, session = auth.login("lead", "secret-password")
                self.assertEqual(auth.authenticate(token)["username"], "lead")
                with self.assertRaises(PermissionError):
                    auth.require_csrf(token, "wrong")
                self.assertEqual(auth.require_csrf(token, session["csrf_token"])["username"], "lead")
                auth.logout(token)
                with self.assertRaises(PermissionError):
                    auth.authenticate(token)
            finally:
                repository.close()
