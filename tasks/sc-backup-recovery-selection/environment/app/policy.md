# Backup types (applies to this task)

- Full backup: everything. INCREMENTAL: only what changed since the
  LAST backup of any type — restoring needs the full backup plus
  EVERY incremental since, IN ORDER; a missing or unreadable
  incremental breaks the chain and nothing after it can be
  recovered from that chain.
- DIFFERENTIAL: everything changed since the last FULL backup —
  restoring needs only the full backup and the LATEST differential.
