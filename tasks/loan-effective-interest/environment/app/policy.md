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
- Borrowings are measured at amortized cost using the effective
  interest method: monthly interest expense = carrying amount at the
  start of the month x the effective monthly rate, rounded to the
  cent. Coupon interest due but unpaid is accrued in
  `Liabilities:InterestPayable`; the difference adjusts the loan's
  carrying amount.
