"""HTTP contract checks using the existing stdlib server and a temporary log directory."""
import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from seasonlens import SeasonLensService


class ApiTests(unittest.TestCase):
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
        self.api.SERVICE = SeasonLensService(export_directory=Path(self.directory.name))

    def request(self, path, body=None, *, researcher=False):
        headers = {"Content-Type": "application/json"}
        if researcher: headers["X-SeasonLens-Researcher"] = "1"
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                text = response.read().decode("utf-8-sig")
                return response.status, text, response.headers
        except HTTPError as error:
            return error.code, error.read().decode(), error.headers

    def create(self):
        status, text, _ = self.request("/api/sessions", {"participant_id": "api-test"})
        self.assertEqual(status, 201)
        return json.loads(text)["data"]["session_id"]

    def test_catalog_and_researcher_mode_gate(self):
        status, text, _ = self.request("/api/items")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(text)), 3)
        self.assertEqual([item["item_id"] for item in json.loads(text)], [
            "demo_anemone_001", "demo_solidago_001", "demo_butterfly_weed_001",
        ])
        session_id = self.create()
        for suffix in ["log", "researcher", "log.csv"]:
            self.assertEqual(self.request(f"/api/sessions/{session_id}/{suffix}")[0], 403)
            self.assertEqual(self.request(f"/api/sessions/{session_id}/{suffix}", researcher=True)[0], 200)
        for suffix in ["hint-override", "researcher-notes", "reset"]:
            self.assertEqual(self.request(f"/api/sessions/{session_id}/{suffix}", {}, researcher=False)[0], 403)

    def test_http_flow_override_notes_and_exports(self):
        session_id = self.create()
        base = f"/api/sessions/{session_id}"
        initial = {"selected_region": {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2},
                   "observation_text": "a green shape", "selected_stage_id": "flower_buds_present", "confidence": 3}
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
        self.assertEqual(log["automatic_hint_id"], "demo_anemone_feature_01")
        self.assertEqual(log["actual_hint_id"], "demo_anemone_feature_02")
        self.assertEqual(log["researcher_notes"], "Private note")
        status, text, headers = self.request(base + "/log.csv", researcher=True)
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("Private note", text)
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
                   "observation_text": "a leaf", "selected_stage_id": "fruiting", "confidence": 2}
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
