
# Tusk Development Guide

**Developer journal and standup tool** built with Bun + SQLite, providing persistent memory for AI agents through MCP.

## Quick Commands

```bash
# Development
bun install && bun run dev

# Testing
bun test
bun test:coverage
bun run type-check

# CLI usage (for hooks)
bun cli.ts checkpoint "What you accomplished"
bun cli.ts recall --days 7
bun cli.ts standup --style executive
bun cli.ts timeline --days 30

# Migration from Python tusk
bun run migrate.ts
```

## Architecture

- **index.ts**: MCP server with 3 tools (checkpoint, recall, plan) + behavioral instructions
- **cli.ts**: Command-line interface with 4 commands (checkpoint, recall, standup, timeline)
- **src/core/journal-db.ts**: SQLite storage with multi-workspace support
- **src/integrations/git.ts**: Git context capture
- **src/reports/standup.ts**: Report formatters (integrated into recall)
- **src/timeline/**: Transcript archive timeline viewer (6 modules)

## Data Storage

- **Location**: `~/.tusk/journal.db` (SQLite)
- **Features**: Multi-workspace isolation, concurrency, cross-platform paths
- **Auto-captures**: Git context, project detection, file changes

## Development Guidelines

- **Use Bun APIs**: `spawnSync()`, `Bun.file()`, native SQLite
- **TypeScript strict mode**: Full typing with Zod validation
- **Error handling**: Graceful fallbacks for git operations
- **Testing**: Comprehensive test suite with performance benchmarks

## Key Principles

✅ **Simple**: 3 MCP tools (checkpoint, recall with integrated standup, plan)
✅ **Fast**: Bun + SQLite with WAL mode
✅ **Persistent**: Survives Claude crashes/compaction
✅ **Git-aware**: Automatic workspace and context detection
✅ **Behavioral**: Built-in AI agent guidance for proactive usage
✅ **Timeline**: Time Machine-style transcript archive viewer (CLI)

## Integration

- **Claude Desktop**: MCP server auto-registers 3 tools and behavioral instructions
- **Claude Code**: CLI commands for post-work hooks (checkpoint, recall, standup, timeline)
- **Direct CLI**: Manual journaling, standup generation, and timeline viewing
