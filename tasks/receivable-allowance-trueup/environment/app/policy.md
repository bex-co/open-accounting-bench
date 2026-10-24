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
- Receivables are carried net of an allowance for doubtful accounts.
  At month-end: first write off invoices approved as uncollectible,
  then adjust the allowance so its balance equals the required
  allowance: the loss rate for each aging bucket times the bucket's
  remaining invoices (Current 1%, 1-30 days 3%, 31-90 days 10%,
  over 90 days 40%), summed. The adjustment is bad-debt expense.
