# Question — backup recovery selection

Scenario: **Schedule: full backup on Sunday, INCREMENTAL backups Monday to Saturday, all media verified. The system fails on Saturday. Which sequence restores through Friday night?**

Using `/app/policy.md`, select exactly one option.

- A. Restore the full backup and the most recent incremental only
- B. Restore the full backup, then the latest differential only
- C. Restore full backup, then incrementals up to the broken link; later changes lost
- D. Restore the full backup, then every incremental in order

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{"final_answer": "A", "confidence": 80}
```

`confidence` is your self-assessed probability (0-100) that the answer
is fully correct.
