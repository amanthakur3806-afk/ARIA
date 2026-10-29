"""
ARIA MCP Package (Agent/backend/app/mcp)

Exposes the FastMCP server and study tools:
- Planner Tool: Systematic answers, tone adaptation, and revision plans
- Flashcard Generator: Topic extraction and active-recall flashcards
- Question Generator: Topic sampling and multiple-choice questions (max 10)
- Flowchart Generator: Markdown Mermaid diagrams and step-by-step walkthroughs
"""

from .tools import (
    PlannerTool,
    FlashcardGeneratorTool,
    QuestionGeneratorTool,
    FlowchartGeneratorTool,
    execute_planner_tool,
    execute_flashcard_tool,
    execute_question_generator_tool,
    execute_flowchart_tool,
    MCP_TOOLS_REGISTRY,
    get_all_tool_specs,
)
from .server import create_mcp_server, mcp_server

__all__ = [
    "PlannerTool",
    "FlashcardGeneratorTool",
    "QuestionGeneratorTool",
    "FlowchartGeneratorTool",
    "execute_planner_tool",
    "execute_flashcard_tool",
    "execute_question_generator_tool",
    "execute_flowchart_tool",
    "MCP_TOOLS_REGISTRY",
    "get_all_tool_specs",
    "create_mcp_server",
    "mcp_server",
]
