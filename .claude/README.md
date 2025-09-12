# Tusk Claude Code Integration

This directory contains Claude Code hooks and custom commands that integrate with the Tusk memory system.

## 🪝 Hooks

### Pre-Compact Hook (`hooks/pre_compact.py`)
**Purpose:** Automatically saves a checkpoint before compaction starts to preserve work context.

**Benefits:**
- Prevents context loss during auto-compaction  
- Quick checkpoint with 24-hour TTL
- Works for both manual and auto compaction
- Non-blocking execution

**Usage:** Automatically triggered when Claude Code is about to compact. No user action required.

### User Prompt Submit Hook (`hooks/user_prompt_submit.py`)
**Purpose:** Captures plan mode discussions and important context to prevent loss during compaction.

**Features:**
- Detects plan mode discussions
- Auto-extracts plan steps, decisions, and discoveries
- Creates checkpoints with structured highlights
- Preserves planning context across sessions

**Usage:** Automatically triggered when you submit prompts. Detects patterns like "plan mode", "implementation plan", "strategy", etc.

### Stop Hook (`hooks/stop.py`) 
**Purpose:** Analyzes responses to detect work completion and suggest todo/plan updates.

**Features:**
- Detects completion language patterns
- Suggests marking todos as completed
- Prevents stale task buildup
- Provides actionable next steps

**Usage:** Automatically triggered when Claude finishes responding. Shows suggestions when completion is detected.

## 🔧 Custom Commands

### `/standup [period]`
Generate a comprehensive standup report showing:
- Recent work and completions
- Current active todos
- Plan progress and next steps
- Recommended priorities

**Examples:**
- `/standup` - Last 2 days (default)
- `/standup weekly` - Last 7 days
- `/standup monthly` - Last 30 days

### `/recall-check [auto|ask]`
Smart context checking with user control:
- `ask` - Show available context, let user decide
- `auto` - Automatically load relevant context
- (no args) - Smart check with recommendations

**Use Cases:**
- Starting fresh vs. continuing work
- Avoiding unwanted context loading
- Controlled session restoration

### `/checkpoint "description"`
Save current work state as a checkpoint:
- Preserves context for future sessions
- Searchable and recallable
- Includes work highlights and decisions

### `/todos [add|complete|list]`
Manage persistent todos:
- `add "task"` - Create new persistent todo
- `complete <id>` - Mark todo as completed
- `list` - Show current todo status

### `/search <query> [scope]`
Search all persistent memory:
- Full-text search across checkpoints, todos, plans
- Scoped search (checkpoints, todos, plans)
- Results with relevance scores

## 🚀 Setup

1. **Enable Hooks**: Ensure hook files in `.claude/hooks/` are executable
2. **Install Dependencies**: Hooks use UV for dependency management
3. **Configure Tusk**: Ensure Tusk server is accessible from hooks
4. **Test Integration**: Use `/standup` to verify everything is working

## 📝 Configuration

### Hook Configuration
Hooks are self-contained UV scripts with embedded dependencies. No additional configuration required.

### Command Configuration  
Commands use Claude Code's built-in argument parsing and tool restrictions. Each command specifies allowed MCP tools in frontmatter.

## 🔍 Troubleshooting

### Hook Issues
- Check `logs/tusk_hooks.json` for hook execution logs
- Verify UV is installed and accessible
- Ensure Tusk server is running and accessible

### Command Issues
- Verify MCP tools are available: `mcp__tusk__*`
- Check tool permissions in command frontmatter
- Confirm Tusk server is running

### Integration Issues
- Test basic Tusk functionality first
- Check hook file permissions (must be executable)
- Verify Python path and dependencies

## 🎯 Best Practices

1. **Use Pre-Compact Hooks**: Let them save context automatically
2. **Regular Standups**: Use `/standup` to review progress
3. **Controlled Recalls**: Use `/recall-check ask` when unsure about context
4. **Active Todo Management**: Complete todos when work is done
5. **Search First**: Use `/search` to find existing context before starting work

## 🔗 Integration with VS Code Bridge

The hooks and commands are designed to work with the MCP-VSCode-Bridge extension for rich visualizations:

- Todo lists with interactive checkboxes
- Timeline views of checkpoints  
- Plan progress visualizations
- Memory usage dashboards

This creates a complete memory system that bridges Claude Code and VS Code for optimal development workflow.