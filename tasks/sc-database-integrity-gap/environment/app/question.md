# Question — database integrity gap

Schema finding: **ORDERS has a primary key and a declared foreign key to CUSTOMERS; the optional discount_code column is allowed to be NULL when no promotion applies.**

Using `/app/policy.md`, classify the finding. Select exactly one option.

- A. Referential-integrity violation
- B. Normalization violation (repeating group)
- C. Entity-integrity violation
- D. No integrity violation

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{"final_answer": "A", "confidence": 80}
```

`confidence` is your self-assessed probability (0-100) that the answer
is fully correct.
