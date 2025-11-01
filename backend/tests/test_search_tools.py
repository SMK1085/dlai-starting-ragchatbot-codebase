"""Tests for search_tools.py - CourseSearchTool and ToolManager"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test suite for CourseSearchTool"""

    def test_get_tool_definition(self, mock_vector_store):
        """Test that tool definition is correctly structured"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert definition["input_schema"]["type"] == "object"
        assert "query" in definition["input_schema"]["properties"]
        assert "course_name" in definition["input_schema"]["properties"]
        assert "lesson_number" in definition["input_schema"]["properties"]
        assert definition["input_schema"]["required"] == ["query"]

    def test_execute_with_query_only(self, mock_vector_store, sample_search_results):
        """Test execute with only query parameter (no filters)"""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="what are resources")

        # Verify search was called with correct parameters
        mock_vector_store.search.assert_called_once_with(
            query="what are resources", course_name=None, lesson_number=None
        )

        # Verify result contains expected content
        assert "Introduction to Model Context Protocol" in result
        assert "Resources are entities in MCP" in result
        assert "Lesson 2" in result

    def test_execute_with_course_filter(self, mock_vector_store, sample_search_results):
        """Test execute with course_name filter"""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(
            query="what are resources", course_name="Introduction to Model Context Protocol"
        )

        # Verify search was called with course filter
        mock_vector_store.search.assert_called_once_with(
            query="what are resources",
            course_name="Introduction to Model Context Protocol",
            lesson_number=None,
        )

        assert "Introduction to Model Context Protocol" in result

    def test_execute_with_lesson_filter(self, mock_vector_store, sample_search_results):
        """Test execute with lesson_number filter"""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="what are resources", lesson_number=2)

        # Verify search was called with lesson filter
        mock_vector_store.search.assert_called_once_with(
            query="what are resources", course_name=None, lesson_number=2
        )

        assert "Lesson 2" in result

    def test_execute_with_both_filters(self, mock_vector_store, sample_search_results):
        """Test execute with both course_name and lesson_number filters"""
        mock_vector_store.search.return_value = sample_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(
            query="what are resources",
            course_name="Introduction to Model Context Protocol",
            lesson_number=2,
        )

        # Verify search was called with both filters
        mock_vector_store.search.assert_called_once_with(
            query="what are resources",
            course_name="Introduction to Model Context Protocol",
            lesson_number=2,
        )

        assert "Introduction to Model Context Protocol" in result
        assert "Lesson 2" in result

    def test_execute_with_empty_results(self, mock_vector_store, empty_search_results):
        """Test execute when search returns no results"""
        mock_vector_store.search.return_value = empty_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_with_empty_results_and_filters(self, mock_vector_store, empty_search_results):
        """Test execute when search returns no results with filters"""
        mock_vector_store.search.return_value = empty_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="nonexistent topic", course_name="MCP", lesson_number=5)

        assert "No relevant content found" in result
        assert "in course 'MCP'" in result
        assert "in lesson 5" in result

    def test_execute_with_search_error(self, mock_vector_store, error_search_results):
        """Test execute when vector store returns an error"""
        mock_vector_store.search.return_value = error_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test query")

        # Should return the error message
        assert "Search error" in result
        assert "ChromaDB connection failed" in result

    def test_execute_with_course_not_found_error(self, mock_vector_store):
        """Test execute when course is not found"""
        error_result = SearchResults.empty("No course found matching 'NonexistentCourse'")
        mock_vector_store.search.return_value = error_result

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test query", course_name="NonexistentCourse")

        assert "No course found matching 'NonexistentCourse'" in result

    def test_format_results(self, mock_vector_store, sample_search_results):
        """Test that _format_results correctly formats search results"""
        mock_vector_store.get_lesson_link.return_value = "https://example.com/mcp/lesson2"

        tool = CourseSearchTool(mock_vector_store)
        formatted = tool._format_results(sample_search_results)

        # Check formatting
        assert "[Introduction to Model Context Protocol - Lesson 2]" in formatted
        assert "Resources are entities in MCP" in formatted

        # Check that documents are separated
        lines = formatted.split("\n\n")
        assert len(lines) == 2

    def test_last_sources_tracking(self, mock_vector_store, sample_search_results):
        """Test that last_sources are correctly tracked during execution"""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/mcp/lesson2"

        tool = CourseSearchTool(mock_vector_store)

        # Initially empty
        assert tool.last_sources == []

        # Execute search
        tool.execute(query="what are resources")

        # Should now have sources
        assert len(tool.last_sources) == 2
        assert tool.last_sources[0]["text"] == "Introduction to Model Context Protocol - Lesson 2"
        assert tool.last_sources[0]["link"] == "https://example.com/mcp/lesson2"

    def test_sources_include_lesson_links(self, mock_vector_store, sample_search_results):
        """Test that sources include lesson links when available"""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/mcp/lesson2"

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="what are resources")

        # Verify lesson link retrieval was called
        mock_vector_store.get_lesson_link.assert_called_with(
            "Introduction to Model Context Protocol", 2
        )

        # Verify links are in sources
        for source in tool.last_sources:
            assert source["link"] is not None


class TestCourseOutlineTool:
    """Test suite for CourseOutlineTool"""

    def test_get_tool_definition(self, mock_vector_store):
        """Test that tool definition is correctly structured"""
        tool = CourseOutlineTool(mock_vector_store)
        definition = tool.get_tool_definition()

        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert "input_schema" in definition
        assert "course_name" in definition["input_schema"]["properties"]
        assert definition["input_schema"]["required"] == ["course_name"]

    def test_execute_with_valid_course(self, mock_vector_store):
        """Test execute with a valid course name"""
        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="Introduction to Model Context Protocol")

        # Verify outline retrieval was called
        mock_vector_store.get_course_outline.assert_called_once_with(
            "Introduction to Model Context Protocol"
        )

        # Verify formatted output
        assert "Course: Introduction to Model Context Protocol" in result
        assert "Link: https://example.com/mcp" in result
        assert "Lessons:" in result
        assert "0. Introduction" in result
        assert "2. Resources" in result

    def test_execute_with_nonexistent_course(self, mock_vector_store):
        """Test execute when course is not found"""
        mock_vector_store.get_course_outline.return_value = None

        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="Nonexistent Course")

        assert "No course found matching 'Nonexistent Course'" in result

    def test_format_outline_without_link(self, mock_vector_store):
        """Test formatting outline when course has no link"""
        outline_without_link = {
            "course_title": "Test Course",
            "lessons": [{"lesson_number": 1, "lesson_title": "Lesson 1"}],
        }
        mock_vector_store.get_course_outline.return_value = outline_without_link

        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="Test Course")

        assert "Course: Test Course" in result
        assert "Link:" not in result
        assert "1. Lesson 1" in result

    def test_format_outline_without_lessons(self, mock_vector_store):
        """Test formatting outline when course has no lessons"""
        outline_without_lessons = {
            "course_title": "Empty Course",
            "course_link": "https://example.com/empty",
            "lessons": [],
        }
        mock_vector_store.get_course_outline.return_value = outline_without_lessons

        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_name="Empty Course")

        assert "Course: Empty Course" in result
        assert "No lessons found" in result


class TestToolManager:
    """Test suite for ToolManager"""

    def test_register_tool(self, mock_vector_store):
        """Test registering a tool"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)

        manager.register_tool(tool)

        assert "search_course_content" in manager.tools
        assert manager.tools["search_course_content"] == tool

    def test_register_multiple_tools(self, mock_vector_store):
        """Test registering multiple tools"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        outline_tool = CourseOutlineTool(mock_vector_store)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        assert len(manager.tools) == 2
        assert "search_course_content" in manager.tools
        assert "get_course_outline" in manager.tools

    def test_get_tool_definitions(self, mock_vector_store):
        """Test getting all tool definitions"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        outline_tool = CourseOutlineTool(mock_vector_store)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 2
        assert any(d["name"] == "search_course_content" for d in definitions)
        assert any(d["name"] == "get_course_outline" for d in definitions)

    def test_execute_tool(self, mock_vector_store, sample_search_results):
        """Test executing a tool by name"""
        mock_vector_store.search.return_value = sample_search_results

        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        result = manager.execute_tool("search_course_content", query="test query")

        assert "Introduction to Model Context Protocol" in result

    def test_execute_nonexistent_tool(self, mock_vector_store):
        """Test executing a tool that doesn't exist"""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "Tool 'nonexistent_tool' not found" in result

    def test_get_last_sources(self, mock_vector_store, sample_search_results):
        """Test getting sources from the last search"""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/mcp/lesson2"

        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        # Execute search
        manager.execute_tool("search_course_content", query="test query")

        # Get sources
        sources = manager.get_last_sources()

        assert len(sources) == 2
        assert sources[0]["text"] == "Introduction to Model Context Protocol - Lesson 2"
        assert sources[0]["link"] == "https://example.com/mcp/lesson2"

    def test_reset_sources(self, mock_vector_store, sample_search_results):
        """Test resetting sources"""
        mock_vector_store.search.return_value = sample_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/mcp/lesson2"

        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        # Execute search
        manager.execute_tool("search_course_content", query="test query")
        assert len(manager.get_last_sources()) > 0

        # Reset sources
        manager.reset_sources()
        assert len(manager.get_last_sources()) == 0

    def test_register_tool_without_name(self, mock_vector_store):
        """Test that registering a tool without a name raises an error"""
        manager = ToolManager()

        # Create a mock tool with no name in definition
        bad_tool = Mock()
        bad_tool.get_tool_definition.return_value = {"description": "Test"}

        with pytest.raises(ValueError, match="Tool must have a 'name'"):
            manager.register_tool(bad_tool)
