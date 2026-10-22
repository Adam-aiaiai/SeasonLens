"""HTTP contract checks using the existing stdlib server and a temporary log directory."""
import importlib.util
import json
import os
import socket
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from seasonlens import FormativeStudyService, PersistentRepository, ResearcherAuth, SeasonLensService


class ApiTests(unittest.TestCase):
    REQUIRED = {
        "A": {"A1": "prefer_not_to_answer", "A3": "not_sure"},
        "B": {"B1": "Not sure", "B2": "Not sure", "B3": "Not sure", "B4": "Not sure", "B4_CONFIDENCE": 3},
        "C": {"C1": "Not sure", "C2": "Not sure", "C3": "Not sure", "C4": "Not sure", "C5": 3, "C6": "Not sure"},
        "D": {"D1": "Not sure", "D2": "Not sure", "D3": "Not sure", "D4": "Not sure", "D_CONFIDENCE": 3, "D5": "No help needed", "D6": "No help needed"},
        "E": {"E1": "Not sure", "E2": "No help needed", "E3": "on_request", "E3_WHY": "Autonomy", "E4": "Not sure"},
    }
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[4]
        spec = importlib.util.spec_from_file_location("seasonlens_api", root / "apps/api/main.py")
        cls.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.api)
        cls.api.SeasonLensHandler.log_message = lambda *args: None
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.api.SeasonLensHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        repository = PersistentRepository(f"sqlite:///{Path(self.directory.name) / 'test.db'}")
        self.addCleanup(repository.close)
        self.api.REPOSITORY = repository
        self.api.SERVICE = SeasonLensService(export_directory=Path(self.directory.name), repository=repository)
        self.api.STUDIES = FormativeStudyService(repository, self.api.SERVICE)
        self.api.AUTH = ResearcherAuth(repository, username="researcher", development_password="test-password")
        self.researcher_cookie = ""
        self.participant_cookie = ""
        self.csrf = ""
        status, text, headers = self.request("/api/researcher/login", {"username": "researcher", "password": "test-password"})
        self.assertEqual(status, 200)
        self.researcher_cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = json.loads(text)["csrf_token"]

    def request(self, path, body=None, *, researcher=False, participant=False, method=None):
        headers = {"Content-Type": "application/json"}
        cookies = []
        if researcher:
            cookies.append(self.researcher_cookie)
            headers["X-CSRF-Token"] = self.csrf
        if participant:
            cookies.append(self.participant_cookie)
        if cookies:
            headers["Cookie"] = "; ".join(cookies)
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                text = response.read().decode("utf-8-sig")
                return response.status, text, response.headers
        except HTTPError as error:
            return error.code, error.read().decode(), error.headers

    def request_bytes(self, path, *, researcher=False):
        headers = {}
        if researcher:
            headers["Cookie"] = self.researcher_cookie
            headers["X-CSRF-Token"] = self.csrf
        request = Request(self.base + path, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def create(self):
        status, text, _ = self.request("/api/sessions", {"participant_id": "api-test"})
        self.assertEqual(status, 201)
        return json.loads(text)["data"]["session_id"]

    def test_production_server_uses_exclusive_port_binding(self):
        server = self.api.SeasonLensHTTPServer(("127.0.0.1", 0), self.api.SeasonLensHandler)
        self.addCleanup(server.server_close)
        self.assertFalse(server.allow_reuse_address)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.assertEqual(
                server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE), 1)

    def test_local_env_loader_preserves_hash_characters_and_process_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "SEASONLENS_TEST_FILE_VALUE=pbkdf2_sha256$600000$salt$digest\n"
                "SEASONLENS_TEST_OVERRIDE=file-value\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"SEASONLENS_TEST_OVERRIDE": "process-value"}):
                os.environ.pop("SEASONLENS_TEST_FILE_VALUE", None)
                try:
                    loaded = self.api.load_local_environment(env_path)
                    self.assertEqual(
                        os.environ["SEASONLENS_TEST_FILE_VALUE"],
                        "pbkdf2_sha256$600000$salt$digest",
                    )
                    self.assertEqual(os.environ["SEASONLENS_TEST_OVERRIDE"], "process-value")
                    self.assertEqual(loaded, ("SEASONLENS_TEST_FILE_VALUE",))
                finally:
                    os.environ.pop("SEASONLENS_TEST_FILE_VALUE", None)

    def test_catalog_and_researcher_mode_gate(self):
        status, text, _ = self.request("/api/items")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(text)), 3)
        self.assertEqual([item["item_id"] for item in json.loads(text)], [
            "demo_anemone_001", "demo_solidago_001", "demo_butterfly_weed_001",
        ])
        session_id = self.create()
        for suffix in ["log", "researcher", "log.csv"]:
            self.assertEqual(self.request(f"/api/sessions/{session_id}/{suffix}")[0], 401)
            self.assertEqual(self.request(f"/api/sessions/{session_id}/{suffix}", researcher=True)[0], 200)
        for suffix in ["hint-override", "researcher-notes", "reset"]:
            self.assertEqual(self.request(f"/api/sessions/{session_id}/{suffix}", {}, researcher=False)[0], 401)

    def test_http_flow_override_notes_and_exports(self):
        session_id = self.create()
        base = f"/api/sessions/{session_id}"
        initial = {"selected_region": {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2},
                   "observation_text": "a green shape", "selected_stage_id": "flower_buds_present",
                   "visual_evidence_reason": "The shape appears near the stem tip.",
                   "judgement_source": "image_evidence", "confidence": 3}
        self.assertEqual(self.request(base + "/initial-observation", initial)[0], 200)
        self.assertEqual(self.request(base + "/hint-override", {"hint_id": "demo_anemone_feature_02"}, researcher=True)[0], 200)
        self.assertEqual(self.request(base + "/researcher-notes", {"researcher_notes": "Private note"}, researcher=True)[0], 200)
        revision = dict(initial, observation_text="rounded closed flower buds")
        for action, payload in [("reobserve", {}), ("revision", revision), ("reveal", {}),
                                ("reflection-stage", {}), ("reflection", {"reflection_text": "Checked again", "reflection_category": "My confidence"})]:
            self.assertEqual(self.request(base + "/" + action, payload)[0], 200)
        status, text, _ = self.request(base + "/log", researcher=True)
        log = json.loads(text)
        self.assertEqual(log["reflection_category"], "My confidence")
        self.assertEqual(log["hint_learning_reflection"], "Checked again")
        self.assertEqual(log["automatic_hint_id"], "demo_anemone_feature_01")
        self.assertEqual(log["actual_hint_id"], "demo_anemone_feature_02")
        self.assertEqual(log["researcher_notes"], "Private note")
        self.assertEqual(log["initial_visual_evidence_reason"], "The shape appears near the stem tip.")
        self.assertEqual(log["initial_judgement_source"], "image_evidence")
        status, text, headers = self.request(base + "/log.csv", researcher=True)
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("Private note", text)
        self.assertIn("initial_visual_evidence_reason", text)
        self.assertIn("initial_judgement_source", text)
        self.assertIn("hint_learning_reflection", text)
        self.assertIn("Checked again", text)
        status, text, _ = self.request(base + "/next-item", {})
        self.assertEqual(json.loads(text)["data"]["item"]["item_id"], "demo_solidago_001")
        saved = json.loads((Path(self.directory.name) / f"{session_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["stage"], "COMPLETE")

    def test_participant_errors_do_not_expose_internal_state(self):
        base = f"/api/sessions/{self.create()}"
        status, text, _ = self.request(base + "/reveal", {})
        self.assertEqual(status, 409)
        self.assertNotIn("REVISED_COMMITTED", text)
        self.assertNotIn("OBSERVE", text)
        status, text, _ = self.request(base + "/reveal", {}, researcher=True)
        self.assertIn("REVISED_COMMITTED", text)

    def test_semantic_hints_and_revision_diagnostics_through_http(self):
        base = f"/api/sessions/{self.create()}"
        item = self.api.SERVICE.catalog.get("demo_anemone_001")
        payload = {"selected_region": item["distractor_regions"][0]["rect"],
                   "observation_text": "a leaf", "selected_stage_id": "fruiting",
                   "visual_evidence_reason": "I mostly noticed a leaf.",
                   "judgement_source": "guessing", "confidence": 2}
        status, text, _ = self.request(base + "/initial-observation", payload)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["data"]["hint"]["hint_id"], "demo_anemone_large_leaf_01")
        self.assertNotIn('"selected_semantic_region":', text)
        status, text, _ = self.request(base + "/researcher", researcher=True)
        self.assertEqual(status, 200)
        researcher = json.loads(text)
        self.assertEqual(researcher["log"]["selected_semantic_region"], "large_leaf_region")
        self.assertEqual(researcher["regions"]["target_region"]["id"], "upper_bud_region")
        self.assertEqual(self.request(base + "/reobserve", {})[0], 200)
        payload.update(selected_region=item["target_region"]["rect"], observation_text="closed flower buds", selected_stage_id="flower_buds_present")
        self.assertEqual(self.request(base + "/revision", payload)[0], 200)
        status, text, _ = self.request(base + "/log", researcher=True)
        log = json.loads(text)
        self.assertEqual(log["initial_selected_semantic_region"], "large_leaf_region")
        self.assertEqual(log["revised_selected_semantic_region"], "upper_bud_region")

    def test_integrated_study_cookie_self_guided_and_export_security(self):
        status, text, headers = self.request("/api/studies", {"participant_id": "F-HTTP", "consent_acknowledged": True})
        self.assertEqual(status, 201)
        created = json.loads(text)
        study_id = created["study_id"]
        self.participant_cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, text, _ = self.request(f"/api/studies/{study_id}/submit",
                                      {"version": created["version"], "values": {**self.REQUIRED["A"], "A6": "never"}}, participant=True)
        participant = json.loads(text)
        self.assertEqual(participant["stage"], "B")
        self.assertEqual(participant["study_mode"], "self_guided")
        self.assertEqual(participant["material"]["images"][0]["image_path"],
                         "/assets/real/anemone_virginiana_001.jpg")
        self.assertEqual(self.request(f"/api/researcher/studies/{study_id}/release",
                                      {"version": participant["version"]})[0], 401)
        self.assertEqual(self.request(f"/api/researcher/studies/{study_id}/release",
                                      {"version": participant["version"]}, researcher=True)[0], 409)
        status, text, _ = self.request(f"/api/studies/{study_id}", participant=True)
        participant = json.loads(text)
        self.assertEqual(participant["stage"], "B")
        self.assertNotIn("diagnostic", text.lower())
        self.assertEqual(self.request("/api/researcher/studies")[0], 401)
        status, text, _ = self.request("/api/researcher/studies", researcher=True)
        self.assertEqual(status, 200)
        self.assertIn(study_id, [row["study_id"] for row in json.loads(text)])
        self.assertEqual(self.request(f"/api/researcher/studies/{study_id}")[0], 401)
        status, text, _ = self.request(f"/api/researcher/studies/{study_id}", researcher=True)
        self.assertEqual(status, 200)
        detail = json.loads(text)
        self.assertEqual(detail["questionnaire_version"], "3.2")
        self.assertEqual(detail["material_set_version"], "3.1")
        self.assertEqual(detail["study_mode"], "self_guided")
        self.assertEqual(self.request(f"/api/researcher/studies/{study_id}/export.json")[0], 401)
        status, text, headers = self.request(f"/api/researcher/studies/{study_id}/export.json", researcher=True)
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(json.loads(text)["study"]["participant_id"], "F-HTTP")
        status, payload, _ = self.request_bytes(
            f"/api/researcher/studies/{study_id}/export.csv", researcher=True)
        self.assertEqual(status, 200)
        self.assertIn(b"questionnaire_version", payload)
        for suffix in ("export.xlsx", "export.zip"):
            status, payload, _ = self.request_bytes(
                f"/api/researcher/studies/{study_id}/{suffix}", researcher=True)
            self.assertEqual(status, 200)
            self.assertTrue(payload.startswith(b"PK"))

    def test_required_submission_returns_structured_422_without_advancing(self):
        status, text, headers = self.request(
            "/api/studies", {"participant_id": "F-VALIDATE", "consent_acknowledged": True})
        self.assertEqual(status, 201)
        created = json.loads(text)
        self.participant_cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, text, _ = self.request(
            f"/api/studies/{created['study_id']}/submit",
            {"version": created["version"], "values": {}}, participant=True)
        self.assertEqual(status, 422)
        error = json.loads(text)
        self.assertEqual({item["question_id"] for item in error["validation_errors"]}, {"A1", "A3"})
        status, text, _ = self.request(f"/api/studies/{created['study_id']}", participant=True)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["stage"], "A")

    def test_researcher_delete_requires_auth_csrf_and_confirmation(self):
        ids = []
        for participant_id in ("F-DELETE", "F-KEEP"):
            status, text, headers = self.request(
                "/api/studies", {"participant_id": participant_id, "consent_acknowledged": True})
            self.assertEqual(status, 201)
            ids.append(json.loads(text)["study_id"])
            self.participant_cookie = headers["Set-Cookie"].split(";", 1)[0]
        target, kept = ids
        path = f"/api/researcher/studies/{target}"
        self.assertEqual(self.request(path, {"confirmation": "DELETE"}, method="DELETE")[0], 401)
        self.assertEqual(self.request(path, {"confirmation": "DELETE"}, participant=True, method="DELETE")[0], 401)
        valid_csrf = self.csrf
        self.csrf = "invalid"
        try:
            self.assertEqual(self.request(path, {"confirmation": "DELETE"}, researcher=True, method="DELETE")[0], 401)
        finally:
            self.csrf = valid_csrf
        self.assertEqual(self.request(path, {"confirmation": "wrong"}, researcher=True, method="DELETE")[0], 422)
        self.assertEqual(self.request(path, {"confirmation": target}, researcher=True, method="DELETE")[0], 200)
        self.assertEqual(self.request(path, researcher=True)[0], 404)
        self.assertEqual(self.request(f"/api/researcher/studies/{target}/export.json", researcher=True)[0], 404)
        self.assertEqual(self.request(f"/api/researcher/studies/{kept}", researcher=True)[0], 200)
        self.assertEqual(self.request(path, {"confirmation": "DELETE"}, researcher=True, method="DELETE")[0], 404)

    def test_completed_participant_can_start_fresh_study_without_changing_old_record(self):
        status, text, headers = self.request(
            "/api/studies", {"participant_id": "F-FIRST", "consent_acknowledged": True})
        self.assertEqual(status, 201)
        current = json.loads(text)
        first_id = current["study_id"]
        self.participant_cookie = headers["Set-Cookie"].split(";", 1)[0]
        for section, expected_stage in zip(("A", "B", "C", "D", "E"), ("B", "C", "D", "E", "COMPLETE"), strict=True):
            status, text, _ = self.request(
                f"/api/studies/{first_id}/submit",
                {"version": current["version"], "values": self.REQUIRED[section]}, participant=True)
            self.assertEqual(status, 200)
            current = json.loads(text)
            self.assertEqual(current["stage"], expected_stage)

        # Start New Study first reads the existing public configuration; no row is
        # created and the completed study remains the active resumable record.
        status, text, _ = self.request("/api/study-config", participant=True)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["version"], "3.2")
        status, text, _ = self.request("/api/studies/current", participant=True)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["study_id"], first_id)

        # Repeated clicks only reread configuration and never create rows.
        self.assertEqual(self.request("/api/study-config", participant=True)[0], 200)
        status, text, _ = self.request("/api/researcher/studies", researcher=True)
        self.assertEqual(status, 200)
        self.assertEqual([row["study_id"] for row in json.loads(text)], [first_id])

        status, text, headers = self.request(
            "/api/studies", {"participant_id": "F-SECOND", "consent_acknowledged": True},
            participant=True)
        self.assertEqual(status, 201)
        second = json.loads(text)
        second_id = second["study_id"]
        self.assertNotEqual(second_id, first_id)
        self.assertEqual(second["stage"], "A")
        self.assertEqual(second["draft"], {})
        self.assertEqual(second["study_mode"], "self_guided")
        self.participant_cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, text, _ = self.request("/api/studies/current", participant=True)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["study_id"], second_id)

        second_current = second
        for section, expected_stage in zip(("A", "B", "C", "D", "E"), ("B", "C", "D", "E", "COMPLETE"), strict=True):
            status, text, _ = self.request(
                f"/api/studies/{second_id}/submit",
                {"version": second_current["version"], "values": self.REQUIRED[section]}, participant=True)
            self.assertEqual(status, 200)
            second_current = json.loads(text)
            self.assertEqual(second_current["stage"], expected_stage)

        details = {}
        for study_id in (first_id, second_id):
            status, text, _ = self.request(
                f"/api/researcher/studies/{study_id}", researcher=True)
            self.assertEqual(status, 200)
            details[study_id] = json.loads(text)
            for suffix in ("export.json", "export.csv", "export.xlsx", "export.zip"):
                status, payload, _ = self.request_bytes(
                    f"/api/researcher/studies/{study_id}/{suffix}", researcher=True)
                self.assertEqual(status, 200)
                self.assertTrue(payload)

        first = details[first_id]
        self.assertEqual(first["stage"], "COMPLETE")
        self.assertEqual(first["participant_id"], "F-FIRST")
        self.assertEqual(len([row for row in first["responses"] if row["submitted_at"]]), 5)
        self.assertEqual(details[second_id]["stage"], "COMPLETE")
        self.assertEqual(details[second_id]["participant_id"], "F-SECOND")
        status, text, _ = self.request("/api/researcher/studies", researcher=True)
        self.assertEqual(status, 200)
        self.assertEqual({row["study_id"] for row in json.loads(text)}, {first_id, second_id})
