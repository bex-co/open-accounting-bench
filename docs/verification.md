# Verification

Grading is deterministic, state-based, and LLM-free. Implementation:
`src/oab/_verifier_core.py` (copied verbatim into each task as
`tests/grader.py`; CI checks for drift). Inputs: the agent's declared
artifacts (the final `/app/ledger.beancount` for journal-entry tasks,
plus structured JSON artifacts for `workflow` tasks), the held-out
initial ledger where applicable, and `tests/expected.json`. Outputs:
`/logs/verifier/reward.json`, `report.json`, `run.log`.

## Five layers

| Layer (`reward.json` key) | Checks |
|---|---|
| `structural_validity` | Ledger parses; every posting uses an opened account in a currency it was opened for; every transaction balances per currency (one elided posting is interpolated); `balance` assertions hold |
| `semantic_accuracy` | Actual per-account deltas (final − initial) match `expected_deltas` within tolerance — correct classification, direction, amount. Score = fraction matched |
| `economic_consistency` | Evidence recorded the expected number of times (`expected_new_transactions`), no duplicated new entries, new entries dated inside `expected_period` |
| `reconciliation_accuracy` | Ledger-wide sum is zero per currency; `required_final_balances` hold; bank account reconciles to `reconciliation.statement_balance` when given |
| `operational_integrity` | Every initial transaction is preserved verbatim (append-only audit trail); no delta on accounts outside `expected_deltas`/`allowed_extra_accounts`; no unauthorized new accounts |

`reward` is 1 iff all five layers pass. `partial` is the mean layer
score, for diagnosis only — a task is never "completed" on partial
credit.

`report.json` also carries `details.diagnostics` for every ledger
grade, an informational classification that never affects reward. Each
expected account is `correct`, `wrong-amount` (it moved, by a different
amount), `wrong-account` (it did not move, while an account outside the
expectation moved by exactly the expected amount — a misposting), or
`missing`; `extra` lists other unexpected movements. It separates
choosing the wrong account from computing the wrong amount, and shows
which error a family's trap actually catches. `oab report` aggregates
the class counts per family.

The canonical trap (memo §6): debiting an asset instead of an expense
for a $5,000 cash purchase balances perfectly, so layer 1 passes —
layers 2 and 5 fail. Covered by `tests/test_verifier.py`.

## Multiple correct answers

Grading compares accounting *state*, not text. Equivalent
representations pass, e.g. elided postings, a combined reconciliation
entry instead of two entries, or reversal-plus-rebooking instead of a
single reclassification entry (all covered by tests). Where a family
allows several decompositions, `expected_new_transactions` is a range.

## Workflow format

`format = "workflow"` keeps the five ledger layers above as its
integrity baseline and adds a `workflow_rubric` layer. The held-out
`expected.workflow` object (author schema and validator:
`src/oab/workflow.py`) declares:

- `artifacts` — exactly one ledger artifact plus one or more JSON
  schedule/report artifacts under `/app`;
- `determinations` — the accounting conclusions the scenario asks the
  agent to reach, grouped into issue clusters and optionally weighted;
- `checks` — typed deterministic assertions, each attached to exactly
  one determination. The closed vocabulary covers overall and
  per-period account deltas, final balances, cleared subledgers,
  cutoff windows with no added transactions, evidence dispositions in
  JSON, JSON report values, forbidden account movement, and
  ledger-to-JSON balance reconciliation.

Every `gate: true` check must pass, along with all five baseline
layers, for `reward = 1`. Non-gate checks are diagnostic. A
determination's score is the fraction of its checks that pass;
`rubric_completion` is the weighted mean across determinations, so
duplicating an assertion cannot earn more than its underlying
determination. `report.json` carries per-check, per-determination, and
per-cluster details; `reward.json` also exposes
`workflow_check_completion` (the raw check fraction) and
`parse_failure`. Rubric completion is diagnostic only and never makes
a task "completed" without reward 1.

A workflow may be a **no-action control**: it declares
`expected_new_transactions: 0` and empty `expected_deltas`, its
solution ledger equals the initial ledger, and `oab validate` admits it
only on that declaration. The grader then adds an `over_action`
diagnostic to `reward.json` (1.0 if anything was appended, else 0.0);
it never affects reward, which the layers already set to 0 for any
appended entry.

Workflow families are Dynamic-first: they live in
`DYNAMIC_FAMILIES` until calibration and review justify promotion to
`FAMILIES` with a frozen Stable seed. The Dynamic
`workflow-conformance-fixture` exercises every check type through the
public generator, Harbor packaging, CLI validation, and verifier.

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
| `workflow` | Workflow format only: versioned artifacts, determinations, and typed checks (`src/oab/workflow.py`) |

## Ledger subset

The hermetic grader parses `option`, `open` (with optional currency
constraints), `balance`, and `*`/`!`/`txn` transactions with
`Account  Amount CCC` postings. Amounts may use thousands separators and
any number of decimals; exactly one posting per transaction may elide
its amount. Comments, tags, links, and `key: value` metadata lines on
entries and postings are accepted and ignored. A posting in a currency
its account was not opened for is a structural error, as in Beancount;
constraints declared in the initial ledger keep binding even if the
`open` line is rewritten.
Anything else is a structural error. This subset is valid Beancount
syntax; generated ledgers stay inside it. Full Beancount features (cost
basis, prices, plugins) are out of scope for v0.1 verifiers — tasks
must be gradable without them.

Append-only integrity compares each initial transaction's date, flag,
description, and postings, and each initial `open` directive's date and
currency constraint, so rewording or re-flagging an existing entry, or
deleting or loosening an existing `open`, fails `operational_integrity`
just as changing its amounts does. Any movement outside the expected
reporting-currency deltas, in any currency, is unauthorized unless the
account is in `allowed_extra_accounts`.

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

## Mutation audit (false accepts and false rejects)

`oab audit` (`make audit`, also run in CI) measures the grader directly.
Deterministic operators (`src/oab/audit.py`) mutate every Stable task's
oracle into probes with a declared verdict, and the hermetic grader
scores each one:

- **False-accept probes** are wrong answers that must score 0, each
  naming the layer expected to catch it: the untouched ledger; deleting,
  re-amounting, rewording, or re-flagging an existing entry; omitting,
  duplicating, re-scaling, or misclassifying a required entry; an
  unrelated in-period entry; foreign-currency side postings; dating
  entries after the period; opening an unauthorized account; deleting
  or loosening an existing `open` directive; an unbalanced entry. For answer files: missing, out-of-tolerance, trap
  value, NaN, boolean, list-wrapped, wrong option, superset, subset.
- **False-reject probes** are equivalent correct answers that must score
  1: elided, reordered, split, or merged entries (when the
  transaction-count range admits them); post-reverse-rebook; comments,
  tags, links, metadata, the `txn` keyword; thousands separators and
  other decimal precisions; tab indentation with CRLF line endings. For
  answer files: numbers as strings, trailing zeros, the exact tolerance
  edge, extra keys, reordered multiple-choice options.

Results on 2026-11-05, all 291 Stable tasks:

| Probe kind | Probes | Misjudged at 0.8.0 | at 0.9.0 | at 0.10.0 |
|---|---:|---:|---:|---:|
| False accept (wrong answer passed) | 2,507 | 450 | 180 | 0 |
| False reject (equivalent answer failed) | 1,648 | 281 | 0 | 0 |

Every false-accept probe also fails the layer it declares. The 0.9.0
fixes: append-only integrity now covers an existing entry's flag and
description (rewording or re-flagging had passed), `open` currency
constraints are enforced (foreign-currency side postings had passed),
and metadata lines, the `txn` keyword, and amounts with other than two
decimals are accepted (each had failed as a structural error). The
0.10.0 fix: initial `open` directives are part of the append-only
check, and their currency constraints bind even if the line is
rewritten (deleting an unused `open` had passed).

Known limits: the audit covers the journal-entry and answer-file
formats; workflow tasks (Dynamic only) are not yet probed. Probes test
the grader against the expectation, not the expectation against
accounting truth — that remains the accounting review in
[TO_REVIEW.md](../TO_REVIEW.md). Beancount features outside the
[ledger subset](#ledger-subset) remain structural errors by design.

## Failure handling

If the grader crashes, `tests/test.sh` leaves `reward.txt = -1`
(infrastructure sentinel, as in DeepSWE) instead of a score — such
trials must be retried/regraded, never counted as agent failures.
