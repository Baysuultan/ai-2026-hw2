"""Extract cited candidate records, score them, and rank in Python."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema
from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CANDIDATES = DATA / "candidates"
MODEL = "gpt-5.6-luna"

EXTRACTION_RULES = """Extract only facts stated in the story. A fact not stated is null; never
estimate it. If GPA is on a non-4.0 scale, convert proportionally as original GPA divided
by the stated scale maximum, multiplied by 4, rounded to two decimals; record the original
value, scale label, and numeric scale maximum. A paper counts as published only if the story says published
or accepted. Submitted, under review, in preparation, planned, and in press outputs do
not count; record them separately with their status. Do not resolve or average
contradictions: set the contradicted field to null and describe the conflict in
ambiguities with evidence quotes for both claims. Count experience in months; overlapping
periods count once and periods without dates are not countable. For every populated
extracted field provide a short verbatim evidence quote. Preserve evidence for each
experience period and each other output. Only classify something as a paper when the
story explicitly calls it a paper, article, or manuscript. Do not classify posters,
theses, or future project plans as papers. Keep the applicant's own name in its original
script."""

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_id": {"type": "string"},
        "full_name": {"type": ["string", "null"]},
        "degree": {"type": ["string", "null"]},
        "graduation_year": {"type": ["integer", "null"]},
        "gpa_4_scale": {"type": ["number", "null"]},
        "gpa_original": {
            "type": "object",
            "properties": {
                "value": {"type": ["number", "null"]},
                "scale": {"type": ["string", "null"]},
                "maximum": {"type": ["number", "null"]},
            },
            "required": ["value", "scale", "maximum"],
            "additionalProperties": False,
        },
        "languages": {"type": ["array", "null"], "items": {"type": "string"}},
        "published_peer_reviewed_outputs": {"type": "integer", "minimum": 0},
        "other_outputs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "kind": {"enum": ["paper", "poster", "thesis", "other"]},
                    "status": {
                        "enum": [
                            "accepted", "published", "submitted", "under_review",
                            "in_preparation", "in_press", "planned", "other",
                        ]
                    },
                    "evidence": {"type": "string"},
                },
                "required": ["description", "kind", "status", "evidence"],
                "additionalProperties": False,
            },
        },
        "relevant_experience_months": {"type": ["number", "null"], "minimum": 0},
        "experience_periods": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "months": {"type": ["number", "null"], "minimum": 0},
                    "evidence": {"type": "string"},
                },
                "required": ["description", "months", "evidence"],
                "additionalProperties": False,
            },
        },
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "conflict": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                },
                "required": ["field", "conflict", "evidence"],
                "additionalProperties": False,
            },
        },
        "evidence": {
            "type": "object",
            "properties": {
                "full_name": {"type": ["string", "null"]},
                "degree": {"type": ["string", "null"]},
                "graduation_year": {"type": ["string", "null"]},
                "gpa_4_scale": {"type": ["string", "null"]},
                "gpa_original": {"type": ["string", "null"]},
                "languages": {"type": ["string", "null"]},
                "published_peer_reviewed_outputs": {"type": ["string", "null"]},
                "relevant_experience_months": {"type": ["string", "null"]},
            },
            "required": [
                "full_name", "degree", "graduation_year", "gpa_4_scale", "gpa_original",
                "languages", "published_peer_reviewed_outputs", "relevant_experience_months",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "candidate_id", "full_name", "degree", "graduation_year", "gpa_4_scale",
        "gpa_original", "languages", "published_peer_reviewed_outputs", "other_outputs",
        "relevant_experience_months", "experience_periods", "ambiguities", "evidence",
    ],
    "additionalProperties": False,
}


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def request_json(client: OpenAI, system: str, user: str) -> tuple[str, Any]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError:
        return raw, None


def extraction_is_valid(record: Any, candidate_id: str) -> bool:
    return extraction_validation_error(record, candidate_id) is None


def extraction_validation_error(record: Any, candidate_id: str) -> str | None:
    if not isinstance(record, dict):
        return "reply is not a JSON object"
    try:
        jsonschema.validate(record, EXTRACTION_SCHEMA)
    except jsonschema.ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "record"
        return f"{location}: {error.message}"
    if record["candidate_id"] != candidate_id:
        return f"candidate_id must be {candidate_id}"
    for field, quote in record["evidence"].items():
        value = record[field]
        populated = value is not None
        if field == "gpa_original":
            populated = any(item is not None for item in value.values())
        if populated and (not isinstance(quote, str) or not quote.strip()):
            return f"evidence.{field} is required for a populated field"
    if any(not item["evidence"].strip() for item in record["experience_periods"]):
        return "every experience period requires an evidence quote"
    if any(
        not item["evidence"] or any(not quote.strip() for quote in item["evidence"])
        for item in record["ambiguities"]
    ):
        return "every ambiguity requires evidence quotes for the conflicting statements"
    return None


def collect_null_fields(value: Any, prefix: str = "") -> list[str]:
    if value is None:
        return [prefix] if prefix else []
    if isinstance(value, dict):
        return [
            path
            for key, item in value.items()
            if key != "evidence"
            for path in collect_null_fields(item, f"{prefix}.{key}" if prefix else key)
        ]
    if isinstance(value, list):
        return [
            path
            for index, item in enumerate(value)
            for path in collect_null_fields(item, f"{prefix}[{index}]")
        ]
    return []


def score_schema(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            item["id"]: {"type": "number", "minimum": 0, "maximum": 5}
            for item in criteria
        },
        "required": [item["id"] for item in criteria],
        "additionalProperties": False,
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing. Add it to the ignored .env file.")

    rubric = read_json(DATA / "candidate_rubric.json")
    client = OpenAI()
    stories = sorted(CANDIDATES.glob("story-*.md"))
    if len(stories) != 6:
        raise SystemExit(f"Expected six story files in {CANDIDATES}, found {len(stories)}.")

    records: dict[str, dict[str, Any] | None] = {}
    raw_extractions: dict[str, str] = {}
    extraction_status: dict[str, tuple[bool, bool]] = {}
    extraction_system = (
        "You convert scholarship application stories into a cited JSON record. "
        f"Follow these rules exactly: {EXTRACTION_RULES}\n\n"
        f"Return exactly this JSON Schema:\n{json.dumps(EXTRACTION_SCHEMA, ensure_ascii=False)}"
    )

    for story_path in stories:
        candidate_id = story_path.stem
        story = story_path.read_text(encoding="utf-8")
        user = json.dumps({"candidate_id": candidate_id, "story": story}, ensure_ascii=False)
        raw, parsed = request_json(client, extraction_system, user)
        validation_error = extraction_validation_error(parsed, candidate_id)
        retried = False
        if validation_error:
            retried = True
            correction = json.dumps(
                {
                    "candidate_id": candidate_id,
                    "previous_reply": raw,
                    "validation_error": validation_error,
                    "instruction": "Correct the reply to match the exact JSON Schema and evidence requirements. Return only corrected JSON.",
                },
                ensure_ascii=False,
            )
            raw, parsed = request_json(client, extraction_system, correction)
            validation_error = extraction_validation_error(parsed, candidate_id)
        raw_extractions[candidate_id] = raw
        parsed_ok = parsed is not None
        valid = validation_error is None
        extraction_status[candidate_id] = (parsed_ok, valid)
        records[candidate_id] = parsed if valid else None
        if validation_error:
            print(f"{candidate_id} extraction remains invalid after correction attempt: {validation_error}")
            print(raw)
        elif retried:
            print(f"{candidate_id} extraction corrected and validated on retry")

    print("=== Extraction results ===")
    print("Story | Parsed | Valid | Null fields | Traps")
    for candidate_id, record in records.items():
        parsed_ok, valid = extraction_status[candidate_id]
        if not isinstance(record, dict):
            print(f"{candidate_id} | {parsed_ok} | {valid} | unavailable | unavailable")
            continue
        null_fields = collect_null_fields(record)
        traps: list[str] = []
        gpa_contradicted = any("gpa" in item["field"].casefold() for item in record["ambiguities"])
        if (
            record["gpa_4_scale"] is None
            and record["gpa_original"]["value"] is None
            and not gpa_contradicted
        ):
            traps.append("no GPA stated")
        elif (
            record["gpa_original"]["maximum"] is not None
            and abs(record["gpa_original"]["maximum"] - 4.0) > 1e-9
        ):
            traps.append("other GPA scale")
        if any(
            item["kind"] == "paper" and item["status"] not in {"published", "accepted"}
            for item in record["other_outputs"]
        ):
            traps.append("paper not published")
        if record["ambiguities"]:
            traps.append("contradiction")
        print(f"{candidate_id} | {parsed_ok} | {valid} | {null_fields or 'none'} | {', '.join(traps) or 'none'}")
    print("\n=== story-06 extraction ===")
    print(raw_extractions.get("story-06", "No reply"))

    score_instructions = (
        "Score this candidate from 0 to 5 for each rubric criterion. Return only one JSON "
        "object with exactly the criterion IDs as numeric fields; do not compute a weighted "
        "total, rank candidates, or add prose. Use only supported evidence. A null or "
        "contradicted extracted field is unknown, not a value to guess. The rubric does not "
        "define a special contradiction penalty, so score only the uncontradicted evidence."
    )
    scoring_schema = score_schema(rubric["criteria"])
    scores: dict[str, dict[str, float]] = {}
    raw_scores: dict[str, str] = {}
    print("\n=== Structured scores ===")
    for candidate_id, record in records.items():
        if record is None:
            raise SystemExit(f"Cannot score {candidate_id}: extraction did not validate.")
        raw, parsed = request_json(
            client,
            score_instructions + "\n\nRubric:\n" + json.dumps(rubric, ensure_ascii=False),
            json.dumps({"candidate_id": candidate_id, "extracted_record": record}, ensure_ascii=False),
        )
        raw_scores[candidate_id] = raw
        try:
            jsonschema.validate(parsed, scoring_schema)
        except (jsonschema.ValidationError, jsonschema.SchemaError, TypeError) as error:
            raise SystemExit(f"Invalid score JSON for {candidate_id}: {error}\n{raw}") from error
        scores[candidate_id] = parsed
        print(f"{candidate_id}: {raw}")

    weights = {item["id"]: item["weight"] for item in rubric["criteria"]}
    totals = {
        candidate_id: round(sum(scores[candidate_id][key] * weight for key, weight in weights.items()), 2)
        for candidate_id in scores
    }
    ranking = sorted(totals, key=lambda candidate_id: totals[candidate_id], reverse=True)
    print("\n=== Code-computed ranking ===")
    print("Candidate | academic | research | experience | weighted total")
    for candidate_id in ranking:
        print(
            f"{candidate_id} | {scores[candidate_id]['academic']} | "
            f"{scores[candidate_id]['research']} | {scores[candidate_id]['experience']} | "
            f"{totals[candidate_id]:.2f}"
        )
    print(f"Winner by code: {ranking[0]}")
    if len(ranking) > 1:
        print(f"Top-two gap: {totals[ranking[0]] - totals[ranking[1]]:.2f}")

    prose_response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "In prose, recommend one candidate based on the stated rubric and evidence. Explain briefly.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"rubric": rubric, "candidate_records": records}, ensure_ascii=False
                ),
            },
        ],
    )
    print("\n=== Separate prose ranking (comparison only) ===")
    print(prose_response.choices[0].message.content or "")


if __name__ == "__main__":
    main()