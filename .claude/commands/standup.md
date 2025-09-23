---
allowed-tools: mcp__tusk__standup
description: Generate standup reports from your development journal
argument-hint: [style] [days]
---

Generate a standup report from your journal showing recent work progress and accomplishments.

Available styles:
- **meeting**: Classic standup format (default)
- **written**: Narrative summary format
- **executive**: High-level impact summary
- **metrics**: Dashboard with productivity stats

$if($1 == "executive")
Generate executive standup using `standup(style="executive", days=3)` for leadership updates.
$elif($1 == "metrics")
Generate metrics dashboard using `standup(style="metrics", days=7)` for detailed analytics.
$elif($1 == "written")
Generate written summary using `standup(style="written", days=2)` for narrative format.
$elif($1)
Generate standup using `standup(style="meeting", days=$1)` for the last $1 days.
$else
Generate daily standup using `standup(style="meeting", days=1)` for recent progress.
$endif

**Features:**
- Multi-workspace support (current workspace by default)
- Automatic project and git context
- Progress highlights and next steps
- File activity tracking (optional)

Examples:
- `/standup` - Daily meeting format
- `/standup executive` - Executive summary
- `/standup metrics` - Analytics dashboard
- `/standup 7` - Weekly meeting format