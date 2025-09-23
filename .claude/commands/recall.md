---
allowed-tools: mcp__tusk__recall
description: Restore context from previous work sessions
argument-hint: [days]
---

$if($ARGUMENTS)
**Recalling Context:** Loading context from the last $ARGUMENTS days.

Using `recall(days=$ARGUMENTS)` to restore recent work context and progress.

$else
**Default Recall:** Loading context from the last 2 days.

Using `recall(days=2)` to restore recent work context and progress.

This helps maintain continuity across Claude sessions by recovering:
- Recent checkpoints and progress
- Project context and decisions
- Key breakthroughs and discoveries

Use `/recall 7` for week-long context or `/recall 1` for just today.

Multi-workspace support: By default shows current workspace only. The tool supports workspace filtering for cross-project context.
$endif