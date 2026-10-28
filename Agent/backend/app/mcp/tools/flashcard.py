"""
ARIA MCP Flashcard Generator Tool (flashcard.py)

This tool analyzes retrieved study chunks/notes, extracts the most relevant
and high-yield academic topics, and polishes them into concise, high-retention
study flashcards.

Features:
- Extracts core academic concepts, definitions, comparisons, and mechanisms from raw text or RAG chunks.
- Polishes and refines raw text: summarizes dense material into bite-sized Front/Back pairs and enriches
  incomplete statements by cross-referencing context across multiple chunks or an optional LLM.
- Generates multiple active-recall formats: Concept/Definition, Question/Answer, Comparison, and Cloze.
- Tracks source provenance (chunk IDs, document references) for citations and RAG alignment.
- Zero mandatory external dependencies (operates standalone using Python standard library),
  with optional LLM enhancement hooks.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


@dataclass
class Flashcard:
    """Represents a single polished active-recall flashcard."""
    card_id: str
    topic: str
    front: str
    back: str
    difficulty: str
    format: str
    key_points: List[str] = field(default_factory=list)
    source_chunks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlashcardSetResult:
    """Complete structured response from the flashcard generation tool."""
    status: str
    total_cards: int
    topics_identified: List[str]
    flashcards: List[Flashcard]
    agent_summary: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "total_cards": self.total_cards,
            "topics_identified": self.topics_identified,
            "flashcards": [c.to_dict() for c in self.flashcards],
            "agent_summary": self.agent_summary,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class FlashcardGeneratorTool:
    """
    Flashcard Generator Tool Implementation.
    
    Extracts key academic topics from study chunks and polishes them into
    high-retention flashcards.
    """

    TOOL_NAME = "flashcard_generator"
    DESCRIPTION = (
        "Extracts the most relevant topics from study text chunks and polishes them into "
        "structured active-recall flashcards with summaries, key points, and cross-chunk context."
    )

    # Patterns for detecting definitions and key academic relationships
    DEFINITION_PATTERNS = [
        # X is/are defined as Y
        r'(?P<term>[A-Z][A-Za-z0-9\s\-]{2,35})\s+(?:is|are)\s+defined\s+as\s+(?P<definition>[^.?!;]+)',
        # X refers to Y
        r'(?P<term>[A-Z][A-Za-z0-9\s\-]{2,35})\s+refers\s+to\s+(?P<definition>[^.?!;]+)',
        # X is/are a/an Y which/that...
        r'(?P<term>[A-Z][A-Za-z0-9\s\-]{2,35})\s+(?:is|are)\s+(?:a|an|the)\s+(?P<definition>[^.?!;]+(?:\bthat\b|\bwhich\b|\bused\s+to\b)[^.?!;]+)',
        # Term: Definition or Term - Definition
        r'^\s*[\*\-]?\s*(?P<term>[A-Z][A-Za-z0-9\s\-]{2,30})\s*[:\-–]\s+(?P<definition>[^.?!;]+)',
        # In general, X is Y
        r'(?P<term>[A-Za-z0-9\s\-]{3,35})\s+(?:acts\s+as|serves\s+as|functions\s+as)\s+(?P<definition>[^.?!;]+)',
    ]

    COMPARISON_PATTERNS = [
        r'(?:difference|contrast|distinction)\s+between\s+(?P<term_a>[^,\s]+(?:\s+[^,\s]+)?)\s+and\s+(?P<term_b>[^,\s]+(?:\s+[^,\s]+)?)\s+(?:is|lies\s+in)\s+(?P<explanation>[^.?!;]+)',
        r'(?P<term_a>[A-Z][A-Za-z\s]+)\s+(?:whereas|while|unlike)\s+(?P<term_b>[A-Za-z\s]+)[,]\s+(?P<explanation>[^.?!;]+)',
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
                                        "title": {"type": "string"},
                                        "document_id": {"type": "string"},
                                        "page": {"type": "integer"}
                                    },
                                    "required": ["text"]
                                }
                            ]
                        },
                        "description": "List of text chunks or RAG retrieved documents to extract flashcards from."
                    },
                    "topic_filter": {
                        "type": "string",
                        "description": "Optional specific topic or keyword to focus flashcard extraction on."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Target number of flashcards to generate (default: 5, max: 20).",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["all", "easy", "medium", "hard"],
                        "description": "Target difficulty filter (default: 'all').",
                        "default": "all"
                    },
                    "card_format": {
                        "type": "string",
                        "enum": ["mixed", "qa", "definition", "comparison"],
                        "description": "Preferred flashcard formatting style (default: 'mixed').",
                        "default": "mixed"
                    }
                },
                "required": ["chunks"]
            }
        }

    def _normalize_chunks(self, chunks: List[Union[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Normalizes input chunks into standard dictionaries with text and metadata."""
        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(chunks):
            if isinstance(item, str):
                text = item.strip()
                if text:
                    chunk_id = f"chunk-{idx + 1}"
                    normalized.append({
                        "chunk_id": chunk_id,
                        "text": text,
                        "title": "Study Notes",
                        "page": None
                    })
            elif isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    chunk_id = str(item.get("chunk_id", f"chunk-{idx + 1}"))
                    normalized.append({
                        "chunk_id": chunk_id,
                        "text": text,
                        "title": item.get("title", "Study Notes"),
                        "document_id": item.get("document_id"),
                        "page": item.get("page")
                    })
        return normalized

    def _extract_sentences(self, text: str) -> List[str]:
        """Splits text into clean sentences."""
        sentences = re.split(r'(?<=[.?!])\s+(?=[A-Z0-9])', text)
        return [s.strip() for s in sentences if len(s.strip()) > 15]

    def _discover_candidate_topics(
        self,
        normalized_chunks: List[Dict[str, Any]],
        topic_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scans all chunks to identify relevant core topics, definitions, and comparisons.
        Cross-references multiple chunks to collect supplementary context.
        """
        candidates: List[Dict[str, Any]] = []
        seen_terms = set()

        # Build topic mention index across chunks for cross-chunk enrichment
        all_text = " ".join(c["text"] for c in normalized_chunks)

        for chunk in normalized_chunks:
            chunk_id = chunk["chunk_id"]
            sentences = self._extract_sentences(chunk["text"])

            for sentence in sentences:
                if topic_filter and topic_filter.lower() not in sentence.lower():
                    continue

                # 1. Match definition patterns
                for pat in self.DEFINITION_PATTERNS:
                    m = re.search(pat, sentence, re.IGNORECASE)
                    if m:
                        term = m.group("term").strip()
                        definition = m.group("definition").strip()
                        term_key = term.lower()

                        if len(term) >= 3 and term_key not in seen_terms:
                            seen_terms.add(term_key)
                            # Find supplementary context across other chunks
                            extra_info = self._find_cross_chunk_context(term, normalized_chunks, exclude_chunk_id=chunk_id)
                            candidates.append({
                                "term": term,
                                "raw_definition": definition,
                                "sentence": sentence,
                                "extra_context": extra_info,
                                "type": "definition",
                                "source_chunks": [chunk_id] + ([extra_info["source_chunk"]] if extra_info else [])
                            })
                            break

                # 2. Match comparison patterns
                for pat in self.COMPARISON_PATTERNS:
                    m = re.search(pat, sentence, re.IGNORECASE)
                    if m:
                        term_a = m.group("term_a").strip()
                        term_b = m.group("term_b").strip()
                        explanation = m.group("explanation").strip()
                        comp_key = f"{term_a.lower()}_vs_{term_b.lower()}"

                        if comp_key not in seen_terms:
                            seen_terms.add(comp_key)
                            candidates.append({
                                "term": f"{term_a} vs {term_b}",
                                "raw_definition": explanation,
                                "sentence": sentence,
                                "extra_context": None,
                                "type": "comparison",
                                "source_chunks": [chunk_id]
                            })
                            break

        # Fallback if patterns found few candidates: extract strong declarative sentences
        if len(candidates) < 3:
            for chunk in normalized_chunks:
                for sentence in self._extract_sentences(chunk["text"]):
                    if topic_filter and topic_filter.lower() not in sentence.lower():
                        continue
                    # Pick informative sentences with key indicators
                    if any(kw in sentence.lower() for kw in ["key", "important", "principle", "algorithm", "because", "primary", "requires"]):
                        words = sentence.split()
                        topic_guess = " ".join(words[:4]).strip(",:;-")
                        if topic_guess.lower() not in seen_terms:
                            seen_terms.add(topic_guess.lower())
                            candidates.append({
                                "term": topic_guess,
                                "raw_definition": sentence,
                                "sentence": sentence,
                                "extra_context": None,
                                "type": "concept",
                                "source_chunks": [chunk["chunk_id"]]
                            })

        return candidates

    def _find_cross_chunk_context(
        self,
        term: str,
        chunks: List[Dict[str, Any]],
        exclude_chunk_id: str
    ) -> Optional[Dict[str, str]]:
        """
        Searches other chunks for mentions of the same term to enrich and polish the flashcard.
        """
        term_lower = term.lower()
        for chunk in chunks:
            if chunk["chunk_id"] == exclude_chunk_id:
                continue
            text = chunk["text"]
            if term_lower in text.lower():
                sentences = self._extract_sentences(text)
                for s in sentences:
                    if term_lower in s.lower() and len(s) > 20:
                        return {
                            "supplemental_text": s.strip(),
                            "source_chunk": chunk["chunk_id"]
                        }
        return None

    def _polish_card(self, candidate: Dict[str, Any], card_index: int, target_format: str) -> Flashcard:
        """
        Polishes a raw topic/definition into a clean, pedagogically sound flashcard.
        Adds formatting, concise summaries, key points, and difficulty ratings.
        """
        term = candidate["term"]
        raw_def = candidate["raw_definition"]
        card_type = candidate.get("type", "definition")
        extra_ctx = candidate.get("extra_context")

        # Polish the definition text
        clean_def = raw_def.rstrip(".?! ") + "."
        clean_def = clean_def[0].upper() + clean_def[1:] if clean_def else ""

        # Build bulleted high-yield points
        key_points = [
            f"Core: {clean_def[:140]}"
        ]

        # Enrich with cross-chunk information if available
        if extra_ctx and "supplemental_text" in extra_ctx:
            supp = extra_ctx["supplemental_text"].rstrip(".?! ") + "."
            key_points.append(f"Related Context: {supp[:140]}")

        # Determine difficulty based on sentence length and terminology complexity
        char_len = len(clean_def)
        if char_len > 120 or "whereas" in clean_def.lower() or "mechanism" in clean_def.lower():
            difficulty = "hard"
        elif char_len > 60:
            difficulty = "medium"
        else:
            difficulty = "easy"

        # Construct Front and Back based on format
        if card_type == "comparison":
            front = f"What is the key difference between {term}?"
            back = f"{clean_def}\n\nKey Takeaways:\n" + "\n".join(f"• {pt}" for pt in key_points)
            fmt = "comparison"
        elif target_format == "qa" or (card_index % 2 == 1 and target_format == "mixed"):
            front = f"Explain the purpose and function of '{term}'."
            back = f"{clean_def}\n\nImportant Details:\n" + "\n".join(f"• {pt}" for pt in key_points)
            fmt = "qa"
        else:
            front = f"{term}"
            back = f"{clean_def}\n\nSummary:\n" + "\n".join(f"• {pt}" for pt in key_points)
            fmt = "definition"

        # Unique reproducible ID
        hash_seed = f"{term}_{front}_{card_index}".encode("utf-8")
        card_id = f"fc_{hashlib.md5(hash_seed).hexdigest()[:8]}"

        tags = [term.lower().replace(" ", "-"), card_type, difficulty]

        return Flashcard(
            card_id=card_id,
            topic=term,
            front=front,
            back=back,
            difficulty=difficulty,
            format=fmt,
            key_points=key_points,
            source_chunks=candidate.get("source_chunks", []),
            tags=tags
        )

    def _call_llm_polish(
        self,
        candidates: List[Dict[str, Any]],
        target_count: int,
        target_format: str
    ) -> Optional[List[Flashcard]]:
        """Uses an optional LLM adapter to polish and enrich flashcards."""
        if not self.llm_adapter or not candidates:
            return None

        prompt_candidates = candidates[:target_count]
        prompt = (
            f"You are a master study assistant. Polish the following raw concepts into {len(prompt_candidates)} "
            f"high-retention flashcards for student revision.\n"
            f"Raw Concepts:\n{json.dumps(prompt_candidates, indent=2)}\n\n"
            f"Requirements:\n"
            f"- Front must be an engaging active-recall prompt or question.\n"
            f"- Back must be a polished, crystal-clear explanation with 1-2 bullet points.\n"
            f"- Enrich the concept with necessary context or analogies if the definition is incomplete.\n"
            f"Return a valid JSON array of objects with keys: topic, front, back, difficulty, key_points, format."
        )

        try:
            raw = self.llm_adapter(prompt, {"temperature": 0.2})
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                cards: List[Flashcard] = []
                for idx, c in enumerate(parsed):
                    hash_id = hashlib.md5(f"llm_{c.get('topic')}_{idx}".encode()).hexdigest()[:8]
                    cards.append(Flashcard(
                        card_id=f"fc_{hash_id}",
                        topic=c.get("topic", "Concept"),
                        front=c.get("front", ""),
                        back=c.get("back", ""),
                        difficulty=c.get("difficulty", "medium"),
                        format=c.get("format", target_format),
                        key_points=c.get("key_points", []),
                        source_chunks=prompt_candidates[min(idx, len(prompt_candidates)-1)].get("source_chunks", []),
                        tags=[c.get("topic", "").lower()]
                    ))
                return cards
        except Exception:
            return None

        return None

    def run(
        self,
        chunks: List[Union[str, Dict[str, Any]]],
        topic_filter: Optional[str] = None,
        count: int = 5,
        difficulty: str = "all",
        card_format: str = "mixed",
    ) -> Dict[str, Any]:
        """
        Executes the flashcard generation tool.
        
        Args:
            chunks: List of raw strings or dictionary chunks with 'text'.
            topic_filter: Optional specific topic or keyword.
            count: Number of flashcards to generate (1 to 20).
            difficulty: 'all', 'easy', 'medium', or 'hard'.
            card_format: 'mixed', 'qa', 'definition', or 'comparison'.
            
        Returns:
            JSON-serializable dictionary with polished flashcards and metadata.
        """
        if not chunks:
            return {
                "status": "error",
                "error_code": "NO_CHUNKS_PROVIDED",
                "message": "Please provide one or more study chunks to generate flashcards from."
            }

        target_count = max(1, min(count, 20))
        normalized = self._normalize_chunks(chunks)

        if not normalized:
            return {
                "status": "error",
                "error_code": "EMPTY_CHUNKS",
                "message": "Provided chunks contain no readable text."
            }

        # 1. Discover relevant topics and relationships
        candidates = self._discover_candidate_topics(normalized, topic_filter=topic_filter)

        if not candidates:
            # Fallback card if text is too short or unstructured
            sample_text = normalized[0]["text"][:200]
            candidates.append({
                "term": "Key Concept Summary",
                "raw_definition": sample_text,
                "sentence": sample_text,
                "extra_context": None,
                "type": "concept",
                "source_chunks": [normalized[0]["chunk_id"]]
            })

        # 2. Try LLM polish if available, else use robust heuristic synthesis
        cards: Optional[List[Flashcard]] = None
        if self.llm_adapter:
            cards = self._call_llm_polish(candidates, target_count, card_format)

        if not cards:
            cards = []
            for idx, cand in enumerate(candidates[:target_count]):
                card = self._polish_card(cand, card_index=idx, target_format=card_format)
                cards.append(card)

        # 3. Apply difficulty filtering if explicitly requested
        if difficulty != "all":
            filtered_cards = [c for c in cards if c.difficulty == difficulty]
            # Keep original list if filter left zero cards
            if filtered_cards:
                cards = filtered_cards

        topics_identified = list(dict.fromkeys(c.topic for c in cards))
        agent_summary = (
            f"Generated {len(cards)} polished flashcard(s) covering {len(topics_identified)} topic(s): "
            f"{', '.join(topics_identified[:3])}{'...' if len(topics_identified) > 3 else ''}."
        )

        result = FlashcardSetResult(
            status="success",
            total_cards=len(cards),
            topics_identified=topics_identified,
            flashcards=cards,
            agent_summary=agent_summary
        )

        return result.to_dict()


# MCP Tool Execution Helper
def execute_flashcard_tool(
    chunks: List[Union[str, Dict[str, Any]]],
    topic_filter: Optional[str] = None,
    count: int = 5,
    difficulty: str = "all",
    card_format: str = "mixed",
    llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None
) -> Dict[str, Any]:
    """Convenience functional wrapper for executing the flashcard generator tool."""
    tool = FlashcardGeneratorTool(llm_adapter=llm_adapter)
    return tool.run(
        chunks=chunks,
        topic_filter=topic_filter,
        count=count,
        difficulty=difficulty,
        card_format=card_format
    )


def get_flashcard_tool_spec() -> Dict[str, Any]:
    """Returns the MCP tool specification for flashcard generator."""
    return FlashcardGeneratorTool.get_tool_spec()
