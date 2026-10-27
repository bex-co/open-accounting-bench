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
- When the held-for-sale criteria in the document are met, transfer
  the asset out of equipment/accumulated depreciation into
  `Assets:AssetHeldForSale` and measure it at the LOWER of carrying
  amount and fair value less costs to sell, recognizing any
  write-down in profit or loss.
