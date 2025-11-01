# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) chatbot system that answers questions about course materials. It combines semantic search (ChromaDB) with AI generation (Claude) using tool calling to intelligently decide when to retrieve course content.

## Development Commands

### Running the Application

```bash
# Quick start (from root directory)
./run.sh

# Manual start (recommended for development with auto-reload)
cd backend
uv run uvicorn app:app --reload --port 8000
```

Access points:
- Web UI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### Dependency Management

```bash
# Install/sync dependencies (uses uv.lock)
uv sync

# Add new dependency
uv add <package-name>
```

### Environment Setup

Required environment variable in `.env`:
```
ANTHROPIC_API_KEY=your_key_here
```

See `.env.example` for template.

## Architecture Overview

### Request Flow (Frontend → Backend)

1. **Frontend (script.js)** → POST `/api/query` with `{query, session_id}`
2. **FastAPI (app.py)** → Creates session if needed, calls `rag_system.query()`
3. **RAG System (rag_system.py)** → Orchestrates: retrieves history, calls AI with tools
4. **AI Generator (ai_generator.py)** → Calls Claude API with system prompt + tools
5. **Claude Decision Point**:
   - General knowledge → Direct answer
   - Course-specific → Calls `search_course_content` tool
6. **Tool Flow** (if triggered):
   - Tool Manager → Course Search Tool → Vector Store → ChromaDB
   - Returns formatted results with sources
   - Second Claude API call to synthesize answer from retrieved context
7. **Response** → `{answer, sources, session_id}` back to frontend

### Two-Call Pattern for Tool Use

When Claude decides to search (for course-specific queries):
- **First API call**: Claude returns `stop_reason: "tool_use"` with tool parameters
- Tool execution happens in `_handle_tool_execution()` (ai_generator.py:89-135)
- **Second API call**: Messages include tool results; Claude synthesizes final answer

This is handled automatically by `ai_generator.py` - never needs manual intervention.

### Core Components

**RAGSystem (rag_system.py)**: Central orchestrator coordinating all components
- Manages document processing, vector storage, AI generation, and sessions
- `query()` method is the main entry point for all queries

**VectorStore (vector_store.py)**: ChromaDB wrapper with dual collections
- `course_catalog`: Metadata (titles, instructors, lessons) - used for fuzzy course name matching
- `course_content`: Text chunks with embeddings - actual searchable content
- `search()` performs: course name resolution → filter building → semantic search

**AIGenerator (ai_generator.py)**: Claude API wrapper
- System prompt (line 8-30) instructs Claude when to search vs. use general knowledge
- Temperature: 0 (deterministic), max_tokens: 800
- Automatically handles tool calling workflow

**SearchTools (search_tools.py)**: Tool definitions and execution
- Abstract `Tool` base class for extensibility
- `CourseSearchTool`: Implements `search_course_content` with optional filters
- `ToolManager`: Registers tools, tracks sources for UI display

**DocumentProcessor (document_processor.py)**: Parses course files
- Extracts structured metadata from document headers (title, instructor, lessons)
- Chunks text with overlap (800 chars, 100 overlap - configurable in config.py)
- Returns `Course` and `CourseChunk` objects

**SessionManager (session_manager.py)**: In-memory conversation history
- Stores last N exchanges per session (default: 2, see config.py MAX_HISTORY)
- History included in system prompt for context-aware responses
- Sessions auto-created if not provided in request

### Data Models (models.py)

```python
Course: {title, course_link, instructor, lessons: [Lesson]}
Lesson: {lesson_number, title, lesson_link}
CourseChunk: {content, course_title, lesson_number, chunk_index}
```

`course.title` is used as unique identifier throughout the system.

### Configuration (config.py)

Key settings (all configurable via Config dataclass):
- `ANTHROPIC_MODEL`: "claude-sonnet-4-20250514"
- `EMBEDDING_MODEL`: "all-MiniLM-L6-v2" (SentenceTransformers)
- `CHUNK_SIZE`: 800, `CHUNK_OVERLAP`: 100
- `MAX_RESULTS`: 5 (search results per query)
- `MAX_HISTORY`: 2 (conversation exchanges to remember)
- `CHROMA_PATH`: "./chroma_db" (persistent vector storage location)

## Important Implementation Details

### Course Name Resolution (Fuzzy Matching)

The system uses semantic search to match partial course names:
- User/Claude provides: "MCP"
- `VectorStore._resolve_course_name()` searches `course_catalog` collection
- Returns exact title: "Introduction to Model Context Protocol"
- This exact title is then used for filtering `course_content` search

Implementation: vector_store.py:102-116

### Document Loading at Startup

`app.py` has an `@app.on_event("startup")` handler (lines 88-98) that automatically loads documents from `../docs/` folder on server start. This happens once at startup and does NOT reload on every request.

To add new courses: place files in `docs/` and restart the server.

### Source Tracking

Sources are tracked in `CourseSearchTool.last_sources` during tool execution, then retrieved via `ToolManager.get_last_sources()` and reset after each query. This ensures the frontend receives accurate source citations.

### Frontend Architecture

Single-page app with vanilla JavaScript (no framework):
- `script.js`: Handles UI, API calls, markdown rendering (using marked.js)
- `index.html`: Chat interface + sidebar with course stats
- `style.css`: Dark theme with custom styling
- Session persistence: `currentSessionId` maintained in frontend state

## Common Development Scenarios

### Modifying Search Behavior

To change search parameters or add new tool parameters:
1. Update tool definition in `CourseSearchTool.get_tool_definition()` (search_tools.py:27-50)
2. Update `execute()` method signature (search_tools.py:52)
3. Update `VectorStore.search()` if new filtering logic needed (vector_store.py:61)

### Changing Claude's Behavior

Edit the system prompt in `AIGenerator.SYSTEM_PROMPT` (ai_generator.py:8-30). This prompt:
- Instructs when to search vs. use general knowledge
- Defines response format and tone
- Sets search usage limits (currently: one search per query maximum)

### Adjusting Chunk Size or Overlap

Modify `CHUNK_SIZE` and `CHUNK_OVERLAP` in config.py, then:
1. Delete `chroma_db/` directory
2. Restart server (documents will be re-chunked and re-indexed)

### Adding New Tool Types

1. Create new class extending `Tool` (search_tools.py:6-17)
2. Implement `get_tool_definition()` and `execute()`
3. Register with ToolManager in `RAGSystem.__init__()` (rag_system.py:24)
4. Claude will automatically see and use the new tool

## File Structure Context

```
backend/
├── app.py                  # FastAPI server, endpoints, startup logic
├── rag_system.py          # Main orchestrator (query entry point)
├── ai_generator.py        # Claude API wrapper, tool calling handler
├── vector_store.py        # ChromaDB wrapper, dual collections
├── document_processor.py  # Document parsing, chunking, metadata extraction
├── search_tools.py        # Tool definitions, CourseSearchTool, ToolManager
├── session_manager.py     # Conversation history management
├── models.py              # Pydantic models (Course, Lesson, CourseChunk)
└── config.py              # Configuration settings

frontend/
├── index.html             # Single-page app structure
├── script.js              # UI logic, API calls, message rendering
└── style.css              # Dark theme styling

docs/                      # Course materials (auto-loaded at startup)
```

## Testing Locally

Manual testing workflow:
1. Start server: `cd backend && uv run uvicorn app:app --reload`
2. Open browser: `http://localhost:8000`
3. Test general knowledge: "What is Python?" (should answer without searching)
4. Test course query: "What are resources in MCP?" (should search and cite sources)
5. Check sources: Expand "Sources" section in response
6. Test multi-turn: Ask follow-up question (should maintain context)

Check API docs at `http://localhost:8000/docs` for interactive API testing.
