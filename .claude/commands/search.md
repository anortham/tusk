---
allowed-tools: mcp__tusk__checkpoint, mcp__tusk__task, mcp__tusk__plan
description: Search all your work data across sessions
argument-hint: <query> [scope]
---

$if($ARGUMENTS)
Search Tusk memory for: "$ARGUMENTS"

This will use the search actions on the unified tools:
- **Checkpoints:** `checkpoint(action="search", query="$ARGUMENTS")`
- **Tasks:** `task(action="search", query="$ARGUMENTS")`
- **Plans:** `plan(action="search", query="$ARGUMENTS")`

The search will return relevant results with scores and allow you to quickly find information from previous sessions.

$else
Search your persistent Tusk memory across all sessions using the unified tools.

Usage: `/search <query> [scope]`

Examples:
- `/search "authentication bug"` - Search across all data types
- `/search "API refactor"` - Find work related to API changes
- `/search "user login"` - Find login-related content

This uses the search actions on `checkpoint()`, `task()`, and `plan()` tools to find relevant context.
$endif