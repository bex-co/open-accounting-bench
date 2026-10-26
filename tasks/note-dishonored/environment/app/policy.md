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
- A dishonored note is transferred back to accounts receivable at
  its maturity value (principal plus all interest to maturity).
  Interest for the current month is recognized as interest income;
  interest accrued in earlier months clears the interest receivable.
  Interest uses a 12-month year (monthly = principal x rate / 12).
