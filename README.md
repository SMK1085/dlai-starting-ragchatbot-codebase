# Course Materials RAG System

A Retrieval-Augmented Generation (RAG) system designed to answer questions about course materials using semantic search and AI-powered responses.

## Overview

This application is a full-stack web application that enables users to query course materials and receive intelligent, context-aware responses. It uses ChromaDB for vector storage, Anthropic's Claude for AI generation, and provides a web interface for interaction.


## Prerequisites

- Python 3.13 or higher
- uv (Python package manager)
- An Anthropic API key (for Claude AI)
- **For Windows**: Use Git Bash to run the application commands - [Download Git for Windows](https://git-scm.com/downloads/win)

## Installation

1. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install Python dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

## Running the Application

### Quick Start

Use the provided shell script:
```bash
chmod +x run.sh
./run.sh
```

### Manual Start

```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

The application will be available at:
- Web Interface: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

## Development

### Code Quality Tools

This project uses several tools to maintain code quality:

- **Black**: Code formatter for consistent style
- **isort**: Import statement organizer
- **Flake8**: Linter for catching common errors
- **MyPy**: Static type checker
- **Pytest**: Testing framework

### Running Quality Checks

Format your code:
```bash
./format.sh
```

Run all quality checks:
```bash
./quality-check.sh
```

Run individual tools:
```bash
# Format code with black
uv run black backend/ main.py

# Sort imports with isort
uv run isort backend/ main.py

# Run linting with flake8
uv run flake8 backend/ main.py

# Run type checking with mypy
uv run mypy backend/ main.py

# Run tests
cd backend && uv run pytest
```

### Running Tests

```bash
cd backend
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_rag_system.py
```

