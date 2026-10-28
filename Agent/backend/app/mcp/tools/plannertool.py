"""
ARIA MCP Planner Tool (plannertool.py)

This tool generates systematic, human-like answers and structured study/revision plans
tailored to the student's query, learning context, and preferred tone.

Features:
- Adapts tone dynamically (e.g., encouraging tutor, concise exam prep, academic, analogy-driven).
- Breaks explanations into systematic, digestible pedagogical segments (Intuition -> Core Breakdown -> Real-World Analogy).
- Generates actionable, time-bounded study plans with spaced repetition milestones.
- Formats structured outputs optimized for both LangGraph Agent state and JSON-friendly frontend consumption.
- Fully operational standalone with zero third-party dependencies (works out of the box with Python standard library),
  while supporting optional LLM adapter hooks when integrated.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ToneType(str, Enum):
    """Supported explanation and communication tones."""
    EMPATHIC_TUTOR = "empathic_tutor"      # Supportive, friendly, patient, reduces study anxiety
    CONCISE_EXAM = "concise_exam"          # Direct, high-yield, bulleted, exam-trap focused
    TECHNICAL_ACADEMIC = "technical_academic"  # Formal, rigorous, deep terminology and citations
    SOCRATIC = "socratic"                  # Guided questions, promotes critical thinking & active recall
    SIMPLE_ANALOGY = "simple_analogy"      # Intuitive mental models, ELI5, zero jargon
    BALANCED = "balanced"                  # Systematic, clear, professional student-first default


@dataclass
class StudyPhase:
    """Represents a discrete milestone or phase in a study plan."""
    phase_number: int
    title: str
    duration_minutes: int
    description: str
    action_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StudyPlan:
    """A systematic, structured study and revision plan."""
    topic: str
    total_duration_minutes: int
    phases: List[StudyPhase] = field(default_factory=list)
    spaced_repetition_schedule: List[str] = field(default_factory=list)
    milestones: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "total_duration_minutes": self.total_duration_minutes,
            "phases": [p.to_dict() for p in self.phases],
            "spaced_repetition_schedule": self.spaced_repetition_schedule,
            "milestones": self.milestones,
        }


@dataclass
class PlannerOutput:
    """Structured output returned by the Planner Tool for the AI Agent and frontend."""
    status: str
    query: str
    tone_applied: str
    direct_answer: str
    systematic_breakdown: List[Dict[str, str]]
    analogy_or_intuition: str
    study_plan: StudyPlan
    pitfalls_and_tips: List[str]
    suggested_followups: List[str]
    agent_action_summary: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "tone_applied": self.tone_applied,
            "direct_answer": self.direct_answer,
            "systematic_breakdown": self.systematic_breakdown,
            "analogy_or_intuition": self.analogy_or_intuition,
            "study_plan": self.study_plan.to_dict(),
            "pitfalls_and_tips": self.pitfalls_and_tips,
            "suggested_followups": self.suggested_followups,
            "agent_action_summary": self.agent_action_summary,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class PlannerTool:
    """
    Planner Tool Implementation.
    
    Generates systematic explanations, tone adaptation, and actionable study plans.
    Can operate in heuristic standalone mode or with an injected LLM adapter.
    """

    TOOL_NAME = "planner_tool"
    DESCRIPTION = (
        "Answers user queries systematically with human-like clarity, adapts tone based on "
        "user persona/intent, and generates a structured study and revision plan."
    )

    TONE_PROFILES: Dict[ToneType, Dict[str, str]] = {
        ToneType.EMPATHIC_TUTOR: {
            "greeting": "Great question! Don't worry if this concept feels a bit tricky at first—we'll break it down step-by-step together.",
            "closing": "You've got this! Take a brief breather, then tackle Phase 1 of the plan when you're ready.",
            "style": "warm, encouraging, reassuring, and conversational"
        },
        ToneType.CONCISE_EXAM: {
            "greeting": "Here is the high-yield breakdown for exam readiness:",
            "closing": "Prioritize memorizing the core definitions and test traps outlined below.",
            "style": "direct, bullet-pointed, zero fluff, exam-oriented"
        },
        ToneType.TECHNICAL_ACADEMIC: {
            "greeting": "A formal analysis and systematic breakdown of the subject matter:",
            "closing": "Synthesize these principles with reference literature for full conceptual mastery.",
            "style": "rigorous, precise terminology, theoretical depth"
        },
        ToneType.SOCRATIC: {
            "greeting": "Let's explore this together by connecting the foundational principles:",
            "closing": "Reflect on how this connects to what you learned previously. What conclusion emerges?",
            "style": "guided inquiry, questioning, active recall"
        },
        ToneType.SIMPLE_ANALOGY: {
            "greeting": "Think of this through a simple everyday real-world picture:",
            "closing": "Once that picture clicks in your mind, the technical details fall right into place!",
            "style": "intuitive, everyday analogies, accessible"
        },
        ToneType.BALANCED: {
            "greeting": "Here is a structured, clear explanation to master this topic:",
            "closing": "Follow the structured phases below to cement your understanding.",
            "style": "balanced, clear, systematic, and supportive"
        },
    }

    def __init__(self, llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None):
        """
        Args:
            llm_adapter: Optional callable `fn(prompt: str, config: dict) -> str`
                         for external model completions.
        """
        self.llm_adapter = llm_adapter

    @classmethod
    def get_tool_spec(cls) -> Dict[str, Any]:
        """Returns the Model Context Protocol (MCP) compliant tool specification."""
        return {
            "name": cls.TOOL_NAME,
            "description": cls.DESCRIPTION,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The academic question, concept, or study request submitted by the student."
                    },
                    "tone": {
                        "type": "string",
                        "enum": [t.value for t in ToneType],
                        "description": "Desired tone: 'empathic_tutor', 'concise_exam', 'technical_academic', 'socratic', 'simple_analogy', or 'balanced'."
                    },
                    "target_duration_minutes": {
                        "type": "integer",
                        "description": "Total study/revision time available in minutes (default: 45).",
                        "default": 45,
                        "minimum": 10,
                        "maximum": 300
                    },
                    "context_chunks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional retrieved document passages or lecture notes from RAG."
                    },
                    "user_preferences": {
                        "type": "object",
                        "description": "Optional user preferences such as learning pace, target exam, or tone preference."
                    }
                },
                "required": ["query"]
            }
        }

    def detect_tone(self, query: str, explicit_tone: Optional[str] = None, preferences: Optional[Dict[str, Any]] = None) -> ToneType:
        """
        Infers the most appropriate tone based on explicit request, user preferences,
        or natural language cues in the query.
        """
        if explicit_tone:
            try:
                return ToneType(explicit_tone.lower().strip())
            except ValueError:
                pass

        if preferences and "preferred_tone" in preferences:
            try:
                return ToneType(preferences["preferred_tone"].lower().strip())
            except ValueError:
                pass

        q_lower = query.lower()

        # Heuristic intent detection
        if any(w in q_lower for w in ["exam", "test", "quiz", "tomorrow", "cheat sheet", "bullet", "quick summary", "high yield"]):
            return ToneType.CONCISE_EXAM
        if any(w in q_lower for w in ["eli5", "like i'm 5", "like im 5", "analogy", "simple terms", "layman"]):
            return ToneType.SIMPLE_ANALOGY
        if any(w in q_lower for w in ["formal", "mathematical", "proof", "derivation", "academic", "theory", "thesis"]):
            return ToneType.TECHNICAL_ACADEMIC
        if any(w in q_lower for w in ["why", "how come", "test me", "guide me", "socratic", "question me"]):
            return ToneType.SOCRATIC
        if any(w in q_lower for w in ["stuck", "confused", "hard", "help me", "overwhelmed", "scared", "struggling"]):
            return ToneType.EMPATHIC_TUTOR

        # Default pedagogical tone: warm & empathic tutor
        return ToneType.EMPATHIC_TUTOR

    def build_study_plan(self, topic: str, duration_minutes: int) -> StudyPlan:
        """
        Creates a systematic, pedagogical multi-phase study plan with spaced repetition.
        """
        duration = max(15, min(duration_minutes, 300))

        # Time allocation: 30% Foundation, 45% Active Practice/Application, 25% Synthesis & Recall
        p1_time = max(5, int(duration * 0.30))
        p2_time = max(5, int(duration * 0.45))
        p3_time = max(5, duration - (p1_time + p2_time))

        phases = [
            StudyPhase(
                phase_number=1,
                title="Foundational Grasp & Intuition",
                duration_minutes=p1_time,
                description=f"Understand the 'why' and core mental model behind {topic}.",
                action_items=[
                    f"Read through the core definitions and the everyday analogy for {topic}.",
                    "Highlight the 2-3 most critical terms or parameters.",
                    "Close your notes and explain the fundamental premise aloud in 60 seconds."
                ]
            ),
            StudyPhase(
                phase_number=2,
                title="Active Application & Dissection",
                duration_minutes=p2_time,
                description=f"Work through worked examples and challenge mechanisms of {topic}.",
                action_items=[
                    f"Trace the primary process, mechanism, or formula governing {topic}.",
                    "Identify key edge cases, variations, and common misconceptions.",
                    "Generate or solve 2-3 targeted practice questions."
                ]
            ),
            StudyPhase(
                phase_number=3,
                title="Active Recall & Synthesis",
                duration_minutes=p3_time,
                description=f"Lock in retention and verify mastery of {topic}.",
                action_items=[
                    "Perform a quick 3-minute self-quiz without peeking at references.",
                    "Create a 1-page condensed revision flashcard or summary sheet.",
                    "Schedule review triggers using the spaced repetition calendar."
                ]
            ),
        ]

        spaced_schedule = [
            "Session Check (Immediate): 5-minute self-quiz right after this session.",
            "Day 1 Review (Tomorrow): 10-minute active recall review of flashcards.",
            "Day 3 Review: Solve 2 practice problems on this topic without notes.",
            "Day 7 Review: Quick 5-minute concept map redraw to cement long-term memory."
        ]

        milestones = [
            f"Milestone 1: Can define '{topic}' in your own words without jargon.",
            f"Milestone 2: Can clearly contrast '{topic}' with related concepts.",
            f"Milestone 3: Successfully completed self-quiz and identified personal weak spots."
        ]

        return StudyPlan(
            topic=topic,
            total_duration_minutes=duration,
            phases=phases,
            spaced_repetition_schedule=spaced_schedule,
            milestones=milestones
        )

    def extract_core_topic(self, query: str) -> str:
        """Extracts the central topic phrase from a user query."""
        cleaned = re.sub(r'^(what is|what are|explain|describe|tell me about|how does|help me understand|can you plan|revision for)\s+', '', query.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r'[?!.,;:]+$', '', cleaned).strip()
        return cleaned.capitalize() if cleaned else "Academic Concept"

    def _generate_heuristic_response(
        self,
        query: str,
        topic: str,
        tone: ToneType,
        context_chunks: Optional[List[str]],
        target_duration: int
    ) -> PlannerOutput:
        """
        Robust heuristic fallback when an LLM adapter is not provided.
        Synthesizes a systematic, human-like pedagogical response.
        """
        tone_profile = self.TONE_PROFILES.get(tone, self.TONE_PROFILES[ToneType.BALANCED])
        greeting = tone_profile["greeting"]
        closing = tone_profile["closing"]

        # Incorporate context chunks if present
        context_summary = ""
        chunk_notes: List[str] = []
        if context_chunks:
            for idx, c in enumerate(context_chunks[:3], 1):
                clean_c = c.strip()
                if clean_c:
                    chunk_notes.append(f"Passage {idx}: {clean_c[:180]}...")
            if chunk_notes:
                context_summary = " " + " ".join(chunk_notes)

        # Tone-specific direct answer
        if tone == ToneType.CONCISE_EXAM:
            direct_answer = (
                f"{greeting}\n"
                f"• Definition: {topic} represents a core mechanism designed to solve specific operational constraints.\n"
                f"• Key Objective: Maximize efficiency, isolate responsibilities, and ensure predictable execution.\n"
                f"• High-Yield Takeaway: Never confuse its theoretical limits with practical implementation."
            )
        elif tone == ToneType.SIMPLE_ANALOGY:
            direct_answer = (
                f"{greeting}\n"
                f"Imagine you are running a bustling restaurant kitchen. {topic} is like having a clear, organized "
                f"station system where each chef knows exactly when to prep, cook, and serve without bumping into one another. "
                f"Instead of chaos, everything flows smoothly through established rules."
            )
        elif tone == ToneType.TECHNICAL_ACADEMIC:
            direct_answer = (
                f"{greeting}\n"
                f"{topic} constitutes a fundamental construct characterized by rigorous structural dependencies, "
                f"deterministic state transitions, and well-defined invariants across execution boundaries."
            )
        elif tone == ToneType.SOCRATIC:
            direct_answer = (
                f"{greeting}\n"
                f"Before we dissect the formulas, ask yourself: what problem was {topic} created to solve? "
                f"If you had to build a system from scratch without it, where would it break first? "
                f"Let's walk through that exact tension."
            )
        else:  # EMPATHIC_TUTOR / BALANCED
            direct_answer = (
                f"{greeting}\n"
                f"At its heart, {topic} is simply a structured way to handle complex tasks reliably. "
                f"Think of it as a blueprint: once you see why each piece is in place, the whole concept clicks."
            )

        # Systematic breakdown
        breakdown = [
            {
                "section": "1. Purpose & Motivation",
                "content": f"{topic} addresses the need for structured coordination, clarity, and systematic problem-solving in this subject area."
            },
            {
                "section": "2. Core Principles & Workflow",
                "content": f"It operates by breaking larger challenges into modular, verifiable units. In practice, this prevents cascading errors and allows independent verification."
            },
            {
                "section": "3. Critical Distinction",
                "content": f"A key nuance in {topic} is distinguishing between the underlying mechanism and its high-level interface. Don't worry about memorizing every detail right away—focus on the workflow."
            }
        ]

        if context_summary:
            breakdown.append({
                "section": "4. Grounded Notes Synthesis",
                "content": f"Based on your study notes:{context_summary}"
            })

        # Analogy
        analogy = (
            f"Analogy: Think of {topic} like a well-organized train dispatch system. Each track has an explicit signal; "
            f"trains (data/tasks) only move when the route is verified clear. This guarantees both safety and speed."
        )

        # Common pitfalls & tips
        pitfalls = [
            f"Common Pitfall: Trying to memorize formulas for {topic} before understanding the underlying problem it solves.",
            "Pro-Tip: Teach the concept to an imaginary student in 2 minutes. If you hesitate, note where you paused.",
            "Exam Trap: Watch out for questions that switch terminology or swap cause and effect."
        ]

        # Active-recall followups
        followups = [
            f"Can you explain the main advantage of {topic} in your own words?",
            f"What is one scenario where applying {topic} would NOT be recommended?",
            f"How does {topic} differ from similar alternative concepts?"
        ]

        study_plan = self.build_study_plan(topic=topic, duration_minutes=target_duration)

        agent_summary = (
            f"Planner completed for topic '{topic}'. Tone applied: '{tone.value}'. "
            f"Generated {len(study_plan.phases)}-phase study plan ({target_duration} mins) "
            f"with {len(followups)} active recall checkpoints."
        )

        return PlannerOutput(
            status="success",
            query=query,
            tone_applied=tone.value,
            direct_answer=direct_answer,
            systematic_breakdown=breakdown,
            analogy_or_intuition=analogy,
            study_plan=study_plan,
            pitfalls_and_tips=pitfalls,
            suggested_followups=followups,
            agent_action_summary=agent_summary
        )

    def _call_llm(
        self,
        query: str,
        topic: str,
        tone: ToneType,
        context_chunks: Optional[List[str]],
        target_duration: int
    ) -> PlannerOutput:
        """Delegates generation to an injected LLM adapter when present."""
        context_text = "\n".join(context_chunks) if context_chunks else "No additional notes provided."
        tone_profile = self.TONE_PROFILES.get(tone, self.TONE_PROFILES[ToneType.BALANCED])

        prompt = (
            f"You are ARIA, an intelligent and empathetic academic tutor.\n"
            f"Topic: {topic}\n"
            f"User Query: {query}\n"
            f"Required Tone: {tone.value} ({tone_profile['style']})\n"
            f"Target Study Time: {target_duration} minutes\n"
            f"Context Notes from RAG:\n{context_text}\n\n"
            f"Task: Provide a systematic, pedagogical explanation close to a human tutor.\n"
            f"Return a valid JSON object with the following schema:\n"
            f"{{\n"
            f'  "direct_answer": "...",\n'
            f'  "systematic_breakdown": [{{"section": "...", "content": "..."}}],\n'
            f'  "analogy_or_intuition": "...",\n'
            f'  "pitfalls_and_tips": ["...", "..."],\n'
            f'  "suggested_followups": ["...", "..."]\n'
            f"}}"
        )

        try:
            assert self.llm_adapter is not None
            raw_response = self.llm_adapter(prompt, {"temperature": 0.3})
            # Extract JSON block
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                study_plan = self.build_study_plan(topic=topic, duration_minutes=target_duration)
                return PlannerOutput(
                    status="success",
                    query=query,
                    tone_applied=tone.value,
                    direct_answer=data.get("direct_answer", ""),
                    systematic_breakdown=data.get("systematic_breakdown", []),
                    analogy_or_intuition=data.get("analogy_or_intuition", ""),
                    study_plan=study_plan,
                    pitfalls_and_tips=data.get("pitfalls_and_tips", []),
                    suggested_followups=data.get("suggested_followups", []),
                    agent_action_summary=f"LLM-generated plan for {topic} in {tone.value} tone."
                )
        except Exception:
            # Graceful fallback to heuristic synthesis on any LLM parsing or invocation error
            pass

        return self._generate_heuristic_response(query, topic, tone, context_chunks, target_duration)

    def run(
        self,
        query: str,
        tone: Optional[str] = None,
        context_chunks: Optional[List[str]] = None,
        target_duration_minutes: int = 45,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the planner tool.
        
        Args:
            query: The academic question, concept, or study request.
            tone: Desired tone (e.g., 'empathic_tutor', 'concise_exam').
            context_chunks: Retrieved document chunks from RAG.
            target_duration_minutes: Available study time (10-300 min).
            user_preferences: Optional user memory/preference dictionary.
            
        Returns:
            JSON-serializable dictionary with systematic answer, plan, and agent metadata.
        """
        if not query or not query.strip():
            return {
                "status": "error",
                "error_code": "EMPTY_QUERY",
                "message": "Query cannot be empty. Please provide a topic or question to plan for."
            }

        resolved_tone = self.detect_tone(query, tone, user_preferences)
        topic = self.extract_core_topic(query)

        if self.llm_adapter:
            output = self._call_llm(query, topic, resolved_tone, context_chunks, target_duration_minutes)
        else:
            output = self._generate_heuristic_response(query, topic, resolved_tone, context_chunks, target_duration_minutes)

        return output.to_dict()


# MCP Tool Execution Helper
def execute_planner_tool(
    query: str = "",
    topic: Optional[str] = None,
    tone: Optional[str] = None,
    context_chunks: Optional[List[str]] = None,
    target_duration_minutes: int = 45,
    target_duration: Optional[int] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Convenience functional wrapper for executing the planner tool."""
    effective_query = query or topic or kwargs.get("prompt", "")
    effective_duration = target_duration if target_duration is not None else target_duration_minutes
    tool = PlannerTool(llm_adapter=llm_adapter)
    return tool.run(
        query=effective_query,
        tone=tone,
        context_chunks=context_chunks,
        target_duration_minutes=effective_duration,
        user_preferences=user_preferences
    )


def get_planner_tool_spec() -> Dict[str, Any]:
    """Returns the MCP tool specification for plannertool."""
    return PlannerTool.get_tool_spec()
