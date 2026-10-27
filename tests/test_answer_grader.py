"""Answer-file grader: choice/numeric scoring, parse failures, MC family."""

import json

import pytest

from oab.families import FAMILIES
from oab.verify import grade_answer


def ans(final, confidence=90):
    return json.dumps({"final_answer": final, "confidence": confidence})


def test_single_choice():
    expected = {"format": "single-choice", "gold": "B"}
    assert grade_answer(expected, ans("B")).reward == 1
    wrong = grade_answer(expected, ans("A"))
    assert wrong.reward == 0
    assert wrong.layers["answer_accuracy"].score == 0.0


def test_multiple_choice_penalty_formula():
    expected = {"format": "multiple-choice", "gold": ["A", "C"]}
    assert grade_answer(expected, ans(["A", "C"])).reward == 1
    partial = grade_answer(expected, ans(["A"]))
    assert partial.reward == 0
    assert partial.layers["answer_accuracy"].score == 0.5
    extra = grade_answer(expected, ans(["A", "C", "D"]))
    assert extra.layers["answer_accuracy"].score == 0.5
    negative = grade_answer(expected, ans(["D", "E"]))
    assert negative.layers["answer_accuracy"].score == -1.0


def test_numeric_tolerances():
    expected = {
        "format": "numeric",
        "gold": "1000",
        "abs_tolerance": "1",
        "rel_tolerance": "0.01",
    }
    assert grade_answer(expected, ans(1005)).reward == 1
    assert grade_answer(expected, ans(1020)).reward == 0
    assert grade_answer(expected, ans("990")).reward == 1


@pytest.mark.parametrize("bad", [None, "", "not json", "[]", '{"x": 1}', ans(123), ans("A")])
def test_parse_failures_score_zero_and_are_flagged(bad):
    expected = {"format": "multiple-choice", "gold": ["A"]}
    report = grade_answer(expected, bad)
    assert report.reward == 0
    assert report.to_reward_json()["parse_failure"] == 1.0


def test_confidence_echoed_but_never_gates_reward():
    expected = {"format": "single-choice", "gold": "B"}
    report = grade_answer(expected, ans("B", confidence=35))
    assert report.reward == 1
    assert report.to_reward_json()["confidence"] == 35.0


@pytest.mark.parametrize("seed", [1, 7, 42, 105])
def test_mc_family_oracle_nop_and_trap(seed):
    instance = FAMILIES["mc-capitalization-treatment"](seed)
    expected = {**instance.expected, "format": instance.format}
    oracle = grade_answer(expected, json.dumps(instance.solution_answer))
    assert oracle.reward == 1, oracle.to_report_json()
    assert grade_answer(expected, None).reward == 0
    # Trap: selecting every option (incl. expensing) must not pass.
    greedy = grade_answer(expected, ans(["A", "B", "C", "D", "E"]))
    assert greedy.reward == 0
    assert greedy.layers["answer_accuracy"].score < 1.0
    # The question documents every option id exactly once.
    question = instance.app_files["question.md"]
    for oid in ["A", "B", "C", "D", "E"]:
        assert f"- {oid}." in question


NUMERIC_FAMILIES = [
    "cvp-target-profit-units",
    "process-costing-equivalent-units",
    "operating-cash-flow-indirect",
    "inventory-days-on-hand",
    "lifo-ending-inventory",
    "materials-price-variance",
    "npv-project-evaluation",
    "make-or-buy-advantage",
    "absorption-variable-income-difference",
    "current-ratio",
    "bank-adjusted-balance",
    "abc-overhead-assigned",
    "high-low-variable-cost",
    "cash-collections-budget",
    "gross-profit-from-trial-balance",
    "ending-retained-earnings",
    "present-value-lump-sum",
    "flexible-budget-total-cost",
    "accounting-equation-missing-equity",
    "current-income-tax-expense",
    "lease-liability-present-value",
    "equity-method-carrying-amount",
    "bond-issue-price",
    "partnership-income-allocation",
    "materials-quantity-variance",
    "cost-of-goods-manufactured",
    "payback-period-years",
    "multiproduct-breakeven-units",
    "total-current-liabilities",
]


@pytest.mark.parametrize("task_id", NUMERIC_FAMILIES)
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_numeric_families_oracle_and_plausible_trap(task_id, seed):
    instance = FAMILIES[task_id](seed)
    expected = {**instance.expected, "format": instance.format}
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    assert grade_answer(expected, None).reward == 0
    # Trap: the documented plausible wrong value (wrong formula/method).
    trap = grade_answer(expected, ans(float(expected["trap_value"])))
    assert trap.reward == 0
    assert trap.layers["answer_accuracy"].score < 1.0


@pytest.mark.parametrize("seed", [1, 7, 42, 106])
def test_mgmt_family_oracle_and_wrong_formula_trap(seed):
    from decimal import Decimal

    instance = FAMILIES["mgmt-break-even-units"](seed)
    expected = {**instance.expected, "format": instance.format}
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    assert grade_answer(expected, None).reward == 0
    gold = Decimal(expected["gold"])
    # Trap scale: answering with current volume (gold + offset) fails.
    assert grade_answer(expected, ans(float(gold) + 500)).reward == 0


@pytest.mark.parametrize("seed", [1, 7, 42, 166])
def test_mc_normal_balances_oracle_and_traps(seed):
    instance = FAMILIES["mc-normal-balances"](seed)
    expected = {**instance.expected, "format": instance.format}
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    assert grade_answer(expected, None).reward == 0
    gold = set(expected["gold"])
    assert 0 < len(gold) < 8
    # Trap: pick the credit-normal accounts instead (contra-assets etc.).
    inverse = sorted(set(expected["options"]) - gold)
    assert grade_answer(expected, ans(inverse)).reward == 0
    assert grade_answer(expected, ans(expected["options"])).reward == 0
    question = instance.app_files["question.md"]
    for oid in expected["options"]:
        assert f"- {oid}." in question


@pytest.mark.parametrize("task_id", ["sc-special-journal-routing", "sc-cash-flow-classification"])
@pytest.mark.parametrize("seed", [1, 7, 42, 167, 5, 9, 11])
def test_single_choice_families_oracle_and_wrong_option(task_id, seed):
    instance = FAMILIES[task_id](seed)
    expected = {**instance.expected, "format": instance.format}
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    assert grade_answer(expected, None).reward == 0
    wrong = next(o for o in expected["options"] if o != expected["gold"])
    report = grade_answer(expected, ans(wrong))
    assert report.reward == 0
    assert report.layers["answer_accuracy"].score == 0.0
