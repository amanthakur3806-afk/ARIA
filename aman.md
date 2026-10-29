# ARIA MCP Tools & Agent Integration Guide (`aman.md`)

**Author:** Aman Thakur (Person 3 — MCP & Agent Orchestration)  
**Package Paths:**  
- `Agent/backend/app/mcp/` (FastMCP Server & Study Tools)  
- `Agent/backend/app/agent/` (Communication Agent, RAG Bridge, Logic Validator)  

---

## 1. Executive Summary & Zero-Change Philosophy

This codebase is designed so that **any teammate (Person 1 for Frontend/RAG, Person 2 for DB/Memory, or a FastAPI route handler) can connect to the Agent and Tools immediately without modifying any internal code**.

### Key Architectural Highlights:
1. **Zero-Friction Import**: All tools and the agent are exposed at package roots (`app.mcp` and `app.agent`).
2. **Resilient Fallbacks**: If the Groq Cloud API or internet is unavailable, all tools seamlessly switch to deterministic heuristic engines that guarantee logically sound, non-circular outputs and pass all strict validation rules.
3. **Flexible Signatures**: Helper execution functions accept multiple naming conventions (`query` or `topic`, `count` or `num_cards`, etc.) and `**kwargs` so calling code never breaks on argument naming variations.
4. **FastMCP Standard Compliant**: Built on the Model Context Protocol (`mcp` SDK v2 `MCPServer`), ready for STDIO, SSE, and MCP Inspector visual debugging.

---

## 2. Quick-Start Connection (Copy-Paste)

From any script or service inside `Agent/backend` (or from project root with `sys.path.insert(0, "Agent/backend")`):

```python
import sys
from pathlib import Path

# 1. Ensure Agent/backend is in sys.path
backend_path = Path(__file__).resolve().parent / "Agent" / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# 2. One-line imports
from app.agent import CommunicationAgent
from app.mcp import (
    execute_planner_tool,
    execute_flashcard_tool,
    execute_question_generator_tool,
    execute_flowchart_tool,
)

# 3. Test Agent
agent = CommunicationAgent()
response = agent.handle_message("Explain Virtual Memory and give me a study plan")
print(f"Intent: {response.intent}")
print(f"Content: {response.content[:150]}...")

# 4. Test Direct Tool Call
plan = execute_planner_tool(query="Deadlock Prevention", target_duration_minutes=30)
print(f"Plan status: {plan['status']} | Phases: {len(plan['study_plan']['phases'])}")
```

---

## 3. Communication Agent (`app.agent.CommunicationAgent`)

The primary conversational orchestrator for student interactions.

### How it works:
- **Multilingual Intent Router**: Detects language (`en`, `hi-en` / Hinglish, `es`, `fr`) and student intent (`explain_and_plan`, `generate_flashcards`, `generate_quiz`, `generate_flowchart`, `full_workflow`).
- **Pedagogical LLM Synthesis**: Powered by Groq Cloud (`qwen/qwen3.8-27b`). Explains concepts with warmth, real-world analogies, and pro-tips.
- **FastMCP Tool Bridge**: Automatically invokes the required tool(s) when the student requests flashcards, quizzes, study plans, or architecture diagrams.
- **Academic Logic Engine**: Validates prerequisite sequences, flashcard non-circularity, and distractor exclusivity.

### Code Connection:
```python
from app.agent import CommunicationAgent

agent = CommunicationAgent()

# Basic student prompt
response = agent.handle_message("Process aur thread ke beech kya difference hai?")

# Response fields available to frontend / API:
print(response.content)       # The full markdown pedagogical response
print(response.intent)        # 'explain_and_plan'
print(response.language)      # 'hi-en'
print(response.tone)          # 'pedagogical'
print(response.latency_ms)    # SLA execution time in ms
print(response.sources)       # Citations: [{document_id, chunk_id, excerpt, page}]
print(response.actions)       # Executed MCP tools: [{tool_name, status, summary, result}]
```

### Ingesting Course Notes into Agent (Person 1 handoff):
```python
# Pass raw document text from PDF / markdown uploads:
chunks = agent.rag.ingest_document(
    document_id="doc_os_unit_1",
    text="Virtual memory decouples logical address space from physical memory...",
    title="OS Lecture Notes Unit 1"
)
# Future user queries will now automatically retrieve and cite these chunks!
```

---

## 4. The 4 FastMCP Tools (Detailed Guide & Code Connection)

### Tool 1: `planner_tool` (`app.mcp.tools.plannertool`)

#### What it does:
Generates systematic concept breakdowns, tone-adapted direct answers, real-world analogies, and time-blocked study/revision plans divided into distinct logical phases (Foundation, Deep Dive, Application & Quiz).

#### Function Signature:
```python
execute_planner_tool(
    query: str = "",                     # Student prompt or topic (can also pass topic="...")
    tone: Optional[str] = None,          # "pedagogical", "concise", "socratic", "motivational", "exam_prep"
    context_chunks: Optional[List[str]] = None, # Relevant course notes
    target_duration_minutes: int = 45    # Target study time in minutes
) -> Dict[str, Any]
```

#### Code Connection Example:
```python
from app.mcp import execute_planner_tool

result = execute_planner_tool(
    topic="Deadlock Prevention and Banker's Algorithm",
    tone="exam_prep",
    target_duration_minutes=45
)

# Accessing Results:
print(result["status"])                  # "success"
print(result["direct_answer"])           # High-yield core answer
print(result["analogy_or_intuition"])    # Real-world intuitive analogy
print(result["study_plan"]["topic"])     # "Deadlock Prevention"
print(result["study_plan"]["total_duration_minutes"]) # 45

for phase in result["study_plan"]["phases"]:
    print(f"Phase {phase['phase_number']}: {phase['phase_name']} ({phase['duration_minutes']} min)")
    print(f"  Focus: {phase['key_focus']}")
    print(f"  Checkpoint: {phase['checkpoint_question']}")
```

---

### Tool 2: `flashcard_generator` (`app.mcp.tools.flashcard`)

#### What it does:
Extracts high-yield academic concepts and definitions from study notes and polishes them into active-recall flashcards. Guaranteed non-circular definitions (front never equals back) with clear summary bullets and difficulty tags.

#### Function Signature:
```python
execute_flashcard_tool(
    chunks: List[Union[str, Dict[str, Any]]], # List of raw text chunks or chunk dicts
    topic_filter: Optional[str] = None,       # Optional topic restriction
    count: int = 5,                           # Number of flashcards (or pass num_cards=5)
    difficulty: str = "all",                  # "easy", "medium", "hard", or "all"
    card_format: str = "mixed"                # "definition", "comparison", "qa", or "mixed"
) -> Dict[str, Any]
```

#### Code Connection Example:
```python
from app.mcp import execute_flashcard_tool

chunks = [
    "Paging divides physical memory into fixed-size frames and virtual memory into pages.",
    "A TLB (Translation Lookaside Buffer) is a high-speed hardware cache for page table lookups."
]

result = execute_flashcard_tool(chunks=chunks, count=3, card_format="mixed")

# Accessing Results:
print(f"Total Cards: {result['total_cards']}")
for card in result["flashcards"]:
    print(f"[{card['difficulty'].upper()}] ID: {card['card_id']}")
    print(f"  Front: {card['front']}")
    print(f"  Back:  {card['back']}")
    print(f"  Key Points: {card['key_points']}")
```

---

### Tool 3: `question_generator` (`app.mcp.tools.question_generator`)

#### What it does:
Samples academic facts across notes and generates multiple-choice questions (MCQs). Strictly enforces:
- Exactly 4 options per question.
- Mutually exclusive options (zero duplicate distractors).
- `correct_option_index` strictly matches `correct_answer` verbatim.
- Enforces strict upper bound of **maximum 10 questions** (even if more are requested).

#### Function Signature:
```python
execute_question_generator_tool(
    chunks: List[Union[str, Dict[str, Any]]], # Course notes text chunks
    num_questions: int = 5,                   # Number of MCQs (strictly clamped to <= 10)
    randomize_topics: bool = True,            # Random topic sampling across notes
    difficulty: str = "all",                  # "easy", "medium", "hard", or "all"
    topic_focus: Optional[str] = None         # Specific topic filter
) -> Dict[str, Any]
```

#### Code Connection Example:
```python
from app.mcp import execute_question_generator_tool

chunks = [
    "Processes have independent memory address spaces. Threads within the same process share heap memory.",
    "Semaphores use wait() and signal() operations to maintain mutual exclusion."
]

result = execute_question_generator_tool(chunks=chunks, num_questions=5)

# Accessing Results:
print(f"Questions Generated: {result['total_questions']}")
for q in result["questions"]:
    print(f"\nQ{q['id']}: {q['question']}")
    for idx, opt in enumerate(q["options"]):
        marker = " [CORRECT]" if idx == q["correct_option_index"] else ""
        print(f"   {chr(65+idx)}. {opt}{marker}")
    print(f"  Explanation: {q['explanation']}")
```

---

### Tool 4: `flowchart_generator` (`app.mcp.tools.flowchart`)

#### What it does:
Creates syntactically balanced Mermaid markdown flowcharts (`graph TD` or `flowchart TD`) representing architectural workflows, execution pipelines, or decision trees. Also returns a step-by-step walkthrough list and decision branch details for clean frontend rendering.

#### Function Signature:
```python
execute_flowchart_tool(
    topic: str = "",                          # Topic (e.g. "RAG Pipeline", "Virtual Memory")
    context_chunks: Optional[List[str]] = None, # Relevant lecture notes
    orientation: str = "TD",                  # "TD" (Top-Down) or "LR" (Left-to-Right)
    detail_level: str = "detailed"            # "concise" or "detailed"
) -> Dict[str, Any]
```

#### Code Connection Example:
```python
from app.mcp import execute_flowchart_tool

result = execute_flowchart_tool(topic="RAG Architecture and Retrieval")

# Accessing Results:
print("--- MERMAID MARKDOWN ---")
print(result["mermaid_markdown"])             # Ready to pass to React / Mermaid renderer!

print("\n--- STEP-BY-STEP WALKTHROUGH ---")
for step in result["steps_walkthrough"]:
    print(f"Step {step['step_number']}: [{step['component']}] -> {step['action']}")

print("\n--- DECISION BRANCHES ---")
for dp in result["decision_points"]:
    print(f"Condition: {dp['condition']}")
    print(f"  YES: {dp['outcome_yes']}")
    print(f"  NO:  {dp['outcome_no']}")
```

---

## 5. FastMCP Server Connection (For External Clients / Inspector)

The FastMCP server (`Agent/backend/app/mcp/server/server.py`) exposes all 4 tools plus `rag_search` via the Model Context Protocol.

### Running Standalone:
```powershell
# In terminal:
cd Agent\backend

# 1. Run via STDIO (For Claude Desktop / Cursor / IDE agents):
python app\mcp\server\server.py --transport stdio

# 2. Run via SSE (Server-Sent Events on port 8000):
python app\mcp\server\server.py --transport sse --port 8000

# 3. Print MCP Inspector connection instructions:
python app\mcp\server\server.py --inspector
```

### Accessing Server in Python:
```python
from app.mcp.server import mcp_server, create_mcp_server

# Access the initialized FastMCP instance:
server = mcp_server
print(f"Server Name: {server.name}")
```

---

## 6. How Person 1 (Frontend & RAG) Connects

### In React / Frontend:
- Pass the student's text to `POST /api/v1/chat/threads/{id}/messages`.
- Receive `AgentResponse`.
- When `response.actions` contains `flowchart_generator`, grab `action.result.mermaid_markdown` and pass it to your Mermaid component or display the `steps_walkthrough`.
- When `response.actions` contains `flashcard_generator`, render interactive flip-cards from `action.result.flashcards`.
- When `response.actions` contains `question_generator`, render interactive MCQ cards with radio options.

### In RAG Ingestion / Retrieval:
- Whenever Person 1 extracts chunks from PDF/Doc files, pass them directly to `execute_flashcard_tool(chunks=...)` or `execute_question_generator_tool(chunks=...)`.
- Chunks can be simple strings (`"..."`) or dicts with metadata (`{"chunk_id": "c1", "text": "...", "section": "..."}`).

---

## 7. How Person 2 (Database & Memory) Connects

Person 2 can capture and persist tool outputs with zero translation:

```python
# When student creates a study plan:
plan_output = execute_planner_tool(query=user_query)

# Person 2 saves to study_plans table:
db.save_study_plan(
    user_id=current_user.id,
    topic=plan_output["study_plan"]["topic"],
    total_duration_minutes=plan_output["study_plan"]["total_duration_minutes"],
    direct_answer=plan_output["direct_answer"],
    phases=plan_output["study_plan"]["phases"]  # Directly maps to study_plan_phases table!
)

# When flashcards are generated:
fc_output = execute_flashcard_tool(chunks=retrieved_chunks, count=5)

# Person 2 saves to flashcard_decks & flashcards tables:
deck = db.create_deck(user_id=current_user.id, title=user_query)
for card in fc_output["flashcards"]:
    db.save_flashcard(
        deck_id=deck.id,
        card_id=card["card_id"],
        topic=card["topic"],
        front=card["front"],
        back=card["back"],
        difficulty=card["difficulty"],
        key_points=card["key_points"]
    )
```

---

## 8. Automated Benchmark & Verification Commands

To verify that all tools and the agent are 100% aligned and passing:

```powershell
# Run the 5-dimension benchmark test suite:
python Agent\backend\app\agent\communication_agent.py --test

# Run the FastMCP server tool verification test:
python Agent\backend\app\mcp\server\server.py --test
```

Both commands will output:
```text
==============================================================================
  [SUCCESS] ALL 5 TEST DIMENSIONS COMPLETED & PASSED WITH 100% SUCCESS!
==============================================================================
```
