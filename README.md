# Tusk - Persistent Memory for AI Agents 🐘

> Like an elephant's memory - never forget your work across Claude sessions

Tusk is a Python-based MCP (Model Context Protocol) server that provides persistent memory for AI agents. Unlike typical AI conversations that "forget" previous sessions, Tusk gives Claude elephant-like memory that remembers your work across sessions and context windows.

## What Does Tusk Do?

- **🔖 Checkpoints**: Save important progress moments with context for later recall
- **📝 Tasks**: Manage to-dos that persist between Claude sessions
- **📋 Plans**: Create multi-step project plans that survive context resets
- **🧠 Recall**: Automatically restore previous work context when you return
- **📊 Standup**: Generate progress summaries across all your work

## Installation & Setup

### 1. Install Tusk
Currently install from source (PyPI package coming soon):

```bash
# Clone the repository
git clone https://github.com/anortham/tusk.git
cd tusk

# Install in development mode
pip install -e ".[dev]"
```

### 2. Start the Tusk Server
```bash
tusk-server
```

The server will start on stdio and create data directories in `~/.coa/tusk/`.

### 3. Configure Claude Desktop
Add Tusk to your Claude Desktop MCP configuration:

**On Windows**: Edit `%APPDATA%\Claude\claude_desktop_config.json`
**On Mac**: Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tusk": {
      "command": "tusk-server",
      "args": []
    }
  }
}
```

### 4. Restart Claude Desktop
Close and reopen Claude Desktop to load the Tusk MCP server.

## Using Tusk

Once configured, Claude will have access to Tusk's memory tools:

### Save Your Progress
```
Create a checkpoint of my current work on the authentication system
```

### Restore Previous Sessions
```
What was I working on? Use recall to show my recent progress
```

### Manage Persistent Tasks
```
Add a task: "Implement password reset functionality"
```

### Plan Multi-Step Projects
```
Create a plan for implementing the user dashboard with these steps: design UI, create API endpoints, add authentication, write tests
```

### Generate Progress Summaries
```
Give me a standup report of what I accomplished this week
```

## How It Works

Tusk stores your work context in human-readable JSON files in `~/.coa/tusk/`. Each piece of information is searchable and organized by project. Your data stays on your machine - nothing is sent to external servers.

## Troubleshooting

### Tusk Server Won't Start
- Ensure Python 3.11+ is installed: `python --version`
- Check if port is available: `netstat -an | findstr :3000`
- Look for error messages in `~/.coa/tusk/logs/tusk.log`

### Claude Can't Find Tusk Tools
- Verify MCP configuration is correct in `claude_desktop_config.json`
- Restart Claude Desktop completely
- Check that `tusk-server` is running: `ps aux | grep tusk-server`

### Memory Not Persisting
- Check data directory exists: `ls ~/.coa/tusk/`
- Verify write permissions on the directory
- Look for storage errors in the logs

### Need Help?
- Check the logs: `~/.coa/tusk/logs/tusk.log`
- Report issues: [GitHub Issues](https://github.com/anortham/tusk/issues)

## Development

Want to contribute or modify Tusk?

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

# Start development server
tusk-server
```

### Testing Your Changes
When modifying Tusk code:
1. Make your changes
2. **Restart Claude Desktop** (important - MCP servers cache code)
3. Test your changes
4. Run the test suite: `pytest`

## Architecture

For developers: Tusk uses FastMCP 2.0 with JSON file storage and Whoosh full-text search. See `CLAUDE.md` for detailed development information.

## License

MIT License - see LICENSE file for details.