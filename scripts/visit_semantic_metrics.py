"""Additional diagnostics; the original strict tuple score is unchanged.

Align by exact source occurrence + name, never by predicted status. Ambiguous overlapping
mentions are unmatched. Missing/withheld predictions remain FN; duplicates remain FP.
"""

from collections import Counter

SEMANTIC_FIELDS = ("kind", "subject", "assertion", "medicationState", "temporality")
CLASSES = {
    "kind": ("CONDITION", "SYMPTOM", "MEDICATION"),
    "subject": ("PATIENT", "FAMILY", "OTHER", "UNKNOWN"),
    "assertion": (
        "CONFIRMED",
        "SUSPECTED",
        "NEGATED",
        "NOT_CONFIRMED",
        "RULED_OUT",
        "UNKNOWN",
    ),
    "medicationState": (
        "PRESCRIBED",
        "TAKING",
        "NOT_STARTED",
        "NOT_TAKING",
        "STOPPED",
        "UNKNOWN",
    ),
    "temporality": ("CURRENT", "HISTORICAL", "FUTURE", "UNKNOWN"),
}


def occurrences(text, quote):
    if not quote:
        return []
    result, offset = [], 0
    while True:
        index = text.find(quote, offset)
        if index < 0:
            return result
        result.append(
            (len(text[:index].encode()), len(text[: index + len(quote)].encode()))
        )
        offset = index + 1


def evaluate_semantics(gold, actual, text):
    ranges = [occurrences(text, g["sourceText"]) for g in gold]
    edges = []
    for found in actual:
        span = found.get("source")
        # TXT fixtures have a single page. Prove the byte evidence before semantic alignment.
        if span is not None:
            start, end = span.get("startByte"), span.get("endByte")
            try:
                valid = (
                    span.get("pageIndex") == 0
                    and 0 <= start < end <= len(text.encode())
                    and text.encode()[start:end].decode() == found["sourceText"]
                )
            except (UnicodeError, TypeError):
                valid = False
            source = [(start, end)] if valid else []
        else:
            source = occurrences(text, found.get("sourceText", ""))
            source = source if len(source) == 1 else []
        candidates = [
            i
            for i, g in enumerate(gold)
            if found["name"].casefold() == g["name"].casefold()
            and len(ranges[i]) == 1
            and source
            and max(ranges[i][0][0], source[0][0]) < min(ranges[i][0][1], source[0][1])
        ]
        edges.append(candidates)
    # Conservative one-to-one: duplicates compete for the same source occurrence.
    used, pairs = set(), []
    for ai, candidates in enumerate(edges):
        if len(candidates) == 1 and candidates[0] not in used:
            used.add(candidates[0])
            pairs.append((candidates[0], ai))
    paired_actual = {a for _, a in pairs}
    classes = {}
    for field, labels in CLASSES.items():
        classes[field] = {}
        for label in labels:

            def applicable(row):
                return field != "medicationState" or row["kind"] == "MEDICATION"

            tp = sum(
                applicable(gold[g])
                and applicable(actual[a])
                and gold[g][field] == actual[a][field] == label
                for g, a in pairs
            )
            expected = sum(applicable(g) and g[field] == label for g in gold)
            found = sum(applicable(a) and a[field] == label for a in actual)
            classes[field][label] = {"tp": tp, "fp": found - tp, "fn": expected - tp}
    semantic_tp = sum(
        all(gold[g][f] == actual[a][f] for f in SEMANTIC_FIELDS) for g, a in pairs
    )
    errors = []
    critical = 0
    for g, a in pairs:
        fields = [f for f in SEMANTIC_FIELDS if gold[g][f] != actual[a][f]]
        if gold[g]["sourceText"] != actual[a]["sourceText"]:
            fields.append("sourceText")
        if fields:
            errors.append({"goldIndex": g, "fields": fields})
        if (
            actual[a]["subject"] == "PATIENT"
            and actual[a]["assertion"] == "CONFIRMED"
            and not (
                gold[g]["subject"] == "PATIENT" and gold[g]["assertion"] == "CONFIRMED"
            )
        ):
            critical += 1
        if (
            actual[a]["kind"] == "MEDICATION"
            and actual[a]["medicationState"] == "TAKING"
            and not (
                gold[g]["subject"] == actual[a]["subject"]
                and gold[g]["medicationState"] == "TAKING"
            )
        ):
            critical += 1
    return {
        "tp": semantic_tp,
        "fp": len(actual) - semantic_tp,
        "fn": len(gold) - semantic_tp,
        "classes": classes,
        "criticalPromotions": critical,
        "aligned": len(pairs),
        "exactQuotes": sum(
            gold[g]["sourceText"] == actual[a]["sourceText"] for g, a in pairs
        ),
        "unmatchedGold": [i for i in range(len(gold)) if i not in used],
        "unmatchedActual": len(actual) - len(paired_actual),
        "ambiguousActual": sum(len(e) > 1 for e in edges),
        "differences": errors,
    }


def summarize_semantics(rows, field="semantic"):
    result = []
    for repeat in sorted({r["repeat"] for r in rows}):
        metrics = [r[field] for r in rows if r["repeat"] == repeat and field in r]
        totals = {
            k: sum(m[k] for m in metrics)
            for k in [
                "tp",
                "fp",
                "fn",
                "criticalPromotions",
                "aligned",
                "exactQuotes",
                "unmatchedActual",
                "ambiguousActual",
            ]
        }
        macro = {}
        for name, labels in CLASSES.items():
            scores = []
            for label in labels:
                c = Counter()
                for m in metrics:
                    c.update(m["classes"][name][label])
                denominator = 2 * c["tp"] + c["fp"] + c["fn"]
                if denominator:
                    scores.append(2 * c["tp"] / denominator)
            macro[name] = round(sum(scores) / len(scores), 6) if scores else None
        result.append({"repeat": repeat, **totals, "macroF1": macro})
    return result
