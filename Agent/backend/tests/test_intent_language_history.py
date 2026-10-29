"""
tests/test_intent_language_history.py

Unit and integration tests verifying:
1. Doubt vs Plan intent distinction (no unwanted revision plan for conceptual questions like 'what is mcp').
2. Explicit plan requests properly trigger StudyIntent.EXPLAIN_AND_PLAN.
3. Language adaptation (Hinglish/Hindi/Spanish/French detection and instructions).
4. Chat persistence: saving messages, retrieving history, LLM title generation, and thread management.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from app.agent.communication_agent import (
    CommunicationAgent,
    StudyIntent,
    SAMPLE_OS_DOCUMENT,
)
from app.agent.guardrails import FakeLLM
from app.db.chat_store import chat_store
from app.main import (
    ChatMessageRequest,
    CreateThreadRequest,
    create_chat_thread,
    get_chat_history,
    handle_chat_message,
    list_chat_threads,
    delete_chat_thread,
    clear_chat_history,
)


@pytest.fixture
def agent():
    comm = CommunicationAgent(llm_communicator=FakeLLM(mode="grounded"))
    return comm


# ------------------------------------------------------------------------------
# 1. Doubt vs Plan Intent Tests (Requirement 1)
# ------------------------------------------------------------------------------

def test_conceptual_doubt_does_not_generate_plan(agent):
    """
    Verifies that conceptual doubts (e.g. 'what is mcp', 'explain paging')
    do NOT trigger the revision planner and do NOT append revision plan cards.
    """
    doubts = [
        "what is mcp",
        "What is Model Context Protocol?",
        "Explain Virtual Memory and paging mechanisms.",
        "How does a semaphore work?",
        "Difference between mutex and semaphore",
        "Summarize deadlock conditions",
        "Doubt in page table lookup",
    ]

    for query in doubts:
        intent = agent.detect_intent(query)
        assert intent == StudyIntent.EXPLAIN_CONCEPT, f"Query '{query}' was expected to be EXPLAIN_CONCEPT, got {intent}"

    # Verify execution with context: No study_plan in structured_data and no plan note
    resp = agent.handle_message(
        "Explain Virtual Memory and paging mechanisms.",
        context_chunks=[SAMPLE_OS_DOCUMENT],
    )
    assert resp.intent == StudyIntent.EXPLAIN_CONCEPT.value
    assert resp.structured_data is None
    assert "revision plan" not in resp.content.lower()
    assert len(resp.actions) == 0  # Planner tool was NOT called


def test_explicit_plan_request_triggers_planner(agent):
    """
    Verifies that explicit requests for revision plans or study schedules
    correctly trigger the planner tool.
    """
    plan_queries = [
        "Create a study plan for OS",
        "give me a revision schedule for virtual memory",
        "make a revision plan for finals",
        "Process aur thread explain karo aur quick revision plan banao",
        "plan my exam revision for operating systems",
    ]

    for query in plan_queries:
        intent = agent.detect_intent(query)
        assert intent == StudyIntent.EXPLAIN_AND_PLAN, f"Query '{query}' was expected to be EXPLAIN_AND_PLAN, got {intent}"

    # Verify execution: study_plan is present in structured_data
    resp = agent.handle_message(
        "Create a study plan for OS",
        context_chunks=[SAMPLE_OS_DOCUMENT],
    )
    assert resp.intent == StudyIntent.EXPLAIN_AND_PLAN.value
    assert resp.structured_data is not None
    assert "study_plan" in resp.structured_data
    assert any(a.tool == "planner_tool" for a in resp.actions)
    assert "revision plan" in resp.content.lower()


# ------------------------------------------------------------------------------
# 2. Language & Tone Adaptation Tests (Requirement 2)
# ------------------------------------------------------------------------------

def test_language_detection(agent):
    """Verifies multilingual and Hinglish language detection."""
    assert agent.detect_language("bhai mcp kya hai samjha do") == "hi-en"
    assert agent.detect_language("Process aur thread ke beech ka difference batao") == "hi-en"
    assert agent.detect_language("Explica la memoria virtual") == "es"
    assert agent.detect_language("Expliquez le processus et la mémoire") == "fr"
    assert agent.detect_language("What is virtual memory?") == "en"


def test_system_prompt_includes_language_adaptation():
    """Verifies that the LLM system message contains explicit tone & language guidance."""
    from app.agent.communication_agent import LLMCommunicator
    llm = LLMCommunicator()
    sys_msg = llm._build_system_message("Base Instructions.", "hi-en")
    assert "COMMUNICATION STYLE & LANGUAGE ADAPTATION" in sys_msg
    assert "Hinglish" in sys_msg


# ------------------------------------------------------------------------------
# 3. Chat Persistence & LLM Title Generation (Requirement 3)
# ------------------------------------------------------------------------------

def test_title_generation(agent):
    """Verifies title generation for various study topics."""
    title1 = agent.generate_conversation_title("what is mcp")
    assert len(title1.strip()) > 0
    assert not title1.startswith('"')

    title2 = agent.generate_conversation_title("Explain Deadlocks and Coffman conditions")
    assert "deadlock" in title2.lower() or "coffman" in title2.lower()


def test_chat_persistence_flow():
    """Verifies the complete chat persistence lifecycle in SQLite (aria_rag.db)."""
    uid = "student_persist_test"
    tid = "thread_persist_test"

    # 1. Clean previous state if any
    chat_store.delete_conversation(tid, uid)

    # 2. Add turn
    msg_id_u = chat_store.add_message(tid, uid, "user", "What is virtual memory?")
    msg_id_a = chat_store.add_message(
        tid, uid, "assistant",
        "Virtual memory abstracts storage.",
        intent="explain_concept",
        language="en",
        sources=[{"title": "OS Notes", "chunk_id": "c1"}],
    )
    assert msg_id_u.startswith("msg_")
    assert msg_id_a.startswith("msg_")

    # 3. Fetch history via get_chat_history endpoint
    history = get_chat_history(thread_id=tid, user_id=uid)
    assert history["thread_id"] == tid
    assert history["total_messages"] == 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][0]["content"] == "What is virtual memory?"
    assert history["messages"][1]["role"] == "assistant"
    assert history["messages"][1]["intent"] == "explain_concept"

    # 4. List threads
    threads_data = list_chat_threads(user_id=uid)
    assert any(t["id"] == tid for t in threads_data["threads"])

    # 5. Clear messages
    clr_res = clear_chat_history(thread_id=tid, user_id=uid)
    assert clr_res["status"] == "ok"
    assert clr_res["deleted_count"] == 2

    # Verify history is now empty
    history_after = get_chat_history(thread_id=tid, user_id=uid)
    assert history_after["total_messages"] == 0

    # 6. Delete conversation
    del_res = delete_chat_thread(thread_id=tid, user_id=uid)
    assert del_res["status"] == "ok"
    threads_after = list_chat_threads(user_id=uid)
    assert not any(t["id"] == tid for t in threads_after["threads"])


# ------------------------------------------------------------------------------
# 4. Single-Plan Guarantee & Flowchart Generation Tests
# ------------------------------------------------------------------------------

def test_clean_topic_extraction():
    """Verifies that conversational chatter is stripped and clean topics are isolated."""
    from app.agent.communication_agent import clean_topic_title
    from app.mcp.tools.plannertool import PlannerTool

    raw_query = "I need a to know how to start studying mcp in detail create plan for me"
    cleaned = clean_topic_title(raw_query)
    assert "mcp" in cleaned.lower()
    assert "i need a to know" not in cleaned.lower()
    assert "create plan for me" not in cleaned.lower()

    tool = PlannerTool()
    topic = tool.extract_core_topic(raw_query)
    assert "mcp" in topic.lower()
    assert "i need" not in topic.lower()

    # Verify flowchart topic cleaning
    flowchart_query = "can you please create a flow chart for mcp in detail"
    assert "mcp" in clean_topic_title(flowchart_query).lower()
    assert "can you please" not in clean_topic_title(flowchart_query).lower()


def test_no_double_plan_generation(agent):
    """
    Verifies that when the LLM outputs a complete multi-phase plan in markdown,
    ARIA suppresses the duplicate card and boilerplate note to avoid generating it twice.
    """
    class PlanTextLLM:
        def generate_response(self, prompt, context_chunks=None, language="en", **kwargs):
            # Simulates an LLM that directly generates phase breakdown in markdown
            return (
                "### Phase 1: Foundations of MCP (Week 1)\n"
                "Understand what MCP is.\n\n"
                "### Phase 2: Building & Implementing MCP (Week 2)\n"
                "Build your first server.",
                50.0
            )

        def get_tool_llm_adapter(self):
            return None

    agent_with_plan_llm = CommunicationAgent(
        rag_pipeline=agent.rag,
        llm_communicator=PlanTextLLM(),
    )

    resp = agent_with_plan_llm.handle_message(
        "I need a to know how to start studying mcp in detail create plan for me",
        context_chunks=[SAMPLE_OS_DOCUMENT],
    )
    # The text already has Phase 1 and Phase 2, so structured_data is suppressed
    assert resp.structured_data is None
    assert "A personalized" not in resp.content
    assert "Phase 1: Foundations of MCP" in resp.content


def test_flowchart_intent_and_tool_execution(agent):
    """Verifies that flowchart requests trigger flowchart tool with clean metadata."""
    query = "make a flow chart for mcp"
    assert agent.detect_intent(query) == StudyIntent.GENERATE_FLOWCHART

    resp = agent.handle_message(query)
    assert resp.intent == StudyIntent.GENERATE_FLOWCHART.value
    assert resp.structured_data is not None
    assert "flowchart" in resp.structured_data
    fc = resp.structured_data["flowchart"]
    assert "mermaid_markdown" in fc
    assert "steps_walkthrough" in fc
    assert len(fc["steps_walkthrough"]) > 0
