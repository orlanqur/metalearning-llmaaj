#!/usr/bin/env python3
"""Explain one prediction using solution's saved rules and train retrieval."""

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solution.eval import predict
from solution.facts import FactSheet
from solution.io import TOPICS
from solution.llm import ChatClient
from solution.semantic import SemanticRuntime


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_example(args):
    if args.id:
        if args.context_file or args.topic:
            raise ValueError("--id cannot be combined with --context-file or --topic")
        for name in ("public_test.csv", "public_train.csv"):
            with (ROOT / "data" / name).open(encoding="utf-8-sig", newline="") as stream:
                for record in csv.DictReader(stream):
                    if record["item_id"] == args.id:
                        # Explicitly discard labels and alternative translations.
                        return dict(item_id=record["item_id"], topic=record["topic"],
                                    context=json.loads(record["context"]),
                                    conversation=json.loads(record["conversation"])), name
        raise ValueError(f"Unknown ID: {args.id}")
    if not args.context_file:
        raise ValueError("--dialog-file requires --context-file")
    context = read_json(args.context_file)
    dialog = read_json(args.dialog_file)
    if not isinstance(context, dict):
        raise ValueError("Context must be a JSON object")
    topic = args.topic or context.get("topic")
    dialog_topic = None
    if isinstance(dialog, dict):
        dialog_topic = dialog.get("topic")
        topic = topic or dialog_topic
        dialog = dialog.get("conversation")
    for supplied in (context.get("topic"), dialog_topic):
        if supplied and supplied != topic:
            raise ValueError("Conflicting topic values")
    return dict(item_id="custom", topic=topic,
                context=context.get("context", context), conversation=dialog), "files"


def validate_example(row):
    if row["topic"] not in TOPICS:
        raise ValueError("Provide --topic or a JSON envelope with topic: " + ", ".join(sorted(TOPICS)))
    if not isinstance(row["context"], dict):
        raise ValueError("Context must be a JSON object")
    dialog = row["conversation"]
    if not isinstance(dialog, list) or not dialog:
        raise ValueError("Dialog must be a nonempty JSON array of role/content messages")
    for message in dialog:
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] not in {"assistant", "user", "system", "tool"}
                or not isinstance(message["content"], str)):
            raise ValueError("Invalid dialog message; expected role and string content")


def explain(row, artifacts):
    """Same engine as eval --no-model; read-only cache, no HTTP or output files."""
    validate_example(row)
    manifest = read_json(artifacts / "rules_spec.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported rules_spec schema_version")
    index = read_json(artifacts / "fewshot_index.json")
    # Disabled clients can read existing cached responses but never write/call HTTP.
    client = ChatClient(artifacts / "cache", disabled=True, dotenv=ROOT / ".env")
    runtime = SemanticRuntime(client, index)
    checks = []
    label = predict(row, manifest["rules"], runtime, manifest.get("default_label", "good"),
                    manifest.get("topic_majority"), checks)
    hit = next((check for check in checks if check["violated"] is True), None)
    unknown = [check["rule_id"] for check in checks if check["violated"] is None]
    rule = next((rule for rule in manifest["rules"] if hit and rule["id"] == hit["rule_id"]), None)
    return dict(label=label, rule=rule, hit=hit, unknown=unknown,
                majority=bool(manifest.get("topic_majority")),
                examples=runtime.fewshot(FactSheet.from_row(row), row["item_id"]))


def quote_lines(text):
    return ["> " + line for line in text.splitlines()]


def render(row, source, result):
    lines = [f"Example: {row['item_id']} ({source}; topic={row['topic']})",
             "Mode: offline; saved semantic cache allowed; no network calls",
             f"Verdict: {result['label']}"]
    if result["hit"]:
        rule, evidence = result["rule"], result["hit"]["evidence"]
        lines += [f"Rule: {rule['id']} (priority={rule['priority']})",
                  f"Condition: {rule['violation']}",
                  "Decision: first violated active rule in (priority, id) order; later rules not evaluated.",
                  f"Evidence: {evidence.get('reason', 'Rule matched')}"]
        for quote in evidence.get("quotes", []):
            lines.append(f"Assistant quote (turn {quote['turn']}):")
            lines.extend(quote_lines(quote["text"]))
        details = {k: v for k, v in evidence.items() if k not in {"quotes", "reason"}}
        if details:
            lines.append("Checker details (may include context-derived values): " + json.dumps(details, ensure_ascii=False))
    else:
        fallback = result["unknown"] and result["majority"]
        lines += ["Rule: none fired",
                  "Decision: " + ("unchecked rules; manifest topic_majority (default_label if topic absent)"
                                   if fallback else "manifest default_label")]
        if not result["unknown"]:
            lines.append("No violation found by evaluated active rules; this is not a guarantee of correctness.")
        sample = next((m for m in row["conversation"] if m["role"] == "assistant"), row["conversation"][0])
        lines.append(f"Dialog excerpt ({sample['role']}; illustration, not violation evidence):")
        lines.extend(quote_lines(sample["content"]))
    if result["unknown"]:
        lines.append("Unchecked/unknown rules: " + ", ".join(result["unknown"]))
    lines += ["", "Similar train examples (TF-IDF dialog; same topic; self/identical dialog excluded):"]
    for example in result["examples"]:
        lines.append(f"- {example['item_id']} | label={example['label']}")
        message = next((m for m in example["conversation"] if m["role"] == "assistant"), example["conversation"][0])
        lines.append(f"  {message['role']} excerpt (first 220 characters):")
        lines.extend(quote_lines(message["content"][:220]))
    if len(result["examples"]) < 2:
        lines.append(f"Only {len(result['examples'])} eligible train examples in this index.")
    lines.append("Similarity does not imply the same violation; labels belong to whole train conversations.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--id", help="Exact item_id from public_test.csv or public_train.csv")
    inputs.add_argument("--dialog-file", type=Path, help="UTF-8 JSON messages or {topic, conversation}")
    parser.add_argument("--context-file", type=Path, help="UTF-8 JSON context or {topic, context}")
    parser.add_argument("--topic", choices=sorted(TOPICS), help="Required for raw JSON files without topic")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts/step2")
    args = parser.parse_args(argv)
    try:
        row, source = load_example(args)
        print(render(row, source, explain(row, args.artifacts)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"demo failed: {error}\n")


if __name__ == "__main__":
    main()
