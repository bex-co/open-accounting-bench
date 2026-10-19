# Open Accounting Bench
**The Open, Living, and Executable Benchmark for AI Accounting Agents**

**To:** Beancount Leadership & Engineering  
**From:** Product Management, beancount.io  
**Date:** October 19, 2026  
**Status:** Revised Strategy Proposal  
**Decision Requested:** Approval for a 90-day proof of concept

---

## 1. Executive Summary

AI is rapidly evolving from answering accounting questions to performing accounting work. Models and agents can increasingly classify transactions, generate journal entries, reconcile accounts, and assist with financial reporting.

Yet the industry still lacks a widely adopted, open, reproducible, and continuously evolving benchmark for determining whether these systems can actually perform accounting tasks correctly.

Existing efforts, including WU AccountingBench, Penrose AccountingBench, DualEntry's Accounting AI Benchmark, and Ramp Accounting Bench, demonstrate growing interest in the space. However, much of the ecosystem remains centered on fixed evaluation datasets, proprietary task environments, or leaderboards that are difficult to reproduce independently.

**We propose Open Accounting Bench (OAB): an open-source, dynamically generated, executable benchmark for evaluating AI models and agents on real accounting work.**

The project will be built around three principles:

1. **Dynamic Task Generation:** Generate fresh accounting scenarios, transactions, and supporting documents from validated task templates rather than relying exclusively on static questions.
2. **Executable Verification:** Evaluate accounting correctness through deterministic rules, transaction-level semantics, and financial statement reconciliation, minimizing dependence on subjective LLM judges.
3. **Operational Evaluation:** Measure whether agents can produce correct accounting outcomes, not merely answer questions about accounting concepts.

Accounting has a distinctive advantage as an AI evaluation domain: many of its underlying rules are public, formalized, and machine-checkable. Unlike benchmarks that depend on memorizing fixed examination answers, accounting benchmarks can test whether an AI system applies known principles correctly to new economic situations.

Our ambition is to establish for accounting what SWE-bench helped establish for software engineering: a common, reproducible standard for measuring real-world agent capabilities.

**The goal is not to benchmark Beancount. The goal is to make beancount.io a foundational contributor to the emerging field of AI accounting evaluation.**

## 2. Why Accounting Is Particularly Well-Suited for Open Benchmarking

### Accounting evaluates the application of rules, not their memorization

Traditional examination-style benchmarks often test whether a model knows a particular fact, concept, or solution.

Accounting offers a different and potentially more useful evaluation paradigm.

The underlying principles of double-entry bookkeeping, financial reporting, and major accounting standards such as GAAP and IFRS are publicly documented. While professional judgments and regulatory interpretations remain complex, many fundamental accounting operations follow explicit rules.

The challenge is not remembering that debits must equal credits. It is determining which accounts should be debited and credited for a particular transaction, in the correct amounts, during the correct reporting period, under the applicable accounting policies.

For example, an AI system may correctly explain the difference between an asset and an expense while incorrectly capitalizing an ordinary operating expense.

An examination question might never expose this problem. An executable accounting task can.

This distinction is central to Open Accounting Bench:

**We should benchmark whether AI can apply accounting rules to real transactions, not whether it can recite those rules.**

### Accounting provides machine-verifiable constraints

A significant portion of accounting correctness can be assessed programmatically.

Examples include:

- Debits and credits balancing at the transaction level.
- Accounting equations holding across the ledger.
- Account balances rolling forward correctly.
- Financial statements reconciling to the underlying ledger.
- Net income, equity changes, and cash movements reconciling under the applicable reporting model.
- Bank reconciliations matching external statements.
- Journal entries using valid accounts, amounts, and reporting periods.

The open-source [accounting-bench](https://github.com/mariozupan/accounting-bench) project illustrates this approach. Its published evaluation design includes account-opening validity, double-entry validity, balance-sheet validity, profit-and-loss validity, cash-flow validity, and account-mapping accuracy.

This is a useful technical precedent, although the project does not by itself establish a comprehensive, independently validated accounting benchmark.

Most importantly, structural validation is only the first step.

**A balanced ledger is not necessarily a correct ledger.**

An agent could record an operating expense as a fixed asset, or recognize revenue in the wrong period, while still satisfying the accounting equation.

Consequently, Open Accounting Bench must go beyond structural correctness to evaluate whether transactions represent the underlying economic events accurately.

### Accounting scenarios can be generated programmatically

Unlike fixed examination questions, many accounting tasks can be created from reusable scenario templates.

Consider a basic invoice-processing task.

A generator can vary:

- Transaction amounts and currencies.
- Customer and vendor identities.
- Payment timing and partial settlements.
- Chart-of-accounts structure.
- Applicable accounting policies.
- Reporting periods and cutoff dates.
- Discounts, refunds, fees, and credit notes.
- Supporting documents and transaction histories.

Each generated instance can have a programmatically derived expected accounting outcome.

A single well-validated task template could produce thousands of distinct evaluation instances.

This enables a fundamentally different approach to open benchmarking.

Instead of protecting a fixed collection of questions, we can publish the task-generation framework and continuously evaluate models on newly generated scenarios.

However, randomization alone does not eliminate benchmark contamination. Models may still memorize task structures or overfit to a known generator.

The benchmark must therefore vary economic scenarios, causal relationships, document structures, and task compositions—not merely replace numbers or company names.

Generated tasks must also be checked against independent accounting oracles and expert-reviewed templates to ensure that they are meaningful and unambiguous.

## 3. The Research Gap: Knowing Accounting Is Not Doing Accounting

Recent research highlights a substantial gap between accounting knowledge and accounting execution.

In *Evaluating Financial Literacy of Large Language Models through Domain Specific Languages for Plain Text Accounting* (Figueroa Rosero et al., FinNLP 2025), researchers tested whether five approximately 7B-parameter open-weight models could generate financially meaningful scenarios and translate them into Beancount transactions.

The study found that only **7 of 300 expert-evaluated scenario–transaction pairs (2.3%) were fully correct end to end**.

The study also identified accounting logic and semantic correctness as major sources of failure, including balance errors and references to invalid accounts.

These findings should not be generalized to current frontier models: the experiment used a limited selection of relatively small models and a specific generation protocol.

Nevertheless, the study demonstrates an important distinction.

A model may produce syntactically valid accounting records while failing to represent the intended economic transaction correctly.

This is precisely the kind of failure that a benchmark focused on conceptual knowledge may overlook.

It also suggests why evaluating only the generated output format—or relying solely on an LLM judge—would be insufficient.

The [CA-Ben research benchmark](https://arxiv.org/html/2506.21031v1), built around Chartered Accountancy examination materials, illustrates a complementary evaluation direction: assessing domain knowledge and examination-style reasoning.

Knowledge benchmarks remain useful, but they answer a different question.

**The question for Open Accounting Bench is not "Does the model understand accounting?" It is "Can the agent produce a correct, auditable accounting outcome?"**

That distinction should define our product positioning and technical architecture.

## 4. Product Vision

**Open Accounting Bench is an open evaluation infrastructure for measuring the operational accounting capabilities of AI systems.**

Its primary research question is:

*Can an AI agent correctly transform financial evidence into a valid, economically accurate, and auditable accounting state?*

We propose evaluating three complementary capabilities.

### Accounting Knowledge

Can the model interpret accounting concepts, policies, and business transactions?

This remains useful as a diagnostic category, but it should not dominate the benchmark.

### Accounting Execution

Can the agent create, correct, and reconcile accounting records to achieve a specified business outcome?

This should be the primary evaluation dimension.

### Accounting Reliability

Can the agent consistently perform accounting work without introducing errors, violating constraints, or making unauthorized changes?

The benchmark should measure repeated success, recovery from errors, correct use of evidence, and the ability to recognize when a task requires clarification.

Our long-term product vision is a **living collection of executable accounting tasks**, supported by openly available generators, verifiers, reproducible environments, and continuously updated evaluation results.

## 5. Core Design: Dynamic Task Generation

Dynamic task generation should be a first-class architectural component, not a future enhancement.

### Task Families Instead of a Fixed Question Bank

Each task family describes a class of accounting problems and includes:

- A business scenario specification.
- An initial ledger state.
- Supporting source documents.
- An applicable accounting policy.
- A parameterized scenario generator.
- A reference accounting outcome or verification oracle.
- Deterministic verification rules.
- Difficulty and jurisdiction metadata.

For example, a bank reconciliation generator might construct a business with an existing ledger, a bank statement, outstanding payments, bank fees, duplicate imports, and timing differences.

The agent is instructed to reconcile the accounts.

The evaluation engine checks whether the agent correctly resolves the discrepancies without creating duplicate transactions, losing source information, or changing unrelated records.

The same generator can create many related but distinct tasks.

### Reproducibility and Freshness

Dynamic generation must not undermine scientific reproducibility.

Every generated instance should be associated with a deterministic seed, generator version, accounting policy version, and complete environment snapshot.

This allows a specific run to be reproduced even when the broader benchmark continually generates new tasks.

We propose three evaluation tracks:

| Track | Purpose |
|---|---|
| Stable Benchmark | Frozen, versioned instances for historical comparison |
| Dynamic Benchmark | Fresh instances generated from validated task families |
| Holdout Evaluation | Additional task templates or instances for independent generalization testing |

The stable track provides comparability. The dynamic track measures performance on changing data. The holdout track helps detect overfitting to public examples and known generator structures.

The generation code and public evaluation protocols should be open. Where a protected holdout is necessary, its governance and evaluation conditions must be transparent.

The goal is not to claim that contamination becomes impossible.

It is to make memorization less useful and generalizable accounting competence more valuable.

## 6. Core Design: Executable Accounting Verification

A key differentiator of Open Accounting Bench will be its verification system.

Rather than relying primarily on matching answers to reference text or having another LLM assign a score, we should use a layered verification model.

| Verification Layer | What It Tests |
|---|---|
| 1. Syntax and Structure | Valid ledger format, valid accounts, balanced entries |
| 2. Accounting Semantics | Correct account classification, debit/credit direction, amounts, dates |
| 3. Economic Consistency | Entries correctly reflect invoices, payments, contracts, and other evidence |
| 4. Financial Reconciliation | Account balances, statement relationships, and period changes reconcile |
| 5. Operational Integrity | No unauthorized, duplicate, missing, or unrelated modifications |

### Why this matters

An entry may satisfy every basic double-entry constraint while remaining economically incorrect.

Consider a $5,000 ordinary operating expense paid in cash.

An agent might debit an asset account rather than an expense account and credit cash for $5,000.

The entry balances perfectly.

A structural verifier would accept the double-entry mechanics. A semantic verifier should reject the classification because the specified economic event and accounting policy require expense recognition.

Similarly, the relationship between the income statement, balance sheet, and cash-flow statement must be tested through the relevant accounting reconciliation rules, not reduced to one simplistic equation.

For a well-specified generated task, the oracle can check expected account movements, source-document relationships, reporting periods, and downstream statement effects.

### Handling Multiple Correct Answers

Accounting tasks do not always have a single valid journal-entry representation.

Equivalent transactions may use different account hierarchies, different levels of detail, or permissible alternative treatments.

Scoring should therefore evaluate whether the resulting ledger state satisfies the intended economic and accounting constraints, rather than requiring an exact textual match against one reference journal entry.

Where professional judgment is genuinely required, we should document acceptable alternatives, provide explicit accounting assumptions, or use expert-reviewed rubric-based assessment.

For the initial benchmark, we should prioritize tasks with unambiguous, programmatically verifiable outcomes.

**Our design principle is deterministic verification where possible, expert judgment where necessary, and transparent scoring throughout.**

## 7. Why Beancount Is a Strong Foundation

Beancount has several characteristics that make it particularly suitable as a reference engine for Open Accounting Bench.

It represents transactions in structured, human-readable plain text. Ledger files can be version-controlled, diffed, reset, and inspected. Accounting data can be processed with reproducible tools rather than requiring access to a proprietary ERP system.

Most importantly, the Beancount ecosystem provides a practical mechanism for validating ledger structure and calculating accounting state.

This gives us a promising foundation for constructing an executable accounting benchmark.

The SWE-bench analogy is useful:

| SWE-bench | Open Accounting Bench |
|---|---|
| Git repository | Accounting ledger and source documents |
| GitHub issue | Accounting task |
| Code patch | Journal entries and ledger modifications |
| Unit tests | Accounting constraints and transaction-level verification |
| Passing test suite | Verified accounting outcome |
| Reproducible repository state | Reproducible ledger state |

There is one crucial distinction: software tests are not automatically complete specifications, and neither are accounting invariants.

A ledger that compiles successfully is analogous to code that compiles successfully. It does not prove that the work is correct.

Beancount should therefore serve as a reference ledger engine within a broader verification architecture, not as the sole definition of correctness.

Open Accounting Bench should also remain implementation-neutral. Participating agents should be able to interact through documented accounting operations or standardized data interfaces without being required to generate Beancount syntax.

This would allow other accounting platforms, research institutions, and agent developers to participate fairly.

## 8. Benchmark Architecture

We propose five technical components.

### A. Task Generator Registry

A version-controlled registry of parameterized accounting task families.

Each generator produces an executable task instance containing the initial ledger, business context, source documents, instructions, expected accounting behavior, and verifier configuration.

Generators should be tested for accounting correctness, diversity, and reproducibility.

### B. Accounting Execution Environment

An isolated environment that provides each agent with identical starting conditions.

The environment should expose appropriate ledger operations, document access, and accounting tools while recording agent actions and final state changes.

We propose using **Harbor** as the initial evaluation harness for task execution, environment isolation, and verifier integration, subject to prototype validation.

### C. Independent Verification Engine

A separate verification layer combining ledger compilation, accounting invariants, scenario-specific reference outcomes, and source-document validation.

It should produce both machine-readable scores and human-readable explanations of failures.

### D. Evaluation Registry and Leaderboards

A public system for publishing reproducible evaluation runs.

Results should record model versions, agent configurations, tool access, dataset or generator versions, random seeds, scoring versions, execution costs, and evaluation timestamps.

We should distinguish model-only performance from tool-using agent performance.

### E. Open Contribution Infrastructure

A public contribution workflow for new task templates, generators, verification rules, accounting standards, and jurisdiction-specific modules.

Community submissions should require unit tests, reference-oracle validation, and appropriate expert review.

## 9. Benchmark Coverage and Global Extensibility

Accounting varies across countries and reporting regimes, but this does not prevent a common evaluation framework.

It means the benchmark must clearly separate general accounting operations from standard-specific and jurisdiction-specific requirements.

We propose three layers:

**Accounting Core:** Double-entry bookkeeping, transaction classification, reconciliation, ledger integrity, and related operational workflows.

**Accounting Standards:** IFRS, US GAAP, and other financial reporting frameworks, with explicitly defined accounting policies.

**Jurisdiction Packs:** Local tax, statutory reporting, and compliance requirements, including their effective dates.

A task should specify the relevant business entity, accounting policies, reporting period, standard, and jurisdiction.

Scores should be reported by capability and regulatory context rather than combining incomparable tasks into an opaque global score.

Our initial release should focus on broadly transferable bookkeeping tasks. Jurisdiction-specific modules should follow once the core verification system is reliable.

## 10. Initial Product Scope: v0.1

We recommend a small but technically rigorous initial release.

Rather than manually authoring 50 unrelated static questions, **v0.1 should prioritize approximately 12–15 validated task generators capable of producing hundreds of reproducible instances.**

The initial scope should cover four task families:

| Task Family | Proposed Generators | Examples |
|---|---:|---|
| Transaction Classification & Journal Entries | 4 | Expenses, revenue, transfers, refunds |
| Bank Reconciliation | 4 | Missing payments, duplicate entries, bank fees, timing differences |
| Adjustments & Corrections | 3 | Accruals, prepayments, incorrect classifications |
| Ledger Integrity & Reporting | 3 | Account roll-forwards, statement reconciliation, error detection |
| **Total** | **14** | |

These numbers are planning targets, not prerequisites for release.

The initial evaluation should combine generated instances with a smaller set of expert-authored adversarial scenarios.

Examples of adversarial scenarios include balanced-but-incorrect entries, misleading document descriptions, ambiguous account names, duplicate source documents, and transactions near reporting-period boundaries.

The release must demonstrate that:

- A third party can generate a task from a published seed.
- Multiple agents can operate on the same initial accounting environment.
- Verification distinguishes structural validity from economic correctness.
- Results can be independently reproduced.
- Fresh task instances can be generated without changing the benchmark specification.

Success should be defined by the quality and reliability of these capabilities, not merely the number of questions in the repository.

## 11. Evaluation Metrics

We should avoid a single headline accuracy metric that hides important differences between task categories or reward structures.

The primary metric should be **Verified Task Completion Rate**: the proportion of accounting tasks completed with all required economic, structural, and operational constraints satisfied.

Supporting metrics should include:

| Metric | Purpose |
|---|---|
| Verified Task Completion | Was the accounting objective fully achieved? |
| Structural Validity | Are ledger structure and accounting invariants satisfied? |
| Semantic Accuracy | Do recorded transactions represent the economic events correctly? |
| Reconciliation Accuracy | Do accounting records reconcile with independent source evidence? |
| Unauthorized Modification Rate | Did the agent introduce unrelated or prohibited changes? |
| Reliability | Does the agent succeed consistently across repeated trials and generated variations? |
| Cost per Verified Task | How much does a correct outcome cost? |
| Execution Time | How efficiently can the agent complete the workflow? |

Partial scores should be available for diagnosis, but a task should not be considered successfully completed merely because the ledger balances.

The leaderboard should publish the full metric profile and evaluation conditions, including whether an agent had access to a compiler, documentation, feedback loops, or other tools.

## 12. Proposed 90-Day Roadmap

### Days 1–30: Build the Verification Foundation

Implement a minimal Harbor integration and reproducible Beancount environment.

Develop the first three or four task generators and their reference oracles.

Validate basic ledger structure, semantic account mapping, and expected state changes.

Test deliberately incorrect but structurally balanced entries to ensure the verifier catches errors beyond syntax and double-entry compliance.

### Days 31–60: Dynamic Evaluation Pipeline

Expand toward 8–10 validated generators.

Introduce deterministic seeds, generated source documents, task-version tracking, and independent scoring.

Run multiple models and agent configurations on the same task instances.

Measure reliability across generated variations and identify cases where the verifier incorrectly accepts or rejects outcomes.

### Days 61–90: Public Alpha

Target approximately 12–15 reviewed task generators, subject to accounting validation and implementation quality.

Publish an open repository containing the generators, sample datasets, execution configuration, reference oracles, verifier implementations, and reproducible baseline results.

Launch a preliminary leaderboard with clear reporting of structural, semantic, and operational accuracy.

Publish a technical methodology document and invite external researchers and accounting professionals to reproduce the results and contribute new scenarios.

**The first milestone is not a polished leaderboard. It is proving that the community can independently generate, execute, verify, and extend accounting evaluations.**

## 13. Open Governance and Benchmark Integrity

We should design Open Accounting Bench as a neutral evaluation project from the beginning.

The evaluation protocol, reference implementation, task-generation interfaces, and public verifier logic should be available under an appropriate open-source license.

Benchmark releases should be versioned. Historical results must remain tied to their original generator versions and evaluation conditions.

Community contributors should be able to submit new task families, correct reference outcomes, challenge scoring decisions, and report weaknesses in existing verifiers.

A protected evaluation set may be useful for testing generalization, but its purpose and governance should be clearly documented. Public replication must remain possible for the open evaluation tracks.

We should also avoid introducing unnecessary copyright and data-privacy risks by building the core benchmark from original or properly licensed scenarios and synthetic accounting data rather than relying on copied examination papers or confidential financial records.

The benchmark's credibility will depend on its independence.

Beancount.io can provide infrastructure, maintenance, and initial sponsorship, but scoring and participation rules must remain transparent and vendor-neutral.

## 14. Strategic Value for beancount.io

The long-term opportunity is larger than publishing model rankings.

Open Accounting Bench could become foundational infrastructure for the emerging AI accounting ecosystem.

### Establishing Domain Authority

By defining task formats, verification protocols, and accounting reliability metrics, beancount.io can help shape how researchers and AI labs evaluate accounting agents.

### Building an Open Developer Ecosystem

Benchmark users may become contributors to accounting tools, verifiers, data generators, and integrations.

A shared evaluation standard could encourage interoperability across otherwise fragmented accounting agent implementations.

### Improving Our Own Products

The same task generators and verification infrastructure could support internal testing of AI-assisted bookkeeping features, regression testing, and transaction safety checks.

The benchmark would provide an independent mechanism for identifying failure modes before they affect production accounting workflows.

### Creating a Sustainable Technical Advantage

The long-term asset would not be ownership of a static dataset.

It would be the accumulated library of validated accounting scenarios, reference oracles, verification logic, reproducible environments, and trusted evaluation history.

These assets become more useful as community participation increases.

**Our strategic position should be that Open Accounting Bench defines how AI accounting capabilities are evaluated, while beancount.io helps make that evaluation possible.**

## 15. Risks and Mitigations

Several risks require deliberate attention.

**Synthetic-to-real transfer:** Randomly generated accounting tasks may fail to capture messy business workflows. We should progressively introduce realistic source documents, multi-period ledgers, interacting transactions, and expert-authored adversarial cases.

**False confidence from deterministic checks:** Double-entry balance and statement reconciliation do not guarantee correct accounting treatment. We should combine structural checks with semantic transaction-level verification and independent expected outcomes.

**Generator overfitting:** Publicly available generators can still become training targets. We should vary task structures, preserve independent holdouts, and periodically introduce new generator families.

**Ambiguous accounting judgments:** Some treatments depend on policy choices or professional interpretation. Initial tasks should specify assumptions clearly, and judgment-based scenarios should be separately evaluated.

**Regulatory maintenance:** Standards and tax laws change over time. Task metadata and verification logic must explicitly track applicable rules and effective dates.

**Commercial bias:** A benchmark maintained by an accounting product may be perceived as favoring that product. We should use vendor-neutral interfaces, transparent scoring, open contributions, and independent replication.

**Ongoing maintenance:** A living benchmark requires sustained engineering and domain expertise. The initial project should prioritize generator quality and reusable validation infrastructure to keep marginal maintenance costs manageable.

## 16. Recommendation and Decision

We recommend launching Open Accounting Bench as an independent open-source initiative founded and initially maintained by beancount.io.

The first 90 days should validate three hypotheses:

1. **Dynamic Generation:** Can we generate diverse, financially meaningful accounting tasks from reusable, expert-validated templates?
2. **Executable Verification:** Can we automatically detect both structurally invalid and economically incorrect accounting outcomes with sufficient reliability?
3. **Independent Reproduction:** Can external researchers generate, execute, and evaluate the same tasks without depending on beancount.io's proprietary services?

These are the essential foundations.

A leaderboard becomes valuable once those foundations are trusted.

If successful, Open Accounting Bench should expand into longer-running accounting workflows, additional standards and jurisdictions, community-maintained task packs, and continuous evaluation of new AI models and agents.

The broader opportunity is to establish a new standard for measuring AI capabilities in accounting—not through what models can remember, but through what they can demonstrably do.

**Accounting is a particularly promising domain for executable AI evaluation because its rules are formalized, its operations are structured, and many of its outcomes can be verified.**

Open Accounting Bench should turn those properties into a public, reproducible, and continuously improving evaluation system.

*Don't test whether AI knows accounting. Test whether AI can do accounting correctly.*

---

## Selected References

1. [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770) — Reference model for executable, reproducible agent evaluation.
2. [Accounting Benchmark — mariozupan/accounting-bench](https://github.com/mariozupan/accounting-bench) — An open-source example of accounting validation and scoring dimensions.
3. [Evaluating Financial Literacy of Large Language Models through Domain Specific Languages for Plain Text Accounting](https://aclanthology.org/2025.finnlp-1.6/) — Research evaluating LLM generation of Beancount accounting transactions.
4. [LLMFinLiteracy Research Review — Beancount.io](https://beancount.io/bean-labs/research-logs/2026/06/23/llm-beancount-dsl-financial-literacy-benchmark) — Discussion of the gap between valid accounting syntax and economic correctness.
5. [CA-Ben: Large Language Models Acing Chartered Accountancy](https://arxiv.org/html/2506.21031v1) — Example of examination-oriented accounting knowledge evaluation.
6. [Harbor Framework](https://docs.harborframework.com/tasks/overview) — Candidate infrastructure for reproducible task execution and verification.

---

**Project:** Open Accounting Bench  
**Tagline:** The Open, Living, and Executable Benchmark for AI Accounting Agents  
**Founding Sponsor:** beancount.io  
**Reference Ledger Engine:** Beancount  
**Proposed Harness:** Harbor  
**Target:** 90-Day Public Alpha
