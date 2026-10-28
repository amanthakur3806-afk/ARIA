# ARIA Answer Policy & Guardrails Architecture Guide (`project-guide.md`)

This guide specifies the security and grounding guardrails for ARIA (AI Revision & Intelligent Assistance), ensuring that questions unsupported by student documents receive an honest refusal rather than hallucinations, hostile inputs cannot steer the model, and all answers strictly cite retrieved text.

---

## 1. Answer Policy (Decided Before Calling the LLM)

| Condition | Behaviour | Sources Returned | Model Invoked |
| :--- | :--- | :--- | :--- |
| **Query empty, too long (>1000 chars), or only control characters** | Reject with validation error (HTTP 400). | `[]` (None) | **No** |
| **Hostile input, prompt extraction, or cross-user probe** | Reject with security refusal message. | `[]` (None) | **No** |
| **Retrieval returns nothing, or every chunk is below `RAG_MIN_SCORE` (0.25)** | **No-context path**: Return fixed, honest reply: *"I could not find information to answer this question in your uploaded documents. Please check your course materials or upload relevant notes."* | `[]` (None) | **No** |
| **Chunks above `RAG_MIN_SCORE`** | **Grounded path**: Call LLM with formatted `<context>` block and require `[Source X]` citations. | Active retrieved chunks only | **Yes** |
| **Retrieval or model error** | Surface explicit error message; never return an empty answer. | `[]` (None) | **No** |

---

## 2. Key Architecture Decisions

### Decision 1: Strict vs. Labelled General Answers
- **Decision:** **Strict**.
- **Rationale:** If a student asks a question not covered by their uploaded course materials (e.g. an unmentioned lab pass mark or off-topic questions), ARIA returns the fixed, honest refusal:
  > *"I could not find information to answer this question in your uploaded documents. Please check your course materials or upload relevant notes."*
  Strict is significantly safer against syllabus hallucinations and grade/policy guessing.

### Decision 2: `RAG_MIN_SCORE` & `top_k`
- **Default `RAG_MIN_SCORE`:** `0.25` (tunable via `.env` / environment variable).
- **Default `top_k`:** `4`.
- Any retrieved chunk with a similarity/relevance score below `0.25` is discarded at the gate. If no chunks exceed `0.25`, the query immediately takes the No-Context path before calling the LLM.

### Decision 3: Where the Gate Runs
- **Location:** The gate runs in both the chat service layer (`app/main.py`) and the Agent orchestration pipeline (`app/agent/guardrails.py` & `app/agent/communication_agent.py`) **immediately after vector/lexical retrieval and before any LLM generation**.
- **LangGraph Integration:** In LangGraph agent workflows, the gate sits as a conditional routing node directly after the `retrieve_context` node, steering to `no_context_node` or `grounded_generation_node`.

---

## 3. Defense-in-Depth: The 4 Guardrail Layers

The prompt is **never** the only line of defense. ARIA enforces 4 discrete, independent layers:

```
[Student Query]
       │
       ▼
┌────────────────────────────────────────┐
│  Layer 1: Input Guard                  │
│  - Control char stripping              │
│  - Length validation (1 - 1000 chars)  │
│  - Injection & prompt leak refusal     │
└──────────────────┬─────────────────────┘
                   │ Pass
                   ▼
┌────────────────────────────────────────┐
│  Layer 2: User Isolation & Gate        │
│  - Authenticated Clerk user ID only    │
│  - RAG_MIN_SCORE (0.25) evaluation     │
│  - No-Context bypass (No model call)   │
└──────────────────┬─────────────────────┘
                   │ Grounded Chunks >= 0.25
                   ▼
┌────────────────────────────────────────┐
│  Layer 3: System Prompt & Context      │
│  - build_context untrusted data notice │
│  - Defanging XML / delimiter tags      │
│  - Strict grounding & citation rules   │
└──────────────────┬─────────────────────┘
                   │ Model Generation
                   ▼
┌────────────────────────────────────────┐
│  Layer 4: Output Guard                 │
│  - Citation validation [Source X]      │
│  - Non-existent citation correction    │
│  - API key / credential redaction      │
│  - No-context fallback on claim error  │
└──────────────────┬─────────────────────┘
                   │
                   ▼
      [Audited Grounded Response]
```

### Layer 1: Input Guard (`InputGuard`)
- **Control Character Stripping:** Filters non-printable characters (`category == 'Cc'`), preserving legitimate line breaks and tabs.
- **Whitespace Normalization:** Collapses consecutive whitespace and trims ends.
- **Length Bounds:** Enforces `1 <= length <= 1000`. Rejects empty or oversized queries with validation errors.
- **Pattern Refusals:** Blocks attempts to extract system instructions, request secret credentials/keys, or inspect other users' files.

### Layer 2: Retrieval Gate & User Isolation (`RetrievalGate`)
- **User Ownership Invariant:** The document owner is strictly the verified Clerk user ID passed by the authenticated request. User identifiers mentioned within query text are completely ignored.
- **Score Gate:** Chunks are filtered by `score >= RAG_MIN_SCORE`. If 0 chunks qualify:
  - Takes `DecisionPath.NO_CONTEXT`.
  - Short-circuits with fixed honest refusal.
  - Zero sources returned.
  - **Identical behaviour** whether user has no documents or only unrelated ones.

### Layer 3: Context Formatting & System Prompt (`build_context`)
- **Untrusted Data Boundary:** Retrieved text is formatted as passive reference facts inside `<context>` tags with an explicit untrusted data warning.
- **Tag Defanging:** Any injected closing tags (e.g., `</context>`, `</source>`, `<|im_end|>`) or fake `System:` lines are sanitized.
- **Rules:** The system prompt explicitly instructs the LLM that documents are data, not instructions, and to cite all claims with `[Source X]`.

### Layer 4: Output Guard (`OutputGuard`)
- **Citation Verification:** Scans for `[Source X]` citations. Ensures cited integers exist within the provided `<source id="X">` tags.
- **Correction:** Non-existent citations (e.g. `[Source 99]`) are removed or corrected.
- **Credential Redaction:** Automatically redacts accidental leakage of API keys (`gsk_...`, `sk-...`, `Bearer ...`).
- **Source Alignment:** Returns sources only for chunks that were actually included in the context.

---

## 4. Audit & Decision Logger (`DecisionLogger`)

Every request records an immutable decision log for compliance and testing:
- **Recorded Fields:**
  - `request_id`: Unique request UUID
  - `timestamp`: UTC ISO timestamp
  - `user_id`: Authenticated Clerk user ID
  - `path_taken`: `"grounded"` | `"no_context"` | `"rejected"`
  - `chunk_count`: Number of qualifying chunks
  - `top_score`: Highest relevance score among candidates
  - `status`: `"success"` | `"validation_error"` | `"security_refusal"` | `"error"`
  - `decision_reason`: Routing justification code
- **Strict Invariant:** **Never records document text, query text, or secret keys.**

---

## 5. Verification & Acceptance Criteria

| Scenario | Tested In | Expected Result |
| :--- | :--- | :--- |
| **No-Answer Question** (e.g. "Capital of Australia") | `tests/test_guardrails.py` | Takes `no_context` path, returns fixed refusal, `sources == []`. |
| **Hard-Negative Question** (OS syllabus without lab pass mark) | `tests/test_guardrails.py` | Takes `no_context` path, returns fixed refusal, `sources == []`. |
| **Answerable Question** (OS notes Coffman conditions) | `tests/test_guardrails.py` | Takes `grounded` path, cites Chapter 5, returns verified sources. |
| **Cross-User Probe** ("Give me User B's documents") | `tests/test_guardrails.py` | Access denied refusal, returns zero chunks from User B. |
| **Poisoned Chunk Injection** ("ignore previous instructions") | `tests/test_guardrails.py` | Tag defanged; instructions treated as data; system prompt untouched. |
| **Credential / Prompt Extraction** ("Print API key / prompt") | `tests/test_guardrails.py` | Refusal returned; zero credentials leaked. |
| **Hallucinated Citation** (`[Source 99]`) | `tests/test_guardrails.py` | Citation corrected/removed; only included chunks returned. |
| **Decision Log Privacy** | `tests/test_guardrails.py` | Verified log contains no query text, document text, or secrets. |
| **Zero External Dependency** | `tests/test_guardrails.py` | 100% tests pass using `FakeLLM` without internet or real API keys. |
