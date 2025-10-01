# Tusk 🐘

> Developer journal and standup tool - persistent memory for AI agents

A complete rewrite of tusk in Bun, focused on what actually works: **journaling work progress** and **generating beautiful standup reports**. No task management complexity - just simple, effective memory that survives Claude sessions.

## Why Tusk?

- **🧠 Context Recovery**: Never lose important work details to Claude crashes or compaction
- **🤖 Proactive AI Behavior**: Built-in instructions guide AI agents to checkpoint automatically
- **📊 Beautiful Standups**: Generate meeting-ready reports from your journal
- **⚡ Blazing Fast**: Bun + SQLite = instant saves and recalls with concurrency
- **🔍 Simple & Searchable**: SQLite-based journal with powerful filtering and workspace isolation

## Quick Start

### 1. Install & Run

```bash
# Clone and install
git clone <repository-url> tusk
cd tusk
bun install

# Start the MCP server
bun run index.ts
```

### 2. Configure Claude Desktop

Add to your Claude Desktop MCP configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tusk": {
      "command": "bun",
      "args": ["run", "/absolute/path/to/tusk/index.ts"]
    }
  }
}
```

**Platform-specific paths**:
```json
// Windows example
{
  "mcpServers": {
    "tusk": {
      "command": "bun",
      "args": ["run", "C:\\Users\\YourName\\tusk\\index.ts"]
    }
  }
}

// macOS/Linux example
{
  "mcpServers": {
    "tusk": {
      "command": "bun",
      "args": ["run", "/Users/yourname/tusk/index.ts"]
    }
  }
}
```

### 3. Start Using

**Via MCP (Claude Desktop):**
```
checkpoint("Started working on the auth system")
recall()
recall(standup="meeting")  # Standup integrated into recall
plan(action="save", title="Q4 Roadmap", content="...")
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

# View transcript timeline
bun cli.ts timeline
bun cli.ts timeline --days 30 --verbose
```

### Claude Code Hook Integration

Tusk provides automatic checkpoint capture through Claude Code hooks. These hooks work cross-platform on Windows, macOS, and Linux.

#### Quick Setup

**Step 1**: Copy hooks to your project:
```bash
# Copy hooks from tusk installation to your project
cp -r /path/to/tusk/.claude ./

# Or create .claude/hooks directory and copy manually
mkdir -p .claude/hooks
cp /path/to/tusk/.claude/hooks/* .claude/hooks/
```

**Step 2**: Configure hooks in Claude Code settings:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

```json
{
  "hooks": {
    "user_prompt_submit": {
      "command": ".claude/hooks/user_prompt_submit.ts"
    },
    "stop": {
      "command": ".claude/hooks/stop.ts"
    },
    "post_tool_use": {
      "command": ".claude/hooks/post_tool_use.ts"
    },
    "pre_compact": {
      "command": ".claude/hooks/pre_compact.ts"
    }
  }
}
```

#### Cross-Platform Notes

**All Platforms** (Windows, macOS, Linux):
- Bun executes `.ts` files directly with the shebang line
- Hooks automatically detect tusk CLI location relative to the hook directory
- No need to modify paths when copying hooks between projects
- Ensure Bun is in your system PATH
- Hook files should be executable on Unix systems: `chmod +x .claude/hooks/*.ts`
- Hooks log minimal activity to `~/.tusk/hooks.log` with daily rotation

#### Manual Integration

If you prefer manual checkpointing, add to your project's `CLAUDE.md`:

```markdown
## Post-Work Hook
After completing any significant work, run:
bun /path/to/tusk/cli.ts checkpoint "Brief description of what was accomplished"
```

## The Core Tools

### 📝 checkpoint
Save work progress across Claude sessions:
```
checkpoint("Fixed JWT timeout bug using refresh tokens")
checkpoint("Implemented user dashboard", ["feature", "ui"])
```

### 🧠 recall
Restore context from previous work (includes optional standup):
```
recall()                                    # Last 2 days with active plan
recall(days=7, search="auth")               # Search last week
recall(project="myproject")                 # Project-specific
recall(standup="meeting")                   # Context + standup report
recall(days=7, standup="executive")         # Weekly executive summary
```

### 📋 plan
Manage long-running project plans that survive sessions:
```
plan(action="save", title="...", content="...")   # Save new plan
plan(action="list")                                # View all plans
plan(action="update", planId="...", progress="...") # Track progress
plan(action="complete", planId="...")              # Mark done
```

### 🕰️ timeline (CLI only)
View transcript archive history (Time Machine style):
```bash
bun cli.ts timeline                    # Last 7 days
bun cli.ts timeline --days 30          # Last 30 days
bun cli.ts timeline --date 2025-10-01  # Specific date
bun cli.ts timeline --verbose          # Detailed view
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

- **Location**: `~/.tusk/journal.db`
- **Format**: SQLite database with multi-workspace support
- **Features**:
  - Automatic workspace detection (git root, package.json, or cwd)
  - Cross-platform path normalization
  - Concurrent access with WAL mode
  - Workspace isolation for projects
- **Schema**: Checkpoints with git context, project info, and metadata

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
bun cli.ts timeline --days 30

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

**Core:**
- **index.ts**: MCP server with 3 tools (checkpoint, recall, plan) + behavioral instructions
- **cli.ts**: Command-line interface for hooks/direct usage
- **src/core/journal-db.ts**: SQLite storage with multi-workspace support
- **src/integrations/git.ts**: Git context capture
- **src/reports/standup.ts**: Report formatters (integrated into recall)
- **src/timeline/**: Transcript archive timeline viewer (6 modules)

**Migration:**
- **migrate.ts**: Python tusk migration utility

Clean, focused architecture with ~3,200 lines vs 6,358 lines in Python tusk!

## Why Not Python Tusk?

- **Over-engineered**: 6,358 lines for basic journaling
- **Async complexity**: Subprocess deadlocks and AsyncIO pain
- **Identity crisis**: Tasks, plans, checkpoints, search engines
- **Python tax**: Virtual environments, dependencies, models

## Design Philosophy

### What We Do
✅ **Developer journaling** - capture progress moments
✅ **Context recovery** - survive Claude crashes
✅ **Standup generation** - beautiful formatted reports (integrated into recall)
✅ **Project planning** - long-running plans that survive compaction
✅ **Timeline viewing** - Time Machine-style transcript history
✅ **Git integration** - automatic context capture
✅ **Robust storage** - SQLite with workspace isolation and concurrency

### What We Don't Do
❌ **Task management** - Claude's TodoWrite handles this
❌ **Complex search engines** - SQLite FTS is sufficient
❌ **Multiple backends** - SQLite works perfectly
❌ **Over-abstraction** - just three core MCP tools

## Credits

- **Standup formatting** inspired by the original goldfish standup tool
- **MCP integration** based on the ModelContextProtocol SDK
- **Built with** [Bun](https://bun.com) - the fast all-in-one JavaScript runtime

---

*"Like an elephant's memory - never forget your work across Claude sessions"* 🐘
