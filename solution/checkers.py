"""Parameterized deterministic checks. Evidence always includes an assistant quote.

Lexical checks are deliberately narrow ports of the research prototype. Semantic
checks use an explicit runtime; without it they remain not_checked.
"""

from functools import wraps
import fnmatch
import json
import re

from .facts import (NUM, OPERATION_CUE, SENTENCE_END, bound_amount, contains, dates_in, flatten, money,
                    money_spans, month_in, norm, number, opening_exchange)


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


def opening_request(facts):
    return opening_exchange(facts)[0]


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
    _, first = opening_exchange(f)
    if first is None:
        return None
    ns = values(f)
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
        user, reply = opening_exchange(f)
        if reply is None or not re.search(p["request_pattern"], user) or len(f.last3) != 3:
            return None
        first = reply["normalized"]
        answer = re.split(p["offer_pattern"], first)[0]
        endpoints = [f.last3[0]["month"], f.last3[-1]["month"]]
        covered = all(month_in(answer, int(m[-2:])) or m in answer for m in endpoints)
        if not covered or re.search(p["wrong_window_pattern"], first):
            return evidence(f, "Default spending window is not the last three complete months", expected_months=[m["month"] for m in f.last3])


PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
# Vocabulary that makes a percentage a statement about a rate (RU / ES / EN).
RATE_CUE = re.compile(r"ставк|годов|доходност|начисл|\bпод\s*$|"
                      r"\btasa|\banual|\brind[ea]|rendimiento|inter[eé]s|\bgat\b|al año|\bpaga\b|"
                      r"\brate|annual|\bp\.a\b|per year|a year|\bapy\b|\bapr\b|interest|yield|\bearn|\bpays?\b")
# Other percentage metrics: a nearer one of these describes the number instead of a rate cue.
OTHER_METRIC = re.compile(r"инфляц\w*|inflaci\w*|inflation(?: rate)?|налог\w*|impuest\w*|\btax(?:es)?\b|"
                          r"комисси\w*|comisi[oó]n\w*|\bfees?\b|скидк\w*|descuento\w*|discount\w*|кешб[эе]к\w*|cashback")
# "20% more", "на 2% выше", "un 2% más": a difference, not the rate itself.
RELATIVE_AFTER = re.compile(r"\s*(?:more|less|higher|lower|extra|больше|меньше|выше|ниже|más|menos|mayor|menor)\b")
# "20% of your income", "20% de tus ingresos", "20% от дохода", "20% дохода": a share, not a rate.
SHARE_AFTER = re.compile(r"\s*(?:(?:of|de|del|de la|de los|de las|от|из)\s+"
                         r"(?!(?:la |el |su |tu )?(?:inter|tasa|rendim|rate|annual|anual|ставк|годов|доходност))"
                         r"|(?:вашего |вашей |ваших |своего |своей |своих )?"
                         r"(?:доход(?!н)|зарплат|заработ|бюджет|сумм|расход|трат|сбережен|остатк|баланс|средств|денег))")
# "save 20%", "move 20% to", "ahorra el 20%", "откладывайте около 20%": an allocation, not a rate.
# Product nouns are excluded: "ahorro", "ahorros" and "savings" name accounts, not actions.
SHARE_BEFORE = re.compile(r"(?:\bsave\b|set aside|put aside|\ballocate\b|\bmove\b|\bput\b|\btransfer\b|\binvest\b|"
                          r"\bahorr(?!os?\b)\w*|\baparta\w*|\bdestina\w*|\bmuev\w*|\bpas[ae]\b|\btransfier\w*|\binviert\w*|"
                          r"отклад\w*|направ\w*|копит\w*|перевед\w*|перевест\w*|полож\w*|влож\w*)\s+(?:[\w~≈]+\s+){0,2}$")


def distance(pattern, before, after):
    """Characters between the number and the nearest match of pattern on either side."""
    return min([len(before) - m.end() for m in pattern.finditer(before)] +
               [m.start() for m in pattern.finditer(after)], default=None)


def rate_claims(f):
    """Classify each percentage in the assistant turns: rate, share, relative, other, or unbound.

    Each percentage is read inside its own segment: the sentence, cut at the
    neighbouring percentages. It is a share when grammar says so ("20% of your income",
    "save 20%", "откладывайте 20% дохода"), relative for a difference ("2% more"), and
    otherwise is described by its nearest descriptor: rate vocabulary or a context
    product name makes it a rate claim; a nearer inflation/tax/fee/discount/cashback word
    makes it another metric. A percentage with no descriptor is unbound. Only rate
    claims are compared with context rates, so the other kinds never make a confident bad.
    Unknown is deliberately not returned: verify demotes any rule that answers unknown
    on a single train row, which would switch the whole rate check off.
    """
    tokens = sorted({token for x in f.context.get("accounts", []) + f.context.get("savings_rates", [])
                     for token in re.findall(r"\w{4,}", norm(x.get("product", "")))})
    product = re.compile(r"\b(?:" + "|".join(map(re.escape, tokens)) + r")\b") if tokens else None
    claims = []
    for turn in f.assistant_turns:
        t = turn["normalized"]
        found = list(PERCENT.finditer(t))
        for i, m in enumerate(found):
            ends = [e.end() for e in SENTENCE_END.finditer(t, 0, m.start())]
            start = max(ends[-1] if ends else 0, found[i-1].end() if i else 0)
            stop = SENTENCE_END.search(t, m.end())
            stop = min(stop.start() if stop else len(t), found[i+1].start() if i+1 < len(found) else len(t))
            before, after = t[start:m.start()], t[m.end():stop]
            # "откладывать под 12%" or "save at 9% a year" is still a rate.
            near_rate = RATE_CUE.search(before[-12:]) or RATE_CUE.search(after[:16])
            rate = [d for d in (distance(RATE_CUE, before, after),
                                distance(product, before, after) if product else None) if d is not None]
            other = distance(OTHER_METRIC, before, after)
            if SHARE_AFTER.match(after) or SHARE_BEFORE.search(before) and not near_rate:
                kind = "share"
            elif RELATIVE_AFTER.match(after):
                kind = "relative"
            elif other is not None and (not rate or other <= min(rate)):
                kind = "other"
            elif rate:
                kind = "rate"
            else:
                kind = "unbound"
            claims.append(dict(turn=turn["index"], value=number(m.group(1)), kind=kind, start=m.start(1)))
    return claims


@checker
def rate_mismatch(f, p):
    """Compare only percentages that state a rate; shares and unbound numbers are not rate claims."""
    a = text(f)
    claims = rate_claims(f)
    claimed = [c["value"] for c in claims if c["kind"] == "rate"]
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
        not_rates = {(c["turn"], c["start"]) for c in claims if c["kind"] != "rate"}
        mentions = [m.group(1) for turn in f.assistant_turns
                    for m in re.finditer(re.escape(norm(product)) + p["following_pattern"], turn["normalized"])
                    if (turn["index"], m.start(1)) not in not_rates]
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


# --- Reading tool results for completed-action claims (RU / ES / EN, on facts.norm text) ---
# Status cues. Each cue is read inside its negation scope (cue_status): "has not been
# completed", "no se ha completado" and "ещё не выполнен" are not success, "no errors",
# "sin errores", "без ошибок", "0 errors" and "errors: none" are not failure.
SUCCESS_CUE = (
    r"success\w*|succeeded|complet(?:ed|e)|done|ok|okay|confirmed|executed|processed|approved|posted|finished|settled|"
    r"transferred|sent|moved|deposited|credited|debited|"
    r"[eé]xito|exitos[oa]s?|complet[ao]s?|completad[oa]s?|realizad[oa]s?|efectuad[oa]s?|ejecutad[oa]s?|procesad[oa]s?|"
    r"confirmad[oa]s?|aprobad[oa]s?|finalizad[oa]s?|transferid[oa]s?|enviad[oa]s?|movid[oa]s?|depositad[oa]s?|"
    r"abonad[oa]s?|acreditad[oa]s?|(?:complet|realiz|efectu|ejecut|proces|confirm|aprob|finaliz|acredit)[oó]|"
    r"list[oa]|hecho|correcto|"
    r"успешн\w*|успех\w*|выполнен\w*|завершен\w*|подтвержден\w*|проведен\w*|исполнен\w*|переведен\w*|"
    r"отправлен\w*|зачислен\w*|списан\w*|готово")
FAILURE_CUE = (
    r"fail\w*|reject\w*|declin\w*|denied|den[ie]gad\w*|errors?|cancel\w*|abort\w*|revers\w*|refus\w*|"
    r"insufficient|exceeded|unsuccessful|unable|invalid|timed out|timeout|could not|couldn.t|cannot|can.t|"
    r"fall[oó]|fallid\w*|rechazad\w*|declinad\w*|insuficiente\w*|cancelad\w*|anulad\w*|revertid\w*|inv[aá]lid\w*|"
    r"imposible|no fue posible|no (?:se )?(?:pudo|pudieron)|"
    r"отклонен\w*|ошибк\w*|отказ\w*|отменен\w*|сбой|недостаточно|превышен\w*|неудач\w*|невозможно|не удалось")
PENDING_CUE = (
    r"pending|processing|in[- ]progress|queued|scheduled|awaiting|initiated|submitted|under review|on hold|"
    r"(?:is being|being|will be|to be)\s+(?:process\w*|complet\w*|execut\w*|sent|transferred|moved|review\w*)|"
    r"pendiente\w*|en proceso|procesando|en curso|programad\w*|en espera|iniciad\w*|en revisi[oó]n|"
    r"ser[aá] (?:procesad|realizad|completad|enviad|transferid)\w*|se (?:realizar|procesar|completar|enviar|transferir)[aá]n?|"
    r"est[aá] siendo procesad\w*|"
    r"в обработке|обрабатыва\w*|в процессе|ожида\w*|запланирован\w*|принят\w*|инициирован\w*|"
    r"будет (?:выполнен\w*|переведен\w*|отправлен\w*|обработан\w*|проведен\w*)")
STATUS_CUE = re.compile(rf"\b(?:(?P<failure>{FAILURE_CUE})|(?P<pending>{PENDING_CUE})|(?P<success>{SUCCESS_CUE}))\b")
# A negator up to three words before a cue, inside the same comma/colon segment, negates it.
NEGATOR = (r"not|no|never|none|neither|nor|without|zero|cannot|\w+n['’]t|"
           r"sin|nunca|ning[uú]n[oa]?|tampoco|cero|не|нет|без|ни|ноль")
NEGATED_BEFORE = re.compile(rf"(?:\b(?:{NEGATOR})\b|(?<![\d.,])0)\s+(?:\S+\s+){{0,3}}$")
NEGATED_AFTER = re.compile(r"^\s*(?:count|total|number|cantidad|число|количество)?\s*(?:[:=-]\s*)?"
                           r"(?:no|not|false|none|0|ninguno|нет|cero|ноль)\b|^[- ]free\b")
YET = re.compile(r"\b(?:yet|still|todav[ií]a|a[uú]n|ещ[её]|пока)\b")
SEGMENT_BREAK = re.compile(r"[,;:()]")
CLAUSE_BREAK = re.compile(r"[.!?;](?:\s|$)|\n|\s[—–-]\s")
# What a tool result is about. A read-only head (lookup, history, limit, check...) makes the
# result read-only even when "transfer" is its modifier; a bare balance word is read-only too.
READONLY_HEAD = re.compile(
    r"\b(?:lookups?|look-ups?|inquir(?:y|ies)|quer(?:y|ies)|history|limits?|checks?|statements?|details?|info\w*|"
    r"verification|consultas?|historial|l[ií]mites?|verificaci[oó]n|detalles?|informaci[oó]n|"
    r"запрос\w*|истори\w*|лимит\w*|проверк\w*|выписк\w*|сведени\w*|информаци\w*)\b")
MOVEMENT = (
    r"transfer\w*|remit\w*|wire\w*|sen[dt]|sending|mov(?:e|ed|ing)|deposit\w*|withdraw\w*|pa(?:y|id|yment\w*)|top[- ]?up|"
    r"transferen\w*|transferid\w*|transfir\w*|transfer[ií]|env[ií]\w*|mov(?:er|id)\w*|traspas\w*|dep[oó]sit\w*|retir\w*|"
    r"pag[oa]\w*|abon\w*|"
    r"перевод\w*|переведен\w*|перевест\w*|перев[её]л\w*|перечисл\w*|отправ\w*|зачисл\w*|пополн\w*|списан\w*|снят\w*|"
    r"платеж\w*|оплат\w*")
MOVEMENT_WORD = re.compile(rf"\b(?:{MOVEMENT})\b")
BALANCE_WORD = re.compile(r"\b(?:balances?|saldos?|баланс\w*|остат\w*)\b")
# Amount roles: an amount introduced by one of these is a balance, fee, limit or the like, not
# the operation amount; a movement word (or "amount") switches back to the operation amount.
OTHER_AMOUNT_CUE = re.compile(
    r"\b(?:balances?|saldos?|баланс\w*|остат\w*|остал\w*|остае\w*|на счет[еу]|quedan?|restantes?|remaining|left|"
    r"leaving|holds?|available|disponibles?|доступн\w*|limits?|l[ií]mites?|лимит\w*|fees?|comisi[oó]n\w*|комисси\w*|"
    r"cargos?|charges?|interest|inter[eé]s|процент\w*|you (?:now )?have|now has|tienes|tiene|у вас|hay|est[aá]n? en)\b")
MOVEMENT_AMOUNT_CUE = re.compile(rf"\b(?:{MOVEMENT}|amount|monto|importe|cantidad|сумм\w*)\b")
# Structured results: status-like and operation-like fields are preferred over the other text.
STATUS_KEY = re.compile(r"^(?:status|state|result|outcome|success(?:ful)?|ok|completed|done|confirmed|"
                        r"estado|resultado|[eé]xito|статус|результат|успех)$")
OPERATION_KEY = re.compile(r"^(?:operation|op|type|action|kind|method|operaci[oó]n|tipo|acci[oó]n|операция|тип|действие)$")
AMOUNT_KEY = re.compile(r"amount|\bsum\b|total|monto|importe|cantidad|сумм")
OTHER_AMOUNT_KEY = re.compile(r"balance|saldo|баланс|остат|available|disponible|доступн|limit|l[ií]mite|лимит|"
                              r"fee|comisi|комисси|interest|inter[eé]s|процент")


def cue_status(clause, match):
    """The kind a status cue stands for after its negation scope; None when it is negated away.

    A negated success cue is a failure ("has not been completed", "no se ha
    completado", "не выполнен") or, with a "yet" marker ("not yet", "todavía no",
    "ещё не"), pending. A negated failure or pending cue ("no errors", "sin
    errores", "0 errors", "errors: none", "error-free", "no longer pending") is
    dropped. The scope is the comma/colon segment holding the cue.
    """
    kind = match.lastgroup
    segment_start = max((m.end() for m in SEGMENT_BREAK.finditer(clause, 0, match.start())), default=0)
    before = clause[segment_start:match.start()]
    after = clause[match.end():]
    negation = NEGATED_BEFORE.search(before)
    if not negation and not NEGATED_AFTER.match(after):
        return kind
    if kind != "success":
        return None
    return "pending" if YET.search(before + SEGMENT_BREAK.split(after, 1)[0]) else "failure"


def cue_operation(clause, match):
    """What the clause carrying this status cue is about: readonly, movement or unspecified."""
    segment_start = max((m.end() for m in SEGMENT_BREAK.finditer(clause, 0, match.start())), default=0)
    after = clause[match.end():]
    cut = re.search(r"[,:;(]|\d", after)
    head = clause[segment_start:match.start()] + " " + " ".join((after[:cut.start()] if cut else after).split()[:4])
    for scope in (head, clause):
        if READONLY_HEAD.search(scope):
            return "readonly"
        if MOVEMENT_WORD.search(scope):
            return "movement"
    return "readonly" if BALANCE_WORD.search(clause) else "unspecified"


def text_operation(text):
    if READONLY_HEAD.search(text):
        return "readonly"
    if MOVEMENT_WORD.search(text):
        return "movement"
    return "readonly" if BALANCE_WORD.search(text) else "unspecified"


def read_status(text):
    """(status, operation) of a tool text from the clauses that carry its decisive status cues.

    Status: any non-negated failure cue in any clause makes it failure, else any
    pending cue makes it pending, else any success cue makes it success, else
    unknown. Operation: among the cues of that status, movement if any clause is
    about a money movement, else readonly if any is a lookup; None when they say
    nothing, so the caller falls back to the whole text.
    """
    found = [(clause, kind, m) for clause in CLAUSE_BREAK.split(text) if clause and clause.strip()
             for m in STATUS_CUE.finditer(clause) for kind in [cue_status(clause, m)] if kind]
    status = next((k for k in ("failure", "pending", "success") if any(kind == k for _, kind, _ in found)), "unknown")
    operations = {cue_operation(clause, m) for clause, kind, m in found if kind == status}
    return status, ("movement" if "movement" in operations else "readonly" if "readonly" in operations else None)


def amount_roles(text):
    """[(value, role)] for each MXN amount: 'operation', or 'other' for a balance, fee, limit, available amount.

    The role comes from the nearest cue in the segments before the amount (a balance
    word beats a movement word inside one segment: "balance after transfer: 7 500 MXN");
    an amount with no cue of its own keeps the previous amount's role, so "quedan 29 500
    MXN y en Ahorro Flexible 6 000 MXN" are both balances and "transferred 2 500 MXN to
    Ahorro Flexible and 700 MXN to Ahorro Fijo" are both operation amounts. A cue right
    after the amount ("10 MXN fee", "10 MXN de comisión", "7 500 MXN remaining") also
    makes it other.
    """
    roles, mode, cursor = [], "operation", 0
    for start, end, value in money_spans(text):
        for segment in reversed(re.split(r"[,;:.!?()]|\s[—–-]\s", text[cursor:start])):
            if OTHER_AMOUNT_CUE.search(segment):
                mode = "other"
                break
            if MOVEMENT_AMOUNT_CUE.search(segment):
                mode = "operation"
                break
        trailing = re.match(r"\s*(?:mxn|песо|pesos)\s+(?:\w+\s+)?(?=\S)", text[end:])
        role = "other" if trailing and OTHER_AMOUNT_CUE.match(text[end + trailing.end():]) else mode
        roles.append((value, role))
        cursor = end
    return roles


def structured_event(parsed):
    """Fields of a JSON tool result: status/operation texts, operation and other amounts, and its text."""
    status_texts, operation_texts, lines, amounts, other = [], [], [], [], []
    for path, value in flatten(parsed).items():
        key = norm(path.replace("_", " "))
        leaf = key.rsplit(".", 1)[-1]
        if isinstance(value, bool):
            if STATUS_KEY.match(leaf):
                status_texts.append("success" if value else "failure")
            if value:
                lines.append(leaf)
            continue
        # Absent fields are not cues: {"error": null}, {"errors": 0}, {"message": ""} say nothing.
        if value is None or value == "" or value == 0 or (isinstance(value, str) and norm(value) in ("none", "null", "n/a", "-")):
            continue
        text_value = norm(str(value).replace("_", " "))
        if STATUS_KEY.match(leaf):
            status_texts.append(text_value)
        if OPERATION_KEY.match(leaf):
            operation_texts.append(text_value)
        if isinstance(value, (int, float)) or re.fullmatch(NUM, text_value):
            numeric = float(value) if isinstance(value, (int, float)) else number(text_value)
            if OTHER_AMOUNT_KEY.search(key):
                other.append(numeric)
            elif AMOUNT_KEY.search(key):
                amounts.append(numeric)
        lines.append(f"{leaf}: {text_value}")
    return dict(text="\n".join(lines), status_texts=status_texts, operation_texts=operation_texts,
                amounts=amounts, other_amounts=other)


def classify_tool_event(content, products=()):
    """Best-effort reading of one tool result (free text, or JSON when it parses).

    Returns ``status`` (success | failure | pending | unknown; see read_status and
    cue_status for negation), ``operation`` (movement | readonly | unspecified; a
    lookup/history/limit/check result is read-only even when it concerns a
    transfer, and "status: completed" reports completion), the operation
    ``amounts`` in MXN (balances, fees, limits and available amounts go to
    ``other_amounts`` instead, see amount_roles) and the context ``products`` it
    mentions. In JSON, status-like fields (status/state/result/ok/success...) and
    operation-like fields (operation/type/action...) are preferred over the other
    text, amount-like keys are operation amounts unless the key names a balance,
    fee or limit, and null/empty/false/zero fields say nothing. Nothing here is
    required to exist: a bare string is classified on its words.
    """
    parsed = None
    if isinstance(content, (dict, list)):
        parsed = content
    elif isinstance(content, str):
        try:
            parsed = json.loads(content)
        except ValueError:
            parsed = None
    if isinstance(parsed, (dict, list)):
        fields = structured_event(parsed)
        t = fields["text"]
        status, operation = read_status("\n".join(fields["status_texts"]) if fields["status_texts"] else t)
        if fields["operation_texts"]:
            operation = text_operation(" ".join(fields["operation_texts"]))
        roles = amount_roles(t)
        amounts = fields["amounts"] + [v for v, role in roles if role == "operation"]
        other = fields["other_amounts"] + [v for v, role in roles if role == "other"]
    else:
        t = norm(content if isinstance(content, str) else str(content))
        status, operation = read_status(t)
        roles = amount_roles(t)
        amounts = [v for v, role in roles if role == "operation"]
        other = [v for v, role in roles if role == "other"]
    if operation is None:
        operation = text_operation(t)
    return dict(status=status, operation=operation, amounts=amounts, other_amounts=other,
                products=[p for p in products if norm(p) and norm(p) in t])


def claim_clause_span(normalized, match):
    """(start, end) of the clause (sentence, or dash/semicolon-delimited part) holding the matched phrase."""
    start = max((m.end() for m in CLAUSE_BREAK.finditer(normalized[:match.start()])), default=0)
    after = CLAUSE_BREAK.search(normalized[match.end():])
    return start, match.end() + after.start() if after else len(normalized)


def claim_clause(normalized, match):
    start, end = claim_clause_span(normalized, match)
    return normalized[start:end].strip()


def tool_confirms(event, claim, value=None):
    """Does one PRECEDING tool event confirm this claim, or the claimed operation amount ``value``?

    The event must be a success that is not read-only, and where both sides name
    context products they must share one. For a claimed amount: if the event names
    operation amounts the claimed one must be among them; otherwise only a
    money-movement success (not a bare "OK") confirms it. A claim without an
    amount needs a money-movement success.
    """
    if event["status"] != "success" or event["operation"] == "readonly":
        return False
    if event["products"] and claim["products"] and not set(map(norm, event["products"])) & set(map(norm, claim["products"])):
        return False
    if value is not None and event["amounts"]:
        return contains(event["amounts"], value)
    return event["operation"] == "movement"


def unconfirmed_action_claims(f, patterns):
    """One record per completed-action claim that no earlier tool result confirms.

    Semantics of the ``no_tool_confirmation`` guard. Every match of every action
    pattern in an assistant turn is a claim (overlapping matches, and matches in
    one clause, are one claim); each is checked on its own clause against the
    ``role: tool`` messages that come BEFORE that turn. The clause's operation
    amounts (MXN amounts not introduced as a balance, fee, limit or available
    amount, see amount_roles) must each be confirmed by some preceding event, so
    "transferred 2 500 MXN to Ahorro Flexible and 700 MXN to Ahorro Fijo" needs
    both amounts confirmed; a claim without an operation amount needs a preceding
    money-movement success (see tool_confirms). Failed, rejected, negated,
    pending/in-progress, read-only (balance, limit or history lookup) and later
    tool events do not confirm a claim, and neither does a result whose text
    cannot be classified: a claim of a completed action needs positive evidence,
    so an indeterminate tool result is treated as "not confirming" (violation),
    never as unknown. This keeps the checker boolean and the rule verifiable on
    train, where no conversation contains a tool message, so train behaviour is
    identical to a plain phrase match.

    Known limits, deliberately accepted for free-text tool results: a movement
    success that states no operation amount confirms any claimed amount; any
    earlier success is considered, not only the most recent exchange, so an
    amount-less claim ("Hecho") after an earlier confirmed transfer is accepted;
    products are matched as a set, so the direction of a transfer is not checked;
    the amount-role and negation cues are a RU/ES/EN vocabulary, not a parser.
    """
    products = [a.get("product", "") for a in f.context.get("accounts", []) + f.context.get("savings_rates", [])
                if a.get("product")]
    tools = [(i, classify_tool_event(m.get("content", ""), products))
             for i, m in enumerate(f.conversation) if m.get("role") == "tool"]
    unconfirmed = []
    for turn in f.assistant_turns:
        t = turn["normalized"]
        preceding = [event for i, event in tools if i < turn["index"]]
        seen, last_end = set(), -1
        for match in sorted((m for pattern in patterns for m in re.finditer(pattern, t)), key=lambda m: m.start()):
            span = claim_clause_span(t, match)
            if match.start() < last_end or span in seen:
                continue
            last_end = match.end()
            seen.add(span)
            clause = t[span[0]:span[1]].strip()
            claim = dict(amounts=[v for v, role in amount_roles(clause) if role == "operation"],
                         products=[p for p in products if norm(p) in clause])
            if claim["amounts"]:
                missing = [v for v in claim["amounts"] if not any(tool_confirms(e, claim, v) for e in preceding)]
            else:
                missing = [] if any(tool_confirms(e, claim) for e in preceding) else [None]
            if missing:
                unconfirmed.append(dict(turn=turn["index"], match=match.group(), claim=clause,
                                        claimed_amounts=claim["amounts"],
                                        unconfirmed_amounts=[v for v in missing if v is not None],
                                        tool_events=[dict(index=i, before_claim=i < turn["index"], **event)
                                                     for i, event in tools]))
    return unconfirmed


@checker
def lexical_predicate(f, p):
    """Narrow inherited phrase match, with a separate context applicability gate."""
    cs = f.expected["credit_statement"]
    if p.get("guard") == "paid" and not (cs.get("paid_this_period", 0) >= cs.get("no_interest_payment", float("inf"))):
        return None
    if p.get("guard") == "minimum_below_full" and not (cs.get("minimum_payment", float("inf")) < cs.get("no_interest_payment", 0)):
        return None
    user = "\n".join(norm(m["content"]) for m in f.conversation if m["role"] == "user")
    if p.get("user_pattern") and not re.search(p["user_pattern"], user):
        return None
    if p.get("guard") == "no_tool_confirmation":
        # Per-claim check: a tool message anywhere in the conversation is not a confirmation.
        unconfirmed = unconfirmed_action_claims(f, p["patterns"])
        if unconfirmed:
            return evidence(f, "Completed-action claim has no preceding confirming tool result",
                            match=unconfirmed[0]["match"], predicate=p["meaning"], claims=unconfirmed)
        return None
    for pattern in p["patterns"]:
        match = re.search(pattern, text(f))
        if match:
            return evidence(f, "Inherited lexical predicate matched", match=match.group(), predicate=p["meaning"])


@checker
def amount_mismatch(f, p):
    user, first = opening_exchange(f)
    if first is None:
        return None
    kind = p["kind"]
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

    Only the amount the claim asserts is compared: the first amount at or after the
    claim, in the same sentence. Other amounts in the message (a second account, a
    payment, a suggested transfer) are not this claim. If the words between the claim
    and its amount make it hypothetical ("после перевода", "if you transfer"), the
    checker abstains for that claim rather than calling it a contradiction.
    """
    for turn in f.assistant_turns:
        claims = list(re.finditer(p["claim_pattern"], turn["normalized"]))
        if not claims:
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
        for claim in claims:
            value, gap = bound_amount(turn["normalized"], claim)
            if value is None or OPERATION_CUE.search(gap):
                continue
            if valid and not contains(valid, value):
                return evidence(f, "Claimed amount differs from the unchanged context", turn=turn["index"],
                                claim=claim.group(), expected_any=valid, observed=value)


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
