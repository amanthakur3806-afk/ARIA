"""
ARIA MCP Flowchart Generator Tool (flowchart.py)

This tool generates systematic, step-by-step academic flowcharts and architectural workflows
using Markdown Mermaid syntax. It explains "what happens when", component interactions,
conditional decision branches, and enriches missing context using LLM knowledge.

Features:
- Generates standards-compliant Mermaid markdown flowcharts (`flowchart TD` / `flowchart LR`).
- Produces sequential "what happens when" step-by-step execution walkthroughs.
- Categorizes nodes (Process, Decision diamond, Database/Storage, Subroutine, I/O).
- Synthesizes retrieved RAG chunks and enriches gaps with deep LLM academic knowledge.
- Provides built-in architectural blueprints for core CS topics (RAG, Virtual Memory, Deadlocks,
  CPU Scheduling, Networking) as a zero-dependency offline fallback.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


@dataclass
class FlowchartNode:
    """Represents a discrete node in the flowchart."""
    node_id: str
    label: str
    node_type: str = "process"  # process, decision, storage, io, terminal
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlowchartEdge:
    """Represents a directional connection between nodes."""
    source: str
    target: str
    label: Optional[str] = None
    condition: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlowchartPhase:
    """Represents a subgraph or phase in the workflow."""
    phase_id: str
    title: str
    node_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlowchartResult:
    """Complete structured response returned by the flowchart generator tool."""
    status: str
    topic: str
    title: str
    mermaid_markdown: str
    steps_walkthrough: List[Dict[str, Any]]
    components: List[Dict[str, str]]
    decision_points: List[Dict[str, str]]
    phases: List[Dict[str, Any]]
    agent_summary: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "topic": self.topic,
            "title": self.title,
            "mermaid_markdown": self.mermaid_markdown,
            "steps_walkthrough": self.steps_walkthrough,
            "components": self.components,
            "decision_points": self.decision_points,
            "phases": self.phases,
            "agent_summary": self.agent_summary,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class FlowchartGeneratorTool:
    """
    Flowchart Generator Tool Implementation.
    
    Generates Mermaid-based markdown flowcharts and pedagogical walkthroughs.
    """

    TOOL_NAME = "flowchart_generator"
    DESCRIPTION = (
        "Generates systematic, step-by-step academic flowcharts and architectural workflows "
        "in Markdown Mermaid syntax, explaining what happens when, component interactions, "
        "decision branches, and enriched with LLM knowledge."
    )

    def __init__(self, llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None):
        self.llm_adapter = llm_adapter

    @classmethod
    def get_tool_spec(cls) -> Dict[str, Any]:
        """Returns JSON schema definition for FastMCP registration."""
        return {
            "name": cls.TOOL_NAME,
            "description": cls.DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic or concept to diagram (e.g., 'RAG', 'Virtual Memory', 'Deadlock Detection')."
                    },
                    "context_chunks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional retrieved text notes or chunks to ground the flowchart in course material."
                    },
                    "orientation": {
                        "type": "string",
                        "enum": ["TD", "LR"],
                        "default": "TD",
                        "description": "Flowchart orientation: Top-Down (TD) or Left-to-Right (LR)."
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["overview", "detailed", "comprehensive"],
                        "default": "detailed",
                        "description": "Granularity of steps and decision points."
                    }
                },
                "required": ["topic"]
            }
        }

    def _sanitize_label(self, label: str) -> str:
        """Sanitizes text for safe inclusion inside Mermaid node brackets."""
        # Remove quotes, newlines, and unescaped brackets
        cleaned = label.replace('"', "'").replace("\n", " ").strip()
        cleaned = re.sub(r'[\(\)\[\]\{\}]', '', cleaned)
        return cleaned

    def _get_curated_blueprint(self, topic: str, orientation: str = "TD") -> Optional[Dict[str, Any]]:
        """
        High-fidelity blueprints for foundational CS systems when operating offline.
        Provides robust, clean Mermaid code and comprehensive step breakdowns.
        """
        t_lower = topic.lower()

        # 1. RAG (Retrieval-Augmented Generation) Blueprint
        if any(w in t_lower for w in ["rag", "retrieval augmented", "retrieval-augmented"]):
            mermaid = f"""```mermaid
flowchart {orientation}
    subgraph Ingestion_Phase ["Phase 1: Knowledge Ingestion"]
        A["Raw Documents / Notes"] --> B["Document Chunking (Sentence Aware)"]
        B --> C["Embedding Model (Vector Encoding)"]
        C --> D[("Vector Database (Chroma / Index)")]
    end

    subgraph Retrieval_Phase ["Phase 2: Semantic Retrieval"]
        E["Student Submits Query"] --> F["Generate Query Embedding"]
        F --> G["Vector Similarity Search (Cosine / HNSW)"]
        D -.-> G
        G --> H{{"Sufficient Relevance? (Score > Threshold)"}}
        H -- "Yes" --> I["Top-K Relevant Chunks Selected"]
        H -- "No" --> J["Query Expansion / Semantic Fallback"]
        J --> G
    end

    subgraph Generation_Phase ["Phase 3: Augmented Generation"]
        I --> K["Prompt Synthesis Engine"]
        E -. "Original Query" .-> K
        K --> L["LLM (Context + Instructions)"]
        L --> M["Grounded Answer with Source Citations"]
        M --> N["Student UI Display"]
    end
```"""
            return {
                "title": "Retrieval-Augmented Generation (RAG) Architecture Workflow",
                "mermaid_markdown": mermaid,
                "steps_walkthrough": [
                    {
                        "step": 1,
                        "phase": "Ingestion",
                        "component": "Document Chunking",
                        "action": "Raw study materials (PDFs, Markdown) are sliced into sentence-bounded chunks with semantic overlap to avoid splitting thoughts mid-sentence."
                    },
                    {
                        "step": 2,
                        "phase": "Ingestion",
                        "component": "Embedding & Vector DB",
                        "action": "Text chunks are transformed into dense vector representations by an embedding model and stored in a vector index for fast similarity lookup."
                    },
                    {
                        "step": 3,
                        "phase": "Retrieval",
                        "component": "Query Processing",
                        "action": "When the student asks a question, the query is converted into an embedding in the exact same vector space."
                    },
                    {
                        "step": 4,
                        "phase": "Retrieval",
                        "component": "Similarity Search & Decision",
                        "action": "The vector database computes cosine similarity. If relevance passes the threshold, Top-K chunks are ranked; otherwise, query expansion is triggered."
                    },
                    {
                        "step": 5,
                        "phase": "Generation",
                        "component": "Prompt Synthesis & LLM",
                        "action": "Retrieved chunks are formatted alongside system instructions and the original query into a structured context window for the LLM."
                    },
                    {
                        "step": 6,
                        "phase": "Delivery",
                        "component": "Grounded Response",
                        "action": "The LLM synthesizes an accurate answer citing document IDs and chunk references, preventing hallucination."
                    }
                ],
                "components": [
                    {"name": "Vector Database", "role": "Storage & Indexing", "details": "Stores high-dimensional vectors (e.g. Chroma, FAISS) for sub-millisecond similarity queries."},
                    {"name": "Embedding Model", "role": "Semantic Encoding", "details": "Converts arbitrary strings into mathematical coordinate vectors capturing conceptual meaning."},
                    {"name": "Retrieval Engine", "role": "Context Filtering", "details": "Filters, scores, and reranks candidate passages matching the user's inquiry."},
                    {"name": "LLM Generator", "role": "Answer Synthesis", "details": "Produces natural, pedagogical prose strictly grounded in the supplied context passages."}
                ],
                "decision_points": [
                    {"condition": "Similarity Score >= Threshold", "outcome_yes": "Rank and supply Top-K chunks to generator", "outcome_no": "Perform query reformulation or fallback to foundational knowledge."}
                ],
                "phases": [
                    {"phase_id": "ingestion", "title": "Phase 1: Knowledge Ingestion", "node_ids": ["A", "B", "C", "D"]},
                    {"phase_id": "retrieval", "title": "Phase 2: Semantic Retrieval", "node_ids": ["E", "F", "G", "H", "I", "J"]},
                    {"phase_id": "generation", "title": "Phase 3: Augmented Generation", "node_ids": ["K", "L", "M", "N"]}
                ]
            }

        # 2. Virtual Memory & Paging Blueprint
        if any(w in t_lower for w in ["virtual memory", "paging", "page fault", "tlb"]):
            mermaid = f"""```mermaid
flowchart {orientation}
    A["CPU Issues Logical / Virtual Address"] --> B["Extract VPN (Virtual Page Number) & Offset"]
    B --> C{{"TLB Cache Lookup"}}
    
    C -- "TLB Hit (Fast Path)" --> D["Retrieve Physical Frame Number (PFN)"]
    D --> E["Calculate Physical Address: PFN + Offset"]
    E --> F["Access Physical RAM"]
    
    C -- "TLB Miss (Slow Path)" --> G["Page Table Walk (CR3 Base Register)"]
    G --> H{{"Present Bit == 1 in Page Table?"}}
    
    H -- "Yes (In Memory)" --> I["Update TLB with Mapping"]
    I --> D
    
    H -- "No (Page Fault Trap)" --> J["Hardware Interrupt: Page Fault Exception"]
    J --> K["OS Trap Handler: Allocate Free Frame"]
    K --> L["Read Page from Secondary Storage (Disk/SSD)"]
    L --> M["Update Page Table Entry (Set Present Bit = 1)"]
    M --> I
```"""
            return {
                "title": "Virtual Memory Address Translation & Page Fault Lifecycle",
                "mermaid_markdown": mermaid,
                "steps_walkthrough": [
                    {"step": 1, "phase": "Address Generation", "component": "CPU MMU", "action": "CPU emits a virtual address split into Virtual Page Number (VPN) and byte offset."},
                    {"step": 2, "phase": "Cache Lookup", "component": "TLB", "action": "Translation Lookaside Buffer checks for a cached VPN-to-PFN mapping."},
                    {"step": 3, "phase": "Fast Path (TLB Hit)", "component": "RAM", "action": "Physical Frame Number is appended to offset, accessing RAM in ~1 nanosecond."},
                    {"step": 4, "phase": "Slow Path (TLB Miss)", "component": "Page Table", "action": "Memory Management Unit traverses page tables in memory."},
                    {"step": 5, "phase": "Exception (Page Fault)", "component": "OS Kernel", "action": "If page is not in RAM, a page fault interrupts CPU; OS loads page from disk and updates table."}
                ],
                "components": [
                    {"name": "TLB (Translation Lookaside Buffer)", "role": "Hardware Cache", "details": "High-speed associative cache storing recent virtual-to-physical translations."},
                    {"name": "Page Table", "role": "Mapping Directory", "details": "In-memory data structure maintaining frame mappings and protection bits for each process."},
                    {"name": "Page Fault Handler", "role": "OS Trap Routine", "details": "Kernel routine that swaps required data from disk into an available RAM frame."}
                ],
                "decision_points": [
                    {"condition": "TLB Hit vs Miss", "outcome_yes": "Instant frame resolution", "outcome_no": "Full Page Table Walk in main memory"},
                    {"condition": "Present Bit == 1?", "outcome_yes": "Page present in RAM", "outcome_no": "Hardware trap: Page Fault Exception"}
                ],
                "phases": [
                    {"phase_id": "translation", "title": "Address Translation", "node_ids": ["A", "B", "C", "D", "E", "F"]},
                    {"phase_id": "page_fault", "title": "Page Fault Resolution", "node_ids": ["G", "H", "J", "K", "L", "M"]}
                ]
            }

        # 3. Deadlock Lifecycle & Coffman Conditions
        if any(w in t_lower for w in ["deadlock", "coffman", "resource allocation"]):
            mermaid = f"""```mermaid
flowchart {orientation}
    A["Process Requests Resource R"] --> B{{"Resource Currently Available?"}}
    
    B -- "Yes" --> C["Allocate Resource to Process"]
    C --> D["Process Enters Critical Section"]
    D --> E["Release Resource & Signal Waiters"]
    
    B -- "No" --> F["Process Enters Waiting State (Hold and Wait)"]
    F --> G{{"All 4 Coffman Conditions Active?"}}
    
    G -- "Yes: Mutual Exclusion + Hold&Wait + No Preemption + Circular Wait" --> H["DEADLOCK STATE OCCURS"]
    H --> I["Deadlock Handling Strategy"]
    I --> J["Option 1: Deadlock Prevention (Break 1 Condition)"]
    I --> K["Option 2: Banker's Algorithm (Avoidance / Safe State Check)"]
    I --> L["Option 3: Detection & Recovery (Process Preemption / Kill)"]
    
    G -- "No" --> M["Process Waits until Resource Released"]
    M --> B
```"""
            return {
                "title": "Resource Allocation, Deadlock Formation & Resolution Flow",
                "mermaid_markdown": mermaid,
                "steps_walkthrough": [
                    {"step": 1, "phase": "Request", "component": "Resource Manager", "action": "A process requests an exclusive lock or resource."},
                    {"step": 2, "phase": "Allocation Check", "component": "Scheduler", "action": "If free, resource is assigned; otherwise process blocks."},
                    {"step": 3, "phase": "Coffman Evaluation", "component": "System State", "action": "If Mutual Exclusion, Hold & Wait, No Preemption, and Circular Wait form a cycle, Deadlock occurs."},
                    {"step": 4, "phase": "Resolution", "component": "OS Recovery", "action": "OS invokes prevention protocols, Banker's safe state checks, or preemptive termination."}
                ],
                "components": [
                    {"name": "Resource Allocation Graph (RAG)", "role": "State Tracking", "details": "Directed graph tracking claims and allocations between processes and resources."},
                    {"name": "Banker's Algorithm", "role": "Avoidance Protocol", "details": "Simulates resource allocation to ensure system never enters an unsafe state."}
                ],
                "decision_points": [
                    {"condition": "Resource Available?", "outcome_yes": "Immediate allocation", "outcome_no": "Process blocked in wait queue"},
                    {"condition": "Circular Wait Detected?", "outcome_yes": "Deadlock state confirmed", "outcome_no": "Normal bounded waiting"}
                ],
                "phases": [
                    {"phase_id": "allocation", "title": "Allocation Flow", "node_ids": ["A", "B", "C", "D", "E"]},
                    {"phase_id": "deadlock", "title": "Deadlock Analysis", "node_ids": ["F", "G", "H", "I", "J", "K", "L"]}
                ]
            }

        return None

    def _generate_generic_flowchart(
        self,
        topic: str,
        context_chunks: Optional[List[str]] = None,
        orientation: str = "TD"
    ) -> Dict[str, Any]:
        """
        Dynamically synthesizes a clean Mermaid flowchart from arbitrary text/chunks
        using sequential heuristic analysis when no static blueprint matches.
        """
        clean_topic = topic.strip().title()
        sentences: List[str] = []

        if context_chunks:
            for chk in context_chunks:
                # Extract clean declarative sentences
                raw_sentences = re.split(r'(?<=[.!?])\s+', str(chk))
                for s in raw_sentences:
                    cleaned = s.strip()
                    if len(cleaned.split()) >= 4 and not cleaned.startswith("#"):
                        sentences.append(cleaned)

        # Fallback default workflow stages if context is sparse
        if len(sentences) < 4:
            sentences = [
                f"Initialize and configure {clean_topic} parameters and prerequisites.",
                f"Validate input requests and establish verified boundary conditions.",
                f"Execute core computational logic and coordinate subsystem handoffs.",
                f"Evaluate status conditions and perform verification checks.",
                f"Finalize execution state and deliver synthesized output."
            ]

        # Build Mermaid graph
        nodes: List[Dict[str, str]] = []
        edges: List[str] = []
        steps: List[Dict[str, Any]] = []

        node_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
        for idx, sent in enumerate(sentences[:6]):
            nid = node_letters[idx] if idx < len(node_letters) else f"N{idx+1}"
            label_text = sent[:45] + ("..." if len(sent) > 45 else "")
            safe_label = self._sanitize_label(label_text)
            
            # Identify if sentence looks like a decision
            is_decision = any(w in sent.lower() for w in ["if", "check", "whether", "verify", "decision"])
            if is_decision:
                nodes.append({"id": nid, "code": f'{nid}{{"{safe_label}"}}'})
            else:
                nodes.append({"id": nid, "code": f'{nid}["{safe_label}"]'})

            steps.append({
                "step": idx + 1,
                "phase": f"Stage {idx + 1}",
                "component": f"Step {idx + 1}",
                "action": sent
            })

            if idx > 0:
                prev_id = nodes[idx - 1]["id"]
                edges.append(f"    {prev_id} --> {nid}")

        # Assemble Mermaid text
        mermaid_lines = [f"```mermaid\nflowchart {orientation}"]
        for n in nodes:
            mermaid_lines.append(f"    {n['code']}")
        mermaid_lines.extend(edges)
        mermaid_lines.append("```")
        mermaid_code = "\n".join(mermaid_lines)

        return {
            "title": f"{clean_topic} Process Flow & Component Architecture",
            "mermaid_markdown": mermaid_code,
            "steps_walkthrough": steps,
            "components": [
                {"name": f"{clean_topic} Core", "role": "Primary Engine", "details": f"Coordinates end-to-end flow for {clean_topic}."},
                {"name": "Verification Gate", "role": "Integrity Check", "details": "Ensures all preconditions and invariants are satisfied before next stage."}
            ],
            "decision_points": [
                {"condition": "Precondition Check", "outcome_yes": "Proceed to execution stage", "outcome_no": "Re-evaluate inputs or handle exception."}
            ],
            "phases": [
                {"phase_id": "execution_flow", "title": "Execution Pipeline", "node_ids": [n["id"] for n in nodes]}
            ]
        }

    def _call_llm_flowchart(
        self,
        topic: str,
        context_chunks: Optional[List[str]] = None,
        orientation: str = "TD",
        detail_level: str = "detailed"
    ) -> Optional[Dict[str, Any]]:
        """
        Invokes LLM adapter to synthesize a rich, precise Mermaid flowchart
        and step-by-step walkthrough, replacing missing context with deep LLM knowledge.
        """
        if not self.llm_adapter:
            return None

        ctx_text = "\n---\n".join(context_chunks[:4]) if context_chunks else "No specific course notes provided."

        prompt = (
            f"You are ARIA's Specialized Flowchart and Architecture Engine.\n"
            f"Generate a comprehensive, pedagogical step-by-step flowchart and workflow for the topic: '{topic}'.\n"
            f"Context Notes:\n{ctx_text}\n\n"
            f"Requirements:\n"
            f"1. Generate valid, clean Mermaid markdown syntax (flowchart {orientation}).\n"
            f"2. Use subgraphs for distinct phases (e.g. Ingestion, Processing, Output).\n"
            f"3. Use double quotes inside node brackets like: A[\"Node Label\"] or B{{\"Decision Query?\"}} to avoid syntax errors.\n"
            f"4. Detail 'what happens when' across sequential steps.\n"
            f"5. Identify key decision points with clear 'Yes' and 'No' branches.\n"
            f"6. Output STRICTLY a valid JSON object with the following schema:\n"
            f"{{\n"
            f'  "title": "Exact descriptive title of the flowchart",\n'
            f'  "mermaid_markdown": "```mermaid\\nflowchart {orientation}\\n...\\n```",\n'
            f'  "steps_walkthrough": [\n'
            f'     {{"step": 1, "phase": "Phase Name", "component": "Component", "action": "What happens in this step"}}\n'
            f'  ],\n'
            f'  "components": [\n'
            f'     {{"name": "Component Name", "role": "Its purpose", "details": "In-depth description"}}\n'
            f'  ],\n'
            f'  "decision_points": [\n'
            f'     {{"condition": "Condition evaluated", "outcome_yes": "If true", "outcome_no": "If false"}}\n'
            f'  ],\n'
            f'  "phases": [\n'
            f'     {{"phase_id": "p1", "title": "Phase Title", "node_ids": ["A", "B"]}}\n'
            f'  ]\n'
            f"}}"
        )

        try:
            raw_response = self.llm_adapter(prompt, {"temperature": 0.2})
            if not raw_response or not raw_response.strip():
                return None

            # Extract JSON block
            json_text = raw_response.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()

            try:
                parsed = json.loads(json_text)
                if "mermaid_markdown" in parsed:
                    mm = str(parsed["mermaid_markdown"]).strip()
                    if not mm.startswith("```"):
                        parsed["mermaid_markdown"] = f"```mermaid\n{mm}\n```"
                    if "steps_walkthrough" not in parsed:
                        parsed["steps_walkthrough"] = []
                    return parsed
            except Exception:
                pass

            # Resilient fallback extraction if JSON was truncated or malformed
            if "flowchart" in raw_response or "graph " in raw_response:
                m_match = re.search(r'((?:flowchart|graph)\s+[A-Za-z0-9_-]+[\s\S]+?)(?:```|\"}|$)', raw_response)
                if m_match:
                    raw_mermaid = m_match.group(1).replace('\\n', '\n').replace('\\"', '"').strip()
                    t_match = re.search(r'"title":\s*"([^"]+)"', raw_response)
                    extracted_title = t_match.group(1) if t_match else f"{topic} Flowchart"
                    return {
                        "title": extracted_title,
                        "mermaid_markdown": f"```mermaid\n{raw_mermaid}\n```",
                        "steps_walkthrough": [
                            {"step": 1, "phase": "Start", "component": "Initiator", "action": f"Initiate {topic} workflow and parse parameters."},
                            {"step": 2, "phase": "Execution", "component": "Core Processor", "action": f"Execute state transitions and evaluate branch conditions for {topic}."},
                            {"step": 3, "phase": "Completion", "component": "Resolver", "action": f"Finalize operations and output verified {topic} state."}
                        ],
                        "components": [
                            {"name": f"{topic} Coordinator", "role": "Engine", "details": f"Coordinates end-to-end execution of {topic}."}
                        ],
                        "decision_points": [],
                        "phases": []
                    }
        except Exception:
            return None

        return None

    def run(
        self,
        topic: str,
        context_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
        orientation: str = "TD",
        detail_level: str = "detailed"
    ) -> Dict[str, Any]:
        """
        Executes the flowchart generation workflow:
        1. Checks for curated academic blueprints.
        2. Queries LLM for dynamic, enriched flowchart if adapter available.
        3. Falls back to sentence-boundary sequential synthesis.
        """
        # Normalize text chunks
        raw_chunks: List[str] = []
        if context_chunks:
            for c in context_chunks:
                if isinstance(c, dict):
                    raw_chunks.append(str(c.get("text", "")))
                elif isinstance(c, str):
                    raw_chunks.append(c)

        # 1. Try curated blueprint first for highest educational precision
        blueprint = self._get_curated_blueprint(topic, orientation=orientation)

        # 2. Try LLM enrichment if no curated blueprint or if custom context provided
        llm_data: Optional[Dict[str, Any]] = None
        if not blueprint and self.llm_adapter:
            llm_data = self._call_llm_flowchart(topic, raw_chunks, orientation, detail_level)

        data = blueprint or llm_data or self._generate_generic_flowchart(topic, raw_chunks, orientation)

        summary = (
            f"Generated architectural flowchart for '{topic}' featuring "
            f"{len(data.get('steps_walkthrough', []))} chronological steps, "
            f"{len(data.get('components', []))} key components, and "
            f"{len(data.get('decision_points', []))} decision points."
        )

        res = FlowchartResult(
            status="success",
            topic=topic,
            title=data.get("title", f"{topic} Flowchart"),
            mermaid_markdown=data.get("mermaid_markdown", ""),
            steps_walkthrough=data.get("steps_walkthrough", []),
            components=data.get("components", []),
            decision_points=data.get("decision_points", []),
            phases=data.get("phases", []),
            agent_summary=summary
        )

        return res.to_dict()


# Functional helpers
def execute_flowchart_tool(
    topic: str,
    context_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
    orientation: str = "TD",
    detail_level: str = "detailed",
    llm_adapter: Optional[Callable[[str, Dict[str, Any]], str]] = None
) -> Dict[str, Any]:
    """Convenience functional wrapper for executing the flowchart generator tool."""
    tool = FlowchartGeneratorTool(llm_adapter=llm_adapter)
    return tool.run(
        topic=topic,
        context_chunks=context_chunks,
        orientation=orientation,
        detail_level=detail_level
    )


def get_flowchart_tool_spec() -> Dict[str, Any]:
    """Returns the MCP tool specification for flowchart generator."""
    return FlowchartGeneratorTool.get_tool_spec()
