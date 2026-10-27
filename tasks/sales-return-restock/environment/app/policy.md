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
- Perpetual inventory: every sale records revenue at the selling
  price and cost of goods sold at unit cost in the same period.
- Sales returns are recorded in the contra-revenue account
  `Income:SalesReturnsAndAllowances` at the selling price
  (debit), never netted directly against sales revenue;
  restocked goods return to inventory at unit cost with the
  offset to cost of goods sold.
