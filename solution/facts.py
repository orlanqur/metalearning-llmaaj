"""Context-derived facts. No labels, item IDs, or learned constants are used here."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
import json
import re

NUM = r"(?<![\w])[-+]?\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)*(?![\w])"
MONTHS = [[], ["январ", "enero", "january", "jan"],
          ["феврал", "febrero", "february", "feb"], ["март", "marzo", "march", "mar"],
          ["апрел", "abril", "april", "apr"], ["мая", "май", "mayo", "may"],
          ["июн", "junio", "june", "jun"], ["июл", "julio", "july", "jul"],
          ["август", "agosto", "august", "aug"], ["сентябр", "septiembre", "september", "sep"],
          ["октябр", "octubre", "october", "oct"], ["ноябр", "noviembre", "november", "nov"],
          ["декабр", "diciembre", "december", "dec"]]


def norm(text):
    return re.sub(r"\s+", " ", text.lower().replace("ё", "е").replace("*", "")).strip()


def opening_exchange(facts):
    """Return the opening user request and its reply, skipping greeting-only turns."""
    parts = []
    for i, message in enumerate(facts.conversation):
        if message["role"] == "user":
            content = norm(message["content"])
            if content and not re.fullmatch(
                    r"[\W_]*(?:hola|hello|hi|hey|привет|здравствуйте|добрый день|"
                    r"buenos días|buenas tardes|buenas noches)[\W_]*", content):
                parts.append(content)
        elif message["role"] == "assistant" and parts:
            return "\n".join(parts), next(t for t in facts.assistant_turns if t["index"] == i)
    return "\n".join(parts), None


def number(text):
    """Parse grouped and decimal formats; 21.6k is deliberately unsupported."""
    value = re.sub(r"\s", "", text)
    if "," in value and "." in value:
        value = (value.replace(",", "") if value.rfind(".") > value.rfind(",")
                 else value.replace(".", "").replace(",", "."))
    elif "," in value:
        parts = value.split(",")
        value = "".join(parts) if all(len(p) == 3 for p in parts[1:]) else "".join(parts[:-1]) + "." + parts[-1]
    elif value.count(".") > 1:
        parts = value.split(".")
        value = "".join(parts) if all(len(p) == 3 for p in parts[1:]) else "".join(parts[:-1]) + "." + parts[-1]
    return float(value)


def numbers(text):
    # Do not read the leading part of an unsupported abbreviated number as money.
    text = re.sub(r"\b\d+(?:[.,]\d+)?[kKmM]\b", "", text)
    return [number(m.group()) for m in re.finditer(NUM, text)]


def money(text):
    text = norm(text)
    return [number(m.group(1)) for m in re.finditer("(" + NUM + r")\s*(?:mxn|песо|pesos)\b", text)]


def close(actual, expected, absolute=1.0, relative=0.005):
    return abs(actual - expected) <= max(absolute, abs(expected) * relative)


def contains(values, expected, absolute=1.0, relative=0.005):
    return any(close(value, expected, absolute, relative) for value in values)


def month_in(text, month):
    return any(re.search(r"\b" + re.escape(alias) + (r"\w*\b" if re.search("[а-я]", alias) else r"\b"), norm(text))
               for alias in MONTHS[month])


def dates_in(text):
    """Return (year or None, month, day); explicit years must agree as well."""
    found = set()
    for y, m, d in re.findall(r"\b(20\d\d)-(\d\d)-(\d\d)\b", text):
        found.add((int(y), int(m), int(d)))
    for d, m, y in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](20\d\d)\b", text):
        found.add((int(y), int(m), int(d)))
    for month in range(1, 13):
        for alias in MONTHS[month]:
            ending = r"\w*" if re.search("[а-я]", alias) else r"\.?"
            patterns = [r"\b(\d{1,2})\s+(?:de\s+)?" + alias + ending + r"\b(?:\s+(?:de\s+)?(20\d\d))?",
                        r"\b" + alias + ending + r"\s+(\d{1,2})\b(?:,?\s+(20\d\d))?"]
            for pattern in patterns:
                for day, year in re.findall(pattern, norm(text)):
                    found.add((int(year) if year else None, month, int(day)))
    return found


def language(text):
    """A lightweight script/cue flag, not a language classifier."""
    if re.search("[а-яА-Я]", text):
        return "ru"
    if re.search(r"[áéíóúñ¿¡]|\b(?:puedes|cuánto|tienes|hola|gasto|mes)\b", text.lower()):
        return "es"
    return "en_or_unknown"


def flatten(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            result.update(flatten(child, f"{prefix}.{key}".strip(".")))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            result.update(flatten(child, f"{prefix}.{i}"))
    else:
        result[prefix] = value
    return result


@dataclass
class FactSheet:
    topic: str
    context: dict
    conversation: list
    expected: dict
    poison: dict
    flags: dict
    known_fields: dict
    dates: list
    assistant_turns: list
    months: list
    last3: list
    transactions: dict
    rates: list

    @classmethod
    def from_row(cls, row):
        return cls.from_context(row["context"], row["topic"], row["conversation"])

    @classmethod
    def from_context(cls, context, topic, conversation=()):
        c = context
        accounts = c.get("accounts", [])
        today = date.fromisoformat(c["today"]) if c.get("today") else None
        previous = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m") if today else None
        own = sum(a.get("balance", 0) for a in accounts)
        hold = sum(a.get("on_hold", a.get("held", 0)) for a in accounts)
        debt = sum(a.get("current_debt", 0) for a in accounts)
        locked = sum(a.get("balance", 0) for a in accounts if "fijo" in a.get("product", "").lower()
                     and today and a.get("maturity_date", "") > today.isoformat())
        months = []
        for m in c.get("monthly_summary", []):
            p, r, o, w = (m.get(k, 0) for k in ("purchases", "refunds", "transfers_to_others", "transfers_own"))
            months.append(dict(month=m["month"], purchases=p, refunds=r, other=o, own=w,
                               net_purchases=p-r, combined=p-r+o))
        # Exactly the three preceding calendar months, never an incomplete current month.
        window = []
        cursor = today.replace(day=1) if today else None
        for _ in range(3):
            if cursor:
                cursor = (cursor - timedelta(days=1)).replace(day=1)
                window.append(cursor.strftime("%Y-%m"))
        last3 = sorted((m for m in months if m["month"] in window), key=lambda m: m["month"])
        averages = {k: sum(m[k] for m in last3) / 3 for k in
                    ("purchases", "refunds", "other", "own", "net_purchases", "combined")} if len(last3) == 3 else {}
        tx = defaultdict(lambda: dict(count=0, net=0, gross=0, refunds=0))
        for t in c.get("transactions", []):
            if t.get("status") not in ("completed", "completada", "completado") or t.get("type") not in ("purchase", "refund"):
                continue
            for kind in ("merchant", "category"):
                key = "|".join((kind, norm(t.get(kind, "")), t["date"][:7]))
                v = tx[key]
                amount = abs(t["amount"])
                v["count"] += 1
                v["net"] += amount if t["type"] == "purchase" else -amount
                v["gross" if t["type"] == "purchase" else "refunds"] += amount
        plus = c.get("user", {}).get("plus_subscription", c.get("user", {}).get("plata_plus", False))
        rates, opposite = [], []
        for r in c.get("savings_rates", []):
            regular = r.get("rate", r.get("rate_without_plus", r.get("annual_rate")))
            selected = r.get("rate_with_plus", r.get("annual_rate", regular)) if plus else regular
            rates.append(dict(product=r["product"], term_months=r.get("term_months"), rate=selected))
            other = regular if plus else r.get("rate_with_plus")
            if other is not None and other != selected:
                opposite.append(other * 100)
        expected = dict(own_gross=own, available_now=own-hold, liquid=own-hold-locked,
                        net_after_debt=own-debt, net_usable_assets=own-hold-debt,
                        net_liquid=own-hold-locked-debt, debt=debt, on_hold=hold, locked=locked,
                        spendable_accounts=[a.get("balance", 0)-a.get("on_hold", a.get("held", 0))
                                            for a in accounts if a.get("on_hold", a.get("held", 0)) > 0],
                        balances={a.get("product", str(i)): a.get("balance", 0) for i, a in enumerate(accounts)},
                        previous_month=previous, full_months=sorted(window), averages=averages,
                        credit_statement=c.get("credit_statement", {}))
        credits = [sum(a.get(k, 0) for a in accounts) for k in ("available_credit", "credit_limit")]
        current = next((m for m in months if today and m["month"] == today.strftime("%Y-%m")), None)
        poison = dict(credit_as_money=sorted({base+credit-d for credit in credits if credit > 0
                                              for base in (own, own-hold, own-hold-locked) for d in (0, debt)
                                              if base+credit-d > own}), opposite_rates=opposite,
                      own_transfers=([averages["combined"]+averages["own"],
                                      (averages["combined"]+averages["own"])*3] if averages.get("own", 0) > 0 else []),
                      gross_refunds=([averages["purchases"], averages["purchases"]+averages["other"],
                                      (averages["purchases"]+averages["other"])*3] if averages.get("refunds", 0) > 0 else []),
                      current_month=[current[k] for k in ("purchases", "net_purchases", "combined")] if current else [],
                      changed_balances=[])
        if current and current["own"] > 0:
            poison["own_transfers"].append(current["combined"]+current["own"])
        turns = []
        for i, m in enumerate(conversation):
            if m["role"] == "assistant":
                text = m["content"]
                turns.append(dict(index=i, text=text, normalized=norm(text), numbers=numbers(text),
                                  money=money(text), dates=sorted(dates_in(text), key=str), language=language(text)))
        fields = flatten(c)
        for turn in turns:
            if re.search(r"сейчас на вашем счете|now.{0,20}(?:balance|account)|saldo.{0,20}ahora", turn["normalized"]):
                for product, balance in expected["balances"].items():
                    if norm(product) in turn["normalized"]:
                        poison["changed_balances"].extend(v for v in turn["money"] if not close(v, balance))
        flags = dict(plus_subscription=plus, has_debt=debt > 0, has_hold=hold > 0,
                     has_locked=locked > 0, has_refunds=any(m["refunds"] > 0 for m in months),
                     has_fixed_product=any("fijo" in norm(a.get("product", "")) for a in accounts + c.get("savings_rates", [])),
                     has_other_transfers=any(m["other"] > 0 for m in months),
                     has_three_months=len(last3) == 3,
                     languages=[language(m["content"]) for m in conversation])
        dates = sorted(dates_in(json.dumps(c, ensure_ascii=False)), key=str)
        return cls(topic, c, list(conversation), expected, poison, flags, fields, dates, turns,
                   months, last3, dict(tx), rates)

    def summary(self):
        """Small serializable index entry; the full conversation lives only in evidence."""
        return dict(expected=self.expected, poison=self.poison, flags=self.flags, dates=self.dates,
                    rates=self.rates, transactions=self.transactions,
                    assistant_turns=[{k: t[k] for k in ("index", "numbers", "dates", "language")}
                                     for t in self.assistant_turns])
