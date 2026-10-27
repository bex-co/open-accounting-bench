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
- Share capital is credited at par value; amounts received above par
  are additional paid-in capital.
- A SMALL stock dividend (under 20-25% of shares outstanding) is
  capitalized at the market value of the shares issued: debit
  retained earnings at market, credit common stock at par and
  additional paid-in capital for the excess.
