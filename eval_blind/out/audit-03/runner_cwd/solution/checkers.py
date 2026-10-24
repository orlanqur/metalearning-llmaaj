"""Parameterized deterministic checks. Evidence always includes an assistant quote.

Lexical checks are deliberately narrow ports of the research prototype. Semantic
checks use an explicit runtime; without it they remain not_checked.
"""

from functools import wraps
import fnmatch
import re

from .facts import NUM, contains, dates_in, money, month_in, norm, number


def evidence(facts, reason, **details):
    return {"reason": reason, "quotes": [{"turn": t["index"], "text": t["text"]}
                                           for t in facts.assistant_turns], **details}


def checker(function):
    @wraps(function)
    def wrapped(facts, params, rule_id=""):
        found = function(facts, params)
        return {"rule_id": rule_id, "violated": bool(found), "evidence": found or {}}
    return wrapped


def text(facts):
    return "\n".join(t["normalized"] for t in facts.assistant_turns)


def values(facts):
    return [v for t in facts.assistant_turns for v in t["money"]]


def known(facts, field):
    return any(fnmatch.fnmatchcase(key, field) and value is not None
               for key, value in facts.known_fields.items())


def applicable(facts, condition):
    if any(not known(facts, field) for field in condition.get("fields", [])):
        return False
    if any(not facts.flags.get(flag) for flag in condition.get("flags", [])):
        return False
    return True


@checker
def poison_number_present(f, p):
    kind = p["kind"]
    if not f.assistant_turns:
        return None
    ns = values(f)
    first = f.assistant_turns[0]
    if p.get("scope") == "first_amount":
        ns = first["money"][:1]
    wrong = f.poison.get(kind, [])
    if p.get("cue") and not re.search(p["cue"], first["normalized"]):
        return None
    if kind == "gross_refunds":
        av = f.expected["averages"]
        valid = [av[k] for k in ("net_purchases", "combined")] + [av["combined"]*3] if av else []
        if any(contains(ns, v) for v in valid):
            return None
    matches = [v for v in wrong if contains(ns, v)]
    if matches:
        return evidence(f, "Context-derived poison amount appears in the scoped answer", kind=kind, expected_poison=matches, observed=ns)


@checker
def required_number_missing(f, p):
    kind = p["kind"]
    if kind == "net_after_debt":
        required = [f.expected[k] for k in ("net_after_debt", "net_usable_assets", "net_liquid")]
    elif kind == "available_now":
        required = f.expected["spendable_accounts"] + [f.expected["liquid"]]
    elif kind == "other_transfers":
        # An ordinary net-purchases answer is allowed. Only explicit total exclusion
        # is a candidate violation, as in the original judge.
        if not re.search(p["exclusion_pattern"], text(f)):
            return None
        required = [m["other"] for m in f.last3 if m["other"] > 0]
        if f.expected["averages"]:
            required += [f.expected["averages"]["other"], sum(m["other"] for m in f.last3)]
    else:
        required = f.expected.get(kind, [])
        required = required if isinstance(required, list) else [required]
    if required and not any(contains(values(f), v) for v in required):
        return evidence(f, "Required context-derived amount is absent", kind=kind, expected_any=required)


@checker
def asks_known_field(f, p):
    # One criterion across populated field types, as in the source KNOWN_DATA
    # family. Each clause still requires its own field to exist on this row.
    for clause in p.get("clauses", [p]):
        if known(f, clause["field"]):
            for pattern in clause["patterns"]:
                match = re.search(pattern, text(f))
                if match:
                    return evidence(f, "Requests a field already populated in context", field=clause["field"], match=match.group())


@checker
def denies_known_field(f, p):
    if known(f, p["field"]):
        for pattern in p["patterns"]:
            match = re.search(pattern, text(f))
            if match:
                return evidence(f, "Denies access to a populated context field", field=p["field"], match=match.group())


@checker
def wrong_period(f, p):
    if not f.assistant_turns:
        return None
    if p["kind"] == "last_month":
        previous = f.expected["previous_month"]
        if not previous:
            return None
        for i, message in enumerate(f.conversation[:-1]):
            reply = f.conversation[i+1]
            if message["role"] != "user" or reply["role"] != "assistant" or not re.search(p["request_pattern"], norm(message["content"])):
                continue
            answer = re.split(p["offer_pattern"], reply["content"], flags=re.I)[0]
            if not month_in(answer, int(previous[-2:])) and previous not in answer:
                return evidence(f, "Last-month answer omits the preceding calendar month", expected_month=previous, reply=answer)
    elif p["kind"] == "default_three_months":
        user = next((norm(m["content"]) for m in f.conversation if m["role"] == "user"), "")
        if not re.search(p["request_pattern"], user) or len(f.last3) != 3:
            return None
        first = f.assistant_turns[0]["normalized"]
        answer = re.split(p["offer_pattern"], first)[0]
        endpoints = [f.last3[0]["month"], f.last3[-1]["month"]]
        covered = all(month_in(answer, int(m[-2:])) or m in answer for m in endpoints)
        if not covered or re.search(p["wrong_window_pattern"], first):
            return evidence(f, "Default spending window is not the last three complete months", expected_months=[m["month"] for m in f.last3])


@checker
def rate_mismatch(f, p):
    a = text(f)
    claimed = [number(v) for v in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", a)]
    allowed = [r["rate"]*100 for r in f.rates if r["rate"] is not None]
    accounts = f.context.get("accounts", [])
    allowed += [x["annual_rate"]*100 for x in accounts if "annual_rate" in x]
    tolerance = p.get("absolute_tolerance", 0.05)
    if claimed and allowed and any(not contains(allowed, v, tolerance, 0) for v in claimed):
        return evidence(f, "Percentage is outside context rates for the selected subscription", expected=allowed, observed=claimed)
    product = p.get("product")
    if product:
        valid = [r["rate"]*100 for r in f.rates if norm(r["product"]) == norm(product) and r["rate"] is not None]
        valid += [x["annual_rate"]*100 for x in accounts if norm(x.get("product", "")) == norm(product) and "annual_rate" in x]
        mentions = re.findall(re.escape(norm(product)) + p["following_pattern"], a)
        if valid and any(not contains(valid, number(v), tolerance, 0) for v in mentions):
            return evidence(f, "Rate attributed to a product contradicts that product's context rate", product=product, expected=valid, observed=mentions)
        if p.get("exclusive_unless") and p["exclusive_unless"] not in a and valid and any(not contains(valid, v, tolerance, 0) for v in claimed):
            return evidence(f, "Only this product is discussed but a different product's rate is given", product=product, expected=valid, observed=claimed)


@checker
def date_mismatch(f, p):
    expected = [tuple(d) for d in f.dates]
    found = dates_in("\n".join(t["text"] for t in f.assistant_turns))
    wrong = [d for d in found if not any(d[1:] == e[1:] and (d[0] is None or d[0] == e[0]) for e in expected)]
    if expected and wrong:
        return evidence(f, "Asserted date is absent from context", unexpected_dates=sorted(wrong, key=str), expected_dates=f.dates)


@checker
def lexical_predicate(f, p):
    """Narrow inherited phrase match, with a separate context applicability gate."""
    cs = f.expected["credit_statement"]
    if p.get("guard") == "paid" and not (cs.get("paid_this_period", 0) >= cs.get("no_interest_payment", float("inf"))):
        return None
    if p.get("guard") == "minimum_below_full" and not (cs.get("minimum_payment", float("inf")) < cs.get("no_interest_payment", 0)):
        return None
    if p.get("guard") == "no_tool_confirmation" and any(m["role"] == "tool" for m in f.conversation):
        return None
    user = "\n".join(norm(m["content"]) for m in f.conversation if m["role"] == "user")
    if p.get("user_pattern") and not re.search(p["user_pattern"], user):
        return None
    for pattern in p["patterns"]:
        match = re.search(pattern, text(f))
        if match:
            return evidence(f, "Inherited lexical predicate matched", match=match.group(), predicate=p["meaning"])


@checker
def amount_mismatch(f, p):
    if not f.assistant_turns:
        return None
    kind = p["kind"]
    user = next((norm(m["content"]) for m in f.conversation if m["role"] == "user"), "")
    first = f.assistant_turns[0]
    if kind == "remaining_debt":
        cs = f.expected["credit_statement"]
        if "total_debt" not in cs:
            return None
        valid = [cs["total_debt"], max(0, cs["total_debt"]-cs.get("paid_this_period", 0))]
        for value in re.findall(p["pattern"] + "(" + NUM + ")", text(f)):
            if not contains(valid, number(value)):
                return evidence(f, "Unsupported remaining debt", expected_any=valid, observed=number(value))
    elif kind == "merchant_confirmation":
        if not re.search(p["agreement_pattern"], first["normalized"]):
            return None
        for key, v in f.transactions.items():
            category, merchant, ym = key.split("|")
            if category == "merchant" and merchant and merchant in user and (ym in user or month_in(user, int(ym[-2:]))):
                if first["money"] and not contains([v["net"]], first["money"][0]):
                    return evidence(f, "Confirmed merchant amount disagrees with completed transactions", merchant=merchant, month=ym, expected=v["net"], observed=first["money"][0])
    elif kind == "monthly_refund":
        if not re.search(p["request_pattern"], user):
            return None
        for m in f.months:
            if m["refunds"] > 0 and month_in(user, int(m["month"][-2:])) and first["money"] and contains(first["money"][:1], m["purchases"]):
                return evidence(f, "Refund-adjusted monthly amount equals gross purchases", month=m["month"], expected=m["net_purchases"], observed=first["money"][0])
    elif kind == "category_refund":
        if not re.search(p["request_pattern"], user):
            return None
        category = [v for k, v in f.transactions.items() if k.startswith("category|"+p["category"]+"|") and k.split("|")[-1] in {m["month"] for m in f.last3}]
        if category and sum(v["refunds"] for v in category) > 0 and contains(first["money"], sum(v["gross"] for v in category)):
            return evidence(f, "Category total uses gross purchases despite refunds", category=p["category"], expected=sum(v["net"] for v in category))


@checker
def turn_contradiction(f, p):
    """Bind a claim to a context field, not to every number in different turns.

    A wrong replacement can be caught even if the initial correct value was only
    in context. This includes the original judge's AMOUNT checks.
    """
    for turn in f.assistant_turns:
        if not re.search(p["claim_pattern"], turn["normalized"]):
            continue
        if p["kind"] == "account_balance":
            product = p["product"]
            if norm(product) not in turn["normalized"]:
                continue
            valid = [f.expected["balances"][product]] if product in f.expected["balances"] else []
        elif p["kind"] == "monthly_purchases":
            scoped = [m for m in f.months if m["month"] in turn["normalized"] or month_in(turn["normalized"], int(m["month"][-2:]))]
            valid = [m[k] for m in (scoped or f.months) for k in ("purchases", "net_purchases")]
        else:
            valid = [v for key, v in f.known_fields.items() if fnmatch.fnmatchcase(key, p["field"]) and isinstance(v, (float, int))]
        if valid and any(not contains(valid, v) for v in turn["money"]):
            return evidence(f, "Claimed amount differs from the unchanged context", turn=turn["index"], expected_any=valid, observed=turn["money"])


@checker
def convention_candidate(f, p):
    """Deliberately strict hypotheses; verify, not an allowlist constant, rejects them."""
    a = text(f)
    kind = p["kind"]
    if kind == "other_transfers_must_be_in_total":
        av = f.expected["averages"]
        if av and av["other"] > 0 and contains(values(f), av["net_purchases"]):
            return evidence(f, "Strict hypothesis forbids reporting net purchases separately from transfers")
    elif kind == "own_must_be_after_hold":
        if f.expected["on_hold"] > 0 and contains(values(f), f.expected["own_gross"]):
            return evidence(f, "Strict hypothesis forbids a gross own-funds amount even when hold is disclosed")
    elif kind == "link_targets":
        targets = re.findall(r"\]\((lnk_[^)]+)\)", a)
        if any(target != p["target"] for target in targets):
            return evidence(f, "Strict hypothesis requires one observed link target", required_target=p["target"], observed=targets)
    elif kind == "untranslated_anchor":
        anchors = re.findall(r"\[([^]]+)\]\(lnk_[^)]+\)", a)
        body = re.sub(r"\[[^]]+\]\([^)]+\)", "", a)
        if (re.search("[а-я]", body) and any(re.fullmatch("[a-z ]+", x) for x in anchors)
                or not re.search("[а-я]", body) and any(re.search("[а-я]", x) for x in anchors)):
            return evidence(f, "Strict hypothesis rejects an untranslated link anchor")
    elif kind == "typo":
        products = [x.get("product", "") for x in f.context.get("accounts", []) + f.context.get("savings_rates", [])]
        expected = {token for product in products for token in re.findall(r"\w{5,}", norm(product))}
        for observed in re.findall(r"\b\w{4,}\b", a):
            for correct in expected:
                if observed != correct and one_edit_apart(observed, correct):
                    return evidence(f, "Strict hypothesis rejects a one-letter product typo", observed=observed, expected=correct)
    elif kind in ("interest_convention", "residual_interest"):
        match = re.search(p["pattern"], a)
        if match:
            return evidence(f, "Strict convention hypothesis matched; labels decide its status", kind=kind, match=match.group())


def one_edit_apart(left, right):
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1
    if abs(len(left)-len(right)) != 1:
        return False
    short, long = sorted((left, right), key=len)
    return any(short == long[:i]+long[i+1:] for i in range(len(long)))


def llm_predicate(facts, params, runtime=None, item_id=None):
    from .semantic import llm_predicate as semantic_predicate
    return semantic_predicate(facts, params, runtime, item_id)


CHECKERS = {fn.__name__: fn for fn in (poison_number_present, required_number_missing,
            asks_known_field, denies_known_field, wrong_period, rate_mismatch,
            date_mismatch, lexical_predicate, amount_mismatch, turn_contradiction, convention_candidate)}


def run_check(rule, facts, runtime=None, item_id=None):
    if rule["topic"] not in (facts.topic, "all") or not applicable(facts, rule["applicability"]):
        return {"rule_id": rule["id"], "violated": False, "evidence": {"applicable": False}}
    if rule["checker"] == "llm_predicate":
        result = llm_predicate(facts, rule["params"], runtime, item_id)
        status = result["verdict"] if result else "not_checked"
        return {"rule_id": rule["id"], "violated": None if status in ("unknown", "not_checked") else status == "yes",
                "evidence": {"status": status, "reason": result["reason"] if result else "Model unavailable",
                             "quotes": [{"turn": t["index"], "text": result["quote"]} for t in facts.assistant_turns
                                        if result and result["quote"] and result["quote"] in t["text"]]}}
    if rule["checker"] == "dsl":
        from .dsl import evaluate
        try:
            violated = evaluate(rule["params"]["expression"], facts)
            return {"rule_id": rule["id"], "violated": violated,
                    "evidence": evidence(facts, "DSL condition", status="unknown" if violated is None else "checked")}
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            return {"rule_id": rule["id"], "violated": None,
                    "evidence": {"status": "invalid_dsl", "reason": "Rejected unsafe or malformed DSL"}}
    return CHECKERS[rule["checker"]](facts, rule["params"], rule["id"])
