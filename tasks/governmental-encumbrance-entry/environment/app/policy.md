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
- Governmental budgetary accounting: issuing a purchase order
  debits encumbrances and credits budgetary fund balance assigned
  for the full estimated amount. On a (partial) receipt, reverse
  the ORIGINAL estimated encumbrance for the goods received only,
  and record the expenditure and payable at the actual invoice;
  the undelivered balance stays encumbered.
