---
allowed-tools: mcp__tusk__standup
description: Generate daily/weekly standup report from Tusk memory
argument-hint: [period]
---

Generate a standup report from Tusk memory showing:

**Recent Work (Last 2 Days):**
- Completed checkpoints with highlights
- Finished todos and their outcomes  
- Plan progress and next steps

**Current Status:**
- Active todos in progress
- Pending tasks to pick up
- Current plan focus areas

**Blockers & Issues:**
- Any incomplete work requiring attention
- Stale todos that may need cleanup

**Next Actions:**
- Recommended priorities for upcoming work
- Plan steps ready to begin
- Context for continued work

$if($1)
Show standup for timeframe: $1 (recent/weekly/monthly)
$else
Show recent standup (last 2 days)
$endif

This uses your persistent Tusk memory to provide context across sessions and gives a comprehensive view of your development progress.