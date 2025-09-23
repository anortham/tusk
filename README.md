# Tusk-Bun 🐘

> Developer journal and standup tool - persistent memory for AI agents

A complete rewrite of tusk in Bun, focused on what actually works: **journaling work progress** and **generating beautiful standup reports**. No task management complexity - just simple, effective memory that survives Claude sessions.

## Why Tusk-Bun?

- **🧠 Context Recovery**: Never lose important work details to Claude crashes or compaction
- **🤖 Proactive AI Behavior**: Built-in instructions guide AI agents to checkpoint automatically
- **📊 Beautiful Standups**: Generate meeting-ready reports from your journal
- **⚡ Blazing Fast**: Bun + JSONL = instant saves and recalls
- **🔍 Simple & Searchable**: Human-readable journal with powerful filtering

## Quick Start

### 1. Install & Run

```bash
# Clone and install
git clone <repository-url> tusk-bun
cd tusk-bun
bun install

# Start the MCP server
bun run index.ts
```

### 2. Configure Claude Desktop

Add to your Claude Desktop MCP configuration:

**Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tusk-bun": {
      "command": "bun",
      "args": ["run", "/path/to/tusk-bun/index.ts"]
    }
  }
}
```

### 3. Start Using

**Via MCP (Claude Desktop):**
```
checkpoint("Started working on the auth system")
recall()
standup(style="meeting")
```

**Via CLI (Command Line & Claude Code Hooks):**
```bash
# Save a checkpoint
bun cli.ts checkpoint "Fixed auth timeout bug"
bun cli.ts cp "Added user dashboard" "feature,ui"

# Recall previous work
bun cli.ts recall
bun cli.ts recall --days 7 --search auth

# Generate standup
bun cli.ts standup
bun cli.ts standup --style executive --days 3
```

### Claude Code Hook Integration

Add to your project's `CLAUDE.md` for automatic progress tracking:

```markdown
## Post-Work Hook
After completing any significant work, run:
bun /path/to/tusk-bun/cli.ts checkpoint "Brief description of what was accomplished"
```

## The Three Tools

### 📝 checkpoint
Save work progress across Claude sessions:
```
checkpoint("Fixed JWT timeout bug using refresh tokens")
checkpoint("Implemented user dashboard", ["feature", "ui"])
```

### 🧠 recall
Restore context from previous work:
```
recall()                           # Last 2 days
recall(days=7, search="auth")      # Search last week
recall(project="myproject")        # Project-specific
```

### 📊 standup
Generate beautiful reports:
```
standup()                          # Meeting format
standup(style="executive")         # High-level summary
standup(style="metrics", days=7)   # Weekly dashboard
```

## Migration from Python Tusk

Import your existing checkpoints:

```bash
# Preview what will be migrated
bun run migrate.ts --dry-run --verbose

# Perform the migration
bun run migrate.ts

# Custom tusk location
PYTHON_TUSK_DIR=/path/to/tusk bun run migrate.ts
```

## Data Storage

- **Location**: `~/.tusk/journal.jsonl`
- **Format**: One JSON object per line (human-readable)
- **Structure**:
  ```json
  {
    "id": "20241201_143052_abc123",
    "type": "checkpoint",
    "timestamp": "2024-12-01T14:30:52.123Z",
    "description": "Fixed auth timeout bug",
    "project": "myproject",
    "gitBranch": "feature/auth-fix",
    "gitCommit": "a1b2c3d",
    "files": ["src/auth.ts", "src/login.tsx"],
    "tags": ["bug-fix", "auth"]
  }
  ```

## Standup Formats

### Meeting Style (Default)
```
🏃‍♂️ Daily Standup (last 24 hours)
📍 Projects: myproject

✅ What I accomplished:
   • Fixed auth timeout bug using JWT refresh pattern (2h ago)
   • Implemented user dashboard UI components (4h ago)

⭐ Key highlights:
   • Resolved critical security vulnerability
   • Achieved 100% test coverage

🚀 Next steps:
   • Deploy auth fix to staging
   • Add user preferences panel
```

### Executive Style
```
🎯 Executive Summary (last 24 hours)
Portfolio: myproject • dashboard-redesign

Impact: Delivered 3 key achievements across 2 strategic initiatives
with high development velocity (8 work sessions).

Strategic Focus:
1. myproject - 6 active sessions
2. dashboard-redesign - 2 active sessions

Key Wins:
1. Resolved critical security vulnerability
2. Achieved 100% test coverage
3. Completed user dashboard implementation

Forward Outlook:
Priority actions: Deploy to staging • Add user preferences
```

## Development

```bash
# Development with hot reload
bun run dev

# Test CLI tools directly
bun cli.ts checkpoint "Test checkpoint from CLI"
bun cli.ts recall --days 7
bun cli.ts standup --style metrics

# Using npm scripts
bun run checkpoint "Test checkpoint"
bun run recall
bun run standup

# Test MCP server manually (advanced)
echo '{"method":"tools/call","params":{"name":"checkpoint","arguments":{"description":"Test checkpoint"}}}' | bun run index.ts

# Run migration
bun run migrate.ts --help
```

## Architecture

- **index.ts**: MCP server with three tools (~350 lines)
- **cli.ts**: Command-line interface for hooks/direct usage (~200 lines)
- **journal.ts**: JSONL storage operations (~150 lines)
- **git.ts**: Git context capture (~100 lines)
- **standup.ts**: Report formatters (~300 lines)
- **migrate.ts**: Python tusk migration (~200 lines)

**Total**: ~1,300 lines vs 6,358 lines in Python tusk!

## Why Not Python Tusk?

- **Over-engineered**: 6,358 lines for basic journaling
- **Async complexity**: Subprocess deadlocks and AsyncIO pain
- **Identity crisis**: Tasks, plans, checkpoints, search engines
- **Python tax**: Virtual environments, dependencies, models

## Design Philosophy

### What We Do
✅ **Developer journaling** - capture progress moments
✅ **Context recovery** - survive Claude crashes
✅ **Standup generation** - beautiful formatted reports
✅ **Git integration** - automatic context capture
✅ **Simple storage** - human-readable JSONL

### What We Don't Do
❌ **Task management** - Claude's TodoWrite handles this
❌ **Project planning** - unnecessary complexity
❌ **Complex search** - grep/filter is sufficient
❌ **Multiple backends** - JSONL works perfectly
❌ **Progressive disclosure** - just three simple tools

## Credits

- **Standup formatting** inspired by the original goldfish standup tool
- **MCP integration** based on the ModelContextProtocol SDK
- **Built with** [Bun](https://bun.com) - the fast all-in-one JavaScript runtime

---

*"Like an elephant's memory - never forget your work across Claude sessions"* 🐘
