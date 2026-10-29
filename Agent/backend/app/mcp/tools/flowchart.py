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


def clean_topic_title(raw_topic: str) -> str:
    """Strips conversational query artifacts to isolate the clean academic topic."""
    if not raw_topic:
        return "Process Architecture"
    cleaned = raw_topic.strip()

    # Strip conversational introductions and request prefixes
    prefixes = [
        r'^(?:please\s+|can\s+you\s+please\s+|can\s+you\s+|could\s+you\s+please\s+|could\s+you\s+)*',
        r'^(?:create|make|generate|genrate|draw|show|build|give\s+me|provide|design)\s+(?:a\s+|an\s+)?(?:flow\s*chart|flowchart|workflow|diagram|architecture|process|map)\s*(?:for|of|about|on|explaining|showing)?\s*(?:topic\s*)?',
        r'^(?:flow\s*chart|flowchart|diagram|workflow)\s+(?:for|of|about|on|explaining|showing)?\s*(?:topic\s*)?',
        r'^(?:i\s+need\s+(?:a\s+)?(?:to\s+)?(?:know\s+)?(?:how\s+to\s+)?(?:start\s+)?(?:studying|learning|understanding)?)\s*',
        r'^(?:can\s+you\s+)?(?:please\s+)?(?:help\s+me\s+)?(?:study|learn|understand|revise|explore)\s*',
        r'^(?:what\s+is|what\s+are|explain|describe|tell\s+me\s+about|how\s+does|how\s+do|give\s+me)\s*',
        r'^(?:kya\s+hai|kaise\s+kaam\s+karta\s+hai|samjha\s+do|batao|bata\s+do|padhna\s+hai)\s*',
        r'^(?:explaining|showing|about|for\s+topic|for|topic)\s+',
    ]
    for p in prefixes:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE).strip()

    # Strip trailing conversational and request artifacts
    suffixes = [
        r'\s+(?:in\s+detail|step\s+by\s+step|from\s+scratch|properly|clearly)$',
        r'\s+(?:create|make|genrate|generate|give\s+me|banao|bana\s+do)\s+(?:a\s+)?(?:flow\s*chart|flowchart|diagram|workflow|plan|schedule)(?:\s+(?:for\s+me|mujhe|plz|please))?$',
        r'\s+(?:flow\s*chart|flowchart|diagram|workflow|plan\s+for\s+me|for\s+me|ka\s+flowchart)$',
        r'[?!.,;:]+$',
    ]
    for s in suffixes:
        cleaned = re.sub(s, '', cleaned, flags=re.IGNORECASE).strip()

    cleaned_lower = cleaned.lower()
    acronym_map = {
        "mcp": "MCP (Model Context Protocol)",
        "model context protocol": "MCP (Model Context Protocol)",
        "rag": "RAG (Retrieval-Augmented Generation)",
        "retrieval augmented generation": "RAG (Retrieval-Augmented Generation)",
        "os": "Operating Systems",
        "vm": "Virtual Memory",
        "dbms": "Database Management Systems",
    }
    if cleaned_lower in acronym_map:
        return acronym_map[cleaned_lower]

    return cleaned.title() if cleaned else "Process Architecture"


def extract_flowchart_metadata(mermaid_text: str, topic: str = "Topic") -> Dict[str, Any]:
    """Extracts chronological steps, components, decision points, and phases directly from Mermaid code."""
    clean = mermaid_text.replace("```mermaid", "").replace("```", "").strip()

    # 1. Subgraphs / Phases
    phases = []
    sg_matches = re.finditer(r'subgraph\s+([A-Za-z0-9_-]+)\s*(?:\[\"?([^\"]+?)\"?\])?([\s\S]*?)end', clean)
    for m in sg_matches:
        sg_id = m.group(1)
        sg_title = m.group(2) or sg_id.replace("_", " ").title()
        sg_body = m.group(3)
        node_ids = re.findall(r'([A-Za-z0-9_-]+)(?:\s*\[|\s*\{|\s*\()', sg_body)
        phases.append({
            "phase_id": sg_id,
            "title": sg_title,
            "node_ids": list(dict.fromkeys(node_ids))
        })

    # 2. Extract discrete nodes with labels
    node_map = {}
    node_matches = re.findall(r'([A-Za-z0-9_-]+)\s*(?:\[\(\"([^\"]+)\"\)\]|\[\"([^\"]+)\"\]|\{\"([^\"]+)\"\}|\(\"([^\"]+)\"\))', clean)
    for nm in node_matches:
        nid = nm[0]
        label = nm[1] or nm[2] or nm[3] or nm[4]
        if nid not in node_map and label:
            node_map[nid] = label

    # 3. Steps walkthrough in node occurrence order
    steps = []
    for idx, (nid, label) in enumerate(node_map.items(), 1):
        parent_phase = "Execution Flow"
        for p in phases:
            if nid in p["node_ids"]:
                parent_phase = p["title"]
                break
        steps.append({
            "step": idx,
            "phase": parent_phase,
            "component": f"{nid}",
            "action": label
        })

    # 4. Decision points
    decisions = []
    decision_matches = re.findall(r'([A-Za-z0-9_-]+)\s*\{\"([^\"]+)\"\}', clean)
    for did, dcond in decision_matches:
        yes_match = re.search(rf'{did}\s*-->\s*\|(?:Yes|True|Valid)\|[ ]*([A-Za-z0-9_-]+)', clean, re.IGNORECASE)
        no_match = re.search(rf'{did}\s*-->\s*\|(?:No|False|Invalid)\|[ ]*([A-Za-z0-9_-]+)', clean, re.IGNORECASE)
        y_target = node_map.get(yes_match.group(1), "Proceed to next execution stage") if yes_match else "Proceed to next stage"
        n_target = node_map.get(no_match.group(1), "Handle exception or alternative state") if no_match else "Handle exception"
        decisions.append({
            "condition": dcond,
            "outcome_yes": y_target,
            "outcome_no": n_target
        })

    # 5. Components
    components = []
    if phases:
        for p in phases:
            components.append({
                "name": p["title"],
                "role": "Execution Subsystem",
                "details": f"Coordinates {len(p['node_ids'])} operation(s) in {topic}."
            })
    else:
        components.append({
            "name": f"{topic} Core Engine",
            "role": "Primary Controller",
            "details": f"Coordinates computational logic and state transitions for {topic}."
        })

    return {
        "steps_walkthrough": steps,
        "phases": phases,
        "decision_points": decisions,
        "components": components
    }


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
        # Strip XML/HTML tags
        cleaned = re.sub(r'<[^>]+>', '', label)
        # Replace & with and, / with -
        cleaned = cleaned.replace('&', 'and').replace('/', ' - ')
        # Remove quotes, newlines, backslashes, brackets, and characters that break Mermaid syntax
        cleaned = cleaned.replace('"', "'").replace("\n", " ").replace("\\", "").strip()
        cleaned = re.sub(r'[\(\)\[\]\{\}<>]', '', cleaned)
        return cleaned

    def _repair_mermaid_syntax(self, mermaid_code: str, orientation: str = "TD") -> str:
        """Repairs truncated or malformed Mermaid markdown code."""
        if not mermaid_code:
            return f"```mermaid\nflowchart {orientation}\n    A[\"Start\"] --> B[\"Process\"]\n```"

        code = mermaid_code.strip()
        if code.startswith("```mermaid"):
            code = code[len("```mermaid"):].strip()
        elif code.startswith("```"):
            code = code[len("```"):].strip()
        if code.endswith("```"):
            code = code[:-3].strip()

        # Unescape escaped characters and backslashes
        code = code.replace('\\"', '"').replace('\\n', '\n').replace('\\', '')
        # Replace & with and to protect parser
        code = code.replace(' & ', ' and ').replace('&', ' and ')
        # Replace slashes in text
        code = re.sub(r'(?<=\w)/(?=\w)', ' - ', code)

        # Ensure flowchart or graph declaration
        if not re.search(r'^(?:flowchart|graph)\s+[A-Za-z]+', code, flags=re.MULTILINE):
            code = f"flowchart {orientation}\n" + code

        # Close any unclosed node brackets
        lines = code.split("\n")
        fixed_lines = []
        for line in lines:
            l = line
            if '{"' in l and '"}' not in l and '}}' not in l:
                l = l.rstrip() + '"}'
            elif '["' in l and '"]' not in l and ']' not in l:
                l = l.rstrip() + '"]'
            elif '(("' in l and '"))' not in l:
                l = l.rstrip() + '"))'
            fixed_lines.append(l)

        joined = "\n".join(fixed_lines)
        subgraph_count = len(re.findall(r'\bsubgraph\b', joined, flags=re.IGNORECASE))
        end_count = len(re.findall(r'\bend\b', joined, flags=re.IGNORECASE))
        if subgraph_count > end_count:
            for _ in range(subgraph_count - end_count):
                joined += "\n    end"

        return f"```mermaid\n{joined}\n```"

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
        A["Raw Documents and Notes"] --> B["Document Chunking - Sentence Aware"]
        B --> C["Embedding Model - Vector Encoding"]
        C --> D[("Vector Database - Chroma Index")]
    end

    subgraph Retrieval_Phase ["Phase 2: Semantic Retrieval"]
        E["Student Submits Query"] --> F["Generate Query Embedding"]
        F --> G["Vector Similarity Search - Cosine or HNSW"]
        D -.-> G
        G --> H{{"Sufficient Relevance - Score above Threshold?"}}
        H -->|Yes| I["Top-K Relevant Chunks Selected"]
        H -->|No| J["Query Expansion or Fallback"]
        J --> G
    end

    subgraph Generation_Phase ["Phase 3: Augmented Generation"]
        I --> K["Prompt Synthesis Engine"]
        E -.->|Original Query| K
        K --> L["LLM - Context and Instructions"]
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
    A["CPU Issues Logical or Virtual Address"] --> B["Extract VPN and Offset"]
    B --> C{{"TLB Cache Lookup"}}
    
    C -->|TLB Hit - Fast Path| D["Retrieve Physical Frame Number"]
    D --> E["Calculate Physical Address: PFN plus Offset"]
    E --> F["Access Physical RAM"]
    
    C -->|TLB Miss - Slow Path| G["Page Table Walk - CR3 Register"]
    G --> H{{"Present Bit equals 1 in Page Table?"}}
    
    H -->|Yes - In Memory| I["Update TLB with Mapping"]
    I --> D
    
    H -->|No - Page Fault| J["Hardware Interrupt: Page Fault Exception"]
    J --> K["OS Trap Handler: Allocate Free Frame"]
    K --> L["Read Page from Secondary Storage"]
    L --> M["Update Page Table Entry - Set Present Bit"]
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
    
    B -->|Yes| C["Allocate Resource to Process"]
    C --> D["Process Enters Critical Section"]
    D --> E["Release Resource and Signal Waiters"]
    
    B -->|No| F["Process Enters Waiting State - Hold and Wait"]
    F --> G{{"All 4 Coffman Conditions Active?"}}
    
    G -->|Yes: Coffman Cycle Formed| H["DEADLOCK STATE OCCURS"]
    H --> I["Deadlock Handling Strategy"]
    I --> J["Option 1: Deadlock Prevention - Break 1 Condition"]
    I --> K["Option 2: Bankers Algorithm - Safe State Check"]
    I --> L["Option 3: Detection and Recovery - Preempt or Kill"]
    
    G -->|No| M["Process Waits until Resource Released"]
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

        # 4. MCP (Model Context Protocol) Architecture Blueprint
        if any(w in t_lower for w in ["mcp", "model context protocol", "model context", "context protocol"]):
            mermaid = f"""```mermaid
flowchart {orientation}
    subgraph Host_Layer ["Phase 1: Host Application and Client Layer"]
        A["LLM Agent Runtime - ARIA"] --> B["MCP Client - Transport Manager"]
    end

    subgraph Protocol_Layer ["Phase 2: Protocol Exchange - JSON-RPC 2.0"]
        B --> C["JSON-RPC Request - tools call"]
        C --> D["Standard IO or SSE Transport Channel"]
    end

    subgraph Server_Execution ["Phase 3: FastMCP Server Execution"]
        D --> E{{"Tool Lookup and Sandbox Check"}}
        E -->|Authorized| F["Execute Deterministic Tool Function"]
        E -->|Unauthorized| G["Permission Denied or Error Trap"]
        F --> H["Format Structured JSON-RPC Response"]
    end

    subgraph Synthesis_Layer ["Phase 4: Output Synthesis and Rendering"]
        H --> I["Deliver Structured Tool Output to Agent State"]
        I --> J["Agent Synthesizes Grounded Pedagogical UI"]
    end
```"""
            return {
                "title": "Model Context Protocol (MCP) Architectural Workflow",
                "mermaid_markdown": mermaid,
                "steps_walkthrough": [
                    {"step": 1, "phase": "Host Application", "component": "LLM Agent Runtime", "action": "Agent evaluates user request and determines MCP tool invocation requirements."},
                    {"step": 2, "phase": "Client Layer", "component": "MCP Client", "action": "Encapsulates request payload and parameters into standard JSON-RPC 2.0 format."},
                    {"step": 3, "phase": "Protocol Layer", "component": "Transport Channel", "action": "Streams JSON-RPC message over standard I/O (stdio) or Server-Sent Events (SSE)."},
                    {"step": 4, "phase": "Server Gate", "component": "FastMCP Registry", "action": "Validates tool permissions, parameter schema, and boundary conditions."},
                    {"step": 5, "phase": "Execution", "component": "Tool Sandbox", "action": "Executes target Python routine (e.g. Flowchart, Planner, RAG) with isolated state."},
                    {"step": 6, "phase": "Delivery", "component": "Response Dispatcher", "action": "Returns structured JSON output for state synthesis and interactive widget mounting."}
                ],
                "components": [
                    {"name": "Host Application (ARIA)", "role": "Cognitive Coordinator", "details": "Initiates intent routing, parameter binding, and response streaming."},
                    {"name": "MCP Client", "role": "Transport Manager", "details": "Maintains persistent session, capability negotiation, and JSON-RPC framing."},
                    {"name": "FastMCP Server", "role": "Tool Provider", "details": "Hosts secure, isolated tools and exposes standardized schemas over stdio/SSE."}
                ],
                "decision_points": [
                    {"condition": "Tool Lookup and Security Authorization", "outcome_yes": "Execute tool function in isolated sandbox", "outcome_no": "Emit permission denied or validation error"}
                ],
                "phases": [
                    {"phase_id": "host_layer", "title": "Host Application and Client Layer", "node_ids": ["A", "B"]},
                    {"phase_id": "protocol_layer", "title": "Protocol Exchange - JSON-RPC 2.0", "node_ids": ["C", "D"]},
                    {"phase_id": "server_execution", "title": "FastMCP Server Execution", "node_ids": ["E", "F", "G", "H"]},
                    {"phase_id": "synthesis_layer", "title": "Output Synthesis and Rendering", "node_ids": ["I", "J"]}
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
                chk_str = str(chk)
                # Strip XML tags like <context>, <source...>, </source>, </context>
                chk_str = re.sub(r'<[^>]+>', '', chk_str)
                # Strip untrusted notices and disclaimers
                chk_str = re.sub(r'(?i)untrusted\s+student\s+data\s+notice:?', '', chk_str)
                chk_str = re.sub(r'(?i)the\s+following\s+passages\s+are\s+student-provided.*?passages\.', '', chk_str)
                # Extract clean declarative sentences
                raw_sentences = re.split(r'(?<=[.!?])\s+', chk_str)
                for s in raw_sentences:
                    cleaned = s.strip()
                    cleaned_lower = cleaned.lower()
                    if (
                        len(cleaned.split()) >= 4 
                        and not cleaned.startswith("#")
                        and "passive factual data" not in cleaned_lower
                        and "untrusted" not in cleaned_lower
                    ):
                        sentences.append(cleaned)

        # Fallback default workflow stages if context is sparse
        if len(sentences) < 4:
            sentences = [
                f"Client submits execution or query request to {clean_topic}.",
                f"Gatekeeper validates parameters, authentication, and boundary conditions.",
                f"Core engine processes task and coordinates subsystem pipeline.",
                f"System verifies output integrity and applies state consistency checks.",
                f"Response dispatcher formats and returns final result to client."
            ]

        # Assemble Mermaid text with subgraphs and decision branch
        mermaid_code = (
            f"```mermaid\n"
            f"flowchart {orientation}\n"
            f'    subgraph Ingestion_Stage ["Stage 1: Request Ingestion"]\n'
            f'        A["Client - Input Trigger"] --> B["Parameter Parsing and Sanitization"]\n'
            f'    end\n\n'
            f'    subgraph Processing_Stage ["Stage 2: Core {clean_topic} Pipeline"]\n'
            f'        B --> C{{"Boundary and Invariant Check"}}\n'
            f'        C -->|Valid| D["Core State Transition and Logic"]\n'
            f'        C -->|Invalid| E["Exception Handling and Rollback"]\n'
            f'        D --> F["Subsystem Synchronization"]\n'
            f'    end\n\n'
            f'    subgraph Output_Stage ["Stage 3: Result Delivery"]\n'
            f'        F --> G["Final State Verification and Response Dispatch"]\n'
            f'    end\n'
            f"```"
        )

        steps = [
            {"step": 1, "phase": "Ingestion", "component": "Input Trigger", "action": f"Client initiates request and parameters are parsed for {clean_topic}."},
            {"step": 2, "phase": "Validation", "component": "Verification Gate", "action": "Validates boundary constraints and preconditions before execution."},
            {"step": 3, "phase": "Core Processing", "component": f"{clean_topic} Engine", "action": "Executes primary state transitions, logic algorithms, and handoffs."},
            {"step": 4, "phase": "Synchronization", "component": "State Coordinator", "action": "Ensures memory isolation, subsystem consistency, and data integrity."},
            {"step": 5, "phase": "Delivery", "component": "Response Dispatcher", "action": "Formats final verified execution state and completes the workflow."}
        ]

        return {
            "title": f"{clean_topic} Architectural Workflow & Execution Pipeline",
            "mermaid_markdown": mermaid_code,
            "steps_walkthrough": steps,
            "components": [
                {"name": f"{clean_topic} Engine", "role": "Primary Processor", "details": f"Coordinates computational logic and state transitions for {clean_topic}."},
                {"name": "Verification Gate", "role": "Integrity Check", "details": "Ensures all preconditions and security boundaries are satisfied."},
                {"name": "State Coordinator", "role": "Subsystem Sync", "details": "Manages resource isolation and cross-component consistency."}
            ],
            "decision_points": [
                {"condition": "Boundary & Invariant Check", "outcome_yes": "Proceed to core execution pipeline", "outcome_no": "Trigger exception handler and safe rollback"}
            ],
            "phases": [
                {"phase_id": "ingestion", "title": "Request Ingestion", "node_ids": ["A", "B"]},
                {"phase_id": "processing", "title": "Core Pipeline", "node_ids": ["C", "D", "E", "F"]},
                {"phase_id": "output", "title": "Result Delivery", "node_ids": ["G"]}
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
        and automatically extracts walkthrough steps and decision points.
        """
        if not self.llm_adapter:
            return None

        ctx_text = "\n---\n".join(context_chunks[:3]) if context_chunks else "General academic knowledge context."

        prompt = (
            f"You are ARIA's Specialized Flowchart and Architecture Engine.\n"
            f"Generate a comprehensive, pedagogical step-by-step flowchart and workflow for the topic: '{topic}'.\n"
            f"Context Notes:\n{ctx_text}\n\n"
            f"Requirements:\n"
            f"1. Generate valid, clean Mermaid markdown syntax (flowchart {orientation}).\n"
            f"2. Use subgraphs for distinct phases (e.g. Ingestion, Processing, Output).\n"
            f"3. Use double quotes inside node brackets like: A[\"Node Label\"] or B{{\"Decision Query?\"}}.\n"
            f"4. Do NOT use '&' or '/' or unescaped symbols inside labels (use 'and', 'or', '-').\n"
            f"5. Detail 'what happens when' across sequential steps with decision branches like: B -->|Yes| C.\n"
            f"6. Output STRICTLY a valid, concise JSON object with schema:\n"
            f"{{\n"
            f'  "title": "Exact descriptive title of the flowchart",\n'
            f'  "mermaid_markdown": "```mermaid\\nflowchart {orientation}\\n...\\n```"\n'
            f"}}"
        )

        try:
            raw_response = self.llm_adapter(prompt, {"temperature": 0.2, "max_tokens": 700})
            if not raw_response or not raw_response.strip():
                return None

            # Extract JSON block
            json_text = raw_response.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()

            raw_mermaid = ""
            extracted_title = f"{topic} Architecture Flow"

            try:
                parsed = json.loads(json_text)
                if "mermaid_markdown" in parsed:
                    raw_mermaid = str(parsed["mermaid_markdown"]).strip()
                if "title" in parsed and parsed["title"]:
                    extracted_title = str(parsed["title"]).strip()
            except Exception:
                pass

            if not raw_mermaid:
                m_match = re.search(r'((?:flowchart|graph)\s+(?:TD|LR|TB|BT|RL)[\s\S]+?)(?:```|\"}|$)', raw_response, flags=re.IGNORECASE)
                if m_match and "-->" in m_match.group(1):
                    raw_mermaid = m_match.group(1).replace('\\n', '\n').replace('\\"', '"').strip()
                t_match = re.search(r'"title":\s*"([^"]+)"', raw_response)
                if t_match and "Exact descriptive" not in t_match.group(1):
                    extracted_title = t_match.group(1).strip()

            if not raw_mermaid or "-->" not in raw_mermaid:
                return None

            repaired_mermaid = self._repair_mermaid_syntax(raw_mermaid, orientation=orientation)
            meta = extract_flowchart_metadata(repaired_mermaid, topic=topic)

            return {
                "title": extracted_title,
                "mermaid_markdown": repaired_mermaid,
                "steps_walkthrough": meta["steps_walkthrough"],
                "components": meta["components"],
                "decision_points": meta["decision_points"],
                "phases": meta["phases"]
            }
        except Exception:
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
        3. Falls back to domain-aware sequential synthesis.
        """
        clean_topic = clean_topic_title(topic)

        # Normalize text chunks
        raw_chunks: List[str] = []
        if context_chunks:
            for c in context_chunks:
                if isinstance(c, dict):
                    raw_chunks.append(str(c.get("text", "")))
                elif isinstance(c, str):
                    raw_chunks.append(c)

        # 1. Try curated blueprint first for highest educational precision
        blueprint = self._get_curated_blueprint(clean_topic, orientation=orientation)

        # 2. Try LLM enrichment if no curated blueprint
        llm_data: Optional[Dict[str, Any]] = None
        if not blueprint and self.llm_adapter:
            llm_data = self._call_llm_flowchart(clean_topic, raw_chunks, orientation, detail_level)

        data = blueprint or llm_data or self._generate_generic_flowchart(clean_topic, raw_chunks, orientation)

        summary = (
            f"Generated architectural flowchart for '{clean_topic}' featuring "
            f"{len(data.get('steps_walkthrough', []))} chronological steps, "
            f"{len(data.get('components', []))} key components, and "
            f"{len(data.get('decision_points', []))} decision points."
        )

        res = FlowchartResult(
            status="success",
            topic=clean_topic,
            title=data.get("title", f"{clean_topic} Architecture Flow"),
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
