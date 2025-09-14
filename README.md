# Tusk - Persistent Memory for AI Agents 🐘

> Like an elephant's memory - never forget your work across Claude sessions

Tusk is a Python-based MCP (Model Context Protocol) server that provides persistent memory across AI agent sessions using FastMCP 2.0. Unlike goldfish memory that fades, Tusk gives AI agents elephant-like memory that spans context windows and sessions.

## Features

- **Checkpoints**: Save work context with highlights for later restoration
- **Tasks**: Cross-session task management that survives context switches  
- **Plans**: Persistent planning that doesn't get lost when contexts reset
- **Recall**: Intelligent session restoration with context replay
- **Standup**: Daily/weekly work summaries across all features
- **Adaptive Tools**: Interfaces that adjust to user expertise level

## Quick Start

1. **Install Tusk**:
   ```bash
   pip install tusk-memory-mcp
   ```

2. **Run the server**:
   ```bash
   tusk-server
   ```

3. **Configure Claude Desktop** to connect to Tusk MCP server

4. **Start using memory**:
   - Use `recall` to restore previous session context
   - Create `checkpoints` to save important work
   - Manage `tasks` that persist across sessions
   - Build `plans` that survive context resets

## Architecture

- **Storage**: JSON files in ~/.coa/tusk/ organized by workspace with Whoosh full-text search
- **Framework**: FastMCP 2.0 with Tool Transformation for adaptive interfaces
- **Models**: Pydantic data models with validation
- **Search**: Whoosh for powerful full-text search and fuzzy matching

## Core Concepts

### Checkpoints
Event-sourced snapshots of your work context:
- Description of current work
- Active files and their states
- Key highlights and decisions
- Git branch information
- TTL-based expiration

### Tasks
Cross-session task management:
- Tasks that survive context windows
- Status tracking and updates
- Priority and tagging system
- Links to checkpoints and plans

### Plans
Persistent planning documents:
- Multi-step project planning
- Goal tracking and progress
- Step-by-step breakdowns
- Status and timeline management

### Recall
Intelligent context restoration:
- Summarize previous session highlights
- Restore relevant context
- Smart filtering and relevance scoring
- Preparation for continued work

## Development

```bash
# Clone and setup
git clone https://github.com/anortham/tusk.git
cd tusk
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests
ruff check src tests --fix

# Type check
mypy src
```

## License

MIT License - see LICENSE file for details.