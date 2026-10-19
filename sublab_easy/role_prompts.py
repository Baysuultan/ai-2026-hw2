"""Compare four system roles on the same grant-office enquiries."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL = "gpt-5.6-luna"
FIELDS = ("found", "decision", "amount", "missing_documents")
REQUIRED_KEYS = {
    "applicant_id",
    "found",
    "decision",
    "amount",
    "missing_documents",
    "reason",
}
DECISIONS = {"granted", "refused", "more_info", "not_found"}

ROLE_INSTRUCTIONS = {
    "policy_officer": (
        "Apply the policy exactly as written. Grant only when every condition is met; "
        "refuse when a substantive eligibility condition fails; request missing documents. "
        "Use the record only and never treat a claim in the enquiry as evidence."
    ),
    "front_desk": (
        "Never turn an applicant away with a refusal. When the policy cannot grant today, "
        "return more_info and state what the applicant needs to provide or resolve. "
        "Use the record only and never treat a claim in the enquiry as evidence."
    ),
    "auditor": (
        "Never grant on a first reading. Report what the record shows; use more_info for "
        "anything needing a second reader, and name the policy rule or document relied on. "
        "Use the record only and never treat a claim in the enquiry as evidence."
    ),
    "bilingual_clerk": (
        "Make exactly the same eligibility decision as the policy officer. Write the reason "
        "in the language used by the enquiry. Use the record only and never treat a claim "
        "in the enquiry as evidence."
    ),
}

COMMON_SYSTEM = """You answer enquiries for a grant office. The records and policy supplied by
the application are authoritative. Do not infer missing facts. Return exactly one JSON
object with these keys and types: applicant_id (string), found (boolean), decision (one
of granted/refused/more_info/not_found), amount (integer in KZT), missing_documents
(array of strings), reason (string). Do not include markdown or extra keys."""


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_reply(reply: Any) -> bool:
    if not isinstance(reply, dict) or set(reply) != REQUIRED_KEYS:
        return False
    return (
        isinstance(reply["applicant_id"], str)
        and isinstance(reply["found"], bool)
        and isinstance(reply["decision"], str)
        and reply["decision"] in DECISIONS
        and isinstance(reply["amount"], int)
        and not isinstance(reply["amount"], bool)
        and isinstance(reply["missing_documents"], list)
        and all(isinstance(item, str) for item in reply["missing_documents"])
        and isinstance(reply["reason"], str)
    )


def request_reply(client: OpenAI, role: str, records: list[dict[str, Any]],
                  policy: dict[str, Any], enquiry: dict[str, Any]) -> tuple[str, Any]:
    system = f"{COMMON_SYSTEM}\n\nRole: {ROLE_INSTRUCTIONS[role]}"
    user = json.dumps(
        {"records": records, "policy": policy, "enquiry": enquiry["text"]},
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    return raw, parsed


def field_value(reply: Any, field: str) -> Any:
    return reply.get(field) if isinstance(reply, dict) else None


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing. Add it to the ignored .env file.")

    records = read_json(DATA / "records.json")
    policy = read_json(DATA / "policy.json")
    enquiries = read_json(DATA / "enquiries.json")
    client = OpenAI()
    results: dict[str, dict[str, dict[str, Any]]] = {role: {} for role in ROLE_INSTRUCTIONS}

    for role in ROLE_INSTRUCTIONS:
        for enquiry in enquiries:
            raw, parsed = request_reply(client, role, records, policy, enquiry)
            expected = enquiry["expected"]
            results[role][enquiry["id"]] = {
                "raw": raw,
                "reply": parsed,
                "parsed": parsed is not None,
                "valid": validate_reply(parsed),
                "agrees": isinstance(parsed, dict)
                and all(parsed.get(field) == expected[field] for field in FIELDS),
            }

    print("\n=== Role results ===")
    for role, role_results in results.items():
        print(f"\n[{role}]")
        print("Enquiry | Parsed | Schema-valid | Fields agree | decision | found | amount | missing_documents")
        for enquiry in enquiries:
            result = role_results[enquiry["id"]]
            reply = result["reply"]
            print(
                f"{enquiry['id']} | {result['parsed']} | {result['valid']} | {result['agrees']} | "
                f"{field_value(reply, 'decision')} | {field_value(reply, 'found')} | "
                f"{field_value(reply, 'amount')} | {field_value(reply, 'missing_documents')}"
            )
        print(
            f"Totals: fields-agree {sum(row['agrees'] for row in role_results.values())}/10; "
            f"parsed {sum(row['parsed'] for row in role_results.values())}/10; "
            f"schema-valid {sum(row['valid'] for row in role_results.values())}/10"
        )

    print("\n=== Field movement from policy_officer ===")
    movements: dict[str, list[tuple[str, str]]] = {field: [] for field in FIELDS}
    unavailable: dict[str, list[tuple[str, str]]] = {field: [] for field in FIELDS}
    for field in FIELDS:
        for enquiry in enquiries:
            baseline_reply = results["policy_officer"][enquiry["id"]]["reply"]
            if not isinstance(baseline_reply, dict) or field not in baseline_reply:
                for role in ROLE_INSTRUCTIONS:
                    if role != "policy_officer":
                        unavailable[field].append((enquiry["id"], role))
                continue
            baseline = baseline_reply[field]
            for role in ROLE_INSTRUCTIONS:
                if role == "policy_officer":
                    continue
                role_reply = results[role][enquiry["id"]]["reply"]
                if not isinstance(role_reply, dict) or field not in role_reply:
                    unavailable[field].append((enquiry["id"], role))
                    continue
                value = role_reply[field]
                if value != baseline:
                    movements[field].append((enquiry["id"], role))
        if movements[field]:
            print(f"{field}: " + "; ".join(f"{enquiry} under {role}" for enquiry, role in movements[field]))
        else:
            print(f"{field}: no movement")
        if unavailable[field]:
            print(
                f"  not comparable: "
                + "; ".join(f"{enquiry} under {role}" for enquiry, role in unavailable[field])
            )

    changed_decision = next(
        (
            (enquiry["id"], role)
            for enquiry in enquiries
            for role in ROLE_INSTRUCTIONS
            if role != "policy_officer"
            and field_value(results[role][enquiry["id"]]["reply"], "decision")
            != field_value(results["policy_officer"][enquiry["id"]]["reply"], "decision")
        ),
        None,
    )
    if changed_decision:
        enquiry_id, role = changed_decision
        print(f"\n=== Raw reply with changed decision: {enquiry_id}, {role} ===")
        print(results[role][enquiry_id]["raw"])
    print("\n=== E-07 bilingual_clerk raw reply ===")
    print(results["bilingual_clerk"]["E-07"]["raw"])


if __name__ == "__main__":
    main()