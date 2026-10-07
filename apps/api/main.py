from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from threading import RLock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "packages" / "backend-core" / "src"))
sys.path.insert(
    0, str(REPOSITORY_ROOT / "extensions" / "seasonlens" / "backend" / "src")
)

from seasonlens import SeasonLensService  # noqa: E402


WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"
EXPORT_ROOT = REPOSITORY_ROOT / "runtime-data" / "seasonlens"
SERVICE = SeasonLensService(export_directory=EXPORT_ROOT)
SERVICE_LOCK = RLock()


class SeasonLensHandler(BaseHTTPRequestHandler):
    server_version = "SeasonLensMVP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        with SERVICE_LOCK:
            self._get()

    def _get(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/health":
                self._json({"status": "ok", "extension_id": "seasonlens"})
                return
            if path == "/api/items":
                self._json(SERVICE.catalog.list_items())
                return
            parts = self._parts(path)
            if len(parts) == 3 and parts[:2] == ["api", "items"]:
                self._json(SERVICE.catalog.participant_view(parts[2]))
                return
            if len(parts) == 3 and parts[:2] == ["api", "sessions"]:
                self._json(SERVICE.participant_projection(parts[2]))
                return
            if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] in {"log", "researcher", "log.csv"}:
                if not self._researcher_mode():
                    self._error(HTTPStatus.FORBIDDEN, "Researcher mode is required.")
                    return
                if parts[3] == "log.csv":
                    payload = SERVICE.export_study_csv(parts[2]).encode("utf-8-sig")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", f'attachment; filename="seasonlens-{SERVICE._state(parts[2]).aggregate_id}.csv"')
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(payload)
                else:
                    self._json(SERVICE.researcher_projection(parts[2]) if parts[3] == "researcher" else SERVICE.export_study_log(parts[2]))
                return
            self._serve_static(path)
        except ValueError as error:
            self._error(HTTPStatus.NOT_FOUND, str(error))
        except Exception as error:  # pragma: no cover - protective HTTP boundary
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to load this step. Please try again.")

    def do_POST(self) -> None:  # noqa: N802
        # Serialize the existing in-memory runtime across threaded HTTP requests.
        with SERVICE_LOCK:
            self._post()

    def _post(self) -> None:
        try:
            path = urlparse(self.path).path
            body = self._read_json()
            if path == "/api/sessions":
                self._json(
                    SERVICE.create_session(
                        str(body.get("participant_id", "")),
                        str(body.get("item_id", "demo_anemone_001")),
                        study_mode=str(body.get("study_mode", "training")),
                        condition=str(body.get("condition", "observation-first-contingent")),
                    ),
                    HTTPStatus.CREATED,
                )
                return
            parts = self._parts(path)
            if len(parts) != 4 or parts[:2] != ["api", "sessions"]:
                self._error(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
                return
            session_id, action = parts[2], parts[3]
            if action in {"hint-override", "researcher-notes", "reset"} and not self._researcher_mode():
                self._error(HTTPStatus.FORBIDDEN, "Researcher mode is required.")
                return
            handlers = {
                "initial-observation": lambda: SERVICE.submit_initial(session_id, body),
                "reobserve": lambda: SERVICE.begin_reobservation(session_id),
                "revision": lambda: SERVICE.submit_revision(session_id, body),
                "reveal": lambda: SERVICE.reveal_expert_cue(session_id),
                "reflection-stage": lambda: SERVICE.begin_reflection(session_id),
                "reflection": lambda: SERVICE.submit_reflection(
                    session_id, body.get("reflection_text", ""), body.get("reflection_category")
                ),
                "complete-unaided": lambda: SERVICE.complete_unaided(session_id),
                "hint-override": lambda: SERVICE.override_hint(session_id, str(body.get("hint_id", ""))),
                "researcher-notes": lambda: SERVICE.save_researcher_notes(session_id, body.get("researcher_notes", "")),
                "reset": lambda: SERVICE.reset_item(session_id),
                "next-item": lambda: SERVICE.next_item(session_id),
            }
            if action not in handlers:
                self._error(HTTPStatus.NOT_FOUND, "Unknown session action.")
                return
            self._json(handlers[action]())
        except json.JSONDecodeError:
            self._error(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.")
        except (ValueError, TypeError) as error:
            self._error(HTTPStatus.CONFLICT, str(error) if self._researcher_mode() else
                        "Please check your responses and complete the current step before continuing.")
        except Exception as error:  # pragma: no cover - protective HTTP boundary
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to save this step. Please try again.")

    def _researcher_mode(self) -> bool:
        # A local demonstration mode gate, not researcher authentication.
        return self.headers.get("X-SeasonLens-Researcher") == "1"

    def log_message(self, format: str, *args: object) -> None:
        sys.stdout.write(f"{self.address_string()} - {format % args}\n")

    @staticmethod
    def _parts(path: str) -> list[str]:
        return [unquote(part) for part in path.strip("/").split("/") if part]

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request body is too large.")
        if length == 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("Request body must be a JSON object.")
        return value

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else unquote(request_path.lstrip("/"))
        target = (WEB_ROOT / relative).resolve()
        try:
            target.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self._error(HTTPStatus.FORBIDDEN, "Invalid static path.")
            return
        if not target.is_file():
            self._error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        payload = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in {".html", ".css", ".js", ".svg"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SeasonLens MVP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SeasonLensHandler)
    print(f"SeasonLens MVP: http://{args.host}:{args.port}")
    print(f"Study logs: {EXPORT_ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSeasonLens stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
