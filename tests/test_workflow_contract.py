"""Professional workflow contract: multi-artifact deterministic rubrics."""

import json
from pathlib import Path

from oab.cli import validate_tasks
from oab.generate import write_task
from oab.report import aggregate_tasks, render_leaderboard
from oab.verify import grade_workflow
from oab.workflow import CHECK_TYPES, DEFAULT_WORKFLOW_ARTIFACT, validate_workflow_spec
from oab.workflow_families import DYNAMIC_FAMILIES

FIXTURE = "workflow-conformance-fixture"
WORKFLOW_PATH = DEFAULT_WORKFLOW_ARTIFACT


def _fixture(seed: int = 42):
    instance = DYNAMIC_FAMILIES[FIXTURE](seed)
    return instance, instance.expected


def _artifacts(instance) -> dict[str, str | None]:
    return {WORKFLOW_PATH: instance.solution_files["workflow.json"]}


def _check(report, check_id: str) -> dict:
    checks = report.to_report_json()["details"]["workflow"]["checks"]
    return next(check for check in checks if check["id"] == check_id)


def test_workflow_fixture_is_deterministic_and_has_auditable_rubric():
    first, expected = _fixture()
    second, _ = _fixture()
    assert first.app_files == second.app_files
    assert first.expected == second.expected
    assert first.solution_files == second.solution_files

    spec = expected["workflow"]
    assert validate_workflow_spec(spec) == []
    assert len(spec["checks"]) >= 30
    determinations = {item["id"] for item in spec["determinations"]}
    assert {check["determination"] for check in spec["checks"]} == determinations
    assert set(CHECK_TYPES) <= {check["type"] for check in spec["checks"]}


def test_workflow_spec_rejects_orphans_and_unknown_fields():
    _instance, expected = _fixture()
    spec = json.loads(json.dumps(expected["workflow"]))
    spec["checks"][0]["determination"] = "missing-determination"
    spec["checks"][0]["unexpected"] = True
    failures = validate_workflow_spec(spec)
    assert any("unknown determination" in failure for failure in failures)
    assert any("unknown field" in failure for failure in failures)


def test_workflow_oracle_nop_and_missing_artifact():
    instance, expected = _fixture()
    oracle = grade_workflow(
        instance.initial_ledger,
        instance.solution_ledger,
        expected,
        _artifacts(instance),
    )
    assert oracle.reward == 1, oracle.to_report_json()
    assert oracle.to_reward_json()["rubric_completion"] == 1.0
    assert oracle.to_reward_json()["workflow_check_completion"] == 1.0

    nop = grade_workflow(
        instance.initial_ledger,
        instance.initial_ledger,
        expected,
        _artifacts(instance),
    )
    assert nop.reward == 0
    assert nop.to_reward_json()["rubric_completion"] < 1.0

    missing = grade_workflow(
        instance.initial_ledger,
        instance.solution_ledger,
        expected,
        {WORKFLOW_PATH: None},
    )
    assert missing.reward == 0
    assert missing.to_reward_json()["parse_failure"] == 1.0


def test_workflow_split_entry_is_equivalent():
    instance, expected = _fixture()
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    original = (
        '2026-01-31 * "Bank" "Monthly account fee"\n'
        "  Expenses:BankFees  25.00 USD\n"
        "  Assets:Bank:Checking  -25.00 USD\n"
    )
    split = (
        '2026-01-31 * "Bank" "Monthly account fee (part 1)"\n'
        "  Expenses:BankFees  10.00 USD\n"
        "  Assets:Bank:Checking  -10.00 USD\n\n"
        '2026-01-31 * "Bank" "Monthly account fee (part 2)"\n'
        "  Expenses:BankFees  15.00 USD\n"
        "  Assets:Bank:Checking  -15.00 USD\n"
    )
    assert original in added
    equivalent = instance.initial_ledger + added.replace(original, split, 1)
    report = grade_workflow(
        instance.initial_ledger,
        equivalent,
        expected,
        _artifacts(instance),
    )
    assert report.reward == 1, report.to_report_json()


def test_workflow_mutants_lose_mapped_checks():
    instance, expected = _fixture()
    added = instance.solution_ledger[len(instance.initial_ledger) :]

    wrong_account = instance.initial_ledger + added.replace(
        "  Expenses:BankFees", "  Assets:Equipment", 1
    )
    report = grade_workflow(
        instance.initial_ledger,
        wrong_account,
        expected,
        _artifacts(instance),
    )
    assert report.reward == 0
    assert _check(report, "bank-fee-account-delta")["passed"] is False
    assert _check(report, "equipment-forbidden-delta")["passed"] is False

    wrong_period = instance.initial_ledger + added.replace("2026-02-03", "2026-03-03", 1)
    report = grade_workflow(
        instance.initial_ledger,
        wrong_period,
        expected,
        _artifacts(instance),
    )
    assert report.reward == 0
    assert _check(report, "customer-receipt-february-delta")["passed"] is False
    assert _check(report, "march-cutoff-no-transactions")["passed"] is False

    workflow = json.loads(instance.solution_files["workflow.json"])
    workflow["report"]["bank_balance"] = str(float(workflow["report"]["bank_balance"]) + 1)
    report = grade_workflow(
        instance.initial_ledger,
        instance.solution_ledger,
        expected,
        {WORKFLOW_PATH: json.dumps(workflow)},
    )
    assert report.reward == 0
    assert _check(report, "report-bank-balance")["passed"] is False
    assert _check(report, "bank-ledger-report-reconciliation")["passed"] is False


def test_workflow_fixture_seed_sweep_oracle():
    for seed in [0, 1, 7, 42, 99]:
        instance, expected = _fixture(seed)
        report = grade_workflow(
            instance.initial_ledger,
            instance.solution_ledger,
            expected,
            _artifacts(instance),
        )
        assert report.reward == 1, (seed, report.to_report_json())


def test_workflow_combined_product_entry_is_equivalent():
    instance, expected = _fixture()
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    deltas = instance.expected["expected_deltas"]
    sale = deltas["Income:ProductRevenue"].lstrip("-")
    cost = deltas["Expenses:CostOfSales"]
    original = (
        '2026-02-10 * "Customer" "Product shipment"\n'
        f"  Assets:AccountsReceivable  {sale} USD\n"
        f"  Income:ProductRevenue  -{sale} USD\n\n"
        '2026-02-10 * "Warehouse" "Cost of product shipment"\n'
        f"  Expenses:CostOfSales  {cost} USD\n"
        f"  Assets:Inventory  -{cost} USD\n"
    )
    combined = (
        '2026-02-10 * "Customer" "Product shipment and cost"\n'
        f"  Assets:AccountsReceivable  {sale} USD\n"
        f"  Income:ProductRevenue  -{sale} USD\n"
        f"  Expenses:CostOfSales  {cost} USD\n"
        f"  Assets:Inventory  -{cost} USD\n"
    )
    assert original in added
    equivalent = instance.initial_ledger + added.replace(original, combined, 1)
    report = grade_workflow(
        instance.initial_ledger,
        equivalent,
        expected,
        _artifacts(instance),
    )
    assert report.reward == 1, report.to_report_json()


def test_workflow_duplicate_and_unresolved_suspense_mutants():
    instance, expected = _fixture()
    added = instance.solution_ledger[len(instance.initial_ledger) :]
    blocks = [block for block in added.split("\n\n") if block.strip()]
    supplier = next(block for block in blocks if "Unrecorded repairs invoice" in block)
    duplicate = instance.solution_ledger + "\n" + supplier + "\n"
    report = grade_workflow(
        instance.initial_ledger,
        duplicate,
        expected,
        _artifacts(instance),
    )
    assert report.reward == 0
    assert _check(report, "supplier-repairs-delta")["passed"] is False

    without_suspense = instance.initial_ledger + "\n\n".join(
        block for block in blocks if "Clear suspense balance" not in block
    )
    report = grade_workflow(
        instance.initial_ledger,
        without_suspense,
        expected,
        _artifacts(instance),
    )
    assert report.reward == 0
    assert _check(report, "suspense-cleared")["passed"] is False


def test_report_keeps_workflow_rubric_separate_from_completion():
    rows = [
        {
            "task_id": FIXTURE,
            "format": "workflow",
            "category": "financial-accounting",
            "framework": "core",
            "level": "university",
            "skill": "analysis",
            "graded": True,
            "reward": 0.0,
            "answer": None,
            "rubric_completion": 0.75,
            "workflow_check_completion": 0.8,
            "confidence": None,
            "parse_failure": 0.0,
            "cost_usd": None,
        }
    ]
    tasks = aggregate_tasks(rows)
    assert tasks[FIXTURE]["score"] == 0.0
    assert tasks[FIXTURE]["mean_rubric_completion"] == 0.75
    board = render_leaderboard(rows, tasks, None)
    assert "Overall verified completion: **0.0%**" in board
    assert "## Workflow rubric" in board
    assert "| workflow-conformance-fixture | 75.0% | 80.0% |" in board


def test_generated_workflow_task_validates(tmp_path: Path):
    instance, _expected = _fixture(7)
    task_dir = write_task(instance, tmp_path, track="dynamic")
    assert validate_tasks(tmp_path) == []
    task_toml = (task_dir / "task.toml").read_text()
    assert 'artifacts = ["/app/ledger.beancount", "/app/workflow.json"]' in task_toml
    assert (task_dir / "solution" / "workflow.json").is_file()
