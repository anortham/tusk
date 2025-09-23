
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

# Migration from Python tusk
bun run migrate.ts
```

## Architecture

- **index.ts**: MCP server with behavioral instructions (~480 lines)
- **cli.ts**: Command-line interface (~295 lines)
- **journal.ts**: SQLite storage with multi-workspace support (~845 lines)
- **git.ts**: Git context capture (~200 lines)
- **standup.ts**: Report formatters (~395 lines)

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

✅ **Simple**: 3 tools (checkpoint, recall, standup)
✅ **Fast**: Bun + SQLite with WAL mode
✅ **Persistent**: Survives Claude crashes/compaction
✅ **Git-aware**: Automatic workspace and context detection
✅ **Behavioral**: Built-in AI agent guidance for proactive usage

## Integration

- **Claude Desktop**: MCP server auto-registers tools and behavioral instructions
- **Claude Code**: CLI commands for post-work hooks
- **Direct CLI**: Manual journaling and standup generation
