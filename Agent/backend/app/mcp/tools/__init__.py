"""
ARIA MCP Tools Package (Agent/backend/app/mcp/tools)

This package contains the core Model Context Protocol (MCP) tool implementations for ARIA:
1. plannertool.py: Systematic answer generation, tone adaptation, and study/revision planning.
2. flashcard.py: Extraction of high-yield topics from chunks and polishing into active-recall flashcards.
3. question_generator.py: Random topic sampling, multiple-choice question generation with 'question' and 'options' JSON output.
4. flowchart.py: Markdown Mermaid flowchart creation, step-by-step walkthroughs, and architecture workflows.
"""

try:
    from .flashcard import (
        Flashcard,
        FlashcardGeneratorTool,
        FlashcardSetResult,
        execute_flashcard_tool,
        get_flashcard_tool_spec,
    )
    from .flowchart import (
        FlowchartEdge,
        FlowchartGeneratorTool,
        FlowchartNode,
        FlowchartPhase,
        FlowchartResult,
        execute_flowchart_tool,
        get_flowchart_tool_spec,
    )
    from .plannertool import (
        PlannerOutput,
        PlannerTool,
        StudyPhase,
        StudyPlan,
        ToneType,
        execute_planner_tool,
        get_planner_tool_spec,
    )
    from .question_generator import (
        QuestionGeneratorResult,
        QuestionGeneratorTool,
        QuizQuestion,
        execute_question_generator_tool,
        get_question_generator_tool_spec,
    )
except ImportError:
    from flashcard import (
        Flashcard,
        FlashcardGeneratorTool,
        FlashcardSetResult,
        execute_flashcard_tool,
        get_flashcard_tool_spec,
    )
    from flowchart import (
        FlowchartEdge,
        FlowchartGeneratorTool,
        FlowchartNode,
        FlowchartPhase,
        FlowchartResult,
        execute_flowchart_tool,
        get_flowchart_tool_spec,
    )
    from plannertool import (
        PlannerOutput,
        PlannerTool,
        StudyPhase,
        StudyPlan,
        ToneType,
        execute_planner_tool,
        get_planner_tool_spec,
    )
    from question_generator import (
        QuestionGeneratorResult,
        QuestionGeneratorTool,
        QuizQuestion,
        execute_question_generator_tool,
        get_question_generator_tool_spec,
    )

# Registry of all MCP tool specs and handlers for server registration
MCP_TOOLS_REGISTRY = {
    PlannerTool.TOOL_NAME: {
        "spec": get_planner_tool_spec(),
        "handler": execute_planner_tool,
        "class": PlannerTool,
    },
    FlashcardGeneratorTool.TOOL_NAME: {
        "spec": get_flashcard_tool_spec(),
        "handler": execute_flashcard_tool,
        "class": FlashcardGeneratorTool,
    },
    QuestionGeneratorTool.TOOL_NAME: {
        "spec": get_question_generator_tool_spec(),
        "handler": execute_question_generator_tool,
        "class": QuestionGeneratorTool,
    },
    FlowchartGeneratorTool.TOOL_NAME: {
        "spec": get_flowchart_tool_spec(),
        "handler": execute_flowchart_tool,
        "class": FlowchartGeneratorTool,
    },
}


def get_all_tool_specs():
    """Returns a list of all tool specifications for MCP server registration."""
    return [info["spec"] for info in MCP_TOOLS_REGISTRY.values()]


__all__ = [
    # Planner Tool
    "PlannerTool",
    "PlannerOutput",
    "StudyPlan",
    "StudyPhase",
    "ToneType",
    "execute_planner_tool",
    "get_planner_tool_spec",
    # Flashcard Tool
    "FlashcardGeneratorTool",
    "Flashcard",
    "FlashcardSetResult",
    "execute_flashcard_tool",
    "get_flashcard_tool_spec",
    # Question Generator Tool
    "QuestionGeneratorTool",
    "QuizQuestion",
    "QuestionGeneratorResult",
    "execute_question_generator_tool",
    "get_question_generator_tool_spec",
    # Flowchart Tool
    "FlowchartGeneratorTool",
    "FlowchartResult",
    "FlowchartNode",
    "FlowchartEdge",
    "FlowchartPhase",
    "execute_flowchart_tool",
    "get_flowchart_tool_spec",
    # Registry
    "MCP_TOOLS_REGISTRY",
    "get_all_tool_specs",
]
