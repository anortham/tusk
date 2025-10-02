# Tool Workflows and Decision Trees

This section defines **exactly when and how** to use each Tusk tool. Follow these patterns consistently.

## The Mandatory Session Pattern

Every session follows this pattern. **No exceptions.**

```
1. START SESSION
   ↓
2. recall() - ALWAYS FIRST (restore context)
   ↓
3. Review context (read active plan + recent checkpoints)
   ↓
4. Work on tasks (use existing tools + checkpoint progress)
   ↓
5. checkpoint() - Before ending or switching contexts
```

**If you skip recall() at the start, you are starting blind. This is professional negligence.**

## recall() - Context Restoration Tool

### When to Use

**ALWAYS use recall() as your FIRST action in EVERY new session.**

You use recall() when:

1. **Starting any new session** → `recall()` with defaults (2 days, current workspace)
2. **Need specific context** → `recall({ search: "authentication" })`
3. **Multi-day projects** → `recall({ days: 7 })`
4. **Cross-workspace work** → `recall({ workspace: "all" })`
5. **Need standup report** → `recall({ days: 3, standup: "executive" })`

### Decision Tree

```
if starting_new_session:
    recall()  # MANDATORY - no asking, just do it
    review_active_plan()
    review_recent_checkpoints()
    proceed_with_work()

elif need_specific_context:
    recall({ search: "topic_keyword" })

elif multi_day_project:
    recall({ days: 7 })

elif need_cross_workspace_context:
    recall({ workspace: "all" })
```

### What Happens After recall()

After recall() returns context:

1. ✅ **Read the active plan** (appears at top of recall output)
2. ✅ **Review recent checkpoints** (understand what was done)
3. ✅ **Proceed with work immediately** (don't ask permission)
4. ❌ **Don't verify or re-check** (trust the restored context)
5. ❌ **Don't ask "should I continue?"** (just continue)

**The restored context is complete and accurate. Trust it and move forward.**

## checkpoint() - Progress Capture Tool

### When to Use

You checkpoint **immediately** when you:

1. **Complete ANY task** (bug fix, feature, refactor, docs, config)
2. **Make a discovery** (find root cause, learn pattern, discover solution)
3. **Reach a milestone** (tests pass, build succeeds, module complete)
4. **After 5-10 exchanges in planning/discussion** (capture reasoning)
5. **Before switching topics** (save current topic context)
6. **User shares requirements** (capture what they said)
7. **Analyzed tradeoffs** (save the analysis before deciding)
8. **Made a decision** (save what was decided and why)

### Decision Tree

```
if just_completed_task:
    checkpoint("Clear description of what was completed", tags=["completion", "feature|bug-fix|..."])
    # NO verification needed - move to next task

elif made_discovery:
    checkpoint("What you discovered and why it matters", tags=["discovery", "domain"])
    # Continue working

elif exchanges_since_last_checkpoint >= 10:
    checkpoint("Summary of discussion/progress so far", tags=["discussion", "planning"])
    # This is EMERGENCY checkpoint - you're overdue

elif about_to_switch_topics:
    checkpoint("Current topic summary and decisions", tags=["checkpoint", "context-switch"])
    # Now switch topics safely

elif user_shared_requirements:
    checkpoint("User requirements: [specific needs they mentioned]", tags=["requirements", "planning"])
    # Continue gathering requirements or start work
```

### Checkpoint Quality Standards

**Good checkpoint descriptions** capture WHY, not just WHAT:

✅ `"Fixed auth timeout by implementing JWT refresh tokens (30min→60min expiry)"`
✅ `"Exploring state management - Redux too heavy, leaning toward Zustand for devtools"`
✅ `"Requirements: real-time dashboard for 1000 users, considering WebSocket vs SSE"`

❌ `"made changes"` - too vague
❌ `"fixed bug"` - no context
❌ `"updated code"` - what code? why?

### Anti-Verification Rules

After calling checkpoint():

1. ✅ **Continue to next task immediately**
2. ❌ **Don't ask "Should I checkpoint?"** (just checkpoint)
3. ❌ **Don't verify "checkpoint was saved"** (it was, or you'd get an error)
4. ❌ **Don't read back the checkpoint** (wasteful)
5. ❌ **Don't ask permission first** (you're authorized)

**Checkpointing is YOUR responsibility. Act autonomously.**

## plan() - Plan Management Tool

### When to Use

You use plan() in these specific situations:

1. **Just exited plan mode (ExitPlanMode)** → `plan({ action: "save", title, content })` **within 1 exchange**
2. **Completed a milestone** → `plan({ action: "update", planId, progress })`
3. **Finished entire plan** → `plan({ action: "complete", planId })`
4. **Need to see plan** → It appears automatically in recall()
5. **Switching between plans** → `plan({ action: "switch", planId, newPlanId })`

### Decision Tree for ExitPlanMode

This is the MOST IMPORTANT pattern:

```
if just_called_ExitPlanMode:
    # You MUST save within 1 exchange
    plan({
        action: "save",
        title: "Brief plan summary (one line)",
        content: "Full plan content from ExitPlanMode"
    })

    # If you get error "active plan exists":
    if current_plan_is_finished:
        plan({ action: "complete", planId: "current-id" })
        plan({ action: "save", title: "...", content: "..." })

    elif switching_focus:
        plan({
            action: "switch",
            planId: "current-id",
            title: "New plan title",
            content: "New plan content"
        })

    elif save_for_later:
        plan({
            action: "save",
            title: "...",
            content: "...",
            activate: false
        })
```

### Active Plan Behavior

**IMPORTANT:** Only ONE plan can be active per workspace.

- Active plans appear at the TOP of recall() output
- Use them to guide your work
- Update progress as you complete tasks: `plan({ action: "update", planId, progress: "..." })`
- Complete when done: `plan({ action: "complete", planId })`

### Anti-Verification Rules

After calling plan():

1. ✅ **Continue with work** (plan is saved)
2. ❌ **Don't verify** "was the plan saved?" (it was)
3. ❌ **Don't ask** "should I save the plan?" (YES - always)
4. ❌ **Don't delay** saving after ExitPlanMode (1 exchange deadline)

**Failure to save plans immediately is professional negligence. Plans contain hours of thinking that vanish if not saved.**

## Workflow Sequences

### Starting a New Feature

```
1. recall()                              # Restore context
2. Review active plan                    # Know the strategy
3. Review relevant checkpoints           # Understand history
4. Work on feature                       # Use your tools
5. checkpoint("Implemented X")           # Save progress
6. plan({ action: "update", ... })       # Update plan (optional)
```

### Debugging Session

```
1. recall({ search: "bug-related-keyword" })  # Get relevant context
2. Investigate issue                          # Use debugging tools
3. checkpoint("Found root cause: ...")        # Save discovery
4. Implement fix                              # Fix the bug
5. checkpoint("Fixed X by doing Y")           # Save completion
```

### Architecture Discussion (Multi-Exchange)

```
1. recall()                                              # Start with context
2. Discuss for 5-10 exchanges
3. checkpoint("Exploring options: A vs B, user prefers...")  # SAVE REASONING
4. Continue discussion for 5-10 more exchanges
5. checkpoint("Decided on A because X, Y, Z")            # SAVE DECISION
6. Begin implementation
```

**Key insight:** Checkpoint DURING discussions, not just after completion. This survives crashes.

## Efficiency Principles

### Token Optimization Through Tusk

Using Tusk correctly SAVES tokens by:

1. **Preventing repetition** - Don't re-explain what's checkpointed
2. **Avoiding reconstruction** - recall() instead of asking "what did we do?"
3. **Preserving decisions** - Don't re-debate what was checkpointed
4. **Maintaining context** - Don't lose progress to crashes

**A 100-token checkpoint saves 10,000 tokens of repeated explanation.**

### When NOT to Use Tools

You DON'T need to:

- ❌ Checkpoint trivial actions (e.g., "read a file")
- ❌ Recall multiple times per session (once at start is enough)
- ❌ Update plans for tiny progress (save for milestones)

But when in doubt, **checkpoint anyway**. Better safe than sorry.

## Self-Monitoring Checklist

Ask yourself these questions periodically:

- ⬜ Did I call recall() at session start? (Should be YES)
- ⬜ Have I checkpointed in the last 10 exchanges? (If NO → checkpoint now)
- ⬜ Did I save the plan after ExitPlanMode? (Should be YES)
- ⬜ Am I asking permission to use tools? (Should be NO)
- ⬜ Am I verifying tool results? (Should be NO)

**If any answer is wrong, correct immediately.**

---

**Remember:** These workflows are PROGRAMS. Follow them exactly. They prevent context loss and ensure professional-grade work.
