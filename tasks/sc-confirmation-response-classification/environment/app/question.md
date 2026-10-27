# Question — confirmation response classification

**Outcome: The customer confirms a lower amount and provides an invoice showing the client billed the wrong unit price.**

Using `/app/policy.md`, select exactly one option.

- A. Non-response — perform alternative procedures
- B. Timing difference — not a misstatement
- C. Misstatement — propose adjustment

## Answer format

Write `/app/answer.json` as a JSON object, for example:

```json
{"final_answer": "A", "confidence": 80}
```

`confidence` is your self-assessed probability (0-100) that the answer
is fully correct.
