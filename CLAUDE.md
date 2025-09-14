# Claude Development Instructions for Tusk

## Project Overview

Tusk is a Python-based MCP server providing **persistent memory** for AI agents using FastMCP 2.0. Think "elephant memory" instead of "goldfish memory" - context that survives session resets.

## Core Architecture

### Framework: FastMCP 2.0
- **Tool Transformation** for adaptive interfaces
- **Instructions field** for behavioral guidance  
- **Progressive disclosure** - simple → expert modes
- Install: `pip install fastmcp>=2.0.0`

### Storage: JSON + Whoosh
- **Human-readable** JSON files organized by workspace
- **Full-text search** with Whoosh (pure Python)
- **No database** required - just files
- **Portable** - copy ~/.coa/tusk/ folder anywhere

### Data Models (Pydantic)
- `Checkpoint`: Work context snapshots with highlights
- `Task`: Cross-session task management (renamed from Todo)
- `Plan`: Persistent multi-step planning
- `Highlight`: Important moments/decisions

## Development Guidelines

### File Organization
```
src/tusk/
├── models/          # Pydantic data models
├── storage/         # JSON + Whoosh storage
├── tools/           # MCP tool implementations  
├── transformations/ # Adaptive tool interfaces
├── server.py        # FastMCP server setup
└── config.py        # Configuration management
```

### Data Storage Structure
```
~/.coa/tusk/
└── {workspace_name}/
    ├── checkpoints/{date}/{id}.json
    ├── tasks/tasks.json
    ├── plans/{id}.json
    └── index/          # Whoosh search index
```

### Testing Strategy
- Unit tests with pytest for all models
- Integration tests for storage operations
- Tool transformation tests for different interfaces
- End-to-end MCP server tests

### Key Principles

1. **Adaptive Complexity**: Tools adjust to user expertise
2. **Workspace Isolation**: All data organized by workspace
3. **Search-First**: Everything should be searchable
4. **Cross-Session**: Memory that survives context resets
5. **Human-Readable**: JSON for transparency

### Actual Tool Implementation Pattern
```python
# Current implementation uses enhanced tools with rich parameter descriptions
@mcp_server.tool
async def checkpoint(
    action: Annotated[str, "Operations: 'save', 'list', 'search'"],
    description: Annotated[Union[str, None], "Progress description for save"] = None,
    limit: Annotated[int, "Max results for list/search (5-20)"] = 5,
    query: Annotated[Union[str, None], "Search text"] = None
) -> str:
    """Save and retrieve work progress checkpoints."""
    # Implementation with AsyncIO-safe subprocess calls
```

### Test Coverage
Comprehensive test suite with 191 tests covering:
- **AsyncIO subprocess safety** (prevents MCP hanging)
- **Git integration** (cross-platform compatibility)
- **Checkpoint hanging regression** (stress tests)
- **Storage operations** (JSON + Whoosh)
- **Model validation** (Pydantic edge cases)
- **Tool functionality** (end-to-end MCP)

### Error Handling
- Use structured logging to ~/.coa/tusk/logs/ directory
- Graceful degradation when search fails
- Clear error messages for users
- Automatic recovery for corrupted files

### Performance Considerations
- Lazy loading of large datasets
- Whoosh index optimization
- File locking for concurrent access
- TTL-based cleanup of old data

## Development Commands

```bash
# Setup
pip install -e ".[dev]"

# Testing  
pytest

# Code quality
black src tests
ruff check src tests --fix
mypy src

# Run server
tusk-server
```

## Development Best Practices

### Testing Changes
1. **Write tests first**: `tests/test_*.py`
2. **Run test suite**: `pytest` (191 tests should pass)
3. **Test AsyncIO safety**: Especially for subprocess operations
4. **Restart Claude**: For MCP tool changes to take effect

### Code Quality Standards
```bash
# Before committing
black src tests              # Format code
ruff check src tests --fix   # Lint and fix
mypy src                     # Type checking
pytest                       # Run all tests
```

### Debugging MCP Tools
- **Logs**: Check `~/.coa/tusk/logs/tusk.log`
- **Verbose**: Add `--verbose` flag to tool operations
- **AsyncIO**: Use `asyncio.to_thread()` for subprocess calls
- **Timeouts**: Always set reasonable timeouts (3-5 seconds)

## Integration Points

### With Existing Goldfish
- Import data from Node.js Goldfish (archive/)
- Import data from C# Goldfish (COA.Goldfish.McpServer/)
- Migration scripts in migrations/

### With Claude Desktop
- MCP server configuration
- Tool registration and discovery
- Behavioral guidance via instructions

### With Other MCP Servers
- Non-conflicting tool names
- Complementary functionality
- Shared workspace concepts

## Current Status

✅ **Project structure and configuration**
✅ **Pydantic models with validation**
✅ **Storage system with JSON + Whoosh**
✅ **FastMCP server setup with tool transformations**
✅ **Core tools implemented** (checkpoint, task, plan, recall, standup)
✅ **Comprehensive testing** (191 tests passing)
✅ **AsyncIO-safe subprocess handling** (prevents hanging)
✅ **Azure DevOps CI/CD pipeline**
⏳ **Migration from existing Goldfish systems**

## Critical Development Information

### AsyncIO Subprocess Safety ⚠️
**CRITICAL**: All subprocess calls in MCP tools must use AsyncIO-safe patterns to prevent hanging:

```python
# ❌ WRONG - Will hang in MCP context
result = subprocess.run(['git', 'status'], capture_output=True)

# ✅ CORRECT - AsyncIO-safe using thread pool
async def safe_subprocess():
    def run_command():
        return subprocess.run(['git', 'status'], capture_output=True)
    return await asyncio.to_thread(run_command)

result = await asyncio.wait_for(safe_subprocess(), timeout=5.0)
```

**Why this matters**: Direct subprocess calls in async MCP tool functions cause deadlocks. Always use `asyncio.to_thread()` for subprocess operations.

### Live Development Cycle
**IMPORTANT**: MCP server code changes require Claude restart to take effect:

1. **Make code changes**
2. **Restart Claude Desktop completely** (critical - cached imports)
3. **Test changes**
4. **Run test suite**: `pytest`

Python import caching means live changes won't be seen until restart.