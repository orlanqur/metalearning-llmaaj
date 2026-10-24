"""Evaluate every candidate on all train rows, retaining auditable witnesses."""

from .checkers import applicable, run_check
from .facts import FactSheet
from .llm import canonical, pmap
import hashlib


def verify(candidates, rows, runtime=None):
    prepared = [(row, FactSheet.from_row(row)) for row in rows]
    verified = []
    for candidate in candidates:
        rule = dict(candidate)
        examples, counterexamples, nonviolating_good = [], [], []
        checked = unchecked = applicable_count = bad_count = good_count = 0
        topic_stats = {}
        # Model-backed checks dominate adapt time: fetch them concurrently, then aggregate in row order.
        if runtime is not None and runtime.client.available and rule.get("checker") == "llm_predicate":
            results = pmap(lambda rf: run_check(rule, rf[1], runtime, rf[0]["item_id"])
                           if rule["topic"] in (rf[1].topic, "all") else None, prepared)
        else:
            results = [None] * len(prepared)
        for (row, facts), ready in zip(prepared, results):
            # Every candidate visits the full dataset; its topic/applicability gate
            # is part of the candidate, not an evaluation subset chosen after hits.
            if rule["topic"] not in (facts.topic, "all"):
                continue
            group = topic_stats.setdefault(facts.topic, dict(TP=0, FP=0, bad_total=0, good_total=0))
            group["bad_total" if row["label"] == "bad" else "good_total"] += 1
            bad_count += row["label"] == "bad"
            good_count += row["label"] == "good"
            result = ready or run_check(rule, facts, runtime, row["item_id"])
            applies = applicable(facts, rule["applicability"])
            applicable_count += applies
            if result["violated"] is None:
                unchecked += 1
            elif applies:
                checked += 1
            if result["violated"]:
                group["TP" if row["label"] == "bad" else "FP"] += 1
                witness = dict(item_id=row["item_id"], label=row["label"], evidence=result["evidence"],
                               context_hash=hashlib.sha256(canonical(row["context"]).encode()).hexdigest())
                (examples if row["label"] == "bad" else counterexamples).append(witness)
            elif applies and result["violated"] is False and row["label"] == "good":
                nonviolating_good.append(dict(item_id=row["item_id"], label="good",
                    evidence={"quotes": [{"turn": t["index"], "text": t["text"]} for t in facts.assistant_turns]}))
        tp, fp = len(examples), len(counterexamples)
        stats = dict(TP=tp, FP=fp, precision=tp/(tp+fp) if tp+fp else None,
                     coverage=tp/bad_count if bad_count else None, bad_total=bad_count,
                     good_total=good_count, applicable=applicable_count, checked=checked, not_checked=unchecked)
        for group in topic_stats.values():
            hits = group["TP"] + group["FP"]
            group["precision"] = group["TP"]/hits if hits else None
            group["coverage"] = group["TP"]/group["bad_total"] if group["bad_total"] else None
        reason = "zero_false_positives_with_support" if tp and not fp else ("false_positives" if fp else "no_positive_support")
        if unchecked:
            reason = "not_checked"
        rule.update(status="active" if tp and not fp and not unchecked else "boundary",
                    status_reason=reason, **stats, by_topic=topic_stats,
                    evaluated_rows=len(rows), examples=examples, counterexamples=counterexamples,
                    example_item_ids=[x["item_id"] for x in examples],
                    counterexample_item_ids=[x["item_id"] for x in counterexamples],
                    distinct_contexts=len({x["context_hash"] for x in examples}),
                    nonviolating_good=nonviolating_good[:2])
        verified.append(rule)
    return verified


def training_summary(rules, rows, runtime=None, default_label="good", topic_majority=None):
    """Resubstitution diagnostic, explicitly not grouped-split validation."""
    from .eval import predict
    by_topic = {}
    errors = []
    for row in rows:
        f = FactSheet.from_row(row)
        predicted = predict(row, rules, runtime, default_label, topic_majority)
        group = by_topic.setdefault(f.topic, dict(n=0, correct=0, TP=0, FP=0, FN=0, TN=0))
        group["n"] += 1
        group["correct"] += predicted == row["label"]
        group[("T" if predicted == row["label"] else "F") + ("P" if predicted == "bad" else "N")] += 1
        if predicted != row["label"]:
            errors.append(dict(item_id=row["item_id"], topic=f.topic, expected=row["label"], predicted=predicted))
    for group in by_topic.values():
        group["accuracy"] = group["correct"]/group["n"]
    return dict(kind="train_resubstitution", grouped_split="not_run", by_topic=by_topic,
                macro_topic_accuracy=sum(g["accuracy"] for g in by_topic.values())/len(by_topic), errors=errors)
