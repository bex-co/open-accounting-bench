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
- Held-to-maturity securities are measured at amortized cost (effective interest method): monthly interest income = carrying
  amount at the start of the month x the effective monthly rate
  stated in the terms, rounded to the cent. The month's coupon accrual
  (face x coupon rate / 12) is debited to interest receivable;
  the excess of the coupon accrual over interest income amortizes
  the premium (credit the investment). Do not use straight-line
  amortization and do not recompute the effective rate.
