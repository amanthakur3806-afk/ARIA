"""
ARIA MCP Question Generator Tool Alias (questiongenerator.py)

Forwarding module to ensure both snake_case (question_generator.py)
and single-word (questiongenerator.py) imports function seamlessly.
"""

try:
    from .question_generator import (
        QuestionGeneratorResult,
        QuestionGeneratorTool,
        QuizQuestion,
        execute_question_generator_tool,
        get_question_generator_tool_spec,
    )
except ImportError:
    from question_generator import (
        QuestionGeneratorResult,
        QuestionGeneratorTool,
        QuizQuestion,
        execute_question_generator_tool,
        get_question_generator_tool_spec,
    )

__all__ = [
    "QuestionGeneratorResult",
    "QuestionGeneratorTool",
    "QuizQuestion",
    "execute_question_generator_tool",
    "get_question_generator_tool_spec",
]
