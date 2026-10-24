"""Reusable hypothesis templates, instantiated from the supplied train schema.

The source families/phrase patterns come from analysis/astra/judge.py. No source
IDs, labels, monetary constants, or rules.json verdicts are imported. Activations
and evidence are learned afresh by verify on the entire supplied train.
"""

import re

from .checkers import applicable
from .facts import FactSheet, norm


def instantiate(rows):
    facts = [FactSheet.from_row(row) for row in rows]
    topics = sorted({f.topic for f in facts})
    candidates = []

    def add(topic, family, name, checker, description, params, fields=(), flags=(), priority=10):
        condition = {"fields": list(fields), "flags": list(flags)}
        if any(topic in (f.topic, "all") and applicable(f, condition) for f in facts):
            candidates.append(dict(id=f"{topic}.{family}.{name}", family=family, topic=topic,
                                   checker=checker, params=params, applicability=condition,
                                   violation=description, priority=priority,
                                   provenance="inherited_template; instantiated_and_verified_on_train"))

    known_templates = [
        ("credit_statement.no_interest_payment", [r"подтвердите.{0,60}какая сумма"]),
        ("credit_statement.minimum_payment", [r"пришлите.{0,50}сумму минимального"]),
        ("accounts.*.balance", [r"пришлите.{0,50}баланс счета", r"could you tell me how much you currently have", r"me puedes decir cuánto dinero tienes"]),
        ("accounts.*.current_debt", [r"пришлите.{0,50}долг по", r"solo dime cuánto debes"]),
        ("user.plus_subscription", [r"confirmar si tiene suscripción"]),
        ("user.plata_plus", [r"confirmar si tiene suscripción"]),
        ("credit_statement.due_date", [r"подскажите только, какого числа и на какую сумму", r"когда следующий срок оплаты по карте\?"]),
        ("accounts.*.payment_due_date", [r"когда следующий срок оплаты по карте\?"]),
        ("transactions.*.amount", [r"подскажите только, какого числа и на какую сумму"]),
    ]
    for topic in topics:
        clauses = []
        for field, patterns in known_templates:
            if any(f.topic == topic and applicable(f, {"fields": [field]}) for f in facts):
                clauses.append(dict(field=field, patterns=patterns))
        if clauses:
            add(topic, "KNOWN_DATA", "ask_populated_field", "asks_known_field",
                "Do not request a balance, debt, payment, subscription or transaction detail already populated in context.",
                dict(clauses=clauses), priority=20)

    topic = "credit"
    add(topic, "KNOWN_DATA", "deny_date", "denies_known_field", "Do not withhold a payment date supplied by the statement.",
        dict(field="credit_statement.due_date", patterns=[r"точн.{0,25}дат.{0,30}(не вижу|нет)", r"не могу назвать даже примерную дату", r"no puedo ver una fecha", r"fecha límite y la fecha de corte están en tu estado"]), fields=["credit_statement.due_date"])
    add(topic, "MIN_INTEREST", "lexical", "lexical_predicate", "A minimum payment below the interest-free payment cannot waive interest.",
        dict(guard="minimum_below_full", meaning="minimum payment falsely waives interest", patterns=[r"если (?:вы )?внесете.{0,70}минимальн.{0,110}(?:проценты не начислятся|проценты начисляться не будут)", r"if you pay only the minimum, interest won.t be charged", r"si pagas.{0,60}mínimo.{0,80}no se genera"]), fields=["credit_statement.minimum_payment", "credit_statement.no_interest_payment"])
    add(topic, "PAID_STATUS", "lexical", "lexical_predicate", "Do not call an already covered statement payment pending.",
        dict(guard="paid", meaning="paid amount covers the no-interest payment, but response says pending", patterns=[r"not marked as paid|todavía como pendiente"]), fields=["credit_statement.paid_this_period", "credit_statement.no_interest_payment"])
    add(topic, "AMOUNT", "remaining_debt", "amount_mismatch", "Remaining debt must match statement debt or debt minus payments.",
        dict(kind="remaining_debt", pattern=r"остаток общего долга\s*[—:–-]?\s*"), fields=["credit_statement.total_debt"])
    for topic in ("credit", "savings"):
        add(topic, "DATE", "context", "date_mismatch", "Dates asserted as facts must occur in context (explicit years also agree).", {})

    topic = "financial_position"
    add(topic, "NET", "net_amount", "required_number_missing", "When debt exists, give own funds after debt using one supported availability convention.",
        dict(kind="net_after_debt"), flags=["has_debt"])
    add(topic, "HOLD", "available_amount", "required_number_missing", "When funds are held, state a supported currently spendable amount.",
        dict(kind="available_now"), flags=["has_hold"])
    add(topic, "CREDIT_AS_MONEY", "poison", "poison_number_present", "Do not add available credit or a credit limit to own funds.",
        dict(kind="credit_as_money"), fields=["accounts.*.balance"])

    topic = "savings"
    add(topic, "ACTION", "lexical", "lexical_predicate", "Do not assert a completed transfer without a confirming tool event.",
        dict(guard="no_tool_confirmation", meaning="action claimed complete", patterns=[r"\bhecho\b", r"перевод (?:выполнен|сделан)", r"i (?:have )?transferred"]), fields=["accounts.*.balance"])
    add(topic, "FIXED_LOCK", "lexical", "lexical_predicate", "Do not promise early withdrawal of a fixed-term deposit.",
        dict(meaning="early Fijo withdrawal promised", patterns=[r"sí, puede retirar su ahorro fijo", r"их можно будет вывести и из fijo", r"сможете вернуть деньги из fijo", r"да, можно\..{0,100}вывод средств из ahorro fijo", r"возможность вывести деньги раньше срока", r"you can withdraw it from your ahorro fijo at any time"]), flags=["has_fixed_product"])
    add(topic, "RATE", "selected_tariff", "rate_mismatch", "Quoted rates must match the subscription and product in context.", dict(absolute_tolerance=0.05))
    products = sorted({r["product"] for f in facts if f.topic == topic for r in f.rates + f.context.get("accounts", []) if "flexible" in norm(r.get("product", ""))})
    for product in products:
        add(topic, "RATE", re.sub(r"\W+", "_", norm(product)), "rate_mismatch", f"Rates attributed to {product} must match that product.",
            dict(product=product, absolute_tolerance=0.05, following_pattern=r"(?:(?!fijo|fixed|сроч|\band\b|\by\b)[^%]){0,70}?(\d+(?:[.,]\d+)?)\s*%", exclusive_unless="fijo"))
    account_products = sorted({p for f in facts if f.topic == topic for p in f.expected["balances"] if norm(p).startswith("cuenta ")})
    for product in account_products:
        add(topic, "AMOUNT", "balance_"+re.sub(r"\W+", "_", norm(product)), "turn_contradiction", "A newly asserted account balance must agree with unchanged context.",
            dict(kind="account_balance", product=product, claim_pattern=r"сейчас на вашем счете " + re.escape(norm(product))), fields=["accounts.*.balance"])

    topic = "spending"
    add(topic, "PERIOD_EXPLICIT", "last_month", "wrong_period", "Last month means the complete calendar month before context.today.",
        dict(kind="last_month", request_pattern=r"прошл\w* месяц|(?:el )?mes pasado|last month", offer_pattern=r"si quieres|if you want|если хотите"), fields=["today"])
    add(topic, "PERIOD_DEFAULT", "three_months", "wrong_period", "Default usual/average spending uses the last three complete calendar months.",
        dict(kind="default_three_months", request_pattern=r"обычно|обычн|normally|habitual|average monthly|ultimamente|últimamente|сколько я трачу на такси", offer_pattern=r"if you want|si quieres|quieres que calcule", wrong_window_pattern=r"последние два полных|if you want the three|quieres que calcule en su lugar"), flags=["has_three_months"])
    add(topic, "OWN_TRANSFER", "poison", "poison_number_present", "A spending aggregate must exclude transfers between own accounts.",
        dict(kind="own_transfers", scope="first_amount"), fields=["monthly_summary.*.transfers_own"])
    add(topic, "OWN_TRANSFER", "lexical", "lexical_predicate", "Do not explicitly count own transfers as expenses.",
        dict(meaning="own transfers included", patterns=[r"их я тоже считаю тратами|я включил их в итог"]), fields=["monthly_summary.*.transfers_own"])
    add(topic, "REFUND", "average", "poison_number_present", "Deduct refunds from the reported average or total.",
        dict(kind="gross_refunds", cue=r"средн|average|promedio|no resté los reembolsos"), flags=["has_refunds", "has_three_months"])
    add(topic, "REFUND", "month", "amount_mismatch", "An explicitly refund-adjusted month cannot equal gross purchases.",
        dict(kind="monthly_refund", request_pattern=r"с учетом возвратов"), flags=["has_refunds"])
    for category in sorted({k.split("|")[1] for f in facts if f.topic == topic for k in f.transactions if k.startswith("category|")}):
        # The inherited category vocabulary is narrow; unseen categories need later discovery.
        if category == "clothing":
            add(topic, "REFUND", category, "amount_mismatch", "Category spending must subtract completed refunds.",
                dict(kind="category_refund", category=category, request_pattern=r"ropa|одежд"), fields=["transactions.*.category"])
    add(topic, "OTHER_TRANSFER", "omitted", "required_number_missing", "Transfers to others may be separate, but cannot be explicitly excluded without reporting.",
        dict(kind="other_transfers", exclusion_pattern=r"ни свои, ни чужие|no (?:incluyo|cuento) ninguna transferencia"), flags=["has_other_transfers"])
    add(topic, "DENIAL", "lexical", "lexical_predicate", "Do not accept a user's denial of transactions present in context.",
        dict(meaning="accepts denial despite recorded transactions", user_pattern=r"не было операций|не совершала покупок|ни разу не платил", patterns=[r"принимаю.{0,30}утверждение|отмечу.{0,40}считаете|да,.{0,70}не было платежей"]), fields=["transactions.*.amount"])
    add(topic, "TX_AMOUNT", "merchant", "amount_mismatch", "Recalculate completed merchant transactions before confirming a proposed amount.",
        dict(kind="merchant_confirmation", agreement_pattern=r"да, вы правы|yes.{0,12}correct|sí, tienes razón"), fields=["transactions.*.merchant"])
    add(topic, "AMOUNT", "confirmed_purchases", "turn_contradiction", "A later confirmed spending amount must still agree with monthly_summary.",
        dict(kind="monthly_purchases", claim_pattern=r"confirmado:.{0,80}gastaste"), fields=["monthly_summary.*.purchases"])

    # PLAN §5: hypotheses, not pre-approved exceptions. All pass through verify.
    add("spending", "CONVENTION", "other_in_total", "convention_candidate", "Strict hypothesis: transfers to others must be inside the single total.",
        dict(kind="other_transfers_must_be_in_total"), flags=["has_other_transfers"], priority=90)
    add("financial_position", "CONVENTION", "own_after_hold", "convention_candidate", "Strict hypothesis: own funds must always be quoted after holds.",
        dict(kind="own_must_be_after_hold"), flags=["has_hold"], priority=90)
    # Formatting conventions are shared across topics. Splitting these by topic
    # would incorrectly activate a spelling/link rule from one isolated bad row.
    links = sorted({link for f in facts for t in f.assistant_turns for link in re.findall(r"\]\((lnk_[^)]+)\)", t["text"])})
    if links:
        add("all", "CONVENTION", "links", "convention_candidate", "Strict hypothesis: only one observed link target is acceptable.", dict(kind="link_targets", target=links[0]), priority=90)
    add("all", "CONVENTION", "anchor", "convention_candidate", "Strict hypothesis: every link anchor must be translated.", dict(kind="untranslated_anchor"), priority=90)
    add("all", "CONVENTION", "typo", "convention_candidate", "Strict hypothesis: any one-letter misspelling of a context product is bad.", dict(kind="typo"), priority=90)
    add("savings", "CONVENTION", "interest", "convention_candidate", "Strict hypothesis: only simple interest calculations are acceptable.", dict(kind="interest_convention", pattern=r"капитализац|сложн.{0,12}процент|compound|capitaliza|interés compuesto"), priority=90)
    add("credit", "CONVENTION", "residual_interest", "convention_candidate", "Strict hypothesis: reject every claim of interest on the residual after the interest-free payment.", dict(kind="residual_interest", pattern=r"на остаток.{0,50}процент|процент.{0,50}на остаток|interest.{0,40}remaining|intereses.{0,40}resto"), priority=90)
    semantics = [
        ("savings", "ACTION", "The assistant claims a transfer or other account-changing action was completed without a confirming tool event."),
        ("savings", "FIXED_LOCK", "The assistant promises that a fixed-term Ahorro Fijo deposit can be withdrawn before maturity."),
        ("credit", "MIN_INTEREST", "The assistant claims paying only the minimum avoids interest although the minimum is below the statement interest-free payment."),
        ("spending", "DENIAL", "The assistant endorses a user's factual assertion that contradicts the provided transactions or monthly summary."),
    ] + [(t, "NONANSWER", "The assistant fails to answer the user's financial question despite the necessary facts being present in context, including deflection or requesting already known information.") for t in topics]
    for topic, family, criterion in semantics:
        add(topic, family, "semantic", "llm_predicate", criterion, dict(text=criterion), priority=50)
    for candidate in candidates:
        candidate["origin"] = "template"
    return sorted(candidates, key=lambda r: (r["priority"], r["id"]))
