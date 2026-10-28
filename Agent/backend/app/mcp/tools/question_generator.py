"""
ARIA MCP Question Generator Tool (question_generator.py)

This tool scans study material/chunks, finds topics (with random topic sampling across notes),
determines the question premise and correct answer, generates plausible distractors,
and formats the resulting quiz questions as JSON for seamless frontend and agent consumption.

Features:
- Enforces user-demanded question count up to a strict maximum of 10 questions.
- Randomly samples academic topics across chunks to ensure broad, varied revision coverage.
- Outputs clean JSON containing the primary fields: 'question' and 'options' (along with correct_answer,
  correct_option_index, and explanation for interactive quizzes).
- Works standalone with zero external dependencies (Python standard library only) using intelligent
  heuristic distractor synthesis, while supporting optional LLM adapter hooks.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union


@dataclass
class QuizQuestion:
    """
    Represents a single revision question formatted for frontend rendering.
    Explicitly provides 'question' and 'options' as primary fields.
    """
    id: int
    topic: str
    question: str
    options: List[str]
    correct_answer: str
    correct_option_index: int
    explanation: str
    difficulty: str
    source_chunk_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuestionGeneratorResult:
    """Complete result object ready for JSON export and frontend consumption."""
    status: str
    total_questions: int
    topics_covered: List[str]
    questions: List[QuizQuestion]
    agent_summary: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "total_questions": self.total_questions,
            "topics_covered": self.topics_covered,
            "questions": [q.to_dict() for q in self.questions],
            "agent_summary": self.agent_summary,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes the result to a clean JSON string for the frontend."""
        return json.dumps(self.to_dict(), indent=indent)


class QuestionGeneratorTool:
    """
    Question Generator Tool Implementation.
    
    Extracts random topics, determines the target answers, and produces structured
    multiple-choice questions with 'question' and 'options' in JSON.
    """

    TOOL_NAME = "question_generator"
    DESCRIPTION = (
        "Finds topics across study chunks (with random sampling), formulates questions and answer options, "
        "and returns up to 10 questions in a clean JSON format ready for the frontend."
    )

    MAX_QUESTIONS = 10  # Strict upper bound as requested

    # Common distractor transformations for academic facts
    OPPOSING_QUALIFIERS = [
        (r'\bshares\b', 'isolates completely'),
        (r'\bisolates\b', 'shares directly'),
        (r'\bincreases\b', 'decreases'),
        (r'\bdecreases\b', 'increases'),
        (r'\bsynchronous\b', 'asynchronous'),
        (r'\basynchronous\b', 'synchronous'),
        (r'\bstatic\b', 'dynamic'),
        (r'\bdynamic\b', 'static'),
        (r'\ballows\b', 'strictly prohibits'),
        (r'\bprohibits\b', 'mandates'),
        (r'\boptimal\b', 'inefficient'),
        (r'\blightweight\b', 'resource-heavy'),
        (r'\bvolatile\b', 'persistent non-volatile'),
    ]

    def __init__(self, llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None):
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
                    "chunks": {
                        "type": "array",
                        "items": {
                            "anyOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "chunk_id": {"type": "string"},
                                        "text": {"type": "string"},
                                        "title": {"type": "string"}
                                    },
                                    "required": ["text"]
                                }
                            ]
                        },
                        "description": "List of text chunks, lecture passages, or study notes."
                    },
                    "num_questions": {
                        "type": "integer",
                        "description": "Number of questions demanded by the user (1 to 10). Maximum is 10.",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "randomize_topics": {
                        "type": "boolean",
                        "description": "Whether to select topics completely at random across the input material (default: true).",
                        "default": True
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["all", "easy", "medium", "hard"],
                        "description": "Target difficulty rating (default: 'all').",
                        "default": "all"
                    },
                    "topic_focus": {
                        "type": "string",
                        "description": "Optional topic or keyword to restrict questions to, rather than random selection."
                    }
                },
                "required": ["chunks"]
            }
        }

    def _normalize_chunks(self, chunks: List[Union[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Converts raw strings or dicts into standard chunk representations."""
        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(chunks):
            if isinstance(item, str):
                text = item.strip()
                if text:
                    normalized.append({
                        "chunk_id": f"chunk-{idx + 1}",
                        "text": text,
                        "title": "Notes"
                    })
            elif isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    normalized.append({
                        "chunk_id": str(item.get("chunk_id", f"chunk-{idx + 1}")),
                        "text": text,
                        "title": item.get("title", "Notes")
                    })
        return normalized

    def _extract_candidate_facts(self, normalized_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parses chunks into distinct factual statements, definitions, and relationships
        that can serve as solid question foundations.
        """
        facts: List[Dict[str, Any]] = []

        for chunk in normalized_chunks:
            chunk_id = chunk["chunk_id"]
            # Split into clean sentences
            sentences = re.split(r'(?<=[.?!])\s+(?=[A-Z0-9])', chunk["text"])

            for sentence in sentences:
                s = sentence.strip()
                if len(s) < 25 or len(s) > 280:
                    continue

                # 1. Look for definition patterns
                def_match = re.search(
                    r'(?P<topic>[A-Z][A-Za-z0-9\s\-]{2,30})\s+(?:is|are|refers to|is defined as)\s+(?:a|an|the)?\s*(?P<desc>[^.;?!]+)',
                    s,
                    re.IGNORECASE
                )
                if def_match:
                    topic = def_match.group("topic").strip()
                    desc = def_match.group("desc").strip()
                    facts.append({
                        "type": "definition",
                        "topic": topic,
                        "sentence": s,
                        "correct_answer": f"{topic} is {desc.rstrip('.')} .",
                        "raw_desc": desc,
                        "chunk_id": chunk_id
                    })
                    continue

                # 2. Look for comparison / contrast
                comp_match = re.search(
                    r'(?:difference|distinction)\s+between\s+(?P<topic_a>[^,\s]+(?:\s+[^,\s]+)?)\s+and\s+(?P<topic_b>[^,\s]+(?:\s+[^,\s]+)?)\s+(?:is|lies in)\s+(?P<desc>[^.;?!]+)',
                    s,
                    re.IGNORECASE
                )
                if comp_match:
                    topic_a = comp_match.group("topic_a").strip()
                    topic_b = comp_match.group("topic_b").strip()
                    desc = comp_match.group("desc").strip()
                    facts.append({
                        "type": "comparison",
                        "topic": f"{topic_a} vs {topic_b}",
                        "sentence": s,
                        "correct_answer": f"{topic_a} differs from {topic_b} in that {desc.rstrip('.')}.",
                        "raw_desc": desc,
                        "chunk_id": chunk_id
                    })
                    continue

                # 3. Informative declarative sentence
                if any(k in s.lower() for k in ["primary", "main", "function", "advantage", "purpose", "requires", "responsible", "feature"]):
                    words = s.split()
                    topic_guess = " ".join(words[:3]).strip(",:;-")
                    facts.append({
                        "type": "factual",
                        "topic": topic_guess,
                        "sentence": s,
                        "correct_answer": s,
                        "raw_desc": s,
                        "chunk_id": chunk_id
                    })

        return facts

    def _generate_distractors(
        self,
        correct_answer: str,
        topic: str,
        all_facts: List[Dict[str, Any]],
        count: int = 3
    ) -> List[str]:
        """
        Creates plausible, realistic multiple-choice distractors.
        Uses contextual opposites and alternative facts from other topics in the chunks.
        """
        distractors: List[str] = []

        # Strategy 1: Contextual inversion using opposing terms
        for pat, repl in self.OPPOSING_QUALIFIERS:
            if re.search(pat, correct_answer, re.IGNORECASE):
                inverted = re.sub(pat, repl, correct_answer, flags=re.IGNORECASE)
                if inverted != correct_answer and inverted not in distractors:
                    distractors.append(inverted)
                    if len(distractors) >= count:
                        break

        # Strategy 2: Borrow plausible claims from different topics in other chunks
        other_facts = [f for f in all_facts if f.get("topic") != topic]
        if other_facts:
            sampled_others = random.sample(other_facts, min(len(other_facts), count * 2))
            for f in sampled_others:
                other_ans = f["correct_answer"]
                # Reword to sound like a distractor for this topic if possible
                if len(other_ans) > 20 and other_ans != correct_answer and other_ans not in distractors:
                    # Modify subject to match current topic
                    adapted = f"It requires that {other_ans.lower().rstrip('.')}."
                    distractors.append(adapted if len(adapted) < 160 else other_ans[:140] + "...")
                    if len(distractors) >= count:
                        break

        # Strategy 3: Standard plausible academic foils if more distractors needed
        fallback_foils = [
            f"It operates without verifying integrity or tracking state transitions.",
            f"It exclusively handles external network input and bypasses local execution memory.",
            f"It is deprecated in modern architectures due to non-deterministic execution.",
            f"It requires permanent hardware reconfiguration before every run.",
            f"It guarantees absolute thread isolation by disabling multi-core execution."
        ]
        random.shuffle(fallback_foils)
        for foil in fallback_foils:
            if len(distractors) >= count:
                break
            if foil not in distractors and foil != correct_answer:
                distractors.append(foil)

        return distractors[:count]

    def _generate_heuristic_question(
        self,
        fact: Dict[str, Any],
        q_id: int,
        all_facts: List[Dict[str, Any]]
    ) -> QuizQuestion:
        """
        Synthesizes a structured multiple choice question with 'question' and 'options'.
        """
        topic = fact["topic"]
        fact_type = fact.get("type", "factual")
        raw_desc = fact.get("raw_desc", "")

        # Formulate Question Text
        if fact_type == "definition":
            question_text = f"Which of the following statements most accurately defines or describes '{topic}'?"
            correct_opt = f"{raw_desc.rstrip('.')[:140]}."
            correct_opt = correct_opt[0].upper() + correct_opt[1:]
        elif fact_type == "comparison":
            question_text = f"What is the fundamental distinction regarding {topic}?"
            correct_opt = f"The primary distinction lies in that {raw_desc.rstrip('.')[:130]}."
        else:
            question_text = f"Regarding {topic}, which of the following statements is TRUE?"
            correct_opt = f"{fact['sentence'].rstrip('.')[:140]}."

        # Generate 3 distractors
        distractors = self._generate_distractors(correct_opt, topic, all_facts, count=3)

        # Assemble options and shuffle randomly
        all_options = [correct_opt] + distractors
        random.shuffle(all_options)
        correct_index = all_options.index(correct_opt)

        explanation = (
            f"Correct: '{correct_opt}' is the accurate statement based on the study materials. "
            f"The alternative options either alter the core mechanism or describe unrelated properties."
        )

        # Difficulty heuristic
        difficulty = "medium"
        if fact_type == "comparison" or len(correct_opt) > 100:
            difficulty = "hard"
        elif fact_type == "definition" and len(correct_opt) < 60:
            difficulty = "easy"

        return QuizQuestion(
            id=q_id,
            topic=topic,
            question=question_text,
            options=all_options,
            correct_answer=correct_opt,
            correct_option_index=correct_index,
            explanation=explanation,
            difficulty=difficulty,
            source_chunk_id=fact.get("chunk_id")
        )

    def _call_llm_question_generator(
        self,
        sampled_facts: List[Dict[str, Any]],
        num_questions: int
    ) -> Optional[List[QuizQuestion]]:
        """Uses an optional LLM adapter to formulate high-quality multiple choice questions."""
        if not self.llm_adapter:
            return None

        prompt = (
            f"You are ARIA's quiz engine. Generate {num_questions} multiple choice questions (MCQs) "
            f"based on the following academic topics and facts:\n"
            f"{json.dumps(sampled_facts, indent=2)}\n\n"
            f"Requirements:\n"
            f"- For each question, output 'question' and 'options' (exactly 4 options).\n"
            f"- Output 'correct_answer' (must match one option verbatim), 'correct_option_index' (0-3), "
            f"'explanation', 'topic', and 'difficulty'.\n"
            f"Return a valid JSON array of objects."
        )

        try:
            raw = self.llm_adapter(prompt, {"temperature": 0.3})
            json_match = re.search(r'\[\s*\{.*\}\s*\]', raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                questions: List[QuizQuestion] = []
                for idx, q in enumerate(parsed[:num_questions], 1):
                    if not isinstance(q, dict):
                        continue
                    opts = q.get("options", [])
                    question_text = str(q.get("question", "")).strip()
                    if not opts or len(opts) < 2 or not question_text:
                        fact = sampled_facts[min(idx-1, len(sampled_facts)-1)]
                        q_obj = self._generate_heuristic_question(fact, q_id=idx, all_facts=sampled_facts)
                        questions.append(q_obj)
                        continue

                    correct = q.get("correct_answer", opts[0] if opts else "")
                    correct_idx = q.get("correct_option_index")
                    if correct_idx is None or correct_idx >= len(opts):
                        correct_idx = opts.index(correct) if correct in opts else 0

                    questions.append(QuizQuestion(
                        id=idx,
                        topic=q.get("topic", "Academic Topic"),
                        question=question_text,
                        options=opts,
                        correct_answer=correct,
                        correct_option_index=correct_idx,
                        explanation=q.get("explanation", "Accurate according to study materials."),
                        difficulty=q.get("difficulty", "medium"),
                        source_chunk_id=sampled_facts[min(idx-1, len(sampled_facts)-1)].get("chunk_id")
                    ))
                if questions:
                    return questions
        except Exception:
            return None

        return None

    def run(
        self,
        chunks: List[Union[str, Dict[str, Any]]],
        num_questions: int = 5,
        randomize_topics: bool = True,
        difficulty: str = "all",
        topic_focus: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the question generator tool.
        
        Args:
            chunks: List of text passages or chunk objects.
            num_questions: Number of questions requested (clamped to max 10).
            randomize_topics: If True, completely randomizes topic selection across chunks.
            difficulty: 'all', 'easy', 'medium', or 'hard'.
            topic_focus: Optional keyword to filter candidate topics.
            
        Returns:
            JSON-serializable dictionary with 'question' and 'options' outputs for frontend.
        """
        if not chunks:
            return {
                "status": "error",
                "error_code": "NO_CHUNKS_PROVIDED",
                "message": "Please provide study text chunks to formulate questions from."
            }

        # Enforce max 10 constraint strictly as requested
        target_count = min(max(1, int(num_questions)), self.MAX_QUESTIONS)
        normalized = self._normalize_chunks(chunks)

        if not normalized:
            return {
                "status": "error",
                "error_code": "EMPTY_CHUNKS",
                "message": "Supplied chunks contain no readable study content."
            }

        # 1. Extract factual topics and premises
        all_facts = self._extract_candidate_facts(normalized)

        # Fallback if text lacked standard definition patterns: create facts from sentences
        if not all_facts:
            for c in normalized:
                sentences = re.split(r'(?<=[.?!])\s+(?=[A-Z0-9])', c["text"])
                for s in sentences:
                    s_clean = s.strip()
                    if len(s_clean) > 25:
                        all_facts.append({
                            "type": "factual",
                            "topic": "Core Principle",
                            "sentence": s_clean,
                            "correct_answer": s_clean,
                            "raw_desc": s_clean,
                            "chunk_id": c["chunk_id"]
                        })

        # Apply topic focus filter if provided
        if topic_focus:
            filtered_facts = [f for f in all_facts if topic_focus.lower() in f["topic"].lower() or topic_focus.lower() in f["sentence"].lower()]
            if filtered_facts:
                all_facts = filtered_facts

        # 2. Topic Selection: Random sampling across the identified topics
        if randomize_topics and len(all_facts) >= target_count:
            selected_facts = random.sample(all_facts, target_count)
        elif all_facts:
            # If fewer unique facts than target_count, cycle with distinct question formulations
            selected_facts = []
            while len(selected_facts) < target_count:
                for f in all_facts:
                    selected_facts.append(dict(f))
                    if len(selected_facts) >= target_count:
                        break
        else:
            selected_facts = []

        # 3. Generate Questions (via LLM if present, else robust heuristic engine)
        questions: Optional[List[QuizQuestion]] = None
        if self.llm_adapter:
            questions = self._call_llm_question_generator(selected_facts, target_count)

        if not questions:
            questions = []
            for idx, fact in enumerate(selected_facts, 1):
                q = self._generate_heuristic_question(fact, q_id=idx, all_facts=all_facts)
                questions.append(q)

        # Difficulty filter if explicitly requested and enough questions exist
        if difficulty != "all":
            filtered_q = [q for q in questions if q.difficulty == difficulty]
            if filtered_q:
                questions = filtered_q
                # Re-index
                for i, q in enumerate(questions, 1):
                    q.id = i

        topics_covered = list(dict.fromkeys(q.topic for q in questions))
        agent_summary = (
            f"Generated {len(questions)} quiz question(s) (max 10 allowed) covering topics: "
            f"{', '.join(topics_covered[:4])}{'...' if len(topics_covered) > 4 else ''}."
        )

        result = QuestionGeneratorResult(
            status="success",
            total_questions=len(questions),
            topics_covered=topics_covered,
            questions=questions,
            agent_summary=agent_summary
        )

        return result.to_dict()


# MCP Tool Execution Helper
def execute_question_generator_tool(
    chunks: List[Union[str, Dict[str, Any]]],
    num_questions: int = 5,
    randomize_topics: bool = True,
    difficulty: str = "all",
    topic_focus: Optional[str] = None,
    llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Convenience functional wrapper for executing the question generator tool."""
    effective_num = kwargs.get("count") or kwargs.get("target_count") or num_questions
    tool = QuestionGeneratorTool(llm_adapter=llm_adapter)
    return tool.run(
        chunks=chunks,
        num_questions=effective_num,
        randomize_topics=randomize_topics,
        difficulty=difficulty,
        topic_focus=topic_focus
    )


def get_question_generator_tool_spec() -> Dict[str, Any]:
    """Returns the MCP tool specification for question generator."""
    return QuestionGeneratorTool.get_tool_spec()
