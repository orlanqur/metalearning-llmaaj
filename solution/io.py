"""Small JSONL/JSON helpers; independent of upstream src/."""

import json
from pathlib import Path

TOPICS = {"credit", "financial_position", "savings", "spending"}


def load_rows(path, training=False):
    rows, seen = [], set()
    with Path(path).open(encoding="utf-8-sig") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not {"item_id", "topic", "context", "conversation"} <= row.keys():
                raise ValueError(f"Line {line_no}: missing required input fields")
            iid = row["item_id"]
            if not isinstance(iid, str) or not iid.strip() or iid in seen:
                raise ValueError(f"Line {line_no}: invalid or duplicate item_id")
            seen.add(iid)
            if row["topic"] not in TOPICS or not isinstance(row["context"], dict):
                raise ValueError(f"Line {line_no}: invalid topic or context")
            if not isinstance(row["conversation"], list) or not row["conversation"]:
                raise ValueError(f"Line {line_no}: conversation must be a nonempty list")
            for message in row["conversation"]:
                if not isinstance(message, dict) or set(message) != {"role", "content"} or message["role"] not in {"assistant", "user", "system", "tool"} or not isinstance(message["content"], str):
                    raise ValueError(f"Line {line_no}: invalid message")
            if training and row.get("label") not in {"good", "bad"}:
                raise ValueError(f"Line {line_no}: training requires good/bad label")
            # Eval cannot use an accidentally supplied label or translated copy.
            rows.append({key: row[key] for key in ("item_id", "topic", "context", "conversation")}
                        | ({"label": row["label"]} if training else {}))
    if not rows:
        raise ValueError("Input is empty")
    return rows


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
