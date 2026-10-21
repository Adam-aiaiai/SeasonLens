from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import secrets
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .service import CONDITION, TRAINING_MODE, SeasonLensService
from .storage import PersistentRepository


STAGE_SEQUENCE = ("A", "WAIT_B", "B", "WAIT_C", "C", "WAIT_D", "D",
                  "WAIT_PROTOTYPE", "PROTOTYPE", "E", "COMPLETE")
WAIT_RELEASES = {"WAIT_B": "B", "WAIT_C": "C", "WAIT_D": "D",
                 "WAIT_PROTOTYPE": "PROTOTYPE"}
SUBMIT_TRANSITIONS = {"A": "WAIT_B", "B": "WAIT_C", "C": "WAIT_D",
                      "D": "WAIT_PROTOTYPE", "E": "COMPLETE"}
METADATA_FIELDS = {
    "A": {"STUDY_DATE_MANUAL"},
    "B": {"B_STATION_ID", "B_START_TIME_MANUAL"},
    "C": {"C_EARLIER_MATERIAL_ID", "C_CURRENT_MATERIAL_ID", "C_PRESENTATION_ORDER"},
    "D": {"D_MATERIAL_ID", "D_START_TIME_MANUAL", "D_FIELD_BASED"},
    "E": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def safe_csv(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else ("" if value is None else str(value))
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


class FormativeStudyService:
    def __init__(self, repository: PersistentRepository, prototype: SeasonLensService, *,
                 clock: Callable[[], str] = utc_now,
                 schema_path: Path | None = None) -> None:
        self.repository = repository
        self.prototype = prototype
        self.clock = clock
        path = schema_path or Path(__file__).resolve().parents[3] / "data" / "formative_questionnaire_v3.json"
        self.schema = json.loads(path.read_text(encoding="utf-8"))
        self._field_specs = {
            section: {field["id"]: field for field in value["fields"]}
            for section, value in self.schema["sections"].items()
        }

    def public_config(self) -> dict[str, Any]:
        return {"instrument_id": self.schema["instrument_id"], "version": self.schema["version"],
                "participant_notice": deepcopy(self.schema["participant_notice"])}

    def create(self, participant_id: str, *, consent_acknowledged: bool = False) -> tuple[dict[str, Any], str]:
        participant_id = participant_id.strip()
        if not participant_id or len(participant_id) > 80:
            raise ValueError("A researcher-assigned participant ID is required (maximum 80 characters).")
        if consent_acknowledged is not True:
            raise ValueError("The participant must acknowledge the study information before beginning.")
        study_id = str(uuid4())
        token = secrets.token_urlsafe(32)
        now = self.clock()
        materials = {
            section: {"section_id": section, "task_index": 0, "images": deepcopy(images),
                      **self._default_material_metadata(section, images)}
            for section, images in self.schema["materials"].items()
        }
        study = {"study_id": study_id, "participant_id": participant_id,
                 "resume_token_hash": token_hash(token), "stage": "A", "version": 0,
                 "created_at": now, "updated_at": now}
        self.repository.create_study(study, materials, self._event(
            study_id, "study.created", participant_id,
            {"participant_id": participant_id, "instrument_id": self.schema["instrument_id"],
             "consent_acknowledged": True, "consent_acknowledged_at": now}, now))
        return self.participant_projection(study_id, token), token

    @staticmethod
    def _default_material_metadata(section: str, images: list[dict[str, Any]]) -> dict[str, Any]:
        if section == "B":
            return {"station_id": images[0]["material_id"]}
        if section == "C":
            return {"earlier_material_id": images[0]["material_id"],
                    "current_material_id": images[1]["material_id"],
                    "presentation_order": "earlier_then_current"}
        return {"material_id": images[0]["material_id"], "field_based": False}

    def authenticate_participant(self, study_id: str, token: str) -> dict[str, Any]:
        study = self.repository.get_study(study_id)
        if not study or not token or not hmac.compare_digest(study["resume_token_hash"], token_hash(token)):
            raise PermissionError("The participant resume session is not valid.")
        return study

    def participant_projection(self, study_id: str, token: str) -> dict[str, Any]:
        study = self.authenticate_participant(study_id, token)
        stage = study["stage"]
        result: dict[str, Any] = {
            "study_id": study_id, "participant_id": study["participant_id"],
            "stage": stage, "version": study["version"], "updated_at": study["updated_at"],
            "progress": self._progress(stage), "prototype_sessions": [row["session_id"] for row in study["prototype_sessions"]],
        }
        if stage in self.schema["sections"]:
            response = next((entry for entry in study["responses"] if entry["section_id"] == stage), None)
            result["section"] = deepcopy(self.schema["sections"][stage])
            result["draft"] = deepcopy(response["draft"] if response else {})
            result["started_at"] = response["started_at"] if response else None
            if stage in {"B", "C", "D"}:
                material = next(entry for entry in study["materials"] if entry["section_id"] == stage)
                result["material"] = self._participant_material(material["config"])
        elif stage == "PROTOTYPE":
            result["prototype_url"] = f"/prototype.html?study_id={study_id}"
        return result

    @staticmethod
    def _participant_material(config: dict[str, Any]) -> dict[str, Any]:
        # Provenance and hashes stay available in researcher exports, not as cues in B-D.
        result = {key: deepcopy(value) for key, value in config.items()
                  if key in {"section_id", "task_index", "station_id", "earlier_material_id",
                             "current_material_id", "presentation_order", "material_id", "field_based"}}
        result["images"] = [{key: image[key] for key in ("material_id", "image_path", "timepoint") if key in image}
                            for image in config["images"]]
        return result

    @staticmethod
    def _progress(stage: str) -> dict[str, Any]:
        position = STAGE_SEQUENCE.index(stage)
        completed = [name for name in ("A", "B", "C", "D", "PROTOTYPE", "E")
                     if STAGE_SEQUENCE.index(name) < position]
        return {"completed": completed, "current": stage}

    def save_draft(self, study_id: str, token: str, version: int, values: dict[str, Any]) -> dict[str, Any]:
        study = self.authenticate_participant(study_id, token)
        section = study["stage"]
        if section not in self._field_specs:
            raise ValueError("There is no participant questionnaire draft at the current stage.")
        clean = self._validate_values(section, values)
        now = self.clock()
        success = self.repository.update_draft(study_id, section, clean, version, now,
            self._event(study_id, "questionnaire.draft-saved", study["participant_id"],
                        {"section_id": section, "field_ids": sorted(clean)}, now))
        if not success:
            raise ValueError("This study changed in another window. Reload before saving again.")
        return self.participant_projection(study_id, token)

    def submit(self, study_id: str, token: str, version: int, values: dict[str, Any]) -> dict[str, Any]:
        study = self.authenticate_participant(study_id, token)
        section = study["stage"]
        if section not in SUBMIT_TRANSITIONS:
            raise ValueError("The current stage cannot be submitted.")
        clean = self._validate_values(section, values)
        now = self.clock()
        next_stage = SUBMIT_TRANSITIONS[section]
        success = self.repository.submit_section(study_id, section, clean, next_stage, version, now,
            self._event(study_id, "questionnaire.section-submitted", study["participant_id"],
                        {"section_id": section, "next_stage": next_stage, "field_ids": sorted(clean)}, now))
        if not success:
            raise ValueError("This study changed in another window. Reload before submitting again.")
        return self.participant_projection(study_id, token)

    def _validate_values(self, section: str, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError("Questionnaire values must be an object.")
        specs = self._field_specs[section]
        allowed = set(specs) | METADATA_FIELDS[section]
        if set(values) - allowed:
            raise ValueError(f"Unexpected field IDs for Section {section}.")
        clean: dict[str, Any] = {}
        for field_id, value in values.items():
            if value in (None, ""):
                clean[field_id] = None
                continue
            if field_id in METADATA_FIELDS[section]:
                if field_id == "D_FIELD_BASED":
                    if not isinstance(value, bool):
                        raise ValueError("D_FIELD_BASED must be true, false, or blank.")
                    clean[field_id] = value
                else:
                    clean[field_id] = self._text(value)
                continue
            spec = specs[field_id]
            if spec["type"] == "confidence":
                if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
                    raise ValueError(f"{field_id} must be a confidence value from 1 to 5 or blank.")
                clean[field_id] = value
            elif spec["type"] == "choice":
                options = {option["value"] for option in spec["options"]}
                if value not in options:
                    raise ValueError(f"{field_id} is not one of the authored options.")
                clean[field_id] = value
            else:
                clean[field_id] = self._text(value)
        return clean

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Text responses must be strings.")
        if len(value) > 10000:
            raise ValueError("A questionnaire response cannot exceed 10,000 characters.")
        return value.strip()

    def release(self, study_id: str, version: int, researcher: str) -> dict[str, Any]:
        study = self._require_study(study_id)
        next_stage = WAIT_RELEASES.get(study["stage"])
        if not next_stage:
            raise ValueError("The study is not waiting for researcher release.")
        now = self.clock()
        success = self.repository.release_stage(study_id, study["stage"], next_stage, version, now,
            self._event(study_id, "study.stage-released", researcher,
                        {"from": study["stage"], "to": next_stage}, now))
        if not success:
            raise ValueError("Study version conflict. Refresh the researcher dashboard.")
        return self.researcher_detail(study_id)

    def start_prototype(self, study_id: str, token: str) -> dict[str, Any]:
        study = self.authenticate_participant(study_id, token)
        if study["stage"] != "PROTOTYPE":
            raise ValueError("The prototype has not been released for this study.")
        if study["prototype_sessions"]:
            return self.prototype.participant_projection(study["prototype_sessions"][-1]["session_id"])
        first = self.prototype.catalog.list_items()[0]["item_id"]
        projection = self.prototype.create_session(study["participant_id"], first,
                                                   study_mode=TRAINING_MODE, condition=CONDITION)
        session_id = projection["data"]["session_id"]
        now = self.clock()
        self.repository.add_prototype_session(study_id, 0, session_id, first, now,
            self._event(study_id, "prototype.session-linked", study["participant_id"],
                        {"session_id": session_id, "item_id": first, "ordinal": 0}, now))
        return projection

    def link_next_prototype(self, previous_session_id: str, projection: dict[str, Any]) -> None:
        link = self.repository.study_for_session(previous_session_id)
        if not link:
            return
        session_id = projection["data"]["session_id"]
        now = self.clock()
        ordinal = int(link["ordinal"]) + 1
        self.repository.add_prototype_session(link["study_id"], ordinal, session_id,
            projection["data"]["item"]["item_id"], now,
            self._event(link["study_id"], "prototype.session-linked", "participant",
                        {"session_id": session_id, "item_id": projection["data"]["item"]["item_id"],
                         "ordinal": ordinal}, now))

    def complete_prototype_if_final(self, session_id: str, projection: dict[str, Any]) -> None:
        if projection["data"]["stage"] != "COMPLETE" or projection["data"]["has_next_item"]:
            return
        link = self.repository.study_for_session(session_id)
        if not link or link["stage"] != "PROTOTYPE":
            return
        now = self.clock()
        self.repository.transition_study(link["study_id"], "PROTOTYPE", "E", link["version"], now,
            self._event(link["study_id"], "prototype.completed", "participant",
                        {"final_session_id": session_id}, now))

    def researcher_detail(self, study_id: str) -> dict[str, Any]:
        study = self._require_study(study_id)
        result = deepcopy(study)
        result.pop("resume_token_hash", None)
        result["events"] = self.repository.events_for_study(study_id)
        return result

    def update_researcher_metadata(self, study_id: str, version: int, researcher: str,
                                   metadata: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            raise ValueError("Researcher metadata must be an object.")
        allowed = {"researcher_id", "study_date_manual", "notes"}
        if set(metadata) - allowed or any(not isinstance(v, str) for v in metadata.values()):
            raise ValueError("Only researcher_id, study_date_manual, and notes text are supported.")
        clean = {key: value.strip()[:10000] for key, value in metadata.items()}
        now = self.clock()
        if not self.repository.update_researcher_metadata(study_id, clean, version, now,
                self._event(study_id, "study.researcher-metadata-updated", researcher,
                            {"field_ids": sorted(clean)}, now)):
            raise ValueError("Study version conflict. Refresh the researcher dashboard.")
        return self.researcher_detail(study_id)

    def update_material(self, study_id: str, section: str, version: int, researcher: str,
                        config: dict[str, Any]) -> dict[str, Any]:
        if section not in {"B", "C", "D"}:
            raise ValueError("Only B, C, and D materials are configurable.")
        study = self._require_study(study_id)
        if STAGE_SEQUENCE.index(study["stage"]) >= STAGE_SEQUENCE.index(section):
            raise ValueError("A material cannot be changed after its section has been released.")
        images = config.get("images")
        if not isinstance(images, list) or len(images) != (2 if section == "C" else 1):
            raise ValueError("Material configuration must retain the required image count.")
        for image in images:
            if not isinstance(image, dict) or not all(isinstance(image.get(key), str) and image[key]
                                                      for key in ("material_id", "image_path", "sha256")):
                raise ValueError("Every configured image requires material_id, image_path, and sha256.")
            if not image["image_path"].startswith("/assets/"):
                raise ValueError("Study images must use a project-controlled /assets/ path.")
            if not isinstance(image.get("source"), dict) or not image["source"]:
                raise ValueError("Every configured image requires provenance in source.")
            asset = Path(__file__).resolve().parents[5] / "apps" / "web" / image["image_path"].lstrip("/")
            if not asset.is_file():
                raise ValueError(f"Configured study image is missing: {image['image_path']}")
            actual_hash = hashlib.sha256(asset.read_bytes()).hexdigest().upper()
            if not hmac.compare_digest(actual_hash, image["sha256"].upper()):
                raise ValueError(f"SHA-256 does not match the configured asset: {image['material_id']}")
        clean = {"section_id": section, "task_index": 0, "images": images,
                 **self._default_material_metadata(section, images)}
        now = self.clock()
        if not self.repository.update_material(study_id, section, clean, version, now,
                self._event(study_id, "study.material-configured", researcher,
                            {"section_id": section, "material_ids": [i["material_id"] for i in images]}, now)):
            raise ValueError("Study version conflict. Refresh the researcher dashboard.")
        return self.researcher_detail(study_id)

    def combined_export(self, study_id: str) -> dict[str, Any]:
        study = self.researcher_detail(study_id)
        prototype_logs = [self.prototype.export_study_log(row["session_id"])
                          for row in study["prototype_sessions"]]
        questionnaire = {entry["section_id"]: {
            "task_index": entry["task_index"], "started_at": entry["started_at"],
            "submitted_at": entry["submitted_at"], "response": entry["response"], "draft": entry["draft"]}
            for entry in study["responses"]}
        return {
            "export_version": 1, "instrument_id": self.schema["instrument_id"],
            "study": {key: study[key] for key in ("study_id", "participant_id", "stage", "version",
                                                   "created_at", "updated_at", "completed_at", "researcher_metadata")},
            "questionnaire": questionnaire, "materials": study["materials"],
            "prototype_session_ids": [row["session_id"] for row in study["prototype_sessions"]],
            "prototype_sessions": prototype_logs, "study_events": study["events"],
        }

    def questionnaire_export(self, study_id: str) -> dict[str, Any]:
        combined = self.combined_export(study_id)
        return {key: combined[key] for key in ("export_version", "instrument_id", "study", "questionnaire", "materials", "study_events")}

    def export_csv(self, study_id: str, *, questionnaire_only: bool = False) -> str:
        value = self.questionnaire_export(study_id) if questionnaire_only else self.combined_export(study_id)
        flat: dict[str, Any] = {"study_id": value["study"]["study_id"],
                                "participant_id": value["study"]["participant_id"],
                                "stage": value["study"]["stage"]}
        for section, record in value["questionnaire"].items():
            for field_id, answer in (record.get("response") or record.get("draft") or {}).items():
                flat[field_id] = answer
            flat[f"{section}_STARTED_AT"] = record["started_at"]
            flat[f"{section}_SUBMITTED_AT"] = record["submitted_at"]
        flat["materials_json"] = value["materials"]
        flat["study_events_json"] = value["study_events"]
        if not questionnaire_only:
            flat["prototype_session_ids"] = value["prototype_session_ids"]
            flat["prototype_sessions_json"] = value["prototype_sessions"]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=list(flat))
        writer.writeheader()
        writer.writerow({key: safe_csv(item) for key, item in flat.items()})
        return output.getvalue()

    def export_xlsx(self, study_id: str) -> bytes:
        combined = self.combined_export(study_id)
        sheets = {
            "Study": [["Field", "Value"], *[[key, safe_csv(value)] for key, value in combined["study"].items()]],
            "Questionnaire": [["Section", "Field", "Value", "Started UTC", "Submitted UTC"]],
            "Prototype Sessions": [["Ordinal", "Session ID", "Item ID", "Stage", "Log JSON"]],
            "Events": [["Source", "Event type", "Recorded UTC", "Payload JSON"]],
        }
        for section, record in combined["questionnaire"].items():
            for field_id, value in (record.get("response") or record.get("draft") or {}).items():
                sheets["Questionnaire"].append([section, field_id, safe_csv(value), record["started_at"], record["submitted_at"]])
        for index, log in enumerate(combined["prototype_sessions"]):
            sheets["Prototype Sessions"].append([index, log["session_id"], log["item_id"], log["stage"], _json_for_export(log)])
            for event in log.get("events", []):
                sheets["Events"].append([f"prototype:{log['session_id']}", event["event_type"], event["recorded_at"], _json_for_export(event["payload"])])
        for event in combined["study_events"]:
            sheets["Events"].append(["study", event["event_type"], event["recorded_at"], _json_for_export(event["payload"])])
        return _xlsx(sheets)

    def export_zip(self, study_id: str) -> bytes:
        combined = self.combined_export(study_id)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("combined-study.json", json.dumps(combined, ensure_ascii=False, indent=2))
            archive.writestr("combined-study.csv", self.export_csv(study_id))
            archive.writestr("questionnaire.json", json.dumps(self.questionnaire_export(study_id), ensure_ascii=False, indent=2))
            archive.writestr("questionnaire.csv", self.export_csv(study_id, questionnaire_only=True))
            archive.writestr("combined-study.xlsx", self.export_xlsx(study_id))
            for index, log in enumerate(combined["prototype_sessions"]):
                name = f"prototype/{index + 1:02d}-{log['session_id']}"
                archive.writestr(name + ".json", json.dumps(log, ensure_ascii=False, indent=2))
                archive.writestr(name + ".csv", self.prototype.export_study_csv(log["session_id"]))
        return stream.getvalue()

    def _require_study(self, study_id: str) -> dict[str, Any]:
        study = self.repository.get_study(study_id)
        if not study:
            raise ValueError("Unknown study.")
        return study

    @staticmethod
    def _event(study_id: str, event_type: str, actor_id: str,
               payload: dict[str, Any], recorded_at: str) -> dict[str, Any]:
        return {"event_id": str(uuid4()), "study_id": study_id, "event_type": event_type,
                "actor_id": actor_id, "payload": payload, "recorded_at": recorded_at}


def _json_for_export(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _column(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_xml(rows: list[list[object]]) -> str:
    body = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for column_index, value in enumerate(row, 1):
            ref = f"{_column(column_index)}{row_index}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape("" if value is None else str(value))}</t></is></c>')
        body.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(body) + "</sheetData></worksheet>"


def _xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets)+1)) + '</Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheets, 1)) + '</sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets)+1)) + '</Relationships>')
        for index, rows in enumerate(sheets.values(), 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
    return output.getvalue()
