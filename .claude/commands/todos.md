---
allowed-tools: mcp__tusk__todo, mcp__tusk__complete
description: Show current todos or manage task list
argument-hint: [add "task" | complete <id> | list]
---

$if($1 == "add")
Add new todo: $2

This will create a persistent todo that survives across Claude Code sessions.

The task will be tracked in your Tusk memory and can be completed later with `/todos complete <id>`.

$elif($1 == "complete")
Mark todo as completed: $2

This will mark the specified todo ID as completed and update your task tracking.

$elif($1 == "list" || !$1)
Show your current todo list from Tusk memory.

This includes:
- **In Progress:** Tasks you're actively working on
- **Pending:** Tasks ready to be picked up
- **Recently Completed:** Tasks finished in recent sessions

Use `/todos add "description"` to add new tasks or `/todos complete <id>` to mark tasks as done.

$else
Manage your persistent todo list:

- `/todos list` - Show current todos
- `/todos add "task description"` - Add new task
- `/todos complete <todo-id>` - Mark task as completed

All todos persist across Claude Code sessions and help maintain continuity in your work.
$endif