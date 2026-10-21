import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from seasonlens import (
    FormativeStudyService,
    PersistentRepository,
    ResearcherAuth,
    SeasonLensService,
)


class IntegratedStudyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "study.db"
        self.repository = PersistentRepository(f"sqlite:///{self.db_path}")
        self.prototype = SeasonLensService(repository=self.repository)
        self.studies = FormativeStudyService(self.repository, self.prototype)

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def create(self):
        projection, token = self.studies.create("F-001", consent_acknowledged=True)
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
        waiting = self.studies.submit(study_id, token, projection["version"], {"A1": "prefer_not_to_answer"})
        self.assertEqual(waiting["stage"], "WAIT_B")
        self.assertNotIn("section", waiting)
        self.assertNotIn("material", waiting)
        with self.assertRaisesRegex(ValueError, "no participant questionnaire"):
            self.studies.save_draft(study_id, token, waiting["version"], {"B1": "early"})
        detail = self.studies.release(study_id, waiting["version"], "researcher")
        b = self.studies.participant_projection(study_id, token)
        self.assertEqual(detail["stage"], "B")
        self.assertEqual(b["material"]["images"][0]["material_id"], "B_COMPLETE_PLANT_001")
        self.assertNotIn("sha256", b["material"]["images"][0])
        self.assertNotIn("source", b["material"]["images"][0])
        text = json.dumps(b, ensure_ascii=False).lower()
        for forbidden in ("hint", "diagnostic", "expert", "correct answer", "target_region"):
            self.assertNotIn(forbidden, text)

    def test_exact_b_d_fields_draft_resume_and_confidence_validation(self):
        study_id, token, projection = self.create()
        waiting = self.studies.submit(study_id, token, projection["version"], {})
        self.studies.release(study_id, waiting["version"], "researcher")
        b = self.studies.participant_projection(study_id, token)
        ids = [field["id"] for field in b["section"]["fields"]]
        self.assertEqual(ids, ["B1", "B2", "B3", "B4", "B5", "B5_CONFIDENCE"])
        saved = self.studies.save_draft(study_id, token, b["version"], {"B1": "紫色花序", "B5_CONFIDENCE": 3})
        self.assertEqual(saved["draft"]["B1"], "紫色花序")
        waiting = self.studies.submit(study_id, token, saved["version"], saved["draft"])
        waiting = self.release_and_submit(study_id, token, "C", {"C5": 2})
        self.studies.release(study_id, waiting["version"], "researcher")
        d = self.studies.participant_projection(study_id, token)
        self.assertEqual([field["id"] for field in d["section"]["fields"]],
                         ["D1", "D2", "D3", "D4", "D_CONFIDENCE", "D5", "D6"])
        with self.assertRaisesRegex(ValueError, "D_CONFIDENCE"):
            self.studies.save_draft(study_id, token, d["version"], {"D_CONFIDENCE": 6})

    def test_full_sequence_three_prototype_items_e_and_exports(self):
        study_id, token, current = self.create()
        current = self.studies.submit(study_id, token, current["version"], {"A6": "never"})
        current = self.release_and_submit(study_id, token, "B", {"B5_CONFIDENCE": 3})
        current = self.release_and_submit(study_id, token, "C", {"C5": 3})
        current = self.release_and_submit(study_id, token, "D", {"D_CONFIDENCE": 2, "D5": "不需要帮助", "D6": "不需要帮助"})
        detail = self.studies.release(study_id, current["version"], "researcher")
        self.assertEqual(detail["stage"], "PROTOTYPE")
        projection = self.studies.start_prototype(study_id, token)
        session_ids = []
        while True:
            session_id = projection["data"]["session_id"]
            session_ids.append(session_id)
            item = self.prototype.catalog.get(projection["data"]["item"]["item_id"])
            payload = {
                "selected_region": item["target_region"]["rect"],
                "observation_text": item["accepted_cue_keywords"][0],
                "selected_stage_id": item["correct_stage_id"],
                "visual_evidence_reason": "Visible authored cue supports this stage.",
                "judgement_source": "image_evidence", "confidence": 4,
            }
            projection = self.prototype.submit_initial(session_id, payload)
            self.assertEqual(projection["data"]["stage"], "POSITIVE_FEEDBACK")
            self.prototype.reveal_expert_cue(session_id)
            self.prototype.begin_reflection(session_id)
            projection = self.prototype.submit_reflection(session_id, "No uncertainty remained.", "My confidence")
            self.studies.complete_prototype_if_final(session_id, projection)
            if not projection["data"]["has_next_item"]:
                break
            next_projection = self.prototype.next_item(session_id)
            self.studies.link_next_prototype(session_id, next_projection)
            projection = next_projection
        self.assertEqual(len(session_ids), 3)
        e = self.studies.participant_projection(study_id, token)
        self.assertEqual(e["stage"], "E")
        self.assertEqual([field["id"] for field in e["section"]["fields"]],
                         ["E1", "E2", "E3", "E3_WHY", "E4"])
        complete = self.studies.submit(study_id, token, e["version"], {"E3": "on_request", "E3_WHY": "保留自主判断"})
        self.assertEqual(complete["stage"], "COMPLETE")
        combined = self.studies.combined_export(study_id)
        self.assertEqual(combined["prototype_session_ids"], session_ids)
        self.assertEqual(len(combined["prototype_sessions"]), 3)
        self.assertTrue(all(log["events"] for log in combined["prototype_sessions"]))
        self.assertIn("D_CONFIDENCE", self.studies.export_csv(study_id))
        xlsx = self.studies.export_xlsx(study_id)
        self.assertTrue(xlsx.startswith(b"PK"))
        with zipfile.ZipFile(io.BytesIO(self.studies.export_zip(study_id))) as archive:
            names = archive.namelist()
            self.assertIn("combined-study.json", names)
            self.assertIn("combined-study.xlsx", names)
            self.assertEqual(len([name for name in names if name.startswith("prototype/") and name.endswith(".json")]), 3)

    def test_prototype_state_survives_repository_and_service_restart(self):
        study_id, token, current = self.create()
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
