# Task families

A family is a validated, parameterized accounting scenario:
`(family, seed, generator_version)` → instruction, initial ledger,
source documents, policy, expectations, reference solution. Authoring
guide: [CONTRIBUTING.md](../CONTRIBUTING.md).

## v0.1 (implemented)

| Task ID | Family | Scenario | Trap |
|---|---|---|---|
| `classify-operating-expense` | transaction-classification | Record a consumables receipt paid from checking | Capitalize as equipment |
| `bank-recon-missing-fee` | bank-reconciliation | Reconcile to statement: duplicate import + missing service charge | Delete the duplicate line; ignore the fee |
| `prepaid-insurance-adjustment` | adjustments-corrections | One month of a 12-month prepayment | Expense all 12 months |
| `correct-misclassification` | ledger-integrity-reporting | Laptop expensed as repairs; capitalize via correcting entry | Edit the original entry in place |

Stable seeds: 101–104 (`STABLE_SEEDS` in `src/oab/families.py`).

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

- Oracle (solution ledger) scores `reward = 1`; untouched initial
  ledger scores 0. (`oab validate`, CI.)
- At least one plausible wrong-but-balanced attempt fails on a
  non-structural layer.
- Same seed → byte-identical task directory (digest in manifest).
- Instruction states paths, output file, append-only rule, and period;
  policy in `/app/policy.md` removes accounting ambiguity.
