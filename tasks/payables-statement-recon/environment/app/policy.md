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
- Supplier statements are reconciled at month-end. Correct only errors
  in our ledger (unrecorded credit notes, mis-keyed amounts) against
  the purchase account. Timing differences are not errors: purchases
  are recorded when goods are received, and payments we have sent
  may not yet appear on the supplier's statement.
