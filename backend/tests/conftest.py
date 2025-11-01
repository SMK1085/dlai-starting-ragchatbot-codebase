"""Shared pytest fixtures for testing the RAG chatbot system"""

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock

import pytest

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from models import Course, CourseChunk, Lesson
from vector_store import SearchResults


@pytest.fixture
def sample_courses() -> List[Course]:
    """Sample course data for testing"""
    return [
        Course(
            title="Introduction to Model Context Protocol",
            course_link="https://example.com/mcp",
            instructor="Test Instructor",
            lessons=[
                Lesson(
                    lesson_number=0,
                    title="Introduction",
                    lesson_link="https://example.com/mcp/lesson0",
                ),
                Lesson(
                    lesson_number=1,
                    title="Getting Started",
                    lesson_link="https://example.com/mcp/lesson1",
                ),
                Lesson(
                    lesson_number=2,
                    title="Resources",
                    lesson_link="https://example.com/mcp/lesson2",
                ),
            ],
        ),
        Course(
            title="Building Towards Computer Use",
            course_link="https://example.com/computer-use",
            instructor="Test Instructor 2",
            lessons=[
                Lesson(
                    lesson_number=0,
                    title="Introduction",
                    lesson_link="https://example.com/cu/lesson0",
                ),
                Lesson(
                    lesson_number=1,
                    title="Fundamentals",
                    lesson_link="https://example.com/cu/lesson1",
                ),
            ],
        ),
    ]


@pytest.fixture
def sample_course_chunks() -> List[CourseChunk]:
    """Sample course chunks for testing"""
    return [
        CourseChunk(
            content="Resources are entities in MCP that servers can provide to clients. They represent data sources or content.",
            course_title="Introduction to Model Context Protocol",
            lesson_number=2,
            chunk_index=0,
        ),
        CourseChunk(
            content="MCP servers can expose multiple resources, each with a unique URI and metadata.",
            course_title="Introduction to Model Context Protocol",
            lesson_number=2,
            chunk_index=1,
        ),
        CourseChunk(
            content="Computer use enables AI systems to interact with software interfaces through visual understanding.",
            course_title="Building Towards Computer Use",
            lesson_number=1,
            chunk_index=0,
        ),
    ]


@pytest.fixture
def sample_search_results() -> SearchResults:
    """Sample search results with documents and metadata"""
    return SearchResults(
        documents=[
            "Resources are entities in MCP that servers can provide to clients. They represent data sources or content.",
            "MCP servers can expose multiple resources, each with a unique URI and metadata.",
        ],
        metadata=[
            {
                "course_title": "Introduction to Model Context Protocol",
                "lesson_number": 2,
                "chunk_index": 0,
            },
            {
                "course_title": "Introduction to Model Context Protocol",
                "lesson_number": 2,
                "chunk_index": 1,
            },
        ],
        distances=[0.2, 0.3],
        error=None,
    )


@pytest.fixture
def empty_search_results() -> SearchResults:
    """Empty search results for testing no-results scenarios"""
    return SearchResults(documents=[], metadata=[], distances=[], error=None)


@pytest.fixture
def error_search_results() -> SearchResults:
    """Search results with error for testing error handling"""
    return SearchResults.empty("Search error: ChromaDB connection failed")


@pytest.fixture
def mock_vector_store(sample_search_results, sample_courses):
    """Mock VectorStore for testing"""
    mock_store = Mock()

    # Default successful search
    mock_store.search.return_value = sample_search_results

    # Mock course outline
    mock_store.get_course_outline.return_value = {
        "course_title": "Introduction to Model Context Protocol",
        "course_link": "https://example.com/mcp",
        "lessons": [
            {"lesson_number": 0, "lesson_title": "Introduction"},
            {"lesson_number": 1, "lesson_title": "Getting Started"},
            {"lesson_number": 2, "lesson_title": "Resources"},
        ],
    }

    # Mock lesson link retrieval
    mock_store.get_lesson_link.return_value = "https://example.com/mcp/lesson2"

    return mock_store


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing AI generation"""
    mock_client = Mock()

    # Default response without tool use
    mock_response = Mock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [Mock(type="text", text="This is a test response from Claude.")]

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_anthropic_tool_use_response():
    """Mock Anthropic response that triggers tool use"""
    mock_response = Mock()
    mock_response.stop_reason = "tool_use"

    # Text block
    text_block = Mock()
    text_block.type = "text"
    text_block.text = "I'll search for information about resources in MCP."

    # Tool use block
    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_use_123"
    tool_block.name = "search_course_content"
    tool_block.input = {
        "query": "resources in MCP",
        "course_name": "Introduction to Model Context Protocol",
    }

    mock_response.content = [text_block, tool_block]

    return mock_response


@pytest.fixture
def mock_anthropic_final_response():
    """Mock Anthropic final response after tool execution"""
    mock_response = Mock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [
        Mock(
            type="text",
            text="Based on the course content, resources are entities in MCP that servers can provide to clients.",
        )
    ]

    return mock_response


@pytest.fixture
def mock_anthropic_second_tool_use_response():
    """Mock Anthropic response for second round of tool use"""
    mock_response = Mock()
    mock_response.stop_reason = "tool_use"

    # Text block
    text_block = Mock()
    text_block.type = "text"
    text_block.text = "Let me search for prompts as well."

    # Tool use block for second search
    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_use_456"
    tool_block.name = "search_course_content"
    tool_block.input = {
        "query": "prompts in MCP",
        "course_name": "Introduction to Model Context Protocol",
    }

    mock_response.content = [text_block, tool_block]

    return mock_response


@pytest.fixture
def sample_tool_definitions() -> List[Dict[str, Any]]:
    """Sample tool definitions for testing"""
    return [
        {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work)",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within",
                    },
                },
                "required": ["query"],
            },
        }
    ]


@pytest.fixture
def mock_tool_manager(sample_tool_definitions):
    """Mock ToolManager for testing"""
    mock_manager = Mock()

    # Mock tool definitions
    mock_manager.get_tool_definitions.return_value = sample_tool_definitions

    # Mock tool execution
    mock_manager.execute_tool.return_value = "[Introduction to Model Context Protocol - Lesson 2]\nResources are entities in MCP that servers can provide to clients."

    # Mock sources
    mock_manager.get_last_sources.return_value = [
        {
            "text": "Introduction to Model Context Protocol - Lesson 2",
            "link": "https://example.com/mcp/lesson2",
        }
    ]

    mock_manager.reset_sources.return_value = None

    return mock_manager
