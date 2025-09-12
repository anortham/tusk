---
allowed-tools: mcp__tusk__search
description: Search all your work data across sessions
argument-hint: <query> [scope]
---

$if($ARGUMENTS)
Search Tusk memory for: "$ARGUMENTS"

This will search across all your persistent data:
- **Checkpoints:** Work sessions and progress milestones
- **Todos:** Current and completed tasks
- **Plans:** Project plans and implementation details
- **Discoveries:** Technical insights and decisions

The search will return relevant results with scores and allow you to quickly find information from previous sessions.

$else
Search your persistent Tusk memory across all sessions.

Usage: `/search <query> [scope]`

Examples:
- `/search "authentication bug"` - Find work related to auth issues
- `/search "API refactor" checkpoints` - Search only checkpoints
- `/search "user login" todos` - Find login-related tasks

Scopes: `all` (default), `checkpoints`, `todos`, `plans`

This helps you quickly find relevant context from previous work sessions.
$endif