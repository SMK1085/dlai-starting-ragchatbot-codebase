"""Tests for ai_generator.py - AIGenerator and tool calling workflow"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from ai_generator import AIGenerator


class TestAIGeneratorBasics:
    """Test basic AIGenerator functionality"""

    def test_initialization(self):
        """Test AIGenerator initialization"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")

        assert generator.model == "claude-sonnet-4-20250514"
        assert generator.base_params["model"] == "claude-sonnet-4-20250514"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    def test_system_prompt_exists(self):
        """Test that system prompt is defined and contains key instructions"""
        assert AIGenerator.SYSTEM_PROMPT is not None
        assert len(AIGenerator.SYSTEM_PROMPT) > 0

        # Check for key elements in system prompt
        assert "tool" in AIGenerator.SYSTEM_PROMPT.lower()
        assert "course" in AIGenerator.SYSTEM_PROMPT.lower()


class TestGenerateResponseWithoutTools:
    """Test response generation without tools"""

    def test_simple_response_without_tools(self, mock_anthropic_client):
        """Test generating a simple response without tools"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        response = generator.generate_response(query="What is Python?")

        # Verify API call was made
        mock_anthropic_client.messages.create.assert_called_once()

        # Verify response
        assert response == "This is a test response from Claude."

    def test_api_call_parameters_without_tools(self, mock_anthropic_client):
        """Test that API call parameters are correctly structured without tools"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        generator.generate_response(query="What is Python?")

        # Get the call arguments
        call_args = mock_anthropic_client.messages.create.call_args

        # Verify parameters
        assert call_args.kwargs["model"] == "test-model"
        assert call_args.kwargs["temperature"] == 0
        assert call_args.kwargs["max_tokens"] == 800
        assert len(call_args.kwargs["messages"]) == 1
        assert call_args.kwargs["messages"][0]["role"] == "user"
        assert call_args.kwargs["messages"][0]["content"] == "What is Python?"
        assert "system" in call_args.kwargs
        assert "tools" not in call_args.kwargs

    def test_response_with_conversation_history(self, mock_anthropic_client):
        """Test that conversation history is included in system prompt"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        history = "User: What is MCP?\nAssistant: MCP is Model Context Protocol."

        generator.generate_response(query="Tell me more", conversation_history=history)

        # Get system parameter
        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs["system"]

        # Verify history is in system content
        assert history in system_content


class TestGenerateResponseWithTools:
    """Test response generation with tools available"""

    def test_response_with_tools_no_tool_use(self, mock_anthropic_client, sample_tool_definitions):
        """Test response when tools are available but not used"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        response = generator.generate_response(
            query="What is Python?", tools=sample_tool_definitions
        )

        # Verify tools were passed to API
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args.kwargs["tools"] == sample_tool_definitions
        assert call_args.kwargs["tool_choice"] == {"type": "auto"}

        # Verify response
        assert response == "This is a test response from Claude."

    def test_response_with_tool_use_triggers_execution(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_final_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that tool_use stop reason triggers tool execution workflow"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First call returns tool use, second call returns final response
        mock_anthropic_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            mock_anthropic_final_response,
        ]

        response = generator.generate_response(
            query="What are resources in MCP?",
            tools=sample_tool_definitions,
            tool_manager=mock_tool_manager,
        )

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="resources in MCP",
            course_name="Introduction to Model Context Protocol",
        )

        # Verify second API call was made
        assert mock_anthropic_client.messages.create.call_count == 2

        # Verify final response
        assert "resources are entities in MCP" in response


class TestHandleToolExecution:
    """Test the _handle_tool_execution method"""

    def test_handle_tool_execution_flow(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_final_response,
        mock_tool_manager,
        sample_tool_definitions,
    ):
        """Test the complete tool execution flow"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # Set up for second API call
        mock_anthropic_client.messages.create.return_value = mock_anthropic_final_response

        base_params = {
            "messages": [{"role": "user", "content": "What are resources in MCP?"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,  # Add tools to base params
        }

        result = generator._handle_tool_execution(
            mock_anthropic_tool_use_response, base_params, mock_tool_manager
        )

        # Verify tool execution
        mock_tool_manager.execute_tool.assert_called_once()

        # Verify second API call was made
        mock_anthropic_client.messages.create.assert_called_once()

        # Check the messages in the second call
        second_call_args = mock_anthropic_client.messages.create.call_args
        messages = second_call_args.kwargs["messages"]

        # Should have: original user message + assistant tool use + user tool results
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

        # IMPORTANT: Verify tools parameter is included in continuation call
        # This enables multi-round tool calling
        assert "tools" in second_call_args.kwargs
        assert second_call_args.kwargs["tools"] == sample_tool_definitions
        assert "tool_choice" in second_call_args.kwargs

        # Verify result
        assert "resources are entities in MCP" in result

    def test_tool_results_structure(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_final_response,
        mock_tool_manager,
        sample_tool_definitions,
    ):
        """Test that tool results are correctly structured"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client
        mock_anthropic_client.messages.create.return_value = mock_anthropic_final_response

        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        generator._handle_tool_execution(
            mock_anthropic_tool_use_response, base_params, mock_tool_manager
        )

        # Get the second API call
        second_call_args = mock_anthropic_client.messages.create.call_args
        tool_result_message = second_call_args.kwargs["messages"][2]

        # Verify structure
        assert tool_result_message["role"] == "user"
        assert isinstance(tool_result_message["content"], list)
        assert len(tool_result_message["content"]) == 1

        tool_result = tool_result_message["content"][0]
        assert tool_result["type"] == "tool_result"
        assert tool_result["tool_use_id"] == "tool_use_123"
        assert "content" in tool_result


class TestErrorHandling:
    """Test error handling in AIGenerator"""

    def test_api_error_propagates(self, mock_anthropic_client):
        """Test that Anthropic API errors propagate up"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # Simulate API error
        mock_anthropic_client.messages.create.side_effect = Exception("API Error: Invalid API key")

        with pytest.raises(Exception, match="API Error: Invalid API key"):
            generator.generate_response(query="Test query")

    def test_empty_content_array_causes_exception(self, mock_anthropic_client):
        """Test that empty content array causes descriptive exception"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # Mock response with empty content
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = []  # Empty content array

        mock_anthropic_client.messages.create.return_value = mock_response

        with pytest.raises(Exception, match="Anthropic API returned empty response content"):
            generator.generate_response(query="Test query")

    def test_tool_execution_error_propagates(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that tool execution errors propagate"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client
        mock_anthropic_client.messages.create.return_value = mock_anthropic_tool_use_response

        # Simulate tool execution error
        mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")

        with pytest.raises(Exception, match="Tool execution failed"):
            generator.generate_response(
                query="Test query", tools=sample_tool_definitions, tool_manager=mock_tool_manager
            )

    def test_second_api_call_error_propagates(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that errors in second API call (after tool use) propagate"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First call succeeds with tool use, second call fails
        mock_anthropic_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            Exception("Second API call failed"),
        ]

        with pytest.raises(Exception, match="Second API call failed"):
            generator.generate_response(
                query="Test query", tools=sample_tool_definitions, tool_manager=mock_tool_manager
            )

    def test_second_api_call_empty_content_causes_exception(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that empty content in second API call causes descriptive exception"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First call succeeds, second call returns empty content
        mock_empty_response = Mock()
        mock_empty_response.content = []

        mock_anthropic_client.messages.create.side_effect = [
            mock_anthropic_tool_use_response,
            mock_empty_response,
        ]

        with pytest.raises(
            Exception, match="Anthropic API returned empty response content in round 1"
        ):
            generator.generate_response(
                query="Test query", tools=sample_tool_definitions, tool_manager=mock_tool_manager
            )


class TestToolCallingWorkflow:
    """Test the complete tool calling workflow"""

    def test_no_tool_manager_with_tool_use_returns_text(
        self, mock_anthropic_client, mock_anthropic_tool_use_response, sample_tool_definitions
    ):
        """Test that tool_use without tool_manager returns text from first content block"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client
        mock_anthropic_client.messages.create.return_value = mock_anthropic_tool_use_response

        # Call without tool_manager
        result = generator.generate_response(
            query="Test query",
            tools=sample_tool_definitions,
            tool_manager=None,  # No tool manager provided
        )

        # Should return text from first content block (ignoring tool use)
        assert result == "I'll search for information about resources in MCP."

    def test_multiple_tool_calls_in_one_response(
        self,
        mock_anthropic_client,
        mock_anthropic_final_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test handling multiple tool calls in a single response"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # Create response with multiple tool uses
        mock_multi_tool_response = Mock()
        mock_multi_tool_response.stop_reason = "tool_use"

        tool_block_1 = Mock()
        tool_block_1.type = "tool_use"
        tool_block_1.id = "tool_1"
        tool_block_1.name = "search_course_content"
        tool_block_1.input = {"query": "first query"}

        tool_block_2 = Mock()
        tool_block_2.type = "tool_use"
        tool_block_2.id = "tool_2"
        tool_block_2.name = "search_course_content"
        tool_block_2.input = {"query": "second query"}

        mock_multi_tool_response.content = [tool_block_1, tool_block_2]

        mock_anthropic_client.messages.create.side_effect = [
            mock_multi_tool_response,
            mock_anthropic_final_response,
        ]

        generator.generate_response(
            query="Test query", tools=sample_tool_definitions, tool_manager=mock_tool_manager
        )

        # Verify both tools were executed
        assert mock_tool_manager.execute_tool.call_count == 2

    def test_tool_use_with_mixed_content_blocks(
        self,
        mock_anthropic_client,
        mock_anthropic_final_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test handling tool use mixed with text blocks"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # Response with text and tool use
        mock_response = Mock()
        mock_response.stop_reason = "tool_use"

        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Let me search for that..."

        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_1"
        tool_block.name = "search_course_content"
        tool_block.input = {"query": "test"}

        mock_response.content = [text_block, tool_block]

        mock_anthropic_client.messages.create.side_effect = [
            mock_response,
            mock_anthropic_final_response,
        ]

        generator.generate_response(
            query="Test query", tools=sample_tool_definitions, tool_manager=mock_tool_manager
        )

        # Verify only tool blocks were executed
        assert mock_tool_manager.execute_tool.call_count == 1
        mock_tool_manager.execute_tool.assert_called_with("search_course_content", query="test")


class TestMultiRoundToolCalling:
    """Test multi-round tool calling functionality"""

    def test_two_sequential_tool_rounds(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_second_tool_use_response,
        mock_anthropic_final_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that Claude can make 2 sequential tool calls"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First call returns tool_use, second call returns tool_use again, third returns final
        mock_anthropic_client.messages.create.side_effect = [
            mock_anthropic_second_tool_use_response,  # Round 1 completion with another tool_use
            mock_anthropic_final_response,  # Round 2 completion
        ]

        base_params = {
            "messages": [{"role": "user", "content": "Compare resources and prompts in MCP"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        result = generator._handle_tool_execution(
            mock_anthropic_tool_use_response, base_params, mock_tool_manager  # Initial tool use
        )

        # Verify 2 API calls made (one for each round after initial)
        assert mock_anthropic_client.messages.create.call_count == 2

        # Verify 2 tool executions
        assert mock_tool_manager.execute_tool.call_count == 2

        # Verify final response returned
        assert "resources are entities in MCP" in result

        # Verify message structure in final call
        final_call_args = mock_anthropic_client.messages.create.call_args
        messages = final_call_args.kwargs["messages"]
        # Should have 5 messages: user query + asst tool_use + user results + asst tool_use + user results
        assert len(messages) == 5

    def test_early_termination_after_one_round(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_final_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that system stops if Claude doesn't request more tools after first round"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First call returns final response (no more tool use)
        mock_anthropic_client.messages.create.return_value = mock_anthropic_final_response

        base_params = {
            "messages": [{"role": "user", "content": "What are resources in MCP?"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        result = generator._handle_tool_execution(
            mock_anthropic_tool_use_response, base_params, mock_tool_manager
        )

        # Only 1 API call made (first round completes)
        assert mock_anthropic_client.messages.create.call_count == 1

        # Only 1 tool execution
        assert mock_tool_manager.execute_tool.call_count == 1

        # Result returned
        assert "resources are entities in MCP" in result

    def test_max_rounds_enforcement(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_second_tool_use_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that system stops after max_tool_rounds even if Claude wants more"""
        generator = AIGenerator(api_key="test-key", model="test-model", max_tool_rounds=2)
        generator.client = mock_anthropic_client

        # Create a third tool use response (which should not be used)
        mock_third_tool_use = Mock()
        mock_third_tool_use.stop_reason = "tool_use"
        mock_third_tool_use.content = [Mock(type="text", text="Let me search one more time.")]

        # Both continuation calls return tool_use (trying to exceed max rounds)
        mock_anthropic_client.messages.create.side_effect = [
            mock_anthropic_second_tool_use_response,  # Round 1 wants more
            mock_third_tool_use,  # Round 2 wants more (but max reached)
        ]

        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        result = generator._handle_tool_execution(
            mock_anthropic_tool_use_response, base_params, mock_tool_manager
        )

        # Exactly 2 API calls made (max rounds = 2)
        assert mock_anthropic_client.messages.create.call_count == 2

        # Exactly 2 tool executions
        assert mock_tool_manager.execute_tool.call_count == 2

        # Result returned (text from final response despite tool_use stop_reason)
        assert result == "Let me search one more time."

    def test_tool_error_in_second_round(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_second_tool_use_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test error handling when tool execution fails in second round"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First continuation returns second tool use
        mock_anthropic_client.messages.create.return_value = mock_anthropic_second_tool_use_response

        # First tool execution succeeds, second fails
        mock_tool_manager.execute_tool.side_effect = [
            "First tool result",
            Exception("Vector store connection failed"),
        ]

        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        with pytest.raises(Exception, match="Tool execution failed in round 2"):
            generator._handle_tool_execution(
                mock_anthropic_tool_use_response, base_params, mock_tool_manager
            )

    def test_api_error_in_second_round(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test error handling when API call fails in second round"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        # First API call succeeds, second fails
        mock_anthropic_client.messages.create.side_effect = [
            Mock(
                stop_reason="tool_use",
                content=[
                    Mock(
                        type="tool_use",
                        id="tool_2",
                        name="search_course_content",
                        input={"query": "test"},
                    )
                ],
            ),
            Exception("API rate limit exceeded"),
        ]

        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        with pytest.raises(Exception, match="Anthropic API error in round 2"):
            generator._handle_tool_execution(
                mock_anthropic_tool_use_response, base_params, mock_tool_manager
            )

    def test_tools_parameter_included_in_all_rounds(
        self,
        mock_anthropic_client,
        mock_anthropic_tool_use_response,
        mock_anthropic_second_tool_use_response,
        mock_anthropic_final_response,
        sample_tool_definitions,
        mock_tool_manager,
    ):
        """Test that tools parameter is included in all continuation API calls"""
        generator = AIGenerator(api_key="test-key", model="test-model")
        generator.client = mock_anthropic_client

        mock_anthropic_client.messages.create.side_effect = [
            mock_anthropic_second_tool_use_response,
            mock_anthropic_final_response,
        ]

        base_params = {
            "messages": [{"role": "user", "content": "Test query"}],
            "system": AIGenerator.SYSTEM_PROMPT,
            "tools": sample_tool_definitions,
        }

        generator._handle_tool_execution(
            mock_anthropic_tool_use_response, base_params, mock_tool_manager
        )

        # Check both API calls
        assert mock_anthropic_client.messages.create.call_count == 2

        # Verify first call has tools
        first_call = mock_anthropic_client.messages.create.call_args_list[0]
        assert "tools" in first_call.kwargs
        assert first_call.kwargs["tools"] == sample_tool_definitions
        assert "tool_choice" in first_call.kwargs

        # Verify second call has tools
        second_call = mock_anthropic_client.messages.create.call_args_list[1]
        assert "tools" in second_call.kwargs
        assert second_call.kwargs["tools"] == sample_tool_definitions
        assert "tool_choice" in second_call.kwargs
