# Tusk Usage Guide

## Quick Start

Tusk provides persistent memory for AI agents through five core tools:

- **`recall`** - Restore context from previous sessions  
- **`checkpoint`** - Save work context with highlights
- **`todo`** - Manage tasks across sessions
- **`plan`** - Create persistent multi-step projects  
- **`standup`** - Generate work summaries

## Getting Started

### 1. Your First Session

Start any Claude conversation with:

```
recall
```

For new workspaces, you'll see:
```
🐘 Tusk Memory Recall - 2025-01-15 14:30
📁 Workspace: my_project

💭 No recent context found
This might be a fresh start! Create a checkpoint to begin tracking your work.
```

### 2. Save Your Work

As you work, save important moments:

```
save_progress "Completed user authentication system"
```

Response:
```
✅ Saved progress: Completed user authentication system

Checkpoint ID: abc123def456
```

### 3. Manage Tasks

Add tasks that persist across sessions:

```
add_task "Write unit tests for auth module"
```

List your tasks:
```
list_tasks
```

Start working on a task:
```
start_task abc123
```

Complete a task:
```
complete_task abc123
```

### 4. Next Session

When you start a new conversation (or hit context limits):

```
recall
```

You'll get a comprehensive summary:
```
🐘 Tusk Memory Recall - 2025-01-15 16:45
📁 Workspace: my_project

📊 Context Summary
- 3 checkpoints from last 7 days
- 2 active todos (1 in progress, 1 pending)
- 1 active plans

🔨 What I Worked On

📚 Recent Checkpoints (3):
1. [01-15 14:30] Completed user authentication system
   💡 2 highlights:
      • [completion] Added JWT token validation
      • [decision] Using bcrypt for password hashing

✅ Active Todos (2):
🔄 In Progress (1):
- Writing unit tests for auth module

⏳ Coming Up (1):
- Deploy to staging environment

🎯 Suggested Next Actions:
- Continue with in-progress todos
- Pick up pending todos
- Create a new checkpoint when you complete significant work
```

## Tool Details

### Checkpoints - Work Context Snapshots

Checkpoints save your work context with highlights for later restoration.

#### Simple Mode (Beginner)
```
save_progress "Your description here"
list_recent_saves
```

#### Expert Mode
```
create_checkpoint "Implemented caching layer" \
  --work-context "Added Redis integration with fallback to in-memory cache" \
  --active-files "cache.py,redis_client.py,config.py" \
  --highlights "Performance improved 10x,Redis failover works correctly" \
  --tags "performance,caching,redis" \
  --ttl "14d"
```

#### Search Checkpoints
```
search_checkpoints "redis caching"
get_checkpoint abc123def456
```

### Todos - Cross-Session Task Management

Todos persist across context resets and sessions.

#### Simple Mode
```
add_task "Fix the login bug"
list_tasks
start_task abc123
complete_task abc123
```

#### Expert Mode
```
create_todo "Implement OAuth integration" \
  --active-form "Implementing OAuth integration" \
  --priority "high" \
  --tags "auth,oauth,integration" \
  --estimated-duration "4h" \
  --notes "Need to support Google and GitHub providers"
```

#### Advanced Todo Management
```
# List by status
list_todos --status pending
list_todos --status completed

# Update status
update_todo_status abc123 blocked --notes "Waiting for API keys"

# Search todos
search_todos "oauth integration"

# Summary statistics
get_todo_summary
```

### Plans - Multi-Step Projects

Plans help manage complex projects with multiple steps.

#### Create a Plan
```
create_plan "User Dashboard Redesign" \
  "Complete overhaul of user dashboard UI/UX" \
  --goals "Improve user engagement,Reduce support tickets,Modern design" \
  --steps "Research current pain points,Create wireframes,Implement new design,User testing,Deploy to production" \
  --category "feature" \
  --priority "high"
```

#### Work with Plans
```
# List plans
list_plans
list_plans --status active

# Get detailed plan view
get_plan abc123def456

# Activate a plan
activate_plan abc123def456

# Complete steps
complete_step abc123def456 1

# Add new steps
add_plan_step abc123def456 "Add mobile responsive design"
```

#### Plan Progress
```
get_plan_summary
search_plans "dashboard redesign"
```

### Recall - Context Restoration

Recall intelligently restores your work context.

#### Basic Recall
```
recall                    # Last 7 days
recall_quick             # Last 2 days
daily_standup           # Yesterday + today's plan
weekly_standup          # Past week summary
```

#### Advanced Recall
```
# Specific timeframes
recall --days-back 14

# Filter by session or branch
recall_session "session_20250115_143022"
recall_branch "feature/auth-system"

# Control what's included
recall --include-todos=false --include-plans=true
```

### Standup - Work Summaries

Generate reports for meetings and progress tracking.

```
# Quick reports
daily_standup
weekly_standup

# Custom reports  
standup --timeframe weekly --include-completed=true
work_summary --days-back 5

# What you'll get:
# - Activity overview (checkpoints, todos, plan steps)
# - What you worked on (completed items)
# - What you're working on (active items)  
# - Blockers and issues
# - Suggested next actions
```

## Advanced Features

### Search Everything

Tusk indexes all your content for fast search:

```
search_checkpoints "performance optimization"
search_todos "bug fix"
search_plans "user experience"
```

### Workspace Management

Organize work by workspace (project):

```bash
# Set workspace via environment
export TUSK_WORKSPACE="mobile_app"

# Or in Claude Desktop config
"env": {
  "TUSK_WORKSPACE": "web_frontend"
}
```

### Adaptive Tool Interfaces

Tusk adjusts complexity based on your expertise:

- **Beginner Mode**: Simple tools (save_progress, add_task, list_tasks)
- **Expert Mode**: Full control (create_checkpoint with all options)

Switch modes:
```bash
export TUSK_EXPERTISE_LEVEL="expert"
```

### Data Management

#### TTL (Time To Live)

Checkpoints automatically expire to keep data manageable:

```bash
export TUSK_DEFAULT_TTL="30d"    # 30 days default
```

Or per checkpoint:
```
create_checkpoint "..." --ttl "90d"
```

#### Backup and Migration

Your data is stored in human-readable JSON:

```bash
# Backup workspace
cp -r data/my_workspace /backup/location/

# Migrate between systems
rsync -av data/ other_machine:/tusk/data/
```

## Best Practices

### 1. Start Sessions with Recall
Always begin conversations with `recall` to restore context.

### 2. Regular Checkpoints
Create checkpoints after:
- Completing significant features
- Making important decisions  
- Solving complex problems
- Before switching contexts

### 3. Meaningful Highlights
When creating checkpoints, include highlights for:
- Key decisions made
- Problems solved
- Performance improvements
- Important discoveries

### 4. Active Todo Management
- Start todos when you begin working
- Complete todos when finished
- Use descriptive active forms
- Add notes for context

### 5. Plan-Driven Development
For complex work:
- Create plans with clear goals
- Break into manageable steps
- Link todos to plan steps
- Track progress regularly

### 6. Use Search
Don't rely on memory - search your history:
- Find past solutions to similar problems
- Locate relevant checkpoints
- Track todo patterns

## Example Workflow

### Starting a New Feature

1. **Recall Context**
```
recall
```

2. **Create Plan** 
```
create_plan "User Profile Settings" \
  "Allow users to customize their profile information" \
  --goals "User customization,Data validation,Security" \
  --steps "Design UI mockups,Backend API endpoints,Frontend components,Validation logic,Testing"
```

3. **Activate Plan**
```
activate_plan abc123
```

4. **Work and Checkpoint**
```
# Do some work...
create_checkpoint "Completed profile settings UI" \
  --highlights "Responsive design works on mobile,Form validation implemented" \
  --active-files "ProfileSettings.tsx,validation.ts"
```

5. **Update Progress**
```
complete_step abc123 1
add_task "Test profile settings on different browsers"
```

6. **End of Session**
```
standup
```

### Next Day

1. **Restore Context**
```
recall
```

2. **Continue Work**
```
# See active todos and plan progress
# Continue with next steps
```

This workflow ensures continuity across sessions and provides rich context for future work.

## Tips and Tricks

- Use descriptive names for checkpoints and todos
- Tag items consistently for better search
- Regular standups help track productivity  
- Export data occasionally as backup
- Use different workspaces for different projects
- Link todos to checkpoints and plans for relationship tracking

## Getting Help

- Use `--help` with any command for detailed usage
- Check logs for debugging: `logs/tusk_{workspace}.log`
- All data is in JSON format for transparency
- Report issues at https://github.com/anortham/tusk/issues