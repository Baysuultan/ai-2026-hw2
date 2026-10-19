"""Compare full chat history with schema-validated compressed memory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import jsonschema
from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = """You are a careful grant-office assistant. Remember the conversation supplied
to you and answer the latest question directly. Distinguish what the applicant stated
from what has been decided; do not invent facts. The grant amount is 250000 KZT for
income band 1 and 150000 KZT for income band 2."""


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def token_count(usage: Any) -> int:
    return int(getattr(usage, "prompt_tokens", 0) or 0)


class ChatSession:
    def __init__(self, client: OpenAI, compressed: bool) -> None:
        self.client = client
        self.compressed = compressed
        self.state: dict[str, Any] | None = None
        self.history: list[dict[str, str]] = []
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0

    def messages(self) -> list[dict[str, str]]:
        prefix = [{"role": "system", "content": SYSTEM_PROMPT}]
        if self.state is not None:
            state_text = json.dumps(self.state, ensure_ascii=False)
            prefix.append({"role": "user", "content": f"Saved conversation state:\n{state_text}"})
        return prefix + self.history

    def call(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        options: dict[str, Any] = {
            "model": MODEL,
            "messages": messages,
        }
        if json_mode:
            options["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**options)
        usage = response.usage
        self.last_prompt_tokens = token_count(usage)
        self.last_completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return response.choices[0].message.content or ""

    def reply(self, user_text: str) -> tuple[str, int]:
        messages = self.messages()
        messages.append({"role": "user", "content": user_text})
        answer = self.call(messages)
        prompt_tokens = self.last_prompt_tokens
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": answer})
        return answer, prompt_tokens

    def compress(self, schema: dict[str, Any]) -> tuple[bool, str]:
        summary_request = (
            "Compress the conversation into exactly one JSON object matching the given schema. "
            "Preserve applicant-stated facts, decisions, constraints, unanswered questions, "
            "and language. Do not invent anything. Return only the object.\n\n"
            f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"
        )
        messages = self.messages()
        messages.append({"role": "user", "content": summary_request})
        raw = self.call(messages, json_mode=True)
        prompt_tokens = self.last_prompt_tokens
        try:
            candidate = json.loads(raw)
        except json.JSONDecodeError:
            return False, f"Summary was not valid JSON; kept conversation history. Reply: {raw}"
        try:
            jsonschema.validate(candidate, schema)
        except jsonschema.ValidationError as error:
            return False, f"Summary failed schema validation ({error.message}); kept conversation history."
        self.state = candidate
        self.history = []
        return True, json.dumps(candidate, ensure_ascii=False, indent=2)


def run_script(client: OpenAI, script: dict[str, Any], schema: dict[str, Any], compressed: bool) -> None:
    label = "B — compressed" if compressed else "A — full history"
    session = ChatSession(client, compressed)
    call_tokens: dict[int, int | None] = {}
    for turn_number, text in enumerate(script["conversation"], start=1):
        if text == "<compress>":
            if compressed:
                ok, detail = session.compress(schema)
                call_tokens[turn_number] = session.last_prompt_tokens
                status = "valid; replaced history" if ok else "invalid; kept history"
                print(f"{label} turn {turn_number}: compression {status}")
                print(detail)
            else:
                call_tokens[turn_number] = None
            continue
        answer, used = session.reply(text)
        call_tokens[turn_number] = used
        print(f"{label} turn {turn_number} assistant: {answer}")

    print(f"\n=== {label}: prompt tokens per scripted turn ===")
    for turn_number in range(1, len(script["conversation"]) + 1):
        value = call_tokens.get(turn_number)
        display = "compress skipped" if value is None else str(value)
        print(f"Turn {turn_number}: {display}")
    sent_counts = [value for value in call_tokens.values() if value is not None]
    print(f"Peak: {max(sent_counts, default=0)}; total: {sum(sent_counts)}")

    print(f"\n=== {label}: probes ===")
    retrieved_count = 0
    for probe in script["probes"]:
        answer, _ = session.reply(probe["question"])
        retrieved = any(expected.casefold() in answer.casefold() for expected in probe["expect_contains"])
        retrieved_count += int(retrieved)
        print(f"{probe['id']} | retrieved={retrieved} | answer={answer}")
    print(f"Retrieved: {retrieved_count}/5")


def interactive(client: OpenAI, schema: dict[str, Any]) -> None:
    session = ChatSession(client, compressed=True)
    print("Chat ready. Enter compress, tokens, or exit.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.casefold() in {"exit", "quit"}:
            break
        if text.casefold() == "tokens":
            print(
                f"Last call: prompt={session.last_prompt_tokens} tokens, "
                f"completion={session.last_completion_tokens} tokens"
            )
            continue
        if text.casefold() == "compress":
            ok, detail = session.compress(schema)
            print("Compression succeeded; history replaced by state." if ok else "Compression failed; history retained.")
            print(detail)
            print(f"Compression call prompt tokens: {session.last_prompt_tokens}")
            continue
        answer, used = session.reply(text)
        print(f"assistant> {answer}\n(prompt tokens: {used})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing. Add it to the ignored .env file.")

    script = read_json(DATA / "chat_script.json")
    schema = read_json(DATA / "memory_state.schema.json")
    client = OpenAI()
    if args.interactive:
        interactive(client, schema)
    else:
        run_script(client, script, schema, compressed=False)
        run_script(client, script, schema, compressed=True)


if __name__ == "__main__":
    main()