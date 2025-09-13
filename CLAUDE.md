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
- `Todo`: Cross-session task management
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
    ├── todos/todos.json
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

### Tool Transformation Examples
```python
# Beginner mode - simplified
simple_checkpoint = Tool.from_tool(
    checkpoint_create,
    name="save",
    transform_args={
        "workspace": ArgTransform(hidden=True, default=current_workspace),
        "highlights": ArgTransform(hidden=True),  # Auto-extract
    }
)

# Expert mode - full control
expert_checkpoint = checkpoint_create  # Original with all options
```

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

## Live Development Limitations

**IMPORTANT**: When the MCP server is running live in a Claude session, code changes to Python modules **will not take effect immediately**. Python imports are cached and the MCP server process continues running with the old code.

**To see code changes:**
- Restart Claude completely to reload the MCP server
- Or restart the `tusk-server` process manually

**This affects:**
- Tool implementations (`src/tusk/tools/`)
- Server configuration (`src/tusk/server.py`)
- Model changes (`src/tusk/models/`)
- Any Python module modifications

**Testing changes during development:**
1. Make code changes
2. Restart Claude session 
3. Test the changes
4. Repeat cycle

This is a standard limitation of live Python processes - not specific to Tusk.

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

✅ Project structure and configuration  
✅ Pydantic models with validation  
🔄 Storage system with JSON + Whoosh  
⏳ FastMCP server setup  
⏳ Core tools with transformations  
⏳ Migration from existing Goldfish  

## Next Steps

1. Implement storage layer with Whoosh
2. Create FastMCP server with tool transformations
3. Build core tools (checkpoint, todo, plan, recall, standup)
4. Add behavioral guidance and progressive disclosure
5. Create migration scripts from existing systems
6. Add comprehensive testing and documentation