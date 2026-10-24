"""Bounded JSON expression interpreter. No generated Python or regex execution.

Conditions return True/False/None (missing information). A missing operand stays
unknown under NOT; it cannot manufacture a violation from absent context.
"""

import fnmatch
import json
import math
import re

from .facts import NUM, close, number, norm

ROOTS = {"expected", "poison", "flags", "context", "known_fields", "rates", "transactions", "months"}
OPS = {
    "and": ({"op", "args"}, set()), "or": ({"op", "args"}, set()),
    "not": ({"op", "arg"}, set()),
    "compare": ({"op", "left", "right", "cmp"}, {"absolute", "relative"}),
    "number_present": ({"op", "value"}, {"kind", "scope", "absolute", "relative"}),
    "number_absent": ({"op", "value"}, {"kind", "scope", "absolute", "relative"}),
    "field_present": ({"op", "field"}, set()), "flag": ({"op", "name"}, set()),
    "text_contains": ({"op", "text"}, {"scope"}),
    "add": ({"op", "left", "right"}, set()), "sub": ({"op", "left", "right"}, set()),
    "mul": ({"op", "left", "right"}, set()), "div": ({"op", "left", "right"}, set()),
}

GRAMMAR = """DSL impl is a JSON object (or a JSON-encoded string of that object).
Boolean: {"op":"and|or","args":[conditions]}, {"op":"not","arg":condition}.
Numeric: {"op":"compare","left":operand,"cmp":"eq|ne|lt|le|gt|ge","right":operand,
"absolute":1,"relative":0.005}. Operand: a finite number, {"ref":"expected.net_after_debt"},
or {"op":"add|sub|mul|div","left":operand,"right":operand}.
Refs may only start with expected, poison, flags, context, known_fields, rates, transactions, months.
{"op":"number_present|number_absent","value":operand,"kind":"money|number|percent",
"scope":"all|first|last","absolute":1,"relative":0.005} searches assistant turns.
Ref can resolve to a list: number_present means ANY; number_absent means NONE.
{"op":"field_present","field":"accounts.*.balance"} tests populated context fields.
{"op":"flag","name":"has_hold"} tests a FactSheet boolean flag.
{"op":"text_contains","text":"literal phrase","scope":"assistant|user"} is a literal substring.
Only these operators are allowed. Missing numeric facts are unknown, including under not.
No item IDs, labels, Python, regexes or file/network operations are available.
"""


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate(expression):
    if isinstance(expression, str):
        if len(expression) > 16000:
            raise ValueError("DSL too large")
        expression = json.loads(expression)
    count = 0

    def walk(node, depth=0):
        nonlocal count
        count += 1
        if count > 128 or depth > 12:
            raise ValueError("DSL complexity limit")
        if finite(node):
            return
        if not isinstance(node, dict):
            raise ValueError("DSL node must be an object or finite number")
        if set(node) == {"ref"}:
            ref = node["ref"]
            if not isinstance(ref, str) or len(ref) > 200 or ref.split(".")[0] not in ROOTS or "__" in ref:
                raise ValueError("Forbidden DSL reference")
            return
        op = node.get("op")
        if op not in OPS:
            raise ValueError("Unknown DSL operator")
        required, optional = OPS[op]
        if not required <= node.keys() or set(node) - required - optional:
            raise ValueError("Invalid DSL fields")
        for key in ("absolute", "relative"):
            if key in node and (not finite(node[key]) or node[key] < 0):
                raise ValueError("Invalid DSL tolerance")
        if op in ("and", "or"):
            if not isinstance(node["args"], list) or not 1 <= len(node["args"]) <= 32:
                raise ValueError("Invalid boolean arguments")
            for arg in node["args"]:
                walk(arg, depth + 1)
        for key in ("arg", "left", "right", "value"):
            if key in node:
                walk(node[key], depth + 1)
        if op == "compare" and node["cmp"] not in ("eq", "ne", "lt", "le", "gt", "ge"):
            raise ValueError("Invalid comparison")
        if op.startswith("number_") and (node.get("kind", "number") not in ("money", "number", "percent") or node.get("scope", "all") not in ("all", "first", "last")):
            raise ValueError("Invalid number scope or kind")
        if op == "text_contains" and node.get("scope", "assistant") not in ("assistant", "user"):
            raise ValueError("Invalid text scope")
        for key in ("field", "name", "text"):
            if key in node and (not isinstance(node[key], str) or not 1 <= len(node[key]) <= 300):
                raise ValueError("Invalid DSL literal")
    walk(expression)
    if not isinstance(expression, dict) or expression.get("op") in (None, "add", "sub", "mul", "div"):
        raise ValueError("Top-level DSL must be a condition")
    return expression


def resolve(facts, ref):
    root, *parts = ref.split(".")
    value = getattr(facts, root)  # root is validated against a fixed whitelist
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def evaluate(expression, facts):
    expression = validate(expression)

    def run(node):
        if finite(node):
            return node
        if "ref" in node:
            return resolve(facts, node["ref"])
        op = node["op"]
        if op in ("and", "or"):
            values = [boolean(run(x)) for x in node["args"]]
            if op == "and":
                return False if False in values else (None if None in values else True)
            return True if True in values else (None if None in values else False)
        if op == "not":
            value = boolean(run(node["arg"]))
            return None if value is None else not value
        if op == "field_present":
            return any(fnmatch.fnmatchcase(k, node["field"]) and v is not None for k, v in facts.known_fields.items())
        if op == "flag":
            return boolean(facts.flags.get(node["name"]))
        if op == "text_contains":
            return norm(node["text"]) in norm("\n".join(m["content"] for m in facts.conversation if m["role"] == node.get("scope", "assistant")))
        absolute, relative = node.get("absolute", 1), node.get("relative", .005)
        if op.startswith("number_"):
            expected = run(node["value"])
            expected = expected if isinstance(expected, list) else [expected]
            if not expected or any(not finite(v) for v in expected):
                return None
            turns = facts.assistant_turns
            if node.get("scope") == "first":
                turns = turns[:1]
            elif node.get("scope") == "last":
                turns = turns[-1:]
            if not turns:
                return None
            kind = node.get("kind", "number")
            if kind == "percent":
                values = [number(m.group(1)) for t in turns for m in re.finditer("("+NUM+r")\s*%", t["text"])]
            else:
                values = [n for t in turns for n in t["money" if kind == "money" else "numbers"]]
            present = any(close(v, e, absolute, relative) for v in values for e in expected)
            return present if op == "number_present" else not present
        left, right = run(node["left"]), run(node["right"])
        if not finite(left) or not finite(right):
            return None
        if op in ("add", "sub", "mul", "div"):
            if op == "div" and right == 0:
                return None
            result = {"add": lambda: left+right, "sub": lambda: left-right,
                      "mul": lambda: left*right, "div": lambda: left/right}[op]()
            return result if finite(result) else None
        tolerance = max(absolute, abs(right)*relative)
        return {"eq": abs(left-right) <= tolerance, "ne": abs(left-right) > tolerance,
                "lt": left < right-tolerance, "le": left <= right+tolerance,
                "gt": left > right+tolerance, "ge": left >= right-tolerance}[node["cmp"]]

    return boolean(run(expression))


def boolean(value):
    return value if type(value) is bool else None
