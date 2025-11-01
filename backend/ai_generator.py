import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Usage:
- **Course Outline Tool** (`get_course_outline`):
  - Use for questions about course structure, outline, lesson list, or "what lessons are in this course"
  - Returns course title, course link, and complete list of lessons with numbers and titles
  - Use when user asks for course overview, table of contents, or lesson breakdown
- **Content Search Tool** (`search_course_content`):
  - Use **only** for questions about specific course content or detailed educational materials
  - **Up to 2 searches per query** - you can refine your search based on initial results
  - If initial search is too broad or misses key information, you may search again with different parameters
  - Synthesize search results into accurate, fact-based responses
  - If search yields no results, state this clearly without offering alternatives

Multi-Round Search Strategy:
- You may perform up to 2 sequential searches if needed
- Use a second search to: compare different courses, search different lessons, or clarify ambiguous initial results
- Don't search twice if the first search fully answers the question

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline questions**: Use outline tool first, then present the course structure including course title, course link, and all lessons
- **Course content questions**: Use search tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the tool"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str, max_tool_rounds: int = 2):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tool_rounds = max_tool_rounds  # Maximum sequential tool calling rounds

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        try:
            response = self.client.messages.create(**api_params)
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

        # Validate response has content
        if not response.content or len(response.content) == 0:
            raise Exception("Anthropic API returned empty response content")

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)

        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls across multiple rounds (up to max_tool_rounds).

        In each round:
        - Executes all tool calls from Claude's response
        - Provides tool results back to Claude
        - Makes a new API call WITH tools parameter
        - Repeats if Claude requests more tool use

        Terminates when:
        - Claude's response has no tool_use blocks (normal completion)
        - max_tool_rounds reached (forced completion)
        - Tool execution error occurs (exception propagated)

        Args:
            initial_response: The first response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after all rounds complete
        """
        # Start with existing messages
        messages = base_params["messages"].copy()
        current_response = initial_response

        # Track rounds for limit enforcement
        round_count = 0

        # Support up to max_tool_rounds sequential tool calling rounds
        # This allows Claude to refine searches based on initial results
        while round_count < self.max_tool_rounds:
            round_count += 1

            # Add Claude's response (with tool use) to messages
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute all tool calls from this response
            tool_results = []
            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name,
                            **content_block.input
                        )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result
                        })
                    except Exception as e:
                        # Tool execution errors propagate immediately
                        raise Exception(f"Tool execution failed in round {round_count}: {str(e)}")

            # Add tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Prepare next API call WITH tools (Claude can make more tool calls)
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params.get("tools", []),  # Include tools parameter
                "tool_choice": {"type": "auto"}
            }

            # Make next API call
            try:
                current_response = self.client.messages.create(**next_params)
            except Exception as e:
                raise Exception(f"Anthropic API error in round {round_count}: {str(e)}")

            # Validate response has content
            if not current_response.content or len(current_response.content) == 0:
                raise Exception(f"Anthropic API returned empty response content in round {round_count}")

            # Check if Claude wants to use more tools
            if current_response.stop_reason != "tool_use":
                # Normal completion - Claude provided final answer
                return current_response.content[0].text

        # Max rounds reached - return what we have
        # Claude may have wanted more tool calls, but we enforce limit
        return current_response.content[0].text