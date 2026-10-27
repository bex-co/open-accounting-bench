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
    "labor-efficiency-variance",
    "diluted-eps",
    "asset-turnover-ratio",
    "breakeven-sales-dollars",
    "direct-materials-used",
    "production-budget-units",
    "predetermined-overhead-applied",
    "interim-income-tax-expense",
    "segment-margin",
    "residual-income",
    "cash-collected-from-customers",
    "free-cash-flow",
    "adjusted-receivable-balance",
    "ppe-additions-inferred",
    "fixed-overhead-volume-variance",
    "cumulative-preferred-dividend",
    "weighted-average-cost-of-capital",
    "standard-cost-per-unit",
    "trial-balance-debit-total",
    "post-closing-debit-total",
    "adjusted-wage-expense",
    "inventory-method-profit-difference",
    "minimum-transfer-price",
    "debt-modification-percent-change",
    "irr-from-annuity-factor",
    "c-corporation-taxable-income",
    "s-corporation-aaa-ending",
    "partnership-outside-basis",
    "performance-materiality",
    "cash-and-equivalents-total",
    "tax-return-crossfoot-difference",
    "tax-cost-recovery-deduction",
    "passthrough-loss-limitation",
    "partnership-distribution-gain",
    "sample-misstatement-projection",
    "capm-expected-return",
    "duplicate-payments-total",
    "inventory-error-income-effect",
    "inventory-lcm-value",
    "expected-profit-choice",
    "receivables-control-balance",
    "partnership-liquidation-distribution",
    "profit-from-capital-movements",
    "sales-from-markup-reconstruction",
    "inventory-cost-inclusions",
    "disposal-of-subsidiary-gain",
    "step-acquisition-remeasurement-gain",
    "weighted-average-ending-inventory",
    "ledger-account-balance-carried-down",
    "allowance-movement-expense",
    "agent-commission-revenue",
    "gift-card-breakage-revenue",
    "adjusted-profit-from-draft",
    "payables-control-balance",
    "restructuring-provision-amount",
    "contract-modification-revenue",
    "lease-component-allocation",
    "separate-statements-investment",
    "change-control-deviation-count",
    "incident-response-deviation-count",
    "sql-join-excluded-count",
    "budget-vs-actual-net-variance",
    "cash-to-accrual-profit",
    "debt-covenant-ratio",
    "exit-obligation-january-amount",
    "nfp-program-expense-allocation",
    "nfp-operating-cash-flow",
    "nfp-restricted-net-assets",
    "notes-figures-difference",
    "tax-basis-net-income",
    "benefit-plan-net-assets",
    "govt-conversion-net-position",
    "govt-capitalized-costs-total",
    "govt-expenditures-december",
    "govt-long-term-debt-total",
    "govt-net-investment-capital",
    "nonexchange-revenue-recognized",
    "adjusted-ebitda-computation",
    "percent-of-sales-afn",
    "sales-mix-variance",
    "state-apportionment-income",
    "tax-penalty-combined",
    "capital-loss-carryforward",
    "disallowed-loss-amount",
    "individual-tax-with-niit",
    "individual-gross-income-total",
    "agi-above-line-adjustments",
    "qbi-deduction-amount",
    "passthrough-ordinary-income",
    "owner-ordinary-from-k1",
    "section1231-capital-amount",
    "depreciation-recapture-ordinary",
    "estimated-tax-installment",
    "installment-sale-gain-year",
    "likekind-exchange-gain",
    "below-market-imputed-interest",
    "tax-equivalent-yield",
    "taxable-gifts-total",
    "charitable-noncash-deduction",
    "corporate-distribution-dividend",
    "liquidation-shareholder-gain",
    "corporate-formation-gain",
    "partnership-contribution-gain",
    "trust-accounting-income",
    "trust-dni-computation",
    "section704c-contributor-gain",
    "constructive-ownership-percent",
    "related-party-resale-gain",
    "basis-adjustment-754-allocation",
    "income-shifting-pv-saving",
    "fsa-tax-saving",
    "builtin-gains-tax-base",
    "varying-interest-allocation",
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


@pytest.mark.parametrize("task_id", NUMERIC_FAMILIES)
def test_numeric_trap_never_within_tolerance_of_gold(task_id):
    """Seeds 0-999: the documented trap must never score as correct.

    Per-seed collisions (trap == gold, or inside the grading
    tolerance) slipped past the 3-seed trap tests for several
    families; the generator serves every seed, so sweep 1,000.
    """
    from decimal import Decimal

    fn = FAMILIES[task_id]
    for seed in range(1000):
        expected = fn(seed).expected
        gold, trap = Decimal(expected["gold"]), Decimal(expected["trap_value"])
        tolerance = Decimal(expected["abs_tolerance"])
        assert abs(trap - gold) > tolerance, (task_id, seed, gold, trap)


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
    question = instance.app_files["question.md"]
    for oid in expected["options"]:
        assert f"- {oid}." in question
    # Documented trap: classify by headline class — sweep the
    # contra-assets (credit-normal) in with the assets and leave the
    # equity/revenue contras (dividends, sales returns) out.
    import re

    by_name = dict(re.findall(r"- ([A-H])\. (.+?) has a normal DEBIT balance\.", question))
    contra_assets = {"Accumulated depreciation", "Allowance for doubtful accounts"}
    debit_lookalikes = {"Dividends declared", "Sales returns and allowances"}
    trap = {oid for oid, name in by_name.items() if name in contra_assets}
    trap |= gold - {oid for oid, name in by_name.items() if name in debit_lookalikes}
    assert trap != gold  # the seeded option set must contain the trap material
    assert grade_answer(expected, ans(sorted(trap))).reward == 0


@pytest.mark.parametrize("seed", [1, 7, 42, 234])
def test_mc_temporary_accounts_oracle_and_traps(seed):
    instance = FAMILIES["mc-temporary-accounts"](seed)
    expected = {**instance.expected, "format": instance.format}
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    assert grade_answer(expected, None).reward == 0
    gold = set(expected["gold"])
    assert 0 < len(gold) < 8
    inverse = sorted(set(expected["options"]) - gold)
    assert grade_answer(expected, ans(inverse)).reward == 0
    assert grade_answer(expected, ans(expected["options"])).reward == 0


@pytest.mark.parametrize("seed", [1, 7, 42, 250])
def test_mc_reportable_segments_oracle_and_traps(seed):
    instance = FAMILIES["mc-reportable-segments"](seed)
    expected = {**instance.expected, "format": instance.format}
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    assert grade_answer(expected, None).reward == 0
    gold = set(expected["gold"])
    assert 0 < len(gold) < len(expected["options"])
    inverse = sorted(set(expected["options"]) - gold)
    assert grade_answer(expected, ans(inverse)).reward == 0
    assert grade_answer(expected, ans(expected["options"])).reward == 0


@pytest.mark.parametrize(
    "task_id",
    [
        "sc-special-journal-routing",
        "sc-cash-flow-classification",
        "sc-subsequent-event-classification",
        "sc-transaction-statement-impact",
        "sc-job-vs-process-costing",
        "sc-fair-value-hierarchy",
        "sc-investment-classification",
        "sc-audit-procedure-selection",
        "sc-control-design-gap",
        "sc-fraud-triangle-classification",
        "sc-debt-equity-classification",
        "sc-control-assessment",
        "sc-measurement-basis",
        "sc-suspense-account-cause",
        "sc-business-vs-asset-acquisition",
        "sc-derecognition-assessment",
        "sc-offsetting-assessment",
        "sc-related-party-identification",
        "sc-backup-recovery-selection",
        "sc-database-integrity-gap",
        "sc-soc-opinion-modification",
        "sc-system-description-gap",
        "sc-governmental-fund-assignment",
        "sc-component-unit-presentation",
        "sc-fund-balance-classification",
        "sc-interfund-activity-type",
        "sc-option-value-sensitivity",
        "sc-capital-gain-classification",
        "sc-s-corp-eligibility",
        "sc-tax-authority-disclosure",
        "sc-filing-status",
        "sc-tax-practice-ethics",
        "sc-income-sourcing",
    ],
)
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


def test_sc_special_journal_return_documented_trap():
    """Documented trap: routing a credit-sale return to the sales journal."""
    import re

    for seed in range(1, 200):
        instance = FAMILIES["sc-special-journal-routing"](seed)
        if "returned merchandise sold on credit" in instance.app_files["question.md"]:
            break
    else:  # pragma: no cover - the case pool guarantees a hit quickly
        raise AssertionError("return case not found in seeds 1..199")
    expected = {**instance.expected, "format": instance.format}
    by_label = dict(re.findall(r"- ([A-E])\. (.+)", instance.app_files["question.md"]))
    sales_journal = next(oid for oid, name in by_label.items() if name == "Sales journal")
    assert grade_answer(expected, json.dumps(instance.solution_answer)).reward == 1
    report = grade_answer(expected, ans(sales_journal))
    assert report.reward == 0
    assert report.layers["answer_accuracy"].score == 0.0
