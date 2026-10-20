---
name: dont-code-but-answer
description: Answer or investigate a question without implementing changes. Use when the user invokes dont-code-but-answer or explicitly asks for explanation, diagnosis, or advice without coding or editing files.
metadata: {"internal": true}
---

# Don't Code, But Answer

Treat the accompanying request as a question to answer, even if it describes a bug, feature, or potential implementation. Complete the analysis and provide the answer without carrying out changes.

- Use read-only inspection of relevant files, logs, git history, or documentation when needed to ground the answer. Do not assume that answering prohibits investigation.
- Do not create, edit, or delete files; apply patches; install dependencies; run formatters or builds; commit or push; or mutate external systems. Avoid commands that write caches or generated artifacts.
- Explain the findings, reasoning, tradeoffs, or recommended approach at the level the question needs. Clearly distinguish verified facts from assumptions and anything that could not be checked through read-only inspection.
- Include illustrative code snippets or suggested diffs in the response only when requested or necessary to explain the answer; never apply them.
- Finish with the substantive answer. Do not ask for permission to implement or automatically continue into coding.

Apply this constraint to the accompanying request and its follow-up discussion. If the user later explicitly asks for implementation, follow that new instruction.
