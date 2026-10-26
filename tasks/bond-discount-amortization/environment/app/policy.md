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
- Bonds are measured at amortized cost (effective interest method):
  monthly interest expense = carrying amount at the start of the
  month x the effective monthly rate stated in the bond terms,
  rounded to the cent. Coupon accrued for the month (face x coupon
  rate / 12) is credited to interest payable; the difference
  amortizes the discount. Do not recompute the effective rate.
