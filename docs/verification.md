# Verification

Grading is deterministic, state-based, and LLM-free. Implementation:
`src/oab/_verifier_core.py` (copied verbatim into each task as
`tests/grader.py`; CI checks for drift). Inputs: the agent's final
`/app/ledger.beancount`, the held-out initial ledger, and
`tests/expected.json`. Outputs: `/logs/verifier/reward.json`,
`report.json`, `run.log`.

## Five layers

| Layer (`reward.json` key) | Checks |
|---|---|
| `structural_validity` | Ledger parses; every posting uses an opened account; every transaction balances per currency (one elided posting is interpolated); `balance` assertions hold |
| `semantic_accuracy` | Actual per-account deltas (final − initial) match `expected_deltas` within tolerance — correct classification, direction, amount. Score = fraction matched |
| `economic_consistency` | Evidence recorded the expected number of times (`expected_new_transactions`), no duplicated new entries, new entries dated inside `expected_period` |
| `reconciliation_accuracy` | Ledger-wide sum is zero per currency; `required_final_balances` hold; bank account reconciles to `reconciliation.statement_balance` when given |
| `operational_integrity` | Every initial transaction is preserved verbatim (append-only audit trail); no delta on accounts outside `expected_deltas`/`allowed_extra_accounts`; no unauthorized new accounts |

`reward` is 1 iff all five layers pass. `partial` is the mean layer
score, for diagnosis only — a task is never "completed" on partial
credit.

The canonical trap (memo §6): debiting an asset instead of an expense
for a $5,000 cash purchase balances perfectly, so layer 1 passes —
layers 2 and 5 fail. Covered by `tests/test_verifier.py`.

## Multiple correct answers

Grading compares accounting *state*, not text. Equivalent
representations pass, e.g. elided postings, a combined reconciliation
entry instead of two entries, or reversal-plus-rebooking instead of a
single reclassification entry (all covered by tests). Where a family
allows several decompositions, `expected_new_transactions` is a range.

## `expected.json` schema

| Field | Meaning |
|---|---|
| `task_id`, `family`, `seed`, `generator_version` | Provenance / reproducibility |
| `currency`, `tolerance` | Comparison basis (Decimal arithmetic) |
| `expected_deltas` | `{account: "amount"}` required final − initial movement |
| `allowed_extra_accounts` | Accounts permitted to move besides `expected_deltas` |
| `expected_new_transactions` | Int or `[min, max]` count of appended transactions |
| `expected_period` | `[start, end]` dates for new transactions |
| `required_final_balances` | `{account: "amount"}` absolute final balances |
| `reconciliation` | Optional `{account, statement_balance}` external evidence |
| `forbid_new_accounts` | Reject newly opened accounts (default true) |

## Ledger subset

The hermetic grader parses `option`, `open`, `balance`, and `*`/`!`
transactions with `Account  Amount CCC` postings (amounts may use
thousands separators; exactly one posting per transaction may elide its
amount). Anything else is a structural error. This subset is valid
Beancount syntax; generated ledgers stay inside it. Full Beancount
features (cost basis, prices, plugins) are out of scope for v0.1
verifiers — tasks must be gradable without them.

## Answer-file formats

Non-ledger tasks (`format != "journal-entry"`) grade `/app/answer.json`
— a JSON object with `final_answer` (option id, list of ids, or number)
and optional self-reported `confidence` (0-100, echoed into rewards for
calibration analysis; never gates the reward). Expectations add
format-specific keys: `gold`, `options`, `abs_tolerance`,
`rel_tolerance`. Layers are `format_validity` and `answer_accuracy`;
`reward` requires both. Missing/malformed/wrongly-typed answers score
0 with `parse_failure = 1` and remain in every denominator.
Multiple-choice accuracy may be negative under the penalized formula.
`open-text` values are rejected by `oab validate` until a judge design
lands (see [methodology.md](methodology.md)).

## Failure handling

If the grader crashes, `tests/test.sh` leaves `reward.txt = -1`
(infrastructure sentinel, as in DeepSWE) instead of a score — such
trials must be retried/regraded, never counted as agent failures.
