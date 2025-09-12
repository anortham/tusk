---
allowed-tools: mcp__tusk__save
description: Save current work state as a checkpoint
argument-hint: [description]
---

$if($ARGUMENTS)
Save checkpoint: $ARGUMENTS

Create a checkpoint to preserve your current work context, progress, and any key decisions or discoveries.

This checkpoint will be searchable and can be recalled in future sessions to restore context.

$else
Save a checkpoint of your current work progress.

Please describe what you've been working on or what significant progress/decisions should be captured.

Example: `/checkpoint "Completed user authentication system with OAuth2 integration"`

Checkpoints help maintain context across sessions and preserve important work milestones.
$endif