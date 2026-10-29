"""
ARIA MCP Server (server.py)

FastMCP-based Model Context Protocol server exposing ARIA study tools:
1. planner_tool: Systematic answers, tone adaptation, and revision plans.
2. flashcard_generator: Topic extraction and polished active-recall flashcards.
3. question_generator: Random topic sampling and multiple-choice questions (max 10) in JSON.
4. rag_search: Semantic retrieval across ingested academic course notes.

Includes support for visual inspection using MCP Inspector (`--inspector`)
and running comprehensive benchmarks across the 5 dimensions (`--test`).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resolve FastMCP with support across fastmcp, mcp SDK, and fallback
try:
    from fastmcp import FastMCP
except Exception:
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        try:
            from mcp.server.mcpserver import MCPServer as FastMCP
        except Exception:
            class FastMCP:
                def __init__(self, name: str = "", instructions: str = "", **kwargs):
                    self.name = name
                    self.instructions = instructions
                def tool(self, *args, **kwargs):
                    def decorator(fn):
                        return fn
                    return decorator
                def run(self, *args, **kwargs):
                    pass

# Ensure project paths are in sys.path (append to avoid shadowing top-level packages)
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_APP_DIR = CURRENT_DIR.parent.parent
if str(BACKEND_APP_DIR) not in sys.path:
    sys.path.append(str(BACKEND_APP_DIR))

# Import existing tools from app.mcp.tools
try:
    from app.mcp.tools import (
        execute_flashcard_tool,
        execute_planner_tool,
        execute_flowchart_tool,
        execute_question_generator_tool,
    )
except ImportError:
    try:
        from mcp.tools import (
            execute_flashcard_tool,
            execute_planner_tool,
        execute_flowchart_tool,
            execute_question_generator_tool,
        )
    except ImportError:
        from ..tools import (
            execute_flashcard_tool,
            execute_planner_tool,
        execute_flowchart_tool,
            execute_question_generator_tool,
        )


def create_mcp_server(name: str = "aria-study-companion") -> FastMCP:
    """
    Constructs and configures the FastMCP server instance, registering the
    underlying study tools without redefining their logic.
    """
    server = FastMCP(
        name=name,
        instructions=(
            "ARIA MCP Server: AI Revision & Intelligent Assistance study tools. "
            "Provides planning, active-recall flashcard generation, and quiz questions."
        )
    )

    # 1. Register Planner Tool
    @server.tool(
        name="planner_tool",
        description=(
            "Answers user queries systematically with human-like pedagogical clarity, "
            "adapts tone (empathic_tutor, concise_exam, technical_academic, socratic, simple_analogy), "
            "and generates a structured study and revision plan."
        )
    )
    def planner_tool(
        query: str,
        tone: Optional[str] = None,
        target_duration_minutes: int = 45,
        context_chunks: Optional[List[str]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call existing planner tool logic."""
        return execute_planner_tool(
            query=query,
            tone=tone,
            context_chunks=context_chunks,
            target_duration_minutes=target_duration_minutes,
            user_preferences=user_preferences
        )

    # 2. Register Flashcard Generator Tool
    @server.tool(
        name="flashcard_generator",
        description=(
            "Extracts relevant topics from study chunks and polishes them into "
            "high-retention active-recall flashcards with cross-chunk context enrichment."
        )
    )
    def flashcard_generator(
        chunks: List[Any],
        topic_filter: Optional[str] = None,
        count: int = 5,
        difficulty: str = "all",
        card_format: str = "mixed",
    ) -> Dict[str, Any]:
        """Call existing flashcard generator tool logic."""
        return execute_flashcard_tool(
            chunks=chunks,
            topic_filter=topic_filter,
            count=count,
            difficulty=difficulty,
            card_format=card_format
        )

    # 3. Register Question Generator Tool
    @server.tool(
        name="question_generator",
        description=(
            "Finds topics across study chunks (with random sampling), formulates questions and "
            "answer options, and outputs up to 10 questions in JSON with 'question' and 'options'."
        )
    )
    def question_generator(
        chunks: List[Any],
        num_questions: int = 5,
        randomize_topics: bool = True,
        difficulty: str = "all",
        topic_focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call existing question generator tool logic."""
        return execute_question_generator_tool(
            chunks=chunks,
            num_questions=num_questions,
            randomize_topics=randomize_topics,
            difficulty=difficulty,
            topic_focus=topic_focus
        )

    # 4. Register Flowchart Generator Tool
    @server.tool(
        name="flowchart_generator",
        description=(
            "Generates systematic, step-by-step academic flowcharts and architectural workflows "
            "in Markdown Mermaid syntax, explaining what happens when, component interactions, "
            "decision branches, and enriched with LLM knowledge."
        )
    )
    def flowchart_generator(
        topic: str,
        context_chunks: Optional[List[Any]] = None,
        orientation: str = "TD",
        detail_level: str = "detailed",
    ) -> Dict[str, Any]:
        """Call existing flowchart generator tool logic."""
        return execute_flowchart_tool(
            topic=topic,
            context_chunks=context_chunks,
            orientation=orientation,
            detail_level=detail_level
        )

    return server


# Default singleton server instance
mcp_server = create_mcp_server()


def print_inspector_guide(server_script_path: str):
    """Prints clear guidance on how to debug this server with MCP Inspector."""
    guide = f"""
================================================================================
                    ARIA MCP SERVER — MCP INSPECTOR GUIDE
================================================================================
To debug and interactively test ARIA's MCP tools using the visual MCP Inspector:

Run the following command in your terminal:
  npx @modelcontextprotocol/inspector python "{server_script_path}"

This will automatically:
  1. Launch the MCP Inspector web UI at http://localhost:5173
  2. Connect to this ARIA FastMCP server over standard I/O (stdio)
  3. Display interactive test consoles for:
     • planner_tool
     • flashcard_generator
     • question_generator
  4. Allow you to inspect JSON schemas, test arguments, and view formatted responses.
================================================================================
"""
    print(guide)


def run_server(
    transport: str = "stdio",
    inspector_mode: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000
):
    """Runs the ARIA FastMCP server with the specified transport."""
    server_path = str(Path(__file__).resolve())

    if inspector_mode:
        print_inspector_guide(server_path)
        transport = "stdio"

    if transport == "stdio":
        mcp_server.run(transport="stdio")
    else:
        mcp_server.run(transport=transport, host=host, port=port)


def main():
    """CLI entrypoint for running, testing, or inspecting the ARIA MCP server."""
    parser = argparse.ArgumentParser(description="ARIA FastMCP Server")
    parser.add_argument(
        "--inspector",
        action="store_true",
        help="Print MCP Inspector debug instructions and start stdio transport for the inspector."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the comprehensive 5-dimension test suite (Language, Latency, Logic, Chunking, LLM)."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport type (default: stdio)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host address for HTTP/SSE transport.")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP/SSE transport.")

    args = parser.parse_args()

    if args.test:
        from app.agent.communication_agent import run_all_tests
        run_all_tests()
    else:
        run_server(
            transport=args.transport,
            inspector_mode=args.inspector,
            host=args.host,
            port=args.port
        )


if __name__ == "__main__":
    main()
