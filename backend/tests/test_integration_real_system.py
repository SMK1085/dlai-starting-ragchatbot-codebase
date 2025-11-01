"""Integration tests against the real system (not mocked)
These tests will use the actual API and database to identify real issues
"""

import sys
from pathlib import Path

import pytest

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import Config
from rag_system import RAGSystem


@pytest.mark.integration
class TestRealSystemIntegration:
    """Integration tests with real system components"""

    def test_system_initialization(self):
        """Test that the RAG system can initialize with real config"""
        try:
            config = Config()
            system = RAGSystem(config)

            print("\nInitialization successful!")
            print(f"API Key present: {bool(config.ANTHROPIC_API_KEY)}")
            print(f"ChromaDB path: {config.CHROMA_PATH}")
            print(f"Embedding model: {config.EMBEDDING_MODEL}")

            # Check if we have data
            analytics = system.get_course_analytics()
            print(f"Total courses in DB: {analytics['total_courses']}")
            print(f"Course titles: {analytics['course_titles']}")

            assert system is not None
            assert analytics["total_courses"] >= 0

        except Exception as e:
            pytest.fail(f"System initialization failed: {e}")

    def test_general_knowledge_query(self):
        """Test a general knowledge query (should not use tools)"""
        try:
            config = Config()
            system = RAGSystem(config)

            print("\n\nTesting general knowledge query...")
            response, sources = system.query("What is Python?")

            print(f"Response: {response[:200]}...")
            print(f"Sources: {sources}")

            assert response is not None
            assert len(response) > 0
            # General knowledge queries typically don't have sources
            assert isinstance(sources, list)

            print("✓ General knowledge query succeeded")

        except Exception as e:
            print("\n✗ General knowledge query failed!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")

            # Print full traceback for diagnosis
            import traceback

            traceback.print_exc()

            pytest.fail(f"General knowledge query failed: {e}")

    def test_course_content_query(self):
        """Test a course content query (should use search tool)"""
        try:
            config = Config()
            system = RAGSystem(config)

            # First check if we have courses
            analytics = system.get_course_analytics()
            if analytics["total_courses"] == 0:
                pytest.skip("No courses in database to test with")

            print("\n\nTesting course content query...")
            print(f"Available courses: {analytics['course_titles']}")

            # Try a query about course content
            response, sources = system.query("What are resources in MCP?")

            print(f"Response: {response[:200]}...")
            print(f"Sources count: {len(sources)}")
            if sources:
                print(f"First source: {sources[0]}")

            assert response is not None
            assert len(response) > 0
            # Course content queries should have sources if found
            assert isinstance(sources, list)

            print("✓ Course content query succeeded")

        except Exception as e:
            print("\n✗ Course content query FAILED!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")

            # Print full traceback for diagnosis
            import traceback

            traceback.print_exc()

            # This is the critical failure we're investigating
            pytest.fail(f"Course content query failed: {e}")

    def test_search_tool_directly(self):
        """Test the search tool directly to isolate issues"""
        try:
            config = Config()
            system = RAGSystem(config)

            # Get the search tool
            search_tool = system.search_tool

            print("\n\nTesting search tool directly...")

            # Test without filters
            result = search_tool.execute(query="resources in MCP")

            print(f"Search result: {result[:200]}...")

            assert result is not None
            assert isinstance(result, str)

            print("✓ Direct search tool test succeeded")

        except Exception as e:
            print("\n✗ Direct search tool test FAILED!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")

            import traceback

            traceback.print_exc()

            pytest.fail(f"Direct search tool test failed: {e}")

    def test_ai_generator_without_tools(self):
        """Test AI generator directly without tools"""
        try:
            config = Config()

            # Import and test AI generator directly
            from ai_generator import AIGenerator

            print("\n\nTesting AI generator without tools...")

            ai = AIGenerator(config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL)

            response = ai.generate_response(
                query="What is 2+2?", conversation_history=None, tools=None, tool_manager=None
            )

            print(f"Response: {response}")

            assert response is not None
            assert len(response) > 0

            print("✓ AI generator test succeeded")

        except Exception as e:
            print("\n✗ AI generator test FAILED!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")

            import traceback

            traceback.print_exc()

            pytest.fail(f"AI generator test failed: {e}")

    def test_ai_generator_with_tools(self):
        """Test AI generator with tools"""
        try:
            config = Config()
            system = RAGSystem(config)

            print("\n\nTesting AI generator with tools...")

            # Check if we have data
            analytics = system.get_course_analytics()
            if analytics["total_courses"] == 0:
                pytest.skip("No courses in database to test with")

            response = system.ai_generator.generate_response(
                query="What are resources in MCP?",
                conversation_history=None,
                tools=system.tool_manager.get_tool_definitions(),
                tool_manager=system.tool_manager,
            )

            print(f"Response: {response[:200]}...")

            assert response is not None
            assert len(response) > 0

            print("✓ AI generator with tools test succeeded")

        except Exception as e:
            print("\n✗ AI generator with tools test FAILED!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")

            import traceback

            traceback.print_exc()

            pytest.fail(f"AI generator with tools test failed: {e}")
