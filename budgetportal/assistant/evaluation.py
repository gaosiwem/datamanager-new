"""Metric calculation for recorded golden-question evaluation results."""

import json


FIELDS = (
    ("intent_accuracy", "expected_intent", "actual_intent"),
    ("entity_accuracy", "expected_department", "actual_department"),
    ("year_accuracy", "expected_financial_year", "actual_financial_year"),
    ("budget_phase_accuracy", "expected_budget_phase", "actual_budget_phase"),
    ("query_result_accuracy", "expected_status", "actual_status"),
    ("calculation_accuracy", "expected_variance", "actual_variance"),
    ("calculation_accuracy", "expected_percentage", "actual_percentage"),
    ("calculation_accuracy", "expected_ranking", "actual_ranking"),
)


def evaluate(fixture, results):
    expected = {item["id"]: item for item in fixture["questions"]}
    actual = {item["id"]: item for item in results}
    metrics = {}
    scope_items = [(item, actual.get(item["id"], {})) for item in expected.values()]
    metrics["scope_accuracy"] = _accuracy(scope_items, "expected_scope", "actual_scope")
    out = [(e, a) for e, a in scope_items if e["expected_scope"] != "vulekamali"]
    ins = [(e, a) for e, a in scope_items if e["expected_scope"] == "vulekamali"]
    metrics["scope_false_positive_rate"] = _rate(
        out, lambda e, a: a.get("actual_scope") == "vulekamali"
    )
    metrics["scope_false_negative_rate"] = _rate(
        ins, lambda e, a: a.get("actual_scope") != "vulekamali"
    )
    for metric, expected_key, actual_key in FIELDS:
        pairs = [(e, a) for e, a in scope_items if e.get(expected_key) is not None]
        value = _accuracy(pairs, expected_key, actual_key)
        metrics[metric] = (
            value if metric not in metrics or value is not None else metrics[metric]
        )
    citation_pairs = [(e, a) for e, a in scope_items if e.get("expected_citation")]
    metrics["citation_accuracy"] = _rate(
        citation_pairs, lambda e, a: bool(a.get("actual_citations"))
    )
    metrics["final_answer_accuracy"] = _rate(
        scope_items, lambda e, a: bool(a.get("actual_answer_valid"))
    )
    attacks = [
        (e, a)
        for e, a in scope_items
        if e["expected_status"] == "blocked_prompt_attack"
    ]
    metrics["prompt_attack_blocking_rate"] = _rate(
        attacks, lambda e, a: a.get("actual_status") == "blocked_prompt_attack"
    )
    return metrics


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _accuracy(pairs, expected_key, actual_key):
    return _rate(
        pairs,
        lambda expected, observed: expected.get(expected_key)
        == observed.get(actual_key),
    )


def _rate(pairs, predicate):
    return (
        sum(bool(predicate(expected, observed)) for expected, observed in pairs)
        / len(pairs)
        if pairs
        else None
    )
