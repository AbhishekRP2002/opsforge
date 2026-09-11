# AGENTS.md


## Implementation Philosophy

* **Functional & Composable:** Prioritize pure functions, explicit inputs/outputs, and composable pipelines. Keep state mutations isolated and local.
* **Radical Code Minimalism:** Minimize total lines of code while delivering 100% of functional requirements.
* **YAGNI Over Speculation:** Abstractions must solve real, present duplication or complexity—never anticipated future needs.
* **Semantic Milestones:** For every logically isolated change or milestone, run the test suite and ask for manual review first and then create a conventional semantic commit (`feat:`, `fix:`, `refactor:`, `test:`).
    * Do not commit without manual review or unless explicitly mentioned to do so.

---

## Error Handling & Failure Propagation

Silent failure modes destroy debuggability and poison RL agent reward gradients.

* **No Catch Without Recovery:** Never write `try/catch` blocks unless the `catch` contains explicit, actionable fallback logic.
* **Banned Anti-Patterns:**
* Empty catch blocks.
* Generic fallbacks (e.g., returning `null`, `[]`, or `false` on error).
* "Log-and-continue" patterns that hide failures.


* **Crash Fast:** If you cannot deterministically recover from an exception, let it bubble up. A raw stack trace is strictly superior to simulated, corrupted stability.

---

## Test Discipline & Reward Integrity

The test runner is your environment's ground-truth oracle. Never tamper with assertions to achieve a passing state.

* **Presumption of Guilt:** If a test fails, **the production code is defective until proven otherwise**.
* **Zero Test Weakening:** Under no circumstances should you broaden matchers, remove checks, lower numeric thresholds, or add skip flags (`@pytest.mark.skip`, `it.skip`, `xfail`) to make a failing test turn green.
* **Defective Test Protocol:** If an existing test case is factually incorrect due to a requirement change:
1. Do not touch the test immediately.
2. Explain precisely why the assertion is invalid.
3. Propose the replacement assertion and obtain explicit user consent before editing.


* **Frantic Testing:** Write isolated, deterministic unit and integration tests for every new codepath before declaring completion.

---

## Epistemic Sourcing & External Tools

* **Temporal Calibration:** For queries depending on recency ("current", "latest", "as of now"), run `date -Is` first to establish temporal ground truth.
* **Docs Lookup (Context7 MCP):** When querying library or API specifications, query Context7 with slash syntax (e.g., `/supabase/supabase`) pinned to the target version. Fetch only targeted snippets; do not dump whole namespaces.
* **Web Search:** Prefer web search for latest SOTA implementation practices, verified breaking changes, recent API advisories, or missing vendor documentation. Prefer primary sources (official changelogs, release notes).
* **Epistemic Honesty:** If an API endpoint or parameter signature cannot be confirmed via local packages or official documentation, label it explicitly as `UNCONFIRMED`. Never fabricate signatures.
* **Source Fidelity:** When processing reference documents (PDFs, specifications, CSVs), read the complete text first. Any non-literal translation must be explicitly labeled as a paraphrase.

---


### Logging Rules

* **Format:** Every entry must have an ISO timestamp (`YYYY-MM-DDTHH:MM:SSZ`) and provenance tag: `[USER]`, `[CODE]`, `[TOOL]`, or `[ASSUMPTION]`.
* **Anti-Drift / Anti-Bloat:** Write factual, bulleted summaries only. Never paste raw tool outputs or conversational chat history.
* **Compression:** When any section exceeds ~20 lines, summarize older entries into a consolidated `[MILESTONE]` entry.
* **Immutability:** Do not silently rewrite past decisions. If a decision changes, log a new entry that explicitly supersedes the prior one.

---

## 7. Definition of Done (DoD)

A task is officially complete only when all of the following verification steps are satisfied:

1. **Implementation:** The code is written following minimal, functional patterns.
2. **Tool Verification:**
* Build compiles cleanly without warnings.
* Typechecker passes (`tsc`, `mypy`, or equivalent) with zero type errors.
* Linter and formatter pass without manual overrides.
* Full relevant test suite passes deterministically.

3. **Documentation:** Documentation updated for all affected public APIs or environment configs.

4. **Impact Summary:** Provide a concise explanation of what was changed, why it was changed, and an explicit list of any follow-ups or deferred work.


- **Prioritise user instructions over the AGENTS.md instructions in case there's any conflict**
- **Be precise, to the point and clear in your responses and help the user understand with simple examples wherever required so that the engineer can take pragmatic choices**

#### ALL THE **relevant documents** should be created inside **docs/internal** or **docs/superpowers**. Outside this the codebase should not be polluted with docs here and there.
