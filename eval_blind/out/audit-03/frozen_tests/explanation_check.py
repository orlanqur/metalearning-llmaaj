"""Conservative structural evidence checks for README's five jury criteria.

This is a lint, not an award of jury points or proof of runtime rule use.
Only generated artifacts and the actual adaptation training input are read.
"""
import argparse
import json
import re
from pathlib import Path


def norm(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def rule_ids(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"id", "rule_id", "rule_name"} and isinstance(child, str):
                found.add(child)
            if key in {"rules", "rules_by_id"} and isinstance(child, dict):
                found.update(child)
            found.update(rule_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(rule_ids(child))
    return found


def sections(text):
    return re.split(r"(?m)(?=^#{1,6}\s)", text)


def check(explanation, train, spec):
    text = explanation.read_text(encoding="utf-8") if explanation.exists() else ""
    rows = [json.loads(line) for line in train.read_text(encoding="utf-8").splitlines() if line.strip()]
    indexed = {r["item_id"]: r for r in rows}
    spec_data = json.loads(spec.read_text(encoding="utf-8")) if spec.exists() else None
    ids = rule_ids(spec_data)
    mentioned = sorted(rid for rid in ids if re.search(r"(?<![\w-])" + re.escape(rid) + r"(?![\w-])", text))
    # Explicitly marked rule-like identifiers, independent of the generated schema.
    tokens = re.findall(r"`([A-Za-z][A-Za-z0-9_.:-]*)`", text)
    declared = {s for s in tokens if re.search(r"^(?:rule[_.:-]|[A-Z]{1,8}[_-]\d)|^[a-z]+(?:_[a-z0-9]+){2,}$", s)}
    declared -= {"macro_topic_accuracy", "rules_spec.json", "financial_position", "item_id"}
    unknown_rules = sorted(declared - ids)
    cited = []
    # Opaque IDs are checked against train. Hex-shaped unknown IDs are also flagged.
    unknown_ids = sorted(set(re.findall(r"\b[0-9a-f]{32}\b", text)) - set(indexed))
    positions = sorted((m.start(), iid) for iid in indexed for m in re.finditer(re.escape(iid), text))
    for pos, iid in positions:
        # Isolate each example from the next reference, so neighboring labels cannot satisfy it.
        end = min([p for p, _ in positions if p > pos] + [pos + 2200, len(text)])
        start = max(text.rfind("\n", 0, pos) + 1, pos - 100)
        local = text[start:end]
        row = indexed[iid]
        after_id = text[pos + len(iid):end]
        labels = re.findall(r"\b(?:good|bad)\b", after_id[:300])
        label_ok = bool(labels) and labels[0] == row["label"]
        source = [m.get("content", "") for m in row["conversation"] if isinstance(m, dict)]
        # Require an actual >=24-character text span, not just a valid ID/label.
        normalized = norm(local)
        excerpts = []
        for content in source:
            content = norm(content)
            if len(content) < 24:
                if content and content in normalized:
                    excerpts.append(content)
            else:
                for offset in range(0, len(content) - 23, 8):
                    candidate = content[offset:offset + 24]
                    if candidate in normalized:
                        excerpts.append(candidate)
                        break
        linked = any(rid in local for rid in ids) or bool(re.search(
            r"criterion|criteria|rule|because|illustrat|violation|критери|правил|потому|наруш|criterio|regla", local, re.I))
        cited.append({"item_id": iid, "gold_label": row["label"], "label_matches": label_ok,
                      "source_excerpt_found": bool(excerpts), "criterion_link_found": linked})
    concrete = bool(re.search(r"\b(?:if|when|must|violation|threshold|require|forbid)\b|если|долж|наруш|cuando|debe", text, re.I))
    verdict = bool(re.search(r"\b(?:good|bad)\b", text))
    priority = bool(re.search(r"priorit|precedence|overrid|any violation|first match|decision order|приоритет|любое нарушение|prioridad", text, re.I))
    boundary_sections = [s for s in sections(text) if re.search(
        r"boundar|limitation|uncertaint|ambigui|unsupported|границ|ограничен|неопредел|l[ií]mit", s.split("\n", 1)[0], re.I)]
    boundary_text = "\n".join(boundary_sections)
    boundary_ids = sorted(iid for iid in indexed if iid in boundary_text)
    boundary_conditions = bool(re.search(
        r"\b(?:if|when|without|missing|unseen|short|inconsisten|not cover|absence|limited|not learn)\w*\b|если|отсутств|коротк|не представлен|недостат", boundary_text, re.I))
    linked_examples = [x for x in cited if x["label_matches"] and x["source_excerpt_found"] and x["criterion_link_found"]]
    mismatches = [x for x in cited if not x["label_matches"]]
    criteria = {
        "clear_criteria": {"structural_pass": concrete and verdict and bool(mentioned),
                           "condition_language": concrete, "verdict_language": verdict, "rule_ids": mentioned},
        "clear_priorities": {"structural_pass": priority and verdict, "priority_language": priority},
        "links_to_training_examples": {"structural_pass": bool(linked_examples) and not mismatches and not unknown_ids,
                                       "references": cited, "unknown_ids": unknown_ids},
        "clear_boundaries": {"structural_pass": bool(boundary_sections) and boundary_conditions and bool(boundary_ids),
                             "specific_condition": boundary_conditions, "train_ids": boundary_ids},
        "consistency_with_implementation": {"structural_pass": bool(mentioned) and not unknown_rules,
                                            "spec_exists": spec.exists(), "spec_rule_ids": sorted(ids),
                                            "explained_spec_rule_ids": mentioned,
                                            "unmatched_rule_like_ids": unknown_rules,
                                            "runtime_use": "not_checked_black_box"},
    }
    return {"explanation": str(explanation), "train": str(train), "rules_spec": str(spec),
            "kind": "structural_lint_not_jury_score", "criteria": criteria,
            "all_structural_checks_pass": all(x["structural_pass"] for x in criteria.values()),
            "limits": ["Human judgment is required for all five jury points.",
                       "Rule ID overlap does not prove rules are executed.",
                       "Free-format explanations can require manual review; no keywords are mandatory in README."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--explanation", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--rules-spec", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = check(args.explanation, args.train, args.rules_spec)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["all_structural_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
