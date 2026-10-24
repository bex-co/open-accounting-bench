# Accounting policy (applies to this task)

- Reporting currency: USD. Reporting period: January 2026.
- Append-only ledger: never edit or delete existing transactions in
  `/app/ledger.beancount`. Record new or correcting entries as new
  transactions so the audit trail is preserved.
- Use only accounts listed in `/app/chart_of_accounts.md`. Do not open
  new accounts.
- Consumable supplies and services consumed in the period are expenses.
  Only items with a useful life over one year are capitalized as assets.
- Every transaction must balance (debits equal credits) and be dated
  within the reporting period unless the task states otherwise.
- Equipment is depreciated straight-line per month: (cost - residual)
  / useful life in months. A full month's depreciation is charged in
  the month of acquisition and in the month of disposal.
- On disposal, remove the asset's cost and accumulated depreciation;
  the difference between proceeds and carrying amount is a gain or
  loss on disposal.
