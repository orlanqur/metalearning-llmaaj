"""Train-only template instantiation, exhaustive verification, and artifact export."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time

from . import __version__
from .io import load_rows, write_json
from .rules_library import instantiate
from .verify import training_summary, verify
from .llm import ChatClient, load_dotenv
from .semantic import SemanticRuntime, build_index
from .induce import induce


def manifest_hash(manifest):
    return hashlib.sha256((json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode()).hexdigest()


def induction_trail(induction, witnesses):
    lines = ["", "## Induction trail", "",
             "Only bad training conversations with no active-rule violation enter the residual set. "
             "Each is paired with the nearest good conversation of the same topic by context TF-IDF. "
             "Each pair proposes up to three conditions on facts; every candidate is verified on all train rows. "
             "One false positive rejects that version, with at most one narrowing attempt. "
             "Residuals are recomputed after each round. Rejected counts include disabled boundaries and duplicates; "
             "narrowed counts are attempts, a subset of accepted/rejected proposals.", "",
             f"Status: `{induction.get('status', 'not_run')}`. Stop: `{induction.get('stop_reason', 'not_run')}`.", "",
             "| Round | Residuals before / after | Proposed | Accepted | Narrowed | Rejected |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in induction.get("rounds", []):
        lines.append(f"| {r['round']} | {len(r['residual_before'])} / {len(r.get('residual_after', []))} | "
                     f"{r['proposed']} | {r['accepted']} | {r['narrowed']} | {r['rejected']} |")
    for d in induction.get("decisions", []):
        final = d.get("final_rule", {})
        initial = d.get("initial_verification", {})
        name = final.get("id", d["proposal"].get("name", "invalid proposal"))
        lines += ["", f"- Round {d['round']}, `{name}`: **{d['status']}**. "
                  + ("Reasons: " + ", ".join(d["reasons"]) + "." if d["reasons"] else "TP >= 1, FP = 0; all applicable train rows checked.")]
        if final.get("status") == "active":
            selected = final["examples"] + final["nonviolating_good"]
            lines.append("  Training witnesses: " + "; ".join(
                f"[{w['item_id']}](#example-{w['item_id']}) (expert label {w['label']})" for w in selected) + ".")
            witnesses.update({w["item_id"]: w for w in selected})
        counterexamples = {w["item_id"]: w for r in (initial, final) for w in r.get("counterexamples", [])}
        if counterexamples:
            lines.append("  Rejected version: false positives on good. Counterexamples: " + "; ".join(
                f"[{w['item_id']}](#example-{w['item_id']}) (expert label good)" for w in counterexamples.values()) + ".")
            witnesses.update(counterexamples)
        elif d["status"] != "active":
            lines.append("  No measured violating good counterexample: rejection is for the reason above, not an observed FP.")
    return lines


def explain(manifest):
    """Render only the same manifest that eval loads, including its evidence."""
    rules = manifest["rules"]
    lines = ["# Explanation — learned rules and deterministic checks", "",
             f"Manifest SHA256: `{manifest_hash(manifest)}`", "",
             "## 1. Clear criteria", "",
             f"Adaptation mode: `{manifest.get('adapt_mode', 'hybrid')}`. "
             "From-scratch mode starts with an empty rule set and never instantiates the family library; "
             "hybrid mode verifies inherited candidates first. Context supplies amounts, dates, rates and periods. "
             "All active rules require TP >= 1 and FP = 0 with no unchecked rows. Induced rules must also cause "
             "no accuracy loss in any topic. These observations do not establish universal rules.", "",
             "| Rule | Topic | Criterion | TP | FP | Precision | Bad coverage |", "|---|---|---|---:|---:|---:|---:|"]
    for r in rules:
        if r["status"] == "active":
            lines.append(f"| `{r['id']}` | {r['topic']} | {r['violation']} | {r['TP']} | {r['FP']} | {r['precision']:.3f} | {r['coverage']:.3f} |")
    lines += ["", "Coverage denominator: all bad training rows in the rule's topic; `all` means all four topics for shared formatting conventions. Precision denominator: TP + FP.",
              "", "## 2. Clear priorities", "",
              "Eval orders active rules by `(priority, id)`. Any violation in any assistant turn makes the entire conversation bad. "
              "No good example or boundary overrides an active violation. If none fires and a check is unknown/unavailable, "
              "use the saved topic majority; otherwise use the manifest default_label. Unknown is never itself a violation. "
              "Numeric tolerance is max(1 currency unit, 0.5% of expected); rate tolerance is 0.05 percentage points.", ""]
    lines += [f"- Priority {priority}: " + ", ".join(f"`{r['id']}`" for r in rules if r["status"] == "active" and r["priority"] == priority)
              for priority in sorted({r["priority"] for r in rules if r["status"] == "active"})]
    lines += ["", "## 3. Links to training examples", ""]
    witnesses = {}
    for r in rules:
        if r["status"] != "active":
            continue
        selected = r["examples"][:2] + r["nonviolating_good"][:1]
        for w in selected:
            witnesses[w["item_id"]] = w
        lines.append(f"- `{r['id']}`: " + "; ".join(f"[{w['item_id']}](#example-{w['item_id']}) ({w['label']})" for w in selected))
    lines += ["", "## 4. Clear boundaries", "",
              "FP > 0 means the strict template conflicts with at least one good label and is disabled. "
              "Induced candidates with FP receive one narrowing round and must then pass the saved acceptance gates. "
              "This is evidence against that candidate, not permission for arbitrary errors. TP = 0 means insufficient support. "
              "Unavailable semantic checks remain explicitly not_checked. No boundary was assigned manually.", ""]
    for r in rules:
        if r["status"] != "boundary":
            continue
        lines.append(f"- `{r['id']}` — {r['violation']} Status: {r['status_reason']}; TP={r['TP']}, FP={r['FP']}.")
        selected = r["counterexamples"][:2] + r["examples"][:1]
        if not r["examples"]:
            selected += r["nonviolating_good"][:1]
        for w in selected:
            witnesses[w["item_id"]] = w
        if selected:
            lines.append("  Evidence: " + "; ".join(f"[{w['item_id']}](#example-{w['item_id']}) ({w['label']})" for w in selected) + ".")
        if not r["examples"]:
            lines.append("  No violating bad witness; no good/bad pair is claimed.")
    lines += ["", "## 5. Consistency with implementation", "",
              "This file is rendered from `rules_spec.json`. `solution.eval` uses its `rules[].status`, `topic`, `applicability`, "
              "`checker`, `params` and `priority`. `solution.checkers.run_check` executes the saved rule; eval never re-instantiates templates "
              "or reads test labels. Labeled train examples are retrieved from fewshot_index.json; the current example is excluded. "
              "TP/FP witnesses and full quotes are persisted in that same manifest. "
              "`llm_predicate` returns yes/no/unknown with an assistant quote, or None if unavailable. "
              "The cache key binds model, system, user and schema. Eval reads artifacts/cache and writes its output cache.", "",
              "### Internal check (limited)", "",
              f"Train resubstitution macro topic accuracy: {manifest['training_summary']['macro_topic_accuracy']:.6f}. "
              "Grouped-context split: not run. This is fitting-set performance, not an independent estimate. "
              + manifest.get("source_limit", "Inherited templates were reconstructed using both public splits.") + " "
              "Public test is a development comparison, not a clean independent holdout.", "",
              "### Train evaluation through the same eval engine", "",
              "| Topic | Correct / N | Accuracy | TP | FP | FN | TN |", "|---|---:|---:|---:|---:|---:|---:|"]
    for topic, g in sorted(manifest["training_summary"]["by_topic"].items()):
        lines.append(f"| {topic} | {g['correct']} / {g['n']} | {g['accuracy']:.6f} | {g['TP']} | {g['FP']} | {g['FN']} | {g['TN']} |")
    induction = manifest.get("induction", {})
    lines += induction_trail(induction, witnesses)
    lines += ["",
              "## Limitations", "",
              f"Model steps: `{manifest.get('model_status', 'not_checked')}`. "
              "Without an API key, new rules, semantic criteria, the zero-shot baseline and rediscovery are not confirmed "
              "by a live model. The cache may replay a previously verified answer; API errors and unknown verdicts are logged. "
              "Support counts exact distinct contexts; near-duplicate grouping and cross-validation are not implemented. "
              "Agreement on train does not prove quality on the private set.", "",
              "### Quoted training evidence", ""]
    for iid, w in sorted(witnesses.items()):
        lines += [f'<a id="example-{iid}"></a>', f"**{iid} — expert label `{w['label']}`**", ""]
        for q in w["evidence"].get("quotes", []):
            lines += [f"> Turn {q['turn']}: " + q["text"].replace("\n", "\n> "), ""]
    return "\n".join(lines) + "\n"


def adapt(input_path="/input/train.jsonl", artifacts="/artifacts", language="original", disable_family=None, no_model=False,
          from_scratch=False):
    started = time.monotonic()
    load_dotenv()
    mode = "from_scratch" if from_scratch else os.getenv("ADAPT_MODE", "hybrid")
    if mode not in ("hybrid", "from_scratch"):
        raise ValueError("ADAPT_MODE must be hybrid or from_scratch")
    rows = load_rows(input_path, training=True)
    output = Path(artifacts)
    output.mkdir(parents=True, exist_ok=True)
    index = build_index(rows)
    write_json(output / "fewshot_index.json", index)
    client = ChatClient(output / "cache", disabled=no_model,
                        max_calls=max(0, int(os.getenv("INDUCTION_MAX_CALLS", "400"))))
    runtime = SemanticRuntime(client, index)
    candidates = [] if mode == "from_scratch" else [r for r in instantiate(rows) if r["family"] != disable_family]
    rules = verify(candidates, rows, runtime)
    print(f"[adapt] {mode}: {len(candidates)} initial candidates verified; "
          f"{client.network_calls} HTTP calls", flush=True)
    rules, induction_log = induce(rows, rules, runtime, output)
    topic_majority = {}
    for topic in sorted({r["topic"] for r in rows}):
        counts = Counter(r["label"] for r in rows if r["topic"] == topic)
        topic_majority[topic] = "bad" if counts["bad"] > counts["good"] else "good"
    summary = training_summary(rules, rows, runtime, topic_majority=topic_majority)
    train_hash = hashlib.sha256(Path(input_path).read_bytes()).hexdigest()
    manifest = dict(schema_version=1, solution_version=__version__, train_sha256=train_hash,
                    default_label="good", topic_majority=topic_majority, disabled_family=disable_family, adapt_mode=mode,
                    selection_policy={"template": "TP>=1 and FP=0; no unchecked rows", "induced": induction_log["selection_policy"]},
                    model_status=("partial_api_unavailable" if client.circuit_open else "budget_exhausted" if client.budget_exhausted
                                  else "enabled" if client.available else "skipped_no_key_or_disabled"),
                    induction=induction_log,
                    source_limit=("No family instantiated; inherited FactSheet and grammar illustrations remain prior knowledge."
                                  if mode == "from_scratch" else "Template library inherited from a reconstruction that inspected both public splits."),
                    rules=rules, training_summary=summary)
    write_json(output / "rules_spec.json", manifest)
    persisted = json.loads((output / "rules_spec.json").read_text(encoding="utf-8"))
    (output / "explanation.md").write_text(explain(persisted), encoding="utf-8")
    prompt = ["Check each active rule in its topic. Any supported violation means bad.",
              "Unknown/unavailable uses topic_majority; otherwise default_label. Boundaries never override an active hit."]
    prompt += [f"{r['status']} | {r['id']} | {r['violation']}" for r in persisted["rules"]]
    (output / "judge_prompt.txt").write_text("\n".join(prompt)+"\n", encoding="utf-8")
    code_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}
    meta = dict(created_at=datetime.now(timezone.utc).isoformat(), solution_version=__version__,
                python=platform.python_version(), model=client.eval_model if client.available else None, adapt_mode=mode,
                induction_max_calls=client.max_calls,
                **client.stats(), wall_seconds=time.monotonic()-started, manifest_sha256=manifest_hash(persisted),
                language=language, language_note="Caller-declared representation; original is multilingual.",
                train_rows=len(rows), train_sha256=train_hash, topic_counts=dict(Counter(r["topic"] for r in rows)),
                statuses=dict(Counter(r["status"] for r in rules)), code_sha256=code_hashes,
                internal_validation="train_resubstitution_only; grouped_split_not_run")
    write_json(output / "run_meta.json", meta)
    write_json(output / "model_log.json", dict(stats=client.stats(), model_events=client.events, semantic_events=runtime.events))
    return dict(train_rows=len(rows), candidates=len(rules), statuses=meta["statuses"], training_summary=summary,
                artifacts=str(output))
