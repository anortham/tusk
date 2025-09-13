---
allowed-tools: mcp__tusk__todo
description: Show current todos or manage task list
argument-hint: [add "task" | complete <id> | list]
---

$if($1 == "add")
Add new todo: $2

This will use `todo(action="add", task="$2")` to create a persistent todo that survives across Claude Code sessions.

$elif($1 == "complete")
Mark todo as completed: $2

This will use `todo(action="complete", task_id="$2")` to mark the specified todo as completed.

$elif($1 == "list" || !$1)
Show your current todo list using `todo(action="list")`.

This includes:
- **In Progress:** Tasks you're actively working on
- **Pending:** Tasks ready to be picked up

Use `/todos add "description"` to add new tasks or `/todos complete <id>` to mark tasks as done.

$else
Manage your persistent todo list using the unified `todo()` tool:

- `/todos list` - Show current todos with `todo(action="list")`
- `/todos add "task description"` - Add new task with `todo(action="add", task="...")`
- `/todos complete <todo-id>` - Mark task as completed with `todo(action="complete", task_id="...")`

All todos persist across Claude Code sessions and help maintain continuity in your work.
$endif