# Task families

A family is a validated, parameterized accounting scenario:
`(family, seed, generator_version)` → instruction, initial state,
source documents, policy, expectations, reference solution. Authoring
guide: [CONTRIBUTING.md](../CONTRIBUTING.md) and
[task-family-template.md](task-family-template.md).

Every task carries a four-axis taxonomy (`task.toml [metadata]`,
`manifest.json`; vocabularies in `oab.families.TAXONOMY`):

- `category`: financial-accounting / management-accounting / tax
- `framework`: core / ifrs / us-gaap (jurisdiction packs add values)
- `level`: vocational / university / professional
- `format`: journal-entry / single-choice / multiple-choice / numeric /
  open-text (open-text has no deterministic grader yet)

## Implemented

| Task ID | Family | Format | Framework | Trap |
|---|---|---|---|---|
| `classify-operating-expense` | transaction-classification | journal-entry | core | Capitalize a consumable |
| `bank-recon-missing-fee` | bank-reconciliation | journal-entry | core | Delete duplicate; ignore fee |
| `prepaid-insurance-adjustment` | adjustments-corrections | journal-entry | core | Expense all 12 months |
| `correct-misclassification` | ledger-integrity-reporting | journal-entry | core | Edit history in place |
| `mc-capitalization-treatment` | transaction-classification | multiple-choice | core | Expense-it distractor |

Stable seeds: 101–105 (`STABLE_SEEDS` in `src/oab/families.py`).

## Coverage matrix (category × framework)

Cell values: number of Stable tasks; `planned` cells are roadmap
placeholders tracked as issues, not directories.

| Category | core | ifrs | us-gaap | jurisdiction pack |
|---|---:|---:|---:|---|
| financial-accounting | 5 | planned | planned | planned |
| management-accounting | planned | planned | planned | planned |
| tax | planned | — | — | planned |

Format coverage: journal-entry ×4, multiple-choice ×1;
single-choice grader exists without a committed family; open-text is
deferred (needs a judge design — see [methodology.md](methodology.md)).

## Roadmap to 12–15 generators (memo §10)

| Family | Target generators | Candidate scenarios |
|---|---:|---|
| Transaction classification & journal entries | 4 | + revenue on account, refund/credit note, inter-account transfer |
| Bank reconciliation | 4 | + outstanding check (timing), deposit in transit, partial payment |
| Adjustments & corrections | 3 | + accrued wages, unearned revenue release |
| Ledger integrity & reporting | 3 | + roll-forward break, period-cutoff error |

Plus a small expert-authored adversarial set: balanced-but-wrong
entries, misleading narrations, ambiguous account names, duplicate
documents, period-boundary dates.

## Instance contract

Every generated task must satisfy, before merge:

- Oracle solution scores `reward = 1`; untouched initial state (or a
  missing answer file) scores 0. (`oab validate`, CI.)
- At least one plausible wrong attempt fails on a non-structural
  dimension (trap test under `tests/`).
- Same seed → byte-identical task directory (digest in manifest).
- Instruction states absolute paths and the single output file
  (`/app/ledger.beancount` or `/app/answer.json`); policy in
  `/app/policy.md` removes accounting ambiguity.
