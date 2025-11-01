"""Tests for FastAPI endpoints - API layer testing"""
import pytest
from unittest.mock import Mock
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


# Mark all tests in this module as API tests
pytestmark = pytest.mark.api


class TestQueryEndpoint:
    """Test /api/query endpoint"""

    def test_query_endpoint_success_without_session(
        self,
        test_client,
        mock_rag_system,
        sample_query_request
    ):
        """Test successful query without providing session ID"""
        response = test_client.post("/api/query", json=sample_query_request)

        # Verify response status
        assert response.status_code == 200

        # Verify response structure
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify session was created
        assert data["session_id"] == "test-session-123"
        mock_rag_system.session_manager.create_session.assert_called_once()

        # Verify RAG system was called
        mock_rag_system.query.assert_called_once()

    def test_query_endpoint_success_with_session(
        self,
        test_client,
        mock_rag_system,
        sample_query_request_with_session
    ):
        """Test successful query with existing session ID"""
        response = test_client.post("/api/query", json=sample_query_request_with_session)

        # Verify response status
        assert response.status_code == 200

        # Verify session ID was preserved
        data = response.json()
        assert data["session_id"] == "test-session-456"

        # Verify session was NOT created (existing session used)
        mock_rag_system.session_manager.create_session.assert_not_called()

        # Verify RAG system was called with session ID
        call_args = mock_rag_system.query.call_args
        assert call_args[0][1] == "test-session-456"

    def test_query_endpoint_response_structure(
        self,
        test_client,
        sample_query_request
    ):
        """Test that response has correct structure and types"""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == 200
        data = response.json()

        # Check types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Check sources structure
        if len(data["sources"]) > 0:
            source = data["sources"][0]
            assert "text" in source
            assert "link" in source

    def test_query_endpoint_with_sources(
        self,
        test_client,
        mock_rag_system
    ):
        """Test query response includes sources correctly"""
        # Configure mock to return sources
        mock_rag_system.query.return_value = (
            "Resources are entities in MCP.",
            [
                {
                    "text": "Introduction to Model Context Protocol - Lesson 2",
                    "link": "https://example.com/mcp/lesson2"
                }
            ]
        )

        response = test_client.post("/api/query", json={
            "query": "What are resources in MCP?",
            "session_id": None
        })

        assert response.status_code == 200
        data = response.json()

        # Verify sources
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Introduction to Model Context Protocol - Lesson 2"
        assert data["sources"][0]["link"] == "https://example.com/mcp/lesson2"

    def test_query_endpoint_without_sources(
        self,
        test_client,
        mock_rag_system
    ):
        """Test query response with no sources (general knowledge)"""
        # Configure mock to return no sources
        mock_rag_system.query.return_value = (
            "Python is a programming language.",
            []
        )

        response = test_client.post("/api/query", json={
            "query": "What is Python?",
            "session_id": None
        })

        assert response.status_code == 200
        data = response.json()

        # Verify no sources
        assert len(data["sources"]) == 0

    def test_query_endpoint_missing_query_field(self, test_client):
        """Test query endpoint with missing required 'query' field"""
        response = test_client.post("/api/query", json={
            "session_id": "test-session"
            # Missing "query" field
        })

        # Should return 422 Unprocessable Entity for validation error
        assert response.status_code == 422

    def test_query_endpoint_empty_query(self, test_client):
        """Test query endpoint with empty query string"""
        response = test_client.post("/api/query", json={
            "query": "",
            "session_id": None
        })

        # Empty query is valid (validation allows it)
        # RAG system should handle it
        assert response.status_code == 200

    def test_query_endpoint_invalid_json(self, test_client):
        """Test query endpoint with invalid JSON payload"""
        response = test_client.post(
            "/api/query",
            data="invalid json{",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 for invalid JSON
        assert response.status_code == 422

    def test_query_endpoint_rag_system_error(
        self,
        test_client,
        mock_rag_system
    ):
        """Test query endpoint when RAG system raises an error"""
        # Configure mock to raise exception
        mock_rag_system.query.side_effect = Exception("RAG system error: Vector store connection failed")

        response = test_client.post("/api/query", json={
            "query": "Test query",
            "session_id": None
        })

        # Should return 500 Internal Server Error
        assert response.status_code == 500
        assert "RAG system error" in response.json()["detail"]

    def test_query_endpoint_session_creation_error(
        self,
        test_client,
        mock_rag_system
    ):
        """Test query endpoint when session creation fails"""
        # Configure mock to raise exception on session creation
        mock_rag_system.session_manager.create_session.side_effect = Exception("Session creation failed")

        response = test_client.post("/api/query", json={
            "query": "Test query",
            "session_id": None  # Will trigger session creation
        })

        # Should return 500 Internal Server Error
        assert response.status_code == 500
        assert "Session creation failed" in response.json()["detail"]


class TestCoursesEndpoint:
    """Test /api/courses endpoint"""

    def test_courses_endpoint_success(self, test_client, mock_rag_system):
        """Test successful retrieval of course statistics"""
        response = test_client.get("/api/courses")

        # Verify response status
        assert response.status_code == 200

        # Verify response structure
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify RAG system was called
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_courses_endpoint_response_structure(self, test_client):
        """Test that course analytics response has correct structure"""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Check types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

        # Verify count matches list length
        assert data["total_courses"] == len(data["course_titles"])

    def test_courses_endpoint_with_courses(self, test_client, mock_rag_system):
        """Test courses endpoint returns expected course data"""
        # Configure mock
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": [
                "Introduction to Model Context Protocol",
                "Building Towards Computer Use"
            ]
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify data
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Introduction to Model Context Protocol" in data["course_titles"]
        assert "Building Towards Computer Use" in data["course_titles"]

    def test_courses_endpoint_no_courses(self, test_client, mock_rag_system):
        """Test courses endpoint when no courses are loaded"""
        # Configure mock for empty state
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify empty data
        assert data["total_courses"] == 0
        assert len(data["course_titles"]) == 0

    def test_courses_endpoint_error_handling(self, test_client, mock_rag_system):
        """Test courses endpoint when RAG system raises an error"""
        # Configure mock to raise exception
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error: Database connection failed")

        response = test_client.get("/api/courses")

        # Should return 500 Internal Server Error
        assert response.status_code == 500
        assert "Analytics error" in response.json()["detail"]

    def test_courses_endpoint_no_body_required(self, test_client):
        """Test that courses endpoint works as GET with no request body"""
        # GET requests should not have body
        response = test_client.get("/api/courses")

        assert response.status_code == 200


class TestEndpointIntegration:
    """Integration tests across multiple endpoints"""

    def test_query_then_courses_flow(self, test_client, mock_rag_system):
        """Test typical flow: query for information, then check courses"""
        # First, make a query
        query_response = test_client.post("/api/query", json={
            "query": "What are resources in MCP?",
            "session_id": None
        })
        assert query_response.status_code == 200

        # Then, get course stats
        courses_response = test_client.get("/api/courses")
        assert courses_response.status_code == 200

        # Verify both responses are valid
        query_data = query_response.json()
        courses_data = courses_response.json()

        assert "answer" in query_data
        assert "total_courses" in courses_data

    def test_multiple_queries_same_session(self, test_client, mock_rag_system):
        """Test multiple queries using the same session ID"""
        session_id = "test-session-123"

        # First query
        response1 = test_client.post("/api/query", json={
            "query": "What is MCP?",
            "session_id": session_id
        })
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id

        # Second query with same session
        response2 = test_client.post("/api/query", json={
            "query": "Tell me more",
            "session_id": session_id
        })
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Verify RAG system was called twice with session
        assert mock_rag_system.query.call_count == 2

    def test_multiple_queries_different_sessions(self, test_client, mock_rag_system):
        """Test multiple queries with different session IDs"""
        # Query 1 with session A
        response1 = test_client.post("/api/query", json={
            "query": "What is MCP?",
            "session_id": "session-A"
        })
        assert response1.status_code == 200

        # Query 2 with session B
        response2 = test_client.post("/api/query", json={
            "query": "What is computer use?",
            "session_id": "session-B"
        })
        assert response2.status_code == 200

        # Verify both sessions were used
        assert response1.json()["session_id"] == "session-A"
        assert response2.json()["session_id"] == "session-B"


class TestHTTPMethods:
    """Test HTTP method restrictions"""

    def test_query_endpoint_get_not_allowed(self, test_client):
        """Test that GET is not allowed on /api/query (POST only)"""
        response = test_client.get("/api/query")

        # Should return 405 Method Not Allowed or 404 Not Found
        assert response.status_code in [404, 405]

    def test_query_endpoint_put_not_allowed(self, test_client):
        """Test that PUT is not allowed on /api/query"""
        response = test_client.put("/api/query", json={
            "query": "Test",
            "session_id": None
        })

        # Should return 405 Method Not Allowed or 404 Not Found
        assert response.status_code in [404, 405]

    def test_query_endpoint_delete_not_allowed(self, test_client):
        """Test that DELETE is not allowed on /api/query"""
        response = test_client.delete("/api/query")

        # Should return 405 Method Not Allowed or 404 Not Found
        assert response.status_code in [404, 405]

    def test_courses_endpoint_post_not_allowed(self, test_client):
        """Test that POST is not allowed on /api/courses (GET only)"""
        response = test_client.post("/api/courses", json={})

        # Should return 405 Method Not Allowed or 404 Not Found
        assert response.status_code in [404, 405]


class TestContentTypes:
    """Test content type handling"""

    def test_query_endpoint_accepts_json(self, test_client):
        """Test that query endpoint accepts JSON content type"""
        response = test_client.post(
            "/api/query",
            json={"query": "Test", "session_id": None},
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200

    def test_query_endpoint_rejects_form_data(self, test_client):
        """Test that query endpoint handles form data (should fail validation)"""
        response = test_client.post(
            "/api/query",
            data={"query": "Test", "session_id": "null"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should return 422 for validation error (expects JSON)
        assert response.status_code == 422

    def test_response_content_type_is_json(self, test_client):
        """Test that responses have JSON content type"""
        response = test_client.post("/api/query", json={
            "query": "Test",
            "session_id": None
        })

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_query_with_very_long_query_string(self, test_client):
        """Test query with very long query string"""
        long_query = "What is MCP? " * 1000  # Very long query

        response = test_client.post("/api/query", json={
            "query": long_query,
            "session_id": None
        })

        # Should handle long queries (might return 200 or 413 depending on limits)
        assert response.status_code in [200, 413]

    def test_query_with_special_characters(self, test_client):
        """Test query with special characters"""
        response = test_client.post("/api/query", json={
            "query": "What is <script>alert('test')</script> in MCP?",
            "session_id": None
        })

        # Should handle special characters safely
        assert response.status_code == 200

    def test_query_with_unicode_characters(self, test_client):
        """Test query with Unicode characters"""
        response = test_client.post("/api/query", json={
            "query": "MCPとは何ですか？ 🤖",
            "session_id": None
        })

        # Should handle Unicode characters
        assert response.status_code == 200

    def test_session_id_with_special_characters(self, test_client):
        """Test session ID with special characters"""
        response = test_client.post("/api/query", json={
            "query": "Test",
            "session_id": "session-123-abc_xyz"
        })

        # Should handle session IDs with hyphens, numbers, underscores
        assert response.status_code == 200

    def test_null_session_id_explicit(self, test_client, mock_rag_system):
        """Test explicitly passing null for session_id"""
        response = test_client.post("/api/query", json={
            "query": "Test",
            "session_id": None
        })

        assert response.status_code == 200
        # Should create new session
        mock_rag_system.session_manager.create_session.assert_called_once()


class TestCORSAndMiddleware:
    """Test CORS and middleware configuration

    Note: TestClient doesn't fully emulate CORS behavior.
    These tests verify basic middleware functionality.
    """

    def test_middleware_does_not_break_requests(self, test_client):
        """Test that middleware configuration doesn't break normal requests"""
        response = test_client.post("/api/query", json={
            "query": "Test",
            "session_id": None
        })

        # Should work normally despite middleware
        assert response.status_code == 200

    def test_app_handles_requests_with_origin_header(self, test_client):
        """Test that app handles requests with Origin header"""
        response = test_client.post(
            "/api/query",
            json={"query": "Test", "session_id": None},
            headers={"Origin": "http://localhost:3000"}
        )

        # Should accept requests with Origin header
        assert response.status_code == 200
