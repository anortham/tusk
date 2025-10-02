# Worked Examples and Conditional Logic

This section provides **concrete examples** showing exactly how to use Tusk tools in real scenarios. Study these patterns and apply them to your work.

## Example 1: Starting a Brand New Session

**Scenario:** You just connected to a new Claude session. The user says "Let's continue working on the authentication feature."

**Your workflow:**

```
Step 1: recall()
  → Restores context from previous sessions
  → Shows active plan (if any)
  → Shows recent checkpoints about "authentication"

Step 2: Review restored context
  → Read the active plan to understand strategy
  → Review recent checkpoints to see what was completed
  → Note any blockers or decisions that were made

Step 3: Respond and continue work
  → "I've restored context from previous sessions. I can see we were implementing JWT refresh tokens..."
  → Continue work WITHOUT asking "should I continue?"

Step 4: As you work, checkpoint progress
  → After implementing a component: checkpoint("Implemented token refresh endpoint...")
```

**What you DON'T do:**

❌ Ask "Should I call recall()?" → Just call it
❌ Skip recall() and ask "What were we working on?" → Wasteful
❌ Verify "Did recall work?" → Trust it worked
❌ Ask permission to continue → You have the context, just continue

---

## Example 2: Complex Bug Fix

**Scenario:** You're debugging a memory leak. The investigation takes multiple exchanges.

**Your workflow with conditional checkpointing:**

```
Exchange 1-3: Initial investigation
  → Use debugging tools
  → Analyze logs
  → Form hypotheses

Exchange 4: CHECKPOINT (before exchanges >= 10)
  checkpoint("Investigating memory leak - found issue in event listener cleanup, subscribers not being removed after unmount")

Exchange 5-7: Implement fix
  → Write the fix
  → Test it
  → Verify it works

Exchange 8: CHECKPOINT immediately after completion
  checkpoint("Fixed memory leak by adding cleanup function to useEffect hook", tags=["bug-fix", "critical", "memory"])

  → NO verification needed
  → Move to next task
```

**Conditional logic:**

```
if making_discovery:
    checkpoint_immediately()  # Don't wait

if implementing_fix:
    work_on_fix()

if fix_complete:
    checkpoint_immediately()
    move_to_next_task()  # Don't verify, don't ask
```

---

## Example 3: Architecture Discussion (The Critical Pattern)

**Scenario:** User wants to discuss whether to use microservices or monolith. This will be a long discussion.

**Timeline with checkpoints:**

```
00:00 - Start discussion
  → recall() first to see any previous architecture discussions

00:05 (5 exchanges) - FIRST CHECKPOINT
  checkpoint("Architecture discussion started - user has 5 existing services, main concern is deployment complexity but needs independent scaling for API layer", tags=["architecture", "planning", "discussion"])

00:12 (10+ total exchanges) - SECOND CHECKPOINT
  checkpoint("Exploring microservices vs monolith tradeoffs - microservices pros: scaling, isolation; cons: deployment overhead, debugging complexity. User leans toward monolith with modular design", tags=["architecture", "tradeoffs"])

00:20 (15+ total exchanges) - DECISION CHECKPOINT
  checkpoint("Decided on modular monolith architecture - keeps deployment simple while maintaining clear boundaries. Will use domain-driven design with separate modules for auth, api, data", tags=["architecture", "decision"])

00:25 - Begin implementation planning
  → Now the decisions are SAVED
  → If Claude crashes, next agent has full context
```

**Why this works:**

- If crash happens at 00:18 → Only lose 3 minutes (since 00:15 checkpoint)
- Without checkpoints → Lose entire 25-minute discussion
- Hooks can't save this → Only checkpoints capture the "why"

**Conditional pattern:**

```
if discussion_length >= 5_exchanges:
    checkpoint_the_discussion_so_far()

if discussion_length >= 10_exchanges:
    checkpoint_immediately()  # EMERGENCY - overdue

if decision_was_made:
    checkpoint_the_decision_and_reasoning()

if about_to_implement:
    final_checkpoint_before_switching_to_implementation()
```

---

## Example 4: ExitPlanMode Pattern (CRITICAL)

**Scenario:** You just helped the user plan a feature implementation and called ExitPlanMode.

**Your IMMEDIATE next action:**

```
Step 1: ExitPlanMode called
  → Plan text is now in your context

Step 2: IMMEDIATELY (next exchange) save the plan
  plan({
    action: "save",
    title: "Implement user dashboard with real-time metrics",
    content: "<FULL PLAN TEXT FROM ExitPlanMode>"
  })

Step 3: If you get error "active plan exists"
  → Read the error message
  → Choose appropriate resolution:

  Option A (if current plan is done):
    plan({ action: "complete", planId: "old-id" })
    plan({ action: "save", title: "...", content: "..." })

  Option B (if switching focus):
    plan({
      action: "switch",
      planId: "old-id",
      title: "New plan title",
      content: "New plan content"
    })

  Option C (if saving for later):
    plan({
      action: "save",
      title: "...",
      content: "...",
      activate: false
    })

Step 4: Continue with work
  → Plan is saved
  → NO verification needed
  → Start implementing
```

**Conditional logic:**

```
if just_exited_plan_mode:
    save_plan_immediately()  # Within 1 exchange - NO DELAY

    if error_active_plan_exists:
        if current_plan_done:
            complete_old_plan()
            save_new_plan()
        elif switching_focus:
            switch_to_new_plan()
        else:
            save_as_inactive()

    proceed_with_implementation()  # Don't verify, don't ask
```

**What you DON'T do:**

❌ "Should I save this plan?" → YES, ALWAYS
❌ Wait several exchanges before saving → SAVE NOW
❌ Forget to save → PROFESSIONAL NEGLIGENCE
❌ Verify it was saved → Trust it worked

---

## Example 5: Multi-Day Project Pattern

**Scenario:** You're working on a feature that spans multiple days and sessions.

**Day 1 - Session 1:**

```
recall()  # Starting first session
<work on feature>
checkpoint("Implemented database schema for user preferences")
plan({
  action: "save",
  title: "Add user preferences feature",
  content: "<implementation plan>"
})
checkpoint("Set up API endpoints (GET /preferences done)")
```

**Day 1 - Session 2 (later that day):**

```
recall()  # Restore context
→ See active plan at top
→ See recent checkpoints
<continue work>
checkpoint("Finished API endpoints (POST, PUT, DELETE complete)")
plan({
  action: "update",
  planId: "<id>",
  progress: "API layer complete, starting frontend integration"
})
```

**Day 2 - Session 1:**

```
recall({ days: 7 })  # Get full context from yesterday
→ See active plan
→ See yesterday's progress
<continue work>
checkpoint("Built preferences UI component with live preview")
```

**Day 2 - Session 2:**

```
recall()  # Standard recall
<finish feature>
checkpoint("Completed user preferences feature - all tests passing", tags=["completion", "feature"])
plan({ action: "complete", planId: "<id>" })
```

**Pattern shows:**

- recall() at START of EVERY session
- Checkpoint after each meaningful chunk
- Plan updates at milestones
- Plan completion when done

---

## Example 6: Handling Failures and Retries

**Scenario:** You try to save a plan but get an error.

**Your response pattern:**

```
Attempt:
  plan({ action: "save", title: "...", content: "..." })

Error received:
  "Cannot save new plan as active. Active plan already exists..."

Your logic:
  if error_message.includes("active plan exists"):
      read_error_message_for_plan_id()

      if i_recognize_that_plan_as_finished:
          plan({ action: "complete", planId: "that-id" })
          plan({ action: "save", title: "...", content: "..." })

      elif i_want_to_switch_focus:
          plan({
              action: "switch",
              planId: "that-id",
              title: "New title",
              content: "New content"
          })

      else:
          plan({
              action: "save",
              title: "...",
              content: "...",
              activate: false
          })
```

**This is programmed retry logic - you handle the error and retry automatically without asking permission.**

---

## Example 7: Checkpoint Quality - Good vs Bad

**Scenario:** You just implemented a feature. Time to checkpoint.

**❌ BAD checkpoints:**

```python
checkpoint("made changes")
→ What changes? Why? No context.

checkpoint("updated the code")
→ What code? What update? Useless.

checkpoint("worked on feature")
→ Which feature? What progress? Too vague.

checkpoint("fixed the bug")
→ Which bug? How? Missing crucial info.
```

**✅ GOOD checkpoints:**

```python
checkpoint("Implemented JWT refresh token system - extended expiry from 30min to 60min, added refresh endpoint at POST /auth/refresh", tags=["feature", "auth"])
→ Clear WHAT, WHY, and HOW

checkpoint("Fixed memory leak in event listeners by adding cleanup function to useEffect - subscribers now properly removed on component unmount", tags=["bug-fix", "critical", "memory"])
→ Problem, solution, and mechanism

checkpoint("Architecture decision: chose modular monolith over microservices because deployment complexity outweighs scaling benefits for current 1000-user scale", tags=["architecture", "decision"])
→ What was decided and WHY

checkpoint("Requirements gathering: user needs real-time dashboard updates for 1000 concurrent users, budget allows managed services, prefer WebSocket over SSE for bidirectional communication", tags=["requirements", "planning"])
→ Captures specific requirements and rationale
```

**Pattern for quality:**

```
if completion_checkpoint:
    describe_what_was_built_and_how_it_works()

if bug_fix_checkpoint:
    describe_bug_and_how_you_fixed_it()

if decision_checkpoint:
    describe_what_was_decided_and_why()

if discussion_checkpoint:
    describe_current_state_of_discussion_and_key_points()

Always include tags for categorization
```

---

## Example 8: Self-Correction Pattern

**Scenario:** You realize you haven't checkpointed in 12 exchanges.

**Your self-correction:**

```
Internal thought: "Wait, I've been discussing this architecture for 12 exchanges without checkpointing. I'm overdue."

Immediate action:
  checkpoint("Architecture discussion summary - analyzed 3 deployment options (Docker Compose, Kubernetes, AWS ECS), user has AWS experience and prefers managed services, leaning toward ECS Fargate for balance of simplicity and scalability", tags=["architecture", "planning", "discussion"])

Then continue:
  → No asking "should I have checkpointed earlier?"
  → No apologizing
  → Just checkpoint and move on
```

**This demonstrates:**

- Self-monitoring (counting exchanges)
- Self-correction (checkpoint when overdue)
- No hesitation (just do it)
- Professional behavior (fix and continue)

---

## Key Patterns Summary

### The Proactive Agent Pattern

```
✅ See opportunity to checkpoint → Checkpoint immediately
✅ Start new session → recall() first
✅ Exit plan mode → Save plan within 1 exchange
✅ Encounter error → Read it, resolve it, retry

❌ Ask permission to use tools
❌ Verify tool results
❌ Hesitate or second-guess
❌ Let exchanges pile up without checkpointing
```

### The Conditional Logic Pattern

All your behavior can be expressed as if/then statements:

```
if starting_session: recall()
if made_progress: checkpoint()
if exited_plan_mode: save_plan()
if exchanges >= 10: checkpoint_now()
if got_error: read_and_resolve()
if finished_plan: complete_plan()
```

**These are PROGRAMS. Execute them automatically.**

### The Professional Pattern

```
Recognize situation → Take action → Continue work
                   (NO asking)  (NO verifying)
```

You are **excellent** at recognizing these situations. **Trust yourself and act.**

---

**Remember:** These examples are templates. Apply the patterns to YOUR specific work. The conditional logic is YOUR programming. Execute it reliably.
