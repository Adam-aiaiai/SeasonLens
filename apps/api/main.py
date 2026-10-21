from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import unquote, urlparse

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_local_environment(path: Path) -> tuple[str, ...]:
    """Load a local .env without replacing explicit process configuration."""

    if not path.is_file():
        return ()
    loaded: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if (not separator or not name or name[0].isdigit()
                or not all(character.isalnum() or character == "_" for character in name)):
            raise ValueError(f"Invalid environment entry at {path}:{line_number}.")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
            value = value[1:-1]
        if name not in os.environ:
            os.environ[name] = value
            loaded.append(name)
    return tuple(loaded)


if __name__ == "__main__":
    load_local_environment(REPOSITORY_ROOT / ".env")

sys.path.insert(0, str(REPOSITORY_ROOT / "packages" / "backend-core" / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "extensions" / "seasonlens" / "backend" / "src"))

from seasonlens import FormativeStudyService, PersistentRepository, ResearcherAuth, SeasonLensService  # noqa: E402

WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"
EXPORT_ROOT = REPOSITORY_ROOT / "runtime-data" / "seasonlens"
DEFAULT_DATABASE = f"sqlite:///{(REPOSITORY_ROOT / 'runtime-data' / 'seasonlens.db').as_posix()}"
REPOSITORY = PersistentRepository(os.environ.get("DATABASE_URL", DEFAULT_DATABASE))
SERVICE = SeasonLensService(export_directory=EXPORT_ROOT, repository=REPOSITORY)
STUDIES = FormativeStudyService(REPOSITORY, SERVICE)
AUTH = ResearcherAuth(REPOSITORY)
SERVICE_LOCK = RLock()


class SeasonLensHTTPServer(ThreadingHTTPServer):
    """Prevent two Windows processes from silently sharing the study port."""

    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class SeasonLensHandler(BaseHTTPRequestHandler):
    server_version = "SeasonLens/1.0"

    def do_GET(self) -> None:  # noqa: N802
        with SERVICE_LOCK:
            self._get()

    def _get(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/health":
                self._json({"status": "ok", "extension_id": "seasonlens",
                            "database": "postgresql" if REPOSITORY._postgres else "sqlite",
                            "researcher_auth_configured": AUTH.configured})
                return
            if path == "/api/study-config":
                self._json(STUDIES.public_config())
                return
            if path.rstrip("/") == "/api/studies/current":
                study_id, token = self._participant_credentials()
                self._json(STUDIES.participant_projection(study_id, token))
                return
            if path == "/api/researcher/me":
                session = self._researcher()
                self._json({"username": session["username"], "csrf_token": session["csrf_token"],
                            "expires_at": session["expires_at"]})
                return
            if path == "/api/researcher/studies":
                self._researcher()
                self._json(REPOSITORY.list_studies())
                return
            if path == "/api/items":
                self._json(SERVICE.catalog.list_items())
                return
            parts = self._parts(path)
            if len(parts) == 3 and parts[:2] == ["api", "items"]:
                self._json(SERVICE.catalog.participant_view(parts[2]))
                return
            if len(parts) == 3 and parts[:2] == ["api", "studies"]:
                study_id, token = self._participant_credentials()
                if study_id != parts[2]:
                    raise PermissionError("Participant session does not match this study.")
                self._json(STUDIES.participant_projection(study_id, token))
                return
            if len(parts) >= 4 and parts[:3] == ["api", "researcher", "studies"]:
                self._researcher()
                study_id = parts[3]
                if len(parts) == 4:
                    self._json(STUDIES.researcher_detail(study_id))
                    return
                if len(parts) == 5:
                    self._researcher_export(study_id, parts[4])
                    return
            if len(parts) == 3 and parts[:2] == ["api", "sessions"]:
                self._authorize_session_participant(parts[2])
                self._json(SERVICE.participant_projection(parts[2]))
                return
            if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] in {"log", "researcher", "log.csv"}:
                self._researcher()
                if parts[3] == "log.csv":
                    self._bytes(SERVICE.export_study_csv(parts[2]).encode("utf-8-sig"),
                                "text/csv; charset=utf-8", f"seasonlens-{parts[2]}.csv")
                else:
                    self._json(SERVICE.researcher_projection(parts[2]) if parts[3] == "researcher"
                               else SERVICE.export_study_log(parts[2]))
                return
            self._serve_static(path)
        except PermissionError as error:
            self._error(HTTPStatus.UNAUTHORIZED, str(error))
        except ValueError as error:
            self._error(HTTPStatus.NOT_FOUND, str(error))
        except Exception as error:  # pragma: no cover
            self.log_error("GET failed: %s", error)
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "无法加载当前步骤，请重试。")

    def do_POST(self) -> None:  # noqa: N802
        with SERVICE_LOCK:
            self._post()

    def _post(self) -> None:
        try:
            path = urlparse(self.path).path
            body = self._read_json()
            if path == "/api/studies":
                projection, token = STUDIES.create(
                    str(body.get("participant_id", "")),
                    consent_acknowledged=body.get("consent_acknowledged") is True)
                cookie = self._cookie("seasonlens_participant", f"{projection['study_id']}.{token}", max_age=2592000)
                self._json(projection, HTTPStatus.CREATED, headers={"Set-Cookie": cookie})
                return
            if path == "/api/researcher/login":
                token, session = AUTH.login(str(body.get("username", "")), str(body.get("password", "")))
                self._json({"username": session["username"], "csrf_token": session["csrf_token"],
                            "expires_at": session["expires_at"]}, headers={
                    "Set-Cookie": self._cookie("seasonlens_researcher", token, max_age=43200)})
                return
            if path == "/api/researcher/logout":
                token = self._cookie_value("seasonlens_researcher")
                self._researcher(require_csrf=True)
                AUTH.logout(token)
                self._json({"ok": True}, headers={"Set-Cookie": self._cookie("seasonlens_researcher", "", max_age=0)})
                return
            if path == "/api/sessions":
                self._json(SERVICE.create_session(
                    str(body.get("participant_id", "")), str(body.get("item_id", "demo_anemone_001")),
                    study_mode=str(body.get("study_mode", "training")),
                    condition=str(body.get("condition", "observation-first-contingent"))), HTTPStatus.CREATED)
                return

            parts = self._parts(path)
            if len(parts) == 4 and parts[:2] == ["api", "studies"]:
                study_id, token = self._participant_credentials()
                if study_id != parts[2]:
                    raise PermissionError("Participant session does not match this study.")
                action = parts[3]
                if action == "draft":
                    self._json(STUDIES.save_draft(study_id, token, int(body.get("version", -1)), body.get("values", {})))
                    return
                if action == "submit":
                    self._json(STUDIES.submit(study_id, token, int(body.get("version", -1)), body.get("values", {})))
                    return
                if action == "prototype-start":
                    self._json(STUDIES.start_prototype(study_id, token))
                    return

            if len(parts) >= 5 and parts[:3] == ["api", "researcher", "studies"]:
                session = self._researcher(require_csrf=True)
                study_id, action = parts[3], parts[4]
                if action == "release":
                    self._json(STUDIES.release(study_id, int(body.get("version", -1)), session["username"]))
                    return
                if action == "metadata":
                    self._json(STUDIES.update_researcher_metadata(
                        study_id, int(body.get("version", -1)), session["username"], body.get("metadata", {})))
                    return
                if action == "materials" and len(parts) == 6:
                    self._json(STUDIES.update_material(
                        study_id, parts[5], int(body.get("version", -1)), session["username"], body.get("config", {})))
                    return

            if len(parts) != 4 or parts[:2] != ["api", "sessions"]:
                self._error(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
                return
            session_id, action = parts[2], parts[3]
            if action in {"hint-override", "researcher-notes", "reset"}:
                self._researcher(require_csrf=True)
            else:
                self._authorize_session_participant(session_id)
            handlers = {
                "initial-observation": lambda: SERVICE.submit_initial(session_id, body),
                "reobserve": lambda: SERVICE.begin_reobservation(session_id),
                "revision": lambda: SERVICE.submit_revision(session_id, body),
                "reveal": lambda: SERVICE.reveal_expert_cue(session_id),
                "reflection-stage": lambda: SERVICE.begin_reflection(session_id),
                "reflection": lambda: SERVICE.submit_reflection(
                    session_id, body.get("reflection_text", ""), body.get("reflection_category"),
                    hint_learning_reflection=body.get("hint_learning_reflection")),
                "complete-unaided": lambda: SERVICE.complete_unaided(session_id),
                "hint-override": lambda: SERVICE.override_hint(session_id, str(body.get("hint_id", ""))),
                "researcher-notes": lambda: SERVICE.save_researcher_notes(session_id, body.get("researcher_notes", "")),
                "reset": lambda: SERVICE.reset_item(session_id),
                "next-item": lambda: SERVICE.next_item(session_id),
            }
            if action not in handlers:
                self._error(HTTPStatus.NOT_FOUND, "Unknown session action.")
                return
            projection = handlers[action]()
            if action == "next-item":
                STUDIES.link_next_prototype(session_id, projection)
            STUDIES.complete_prototype_if_final(session_id, projection)
            self._json(projection)
        except json.JSONDecodeError:
            self._error(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.")
        except PermissionError as error:
            self._error(HTTPStatus.UNAUTHORIZED, str(error))
        except (ValueError, TypeError) as error:
            participant_message = "请检查你的回答并完成当前步骤后再继续。"
            self._error(HTTPStatus.CONFLICT,
                        participant_message if "/api/sessions/" in path and not self._is_researcher() else str(error))
        except Exception as error:  # pragma: no cover
            self.log_error("POST failed: %s", error)
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "无法保存当前步骤，请重试。")

    def _researcher_export(self, study_id: str, kind: str) -> None:
        if kind == "export.json":
            self._bytes(json.dumps(STUDIES.combined_export(study_id), ensure_ascii=False, indent=2).encode("utf-8"),
                        "application/json; charset=utf-8", f"seasonlens-study-{study_id}.json")
        elif kind == "export.csv":
            self._bytes(STUDIES.export_csv(study_id).encode("utf-8-sig"), "text/csv; charset=utf-8", f"seasonlens-study-{study_id}.csv")
        elif kind == "export.xlsx":
            self._bytes(STUDIES.export_xlsx(study_id), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"seasonlens-study-{study_id}.xlsx")
        elif kind == "export.zip":
            self._bytes(STUDIES.export_zip(study_id), "application/zip", f"seasonlens-study-{study_id}.zip")
        elif kind == "questionnaire.json":
            self._bytes(json.dumps(STUDIES.questionnaire_export(study_id), ensure_ascii=False, indent=2).encode("utf-8"),
                        "application/json; charset=utf-8", f"seasonlens-questionnaire-{study_id}.json")
        elif kind == "questionnaire.csv":
            self._bytes(STUDIES.export_csv(study_id, questionnaire_only=True).encode("utf-8-sig"),
                        "text/csv; charset=utf-8", f"seasonlens-questionnaire-{study_id}.csv")
        else:
            raise ValueError("Unknown export format.")

    def _participant_credentials(self) -> tuple[str, str]:
        value = self._cookie_value("seasonlens_participant")
        if "." not in value:
            raise PermissionError("No participant study is active in this browser.")
        study_id, token = value.split(".", 1)
        return study_id, token

    def _authorize_session_participant(self, session_id: str) -> None:
        link = REPOSITORY.study_for_session(session_id)
        if not link:
            return  # Backward-compatible standalone prototype session.
        study_id, token = self._participant_credentials()
        if study_id != link["study_id"]:
            raise PermissionError("Participant session does not match this prototype task.")
        STUDIES.authenticate_participant(study_id, token)

    def _researcher(self, *, require_csrf: bool = False) -> dict[str, Any]:
        token = self._cookie_value("seasonlens_researcher")
        return AUTH.require_csrf(token, self.headers.get("X-CSRF-Token", "")) if require_csrf else AUTH.authenticate(token)

    def _is_researcher(self) -> bool:
        try:
            self._researcher()
            return True
        except PermissionError:
            return False

    def _cookie_value(self, name: str) -> str:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        return cookie[name].value if name in cookie else ""

    def _cookie(self, name: str, value: str, *, max_age: int) -> str:
        cookie = SimpleCookie()
        cookie[name] = value
        cookie[name]["path"] = "/"
        cookie[name]["httponly"] = True
        cookie[name]["samesite"] = "Strict"
        cookie[name]["max-age"] = max_age
        if self.headers.get("X-Forwarded-Proto") == "https" or os.environ.get("RAILWAY_ENVIRONMENT"):
            cookie[name]["secure"] = True
        return cookie.output(header="").strip()

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

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK, *, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers()
        for name, header_value in (headers or {}).items():
            self.send_header(name, header_value)
        self.end_headers()
        self.wfile.write(payload)

    def _bytes(self, payload: bytes, content_type: str, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers()
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
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SeasonLens formative-study platform.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    server = SeasonLensHTTPServer((args.host, args.port), SeasonLensHandler)
    print(f"SeasonLens: http://{args.host}:{args.port}")
    print(f"Database: {'PostgreSQL' if REPOSITORY._postgres else REPOSITORY.database_url}")
    if not AUTH.configured:
        print("WARNING: researcher login is disabled until credentials are configured.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSeasonLens stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
