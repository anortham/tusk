# Tusk-Bun Design Document

## Vision
A simple developer journal that captures work progress and generates beautiful standup reports. Focus on what actually works: journaling + standups, not task management.

## Core Problems Solved
1. **Context Loss**: Claude crashes/compaction lose important work details
2. **Standup Generation**: Need formatted reports for meetings
3. **Work Continuity**: Returning to projects after time away

## Architecture (~500 lines total)

### File Structure
```
tusk-bun/
├── index.ts           # MCP server + tool registration (~150 lines)
├── journal.ts         # JSONL read/write operations (~100 lines)
├── git.ts            # Git context capture (~50 lines)
├── standup.ts        # Report formatters (~300 lines)
├── migrate.ts        # Migration from Python tusk (~50 lines)
└── docs/
    └── DESIGN.md     # This file
```

### Storage Strategy
- **Single file**: `~/.tusk/journal.jsonl`
- **One line per checkpoint**: JSON object with timestamp, description, git info
- **No database**: Read entire file into memory (fast in Bun)
- **Human readable**: Can inspect/edit with any text editor

### Journal Entry Format
```typescript
interface JournalEntry {
  id: string              // timestamp_random
  type: "checkpoint"      // Only checkpoints for now
  timestamp: string       // ISO 8601
  description: string     // User-provided progress description
  project?: string        // Auto-detected from git/path
  gitBranch?: string      // Current git branch
  gitCommit?: string      // Latest commit hash
  files?: string[]        // Recently modified files
  tags?: string[]         // User-provided tags
}
```

## The Three Tools

### 1. checkpoint
**Purpose**: Save work progress for later recall
```typescript
checkpoint(description: string, tags?: string[])
```
- Auto-captures: timestamp, git branch/commit, project path
- Appends to JSONL instantly
- No validation overhead

### 2. recall
**Purpose**: Restore context from previous work
```typescript
recall(days?: number, search?: string, project?: string)
```
- Returns recent checkpoints formatted nicely
- Search across descriptions, tags, projects
- Always used at session start

### 3. standup
**Purpose**: Generate formatted reports from journal
```typescript
standup(style: "meeting" | "written" | "executive", days?: number)
```
- **Meeting**: What I did, highlights, next steps
- **Written**: Narrative summary for documentation
- **Executive**: High-level impact metrics

## Key Design Principles

### What We ARE Building
✅ **Developer journal** - capture progress moments
✅ **Context recovery** - survive Claude crashes
✅ **Standup generation** - beautiful formatted reports
✅ **Git integration** - automatic branch/commit capture
✅ **Search/filter** - find specific work easily
✅ **Simple storage** - human-readable JSONL

### What We're NOT Building
❌ **Task management** - Claude's TodoWrite owns this
❌ **Project planning** - unnecessary complexity
❌ **Search indexes** - grep/filter is fast enough
❌ **Multiple backends** - JSONL is sufficient
❌ **Models/validation** - keep it simple
❌ **Progressive disclosure** - just three tools

## Migration Strategy
- Read existing Python tusk checkpoints from `~/.coa/tusk/`
- Convert to new JSONL format
- One-time import script
- Preserve timestamps and context

## Standup Formatting (from Goldfish)

### Meeting Style
```
🏃‍♂️ Daily Standup (last 24 hours)
📍 Project: myproject

✅ What I accomplished:
   • Fixed auth bug in login system
   • Completed user dashboard implementation

⭐ Key highlights:
   • 100% test coverage achieved

🚀 Next steps:
   • Deploy to staging environment
```

### Executive Style
```
🎯 Executive Summary (last 24 hours)
myproject

Impact: Delivered 3 completed tasks with 90% completion rate across 2 strategic initiatives.

Strategic Focus:
1. Authentication system - 85% complete
2. User dashboard - 100% complete

Key Wins:
1. Resolved critical security vulnerability
2. Achieved full test coverage
```

## Success Metrics
- ✅ Under 600 lines total
- ✅ Instant checkpoint saves (<100ms)
- ✅ Beautiful standup output (like goldfish)
- ✅ Survives Claude crashes
- ✅ Works immediately on install
- ✅ No dependencies beyond MCP SDK

## Usage Workflow

### Daily Workflow
1. **Start session**: Claude automatically runs `recall()`
2. **Work & capture**: `checkpoint("Fixed the auth timeout bug")`
3. **Generate standup**: `standup(style="meeting")` for team meeting

### Recovery Workflow
```
[Claude crashes during debugging]

New session:
> Claude runs recall() automatically
> Shows: "Recently you were working on auth timeout bug"
> Context restored, work continues
```

## Why This Will Work

### Solves Real Problems
- You miss tusk when it's not installed = genuine value
- Standup reports are actually used
- Context recovery prevents lost work

### Focused Scope
- No feature creep
- Competes with nothing (TodoWrite owns tasks)
- Does one thing extremely well

### Technical Advantages
- Bun eliminates Python complexity
- JSONL is portable and debuggable
- No async subprocess pain
- Hot reload for development

## Implementation Priority

1. ✅ **Project setup** - Bun init, dependencies
2. 🔄 **Journal storage** - JSONL operations
3. **Git integration** - Capture branch/commit info
4. **Standup formatters** - Port goldfish styles
5. **MCP server** - Register the three tools
6. **Migration script** - Import from Python tusk
7. **Testing** - Verify Claude Desktop integration

## Notes from Analysis

### Why Python Tusk Failed
- 6,358 lines for what should be simple
- Multiple inheritance layers (base → unified → enhanced_base → enhanced_unified → enhanced_all)
- Trying to be everything (tasks, plans, checkpoints, search)
- AsyncIO complexity for subprocess calls

### Why Original Goldfish Worked
- 638 lines of focused TypeScript
- Beautiful formatted output
- Smart aggregation across work types
- Actually solved the standup problem

### The Core Insight
You use this as a **work journal with standup generation**. Everything else was noise trying to find a purpose.