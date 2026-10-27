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
- Net periodic pension cost = service cost + interest cost -
  expected return on plan assets + amortization amounts. The
  amortization of prior losses is reclassified OUT OF accumulated
  other comprehensive income (credit `Equity:AccumulatedOther-
  ComprehensiveIncome`); it does not pass through the pension
  liability. Service cost, interest cost, expected return, and
  the contribution do. Employer cash contributions are funding,
  not expense (credit bank for the full contribution).
