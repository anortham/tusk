# Tusk Installation Guide

## Prerequisites

- Python 3.11 or later
- Claude Desktop (for MCP integration)

## Installation

### Option 1: Install from Source (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/anortham/tusk.git
cd tusk

# Create a virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

### Option 2: Install from PyPI (Coming Soon)

```bash
pip install tusk-memory-mcp
```

## Configuration

### Environment Variables

You can configure Tusk using environment variables:

```bash
# Basic configuration
export TUSK_WORKSPACE="my_project"           # Default workspace name
export TUSK_DATA_DIR="~/.coa/tusk"          # Data storage directory (default: ~/.coa/tusk)
export TUSK_LOG_LEVEL="INFO"                 # Logging level
export TUSK_EXPERTISE_LEVEL="beginner"       # Tool complexity level

# Advanced configuration  
export TUSK_DEFAULT_TTL="7d"                 # Default checkpoint expiration
export TUSK_MAX_SEARCH_RESULTS="20"          # Maximum search results
export TUSK_TRANSFORMATIONS="true"           # Enable adaptive tools
```

### Claude Desktop Configuration

Add Tusk to your Claude Desktop MCP servers configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tusk": {
      "command": "python",
      "args": ["-m", "src.tusk.server"],
      "env": {
        "TUSK_WORKSPACE": "default",
        "TUSK_DATA_DIR": "~/.coa/tusk"
      }
    }
  }
}
```

Alternatively, if you installed globally:

```json
{
  "mcpServers": {
    "tusk": {
      "command": "tusk-server",
      "env": {
        "TUSK_WORKSPACE": "my_project"
      }
    }
  }
}
```

## Testing Installation

### Run Unit Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_basic_functionality.py
```

### Manual Testing

Start the server manually to test:

```bash
# Run in stdio mode (for Claude Desktop)
python -m src.tusk.server

# Or use the command line tool (after pip install)
tusk-server
```

The server will start and display:
```
INFO - Tusk server starting with stats: {'workspace': 'default', 'checkpoints': 0, 'todos': 0, 'plans': 0}
INFO - Starting Tusk server with stdio transport
```

### Test with Claude Desktop

1. Restart Claude Desktop after updating the configuration
2. Start a new conversation
3. Try these commands to test Tusk:

```
recall
```

Should respond with a welcome message showing no previous context.

```
save_progress "Testing Tusk installation"
```

Should create your first checkpoint.

```
add_task "Set up my first project"
```

Should create your first todo.

## Directory Structure

After installation and first use, Tusk creates this structure:

```
~/.coa/tusk/
├── {workspace_name}/
│   ├── checkpoints/
│   │   └── {date}/
│   │       └── {checkpoint_id}.json
│   ├── todos/
│   │   └── todos.json
│   ├── plans/
│   │   └── {plan_id}.json
│   └── index/              # Whoosh search index
├── logs/
│   └── tusk_{workspace}.log
```

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'tusk'"**
- Make sure you activated your virtual environment
- Reinstall with `pip install -e .`

**"Permission denied" when starting server**
- Check file permissions in your data directory
- Make sure the data directory exists and is writable

**"Index creation failed" in logs**
- Check disk space in your data directory
- Verify write permissions for the index directory

**Claude Desktop doesn't recognize Tusk**
- Verify the JSON configuration is valid (use a JSON validator)
- Check the path to Python and tusk-server command
- Restart Claude Desktop completely

### Debug Mode

Enable debug logging for more detailed information:

```bash
export TUSK_LOG_LEVEL="DEBUG"
tusk-server
```

### Getting Help

- Check the logs in `~/.coa/tusk/logs/tusk_{workspace}.log`
- Run tests to verify installation: `pytest -v`
- Create an issue at https://github.com/anortham/tusk/issues

## Next Steps

Once installed, see [USAGE.md](USAGE.md) for a comprehensive guide to using Tusk's memory features.