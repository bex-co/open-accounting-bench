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
- Inventory uses a perpetual FIFO system. Sales are already recorded;
  cost of sales has not been posted for January.
- At month-end inventory is measured at the lower of FIFO cost and net
  realizable value (estimated selling price less costs to sell), item
  by item; any write-down goes to `Expenses:InventoryWriteDown`.
