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
- Cash-flow hedge (IFRS 9): the effective portion recognized in
  other comprehensive income is the LOWER of (a) the cumulative
  gain or loss on the hedging instrument and (b) the cumulative
  change in the present value of the hedged forecast cash flows.
  Any excess gain on the instrument is ineffectiveness,
  recognized immediately in profit or loss.
