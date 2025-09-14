---
allowed-tools: mcp__tusk__task
description: Show current tasks or manage task list
argument-hint: [add "task" | complete <id> | list]
---

$if($1 == "add")
Add new task: $2

This will use `task(action="add", task="$2")` to create a persistent task that survives across Claude Code sessions.

$elif($1 == "complete")
Mark task as completed: $2

This will use `task(action="complete", task_id="$2")` to mark the specified task as completed.

$elif($1 == "list" || !$1)
Show your current task list using `task(action="list")`.

This includes:
- **In Progress:** Tasks you're actively working on
- **Pending:** Tasks ready to be picked up

Use `/tasks add "description"` to add new tasks or `/tasks complete <id>` to mark tasks as done.

$else
Manage your persistent task list using the unified `task()` tool:

- `/tasks list` - Show current tasks with `task(action="list")`
- `/tasks add "task description"` - Add new task with `task(action="add", task="...")`
- `/tasks complete <task-id>` - Mark task as completed with `task(action="complete", task_id="...")`

All tasks persist across Claude Code sessions and help maintain continuity in your work.
$endif