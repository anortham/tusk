
# Tusk-Bun Development Guide

This project is a **developer journal and standup tool** built with Bun, providing persistent memory for AI agents through MCP (Model Context Protocol).

## Core Architecture

- **MCP Server** (`index.ts`): Serves 3 tools to Claude Desktop - checkpoint, recall, standup
- **CLI Interface** (`cli.ts`): Command-line access for hooks and direct usage
- **Journal Storage** (`journal.ts`): JSONL-based persistence in `~/.tusk/journal.jsonl`
- **Git Integration** (`git.ts`): Automatic context capture (branch, commit, files)
- **Report Generation** (`standup.ts`): 4 report styles (meeting, written, executive, metrics)

## Development Commands

**Use Bun for all operations:**

```bash
# Install dependencies
bun install

# Start MCP server (for Claude Desktop)
bun run index.ts

# Development with hot reload
bun run dev

# Test CLI tools directly
bun cli.ts checkpoint "Test checkpoint"
bun cli.ts recall --days 7
bun cli.ts standup --style executive

# Using npm scripts
bun run checkpoint "Test checkpoint"
bun run recall
bun run standup

# Run migration from Python tusk
bun run migrate.ts --help
```

## Testing the Project

```bash
# Test all functionality
bun run test-tools.ts  # (create if needed)

# Test MCP server manually
echo '{"method":"tools/call","params":{"name":"checkpoint","arguments":{"description":"Test"}}}' | bun run index.ts

# Check journal contents
cat ~/.tusk/journal.jsonl
```

## Project Structure

```
tusk-bun/
├── index.ts          # MCP server (main entry point)
├── cli.ts            # Command-line interface
├── journal.ts        # JSONL storage operations
├── git.ts            # Git context capture
├── standup.ts        # Report formatters
├── migrate.ts        # Python tusk migration
└── package.json      # Dependencies and scripts
```

## Data Storage

- **Location**: `~/.tusk/journal.jsonl`
- **Format**: One JSON object per line (human-readable)
- **Auto-captures**: Git branch, commit, changed files, project name

## Development Workflow

1. **Make changes** to TypeScript files
2. **Test with CLI**: `bun cli.ts checkpoint "What you accomplished"`
3. **Test MCP integration**: Start server with `bun run index.ts`
4. **Verify data**: Check `~/.tusk/journal.jsonl` for entries

## Code Style

- Use **Bun APIs** where possible: `Bun.file()`, `spawnSync()`, etc.
- **TypeScript**: Strict typing with Zod validation
- **Error handling**: Graceful fallbacks for git operations
- **Simple storage**: Append-only JSONL for persistence

## Integration Points

- **Claude Desktop**: Add to `claude_desktop_config.json` as MCP server
- **Claude Code Hooks**: Use `bun cli.ts checkpoint` in post-work hooks
- **Command Line**: Direct CLI usage for manual journaling

## Key Design Principles

✅ **Simple**: 3 tools, JSONL storage, ~1,300 lines
✅ **Fast**: Bun + simple file operations
✅ **Persistent**: Survives Claude crashes/compaction
✅ **Git-aware**: Automatic context capture
✅ **Human-readable**: JSONL you can edit/search manually
✅ **Behavioral**: Built-in instructions guide proactive AI agent usage

## Behavioral Instructions

The MCP server includes comprehensive behavioral instructions that guide AI agents to:

### 🎯 **Proactive Usage Patterns**
- **Always start sessions** with `recall()` to restore context
- **Automatically checkpoint** after significant work (bug fixes, features, discoveries)
- **Build emergency recovery data** with quality descriptions and tags
- **Generate standups** for progress summaries and team updates

### 🚨 **Critical Triggers for Checkpointing**
- Code completion (functions, classes, modules)
- Bug fixes and problem resolution
- Important discoveries or breakthroughs
- Work session milestones
- Before context switching

### 🎪 **Success Metrics**
- Sessions start with context recovery
- Important moments are captured
- Knowledge persists across sessions
- Valuable standup reports generated

These instructions are embedded directly in the server initialization, ensuring Claude receives behavioral guidance automatically when the MCP server is registered.
