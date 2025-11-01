"""Tests for rag_system.py - End-to-end RAG system integration tests"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from rag_system import RAGSystem
from vector_store import SearchResults


@pytest.fixture
def mock_config():
    """Mock configuration object"""
    config = Mock()
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.CHROMA_PATH = "./test_chroma_db"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 5
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "test-model"
    config.MAX_HISTORY = 2
    return config


class TestRAGSystemInitialization:
    """Test RAG system initialization"""

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_initialization(
        self,
        mock_session_manager,
        mock_ai_generator,
        mock_vector_store,
        mock_doc_processor,
        mock_config
    ):
        """Test that RAG system initializes all components correctly"""
        system = RAGSystem(mock_config)

        # Verify all components were initialized
        assert system.document_processor is not None
        assert system.vector_store is not None
        assert system.ai_generator is not None
        assert system.session_manager is not None
        assert system.tool_manager is not None
        assert system.search_tool is not None
        assert system.outline_tool is not None

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_tools_registered(
        self,
        mock_session_manager,
        mock_ai_generator,
        mock_vector_store,
        mock_doc_processor,
        mock_config
    ):
        """Test that both search tools are registered"""
        system = RAGSystem(mock_config)

        # Check tools are registered
        tool_definitions = system.tool_manager.get_tool_definitions()
        assert len(tool_definitions) == 2

        tool_names = [tool["name"] for tool in tool_definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


class TestRAGSystemQuery:
    """Test RAG system query functionality"""

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_query_general_knowledge_no_tool_use(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test query for general knowledge (should not use tools)"""
        # Set up mocks
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Python is a programming language."
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query
        response, sources = system.query("What is Python?")

        # Verify AI was called
        mock_ai_instance.generate_response.assert_called_once()

        # Verify response
        assert response == "Python is a programming language."
        assert sources == []

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_query_course_content_with_tool_use(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test query for course content (should use tools and return sources)"""
        # Set up mocks
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Resources are entities in MCP."
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        mock_sources = [
            {
                "text": "Introduction to Model Context Protocol - Lesson 2",
                "link": "https://example.com/mcp/lesson2"
            }
        ]
        mock_tool_manager.get_last_sources.return_value = mock_sources

        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query
        response, sources = system.query("What are resources in MCP?")

        # Verify AI was called
        mock_ai_instance.generate_response.assert_called_once()

        # Verify tools were passed
        call_args = mock_ai_instance.generate_response.call_args
        assert call_args.kwargs["tools"] is not None
        assert call_args.kwargs["tool_manager"] is not None

        # Verify response and sources
        assert response == "Resources are entities in MCP."
        assert len(sources) == 1
        assert sources[0]["text"] == "Introduction to Model Context Protocol - Lesson 2"

        # Verify sources were reset after retrieval
        mock_tool_manager.reset_sources.assert_called_once()

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_query_with_session_id(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test query with session ID for conversation context"""
        # Set up mocks
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "It is a protocol."
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_history = "User: What is MCP?\nAssistant: MCP is Model Context Protocol."
        mock_session_instance.get_conversation_history.return_value = mock_history
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query with session
        session_id = "test-session-123"
        response, sources = system.query("Tell me more", session_id=session_id)

        # Verify history was retrieved
        mock_session_instance.get_conversation_history.assert_called_once_with(session_id)

        # Verify history was passed to AI
        call_args = mock_ai_instance.generate_response.call_args
        assert call_args.kwargs["conversation_history"] == mock_history

        # Verify exchange was added to history (original query, not wrapped prompt)
        mock_session_instance.add_exchange.assert_called_once_with(
            session_id,
            "Tell me more",
            "It is a protocol."
        )

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_query_without_session_id(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test query without session ID (no history)"""
        # Set up mocks
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Response"
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query without session
        response, sources = system.query("What is Python?")

        # Verify history was NOT retrieved
        mock_session_instance.get_conversation_history.assert_not_called()

        # Verify exchange was NOT added
        mock_session_instance.add_exchange.assert_not_called()

        # Verify AI was called with None history
        call_args = mock_ai_instance.generate_response.call_args
        assert call_args.kwargs["conversation_history"] is None


class TestRAGSystemErrorHandling:
    """Test error handling in RAG system"""

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_query_with_ai_api_error(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test that AI API errors propagate through query"""
        # Set up mocks
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.side_effect = Exception("API Error: Invalid API key")
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query - should raise exception
        with pytest.raises(Exception, match="API Error: Invalid API key"):
            system.query("Test query")

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_query_with_tool_execution_error(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test that tool execution errors propagate through query"""
        # Set up mocks
        mock_ai_instance = Mock()
        # Simulate tool execution error during generate_response
        mock_ai_instance.generate_response.side_effect = Exception("Tool execution failed")
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query - should raise exception
        with pytest.raises(Exception, match="Tool execution failed"):
            system.query("What are resources in MCP?")


class TestRAGSystemEndToEnd:
    """End-to-end integration tests simulating real workflow"""

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_complete_workflow_with_search(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config,
        sample_search_results
    ):
        """Test complete workflow: query → tool decision → search → synthesis"""
        # Set up mocks to simulate tool calling workflow
        mock_ai_instance = Mock()

        # Simulate: first call triggers tool use, second call returns final answer
        def ai_side_effect(*args, **kwargs):
            # If this is being called by tool handling, return final response
            # Otherwise, this simulates the tool calling flow internally
            return "Resources are entities in MCP that servers provide to clients."

        mock_ai_instance.generate_response.side_effect = ai_side_effect
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_instance

        # Set up vector store mock
        mock_vector_store_instance = Mock()
        mock_vector_store_instance.search.return_value = sample_search_results
        mock_vector_store_instance.get_lesson_link.return_value = "https://example.com/mcp/lesson2"
        mock_vector_store_class.return_value = mock_vector_store_instance

        mock_tool_manager = Mock()
        mock_sources = [
            {
                "text": "Introduction to Model Context Protocol - Lesson 2",
                "link": "https://example.com/mcp/lesson2"
            }
        ]
        mock_tool_manager.get_last_sources.return_value = mock_sources

        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        # Execute query
        response, sources = system.query("What are resources in MCP?", session_id="test-session")

        # Verify complete workflow
        assert "Resources are entities in MCP" in response
        assert len(sources) == 1
        assert sources[0]["text"] == "Introduction to Model Context Protocol - Lesson 2"

        # Verify history was updated
        mock_session_instance.add_exchange.assert_called_once()

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_multi_turn_conversation(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test multi-turn conversation with context"""
        # Set up mocks
        mock_ai_instance = Mock()
        mock_ai_generator_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_manager_class.return_value = mock_session_instance

        mock_tool_manager = Mock()
        mock_tool_manager.get_last_sources.return_value = []

        system = RAGSystem(mock_config)
        system.tool_manager = mock_tool_manager

        session_id = "test-session"

        # First turn
        mock_session_instance.get_conversation_history.return_value = None
        mock_ai_instance.generate_response.return_value = "MCP is Model Context Protocol."
        response1, _ = system.query("What is MCP?", session_id=session_id)

        # Second turn with history
        history = "User: What is MCP?\nAssistant: MCP is Model Context Protocol."
        mock_session_instance.get_conversation_history.return_value = history
        mock_ai_instance.generate_response.return_value = "It enables LLMs to interact with external tools."
        response2, _ = system.query("How does it work?", session_id=session_id)

        # Verify both exchanges were added
        assert mock_session_instance.add_exchange.call_count == 2

        # Verify second call used history
        second_call_args = mock_ai_instance.generate_response.call_args
        assert second_call_args.kwargs["conversation_history"] == history


class TestRAGSystemAnalytics:
    """Test course analytics functionality"""

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    def test_get_course_analytics(
        self,
        mock_session_manager_class,
        mock_ai_generator_class,
        mock_vector_store_class,
        mock_doc_processor,
        mock_config
    ):
        """Test getting course analytics"""
        # Set up mocks
        mock_vector_store_instance = Mock()
        mock_vector_store_instance.get_course_count.return_value = 4
        mock_vector_store_instance.get_existing_course_titles.return_value = [
            "Introduction to Model Context Protocol",
            "Building Towards Computer Use",
            "Course 3",
            "Course 4"
        ]
        mock_vector_store_class.return_value = mock_vector_store_instance

        system = RAGSystem(mock_config)

        # Get analytics
        analytics = system.get_course_analytics()

        # Verify analytics
        assert analytics["total_courses"] == 4
        assert len(analytics["course_titles"]) == 4
        assert "Introduction to Model Context Protocol" in analytics["course_titles"]
