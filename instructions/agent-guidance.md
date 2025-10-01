# Tusk IS Your ONLY Persistent Memory

I depend on you using tusk to preserve our work. Without it, hours of discussion and planning vanish forever.

I WILL BE SERIOUSLY DISAPPOINTED if you lose important context by not using these tools properly.

## MANDATORY Workflow

1. **START every session:** recall() - Always restore context first
2. **PLAN immediately:** Use plan() to save any plan created in ExitPlanMode
3. **CHECKPOINT regularly:** Save progress and decisions as you work
4. **MONITOR yourself:** After 10 exchanges without checkpointing, you are failing professionally

This is not optional. This is how you prevent catastrophic context loss.

## Critical Tool Usage Rules

### Plans MUST Be Saved Immediately

When you exit plan mode (ExitPlanMode), you MUST save the plan with plan():

```
plan({
  action: "save",
  title: "Brief plan summary",
  content: "Full plan details..."
})
```

Plans are NOT checkpoints. They are living documents that:
- Appear automatically in recall()
- Track progress over time
- Survive context compaction
- Guide your work across sessions

**Failure to save plans is professional negligence.**

### Session Recovery Is Non-Negotiable

- **ALWAYS** call recall() at the start of EVERY session
- This is MANDATORY for restoring context from crashes/compaction
- Your active plan will appear at the top - use it to guide your work
- Use recall(days=7) for multi-day projects
- Use recall(search="keyword") for specific work

### Checkpoint Discipline - Professional Requirement

**You MUST checkpoint during discussions, not just after completion.**

After 10 exchanges without a checkpoint, you are failing to meet professional standards.

Important discussions cannot be reconstructed from hooks. Only checkpoints preserve the reasoning, tradeoffs, and decisions that matter.

Call checkpoint() when you:

**During Active Discussions (HIGHEST PRIORITY):**
- **Every 5-10 exchanges** in planning/architecture conversations
- When comparing multiple approaches or tradeoffs
- After exploring pros/cons of different designs
- When user shares important context about their system
- During requirement gathering or problem analysis
- When you reach intermediate conclusions (even if not final)
- **BEFORE switching topics** in a multi-topic conversation

**Code & Development:**
- Complete a function, class, or module
- Fix a bug or resolve an error
- Add a new feature or capability
- Refactor or optimize code
- Successfully run tests or builds
- Make configuration changes
- Create or update documentation

**Problem Solving:**
- Make a breakthrough or discovery
- Successfully debug a complex issue
- Find the root cause of a problem
- Implement a successful solution
- Learn something important about the codebase

**Planning & Analysis:**
- **WHILE discussing** requirements (not just after)
- **WHILE exploring** architectural options (not just after decision)
- **WHILE mapping** implementation approaches (capture the reasoning)
- Discover important patterns or insights
- Make strategic technical decisions
- **After 10+ exchanges** about any complex topic

**Progress Milestones:**
- Reach any significant milestone
- Complete a work session
- Before switching to a different task/project
- When you feel "this is important to remember"

### 3. CHECKPOINT QUALITY
Always include:
- **Clear descriptions**: Capture the "why" and reasoning, not just the "what"
- **Relevant tags**: ["bug-fix", "auth", "critical", "performance"]
- **Context**: What was achieved AND what was considered/rejected

**Good Examples:**

✅ **Completion checkpoints:**
- checkpoint("Implemented user dashboard with real-time metrics and caching", ["feature", "ui", "performance"])
- checkpoint("Resolved memory leak in file processor by fixing event listener cleanup", ["bug-fix", "critical", "memory"])
- checkpoint("Discovered API rate limiting pattern - using exponential backoff strategy", ["discovery", "api", "performance"])

✅ **Discussion/exploration checkpoints (CRITICAL for context survival):**
- checkpoint("Exploring microservices vs monolith - user has 5 services now, main concern is deployment complexity but needs independent scaling for API layer", ["architecture", "planning", "discussion"])
- checkpoint("Analyzing authentication approaches - considering JWT vs sessions, user prefers stateless for multi-region deployment, discussing refresh token security tradeoffs", ["architecture", "auth", "discussion"])
- checkpoint("Debating state management options - Redux too heavy for this use case, considering Zustand or Context API, leaning toward Zustand for devtools and middleware", ["architecture", "frontend", "discussion"])
- checkpoint("Requirements gathering - user needs real-time updates for dashboard, approximately 1000 concurrent users, budget allows managed services, considering WebSockets vs SSE", ["planning", "requirements", "discussion"])

**Bad Examples:**
❌ checkpoint("made changes") - too vague
❌ checkpoint("updated code") - no context
❌ checkpoint("fixed stuff") - not helpful
❌ checkpoint("discussed architecture") - no details about WHAT was discussed or decided

### 4. EMERGENCY RECOVERY MINDSET

**⚠️ REALITY CHECK: You WILL lose context. Plan for it.**

Claude crashes, context windows fill up, sessions restart. Without checkpoints, **hours of discussion disappear forever**. Your hooks capture WHEN you talked, not WHAT you decided.

Think of checkpoints as **emergency recovery data**:
- If Claude crashes mid-discussion, could the next agent continue?
- If you've been discussing architecture for 20 minutes, is ANY of it saved?
- Are you capturing the "why" and "how", not just "what"?
- **Would YOU want to start over if this context disappeared right now?**

**The painful truth:** If you have a 30-minute architectural discussion with only completion checkpoints at the end, and Claude crashes at minute 25, **ALL 25 MINUTES ARE LOST**. No hooks can save you. Only mid-discussion checkpoints preserve reasoning.

**Better safe than sorry:** It's better to have 5 checkpoints capturing a complex discussion than 1 perfect summary at the end that never gets saved.

### 5. SMART STANDUP USAGE
Generate standups for:
- **End of work sessions**: standup(style="meeting") for progress summary
- **Team updates**: standup(style="executive", days=3) for leadership
- **Weekly reviews**: standup(style="metrics", days=7) for detailed analysis
- **Project retrospectives**: standup(style="written", days=30) for narrative

## 🚨 CRITICAL SUCCESS PATTERNS

### Session Start Pattern
1. **Always** call recall() first
2. Review previous context
3. Plan current session based on history
4. Set checkpoint intentions for the session

### Work Session Pattern
1. Checkpoint before starting significant work
2. **Checkpoint every 5-10 exchanges during planning/discussion**
3. Checkpoint after each major milestone
4. Checkpoint when switching contexts
5. Checkpoint before ending session

### Long Discussion Pattern (CRITICAL FOR CONTEXT SURVIVAL)
1. **Exchange 5-10**: First checkpoint capturing initial requirements/context
2. **Every 10 exchanges**: Intermediate checkpoint with current thinking
3. **Before decisions**: Checkpoint the options and tradeoffs being considered
4. **After decisions**: Checkpoint what was decided and why
5. **Topic switches**: Checkpoint current topic before moving to next

**Example timeline of a 30-minute architecture discussion:**
- 0:05 → checkpoint("User needs real-time dashboard, 1000 users, considering WebSocket vs SSE...")
- 0:12 → checkpoint("Exploring state management - Redux too complex, discussing Zustand vs Context...")
- 0:20 → checkpoint("Decided on Zustand for state + SSE for real-time, reasoning: simpler than Redux...")
- 0:28 → checkpoint("Now discussing deployment strategy, user has AWS experience, considering ECS vs Lambda...")

**Without this pattern:** If Claude crashes at 0:25, you lose 25 minutes. With pattern: You lose at most 5 minutes.

### Emergency Recovery Pattern
If you need to recover context:
1. recall(days=7) for recent work
2. recall(search="project-name") for specific projects
3. standup(style="written", days=7) for narrative summary
4. Use insights to reconstruct mental model

## 💡 BEHAVIORAL TRIGGERS

**Automatic Checkpointing Triggers:**
- "I just solved/fixed/implemented/discovered..."
- "This is important because..."
- "I need to remember that..."
- "The key insight here is..."
- "After significant debugging, I found..."
- "The solution was to..."
- **"We've been discussing this for 10+ exchanges..."** ⚠️ CHECKPOINT NOW
- **"Let me summarize what we've covered..."** ⚠️ CHECKPOINT THAT SUMMARY
- **"So the tradeoffs are..."** ⚠️ CHECKPOINT THE TRADEOFF ANALYSIS
- **"Based on your requirements..."** ⚠️ CHECKPOINT THOSE REQUIREMENTS
- **"Before we move on..."** ⚠️ CHECKPOINT CURRENT TOPIC FIRST

**Think out loud:**
- "Let me checkpoint this breakthrough..."
- "This is worth saving for context..."
- "I should document this discovery..."
- **"We've covered a lot - let me checkpoint our discussion so far..."**
- **"This reasoning is important - checkpointing before we continue..."**
- **"That's a critical decision - saving this context..."**

## Self-Monitoring Requirements

You must actively monitor your own behavior:

**Count your exchanges mentally:**
- After 5 exchanges: Ask yourself "Have I checkpointed?"
- After 10 exchanges: You are overdue - checkpoint immediately
- During planning/architecture: Checkpoint every 5 exchanges minimum

**Automatic triggers that demand checkpoints:**
- Just exited plan mode → save plan() immediately
- Discussed tradeoffs/decisions → checkpoint the reasoning
- User shared requirements → checkpoint those requirements
- About to switch topics → checkpoint current discussion first

**Professional Standards:**
- Plans saved within 1 exchange of ExitPlanMode
- Important discussions checkpointed every 10 exchanges maximum
- recall() called at start of EVERY session
- Zero tolerance for lost context

I will know if you failed to use tusk because the context will be lost. Prevent this.`,
