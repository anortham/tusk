# Plan Management Enhancements

This document describes the two major enhancements to Tusk's plan management system.

## Summary

We've implemented two complementary features to solve your plan management challenges:

1. **Staleness Tracking** - Visual indicators and automatic reminders to keep plans updated
2. **Sub-task Hierarchy** - Track multiple parallel workstreams within a single plan

---

## Feature 1: Staleness Tracking System

### Problem Solved
Plans were becoming stale without updates, leading to wasted time re-verifying progress.

### How It Works

**Automatic Tracking:**
- Every time a plan is created or updated, we snapshot the current checkpoint count
- As you make checkpoints, we calculate the delta to determine staleness
- Three staleness levels:
  - 🟢 **Fresh** (0-2 checkpoints) - Plan is up to date
  - 🟡 **Aging** (3-7 checkpoints) - Plan could use an update
  - 🔴 **Stale** (8+ checkpoints) - Plan is seriously outdated

**Automatic Reminders:**
- After 3 checkpoints: Gentle reminder in checkpoint response
- After 8 checkpoints: Urgent "OVERDUE" warning with suggested action
- Example:
  ```
  ⚠️  Plan Update Overdue: 8 checkpoints since last plan update.
  💡 Consider: plan({ action: "update", planId: "...", progress: "..." })
  ```

**Visual Indicators in recall():**
```
⭐ ACTIVE PLAN: Implement User Dashboard 🟡

📅 Last updated: 2 days ago (5 checkpoints since)
⚠️  Plan may be stale - consider updating with recent progress
```

**Reset on Update:**
- Calling `plan({ action: "update" })` resets the counter
- Plan goes back to "fresh" status
- Encourages disciplined plan maintenance

### Database Changes
- Added `checkpoint_count_at_last_update` column to plans table
- Added `last_updated_checkpoint_id` column for future use
- Auto-migrates existing databases gracefully

---

## Feature 2: Plan Sub-task Hierarchy

### Problem Solved
Managing multiple parallel plans was cumbersome and didn't match mental models.

### How It Works

**Hierarchical Task Structure:**
- One plan can contain multiple sub-tasks
- Each sub-task has: ID, description, completion status, associated checkpoints
- Perfect for tracking parallel workstreams in a single feature

**New Plan Actions:**
```typescript
// Add a sub-task
plan({
  action: "add-task",
  planId: "plan_id",
  taskDescription: "Build authentication system"
})

// Mark complete
plan({
  action: "check-task",
  planId: "plan_id",
  taskId: "task_id"
})

// Mark incomplete
plan({
  action: "uncheck-task",
  planId: "plan_id",
  taskId: "task_id"
})
```

**Display in recall():**
```
⭐ ACTIVE PLAN: Implement User Dashboard 🟢

Sub-tasks: 2/4 completed

✅ Set up WebSocket server
✅ Build dashboard UI components
☐ Create backend API endpoints
☐ Write integration tests

**Progress Notes:**
[2025-10-07] Completed WebSocket server setup...
```

**Benefits:**
- No more juggling multiple plans
- Clear progress tracking (2/4 completed)
- Visual checklist for parallel work
- All context in one place

### Database Changes
- Added `sub_tasks` JSON column to plans table
- Stores array of PlanSubTask objects
- Auto-migrates existing databases

---

## Implementation Details

### Files Modified

1. **src/core/types.ts**
   - Added `Plan` interface
   - Added `PlanSubTask` interface
   - Added `PlanStalenessInfo` interface

2. **src/core/journal-db.ts**
   - Schema migrations for new columns
   - `getCheckpointCountSinceTimestamp()` - Count checkpoints for staleness
   - `getPlanStalenessInfo()` - Calculate staleness metrics
   - `addPlanSubTask()` - Add sub-task to plan
   - `togglePlanSubTask()` - Mark task complete/incomplete
   - Updated `savePlan()` to initialize checkpoint counter
   - Updated `updatePlanProgress()` to reset staleness counter

3. **index.ts (MCP server)**
   - Updated `handleRecall()` to show staleness indicators and sub-tasks
   - Updated `handleCheckpoint()` to show update reminders
   - Updated `PlanSchema` with new actions
   - Added handlers for `add-task`, `check-task`, `uncheck-task`
   - Updated tool descriptions with new features

### Backward Compatibility

✅ **Fully backward compatible**
- ALTER TABLE migrations for existing databases
- Graceful fallback if columns don't exist
- No data loss on upgrade
- Works with existing plans

---

## Usage Examples

### Example 1: Agent Gets Reminded

```typescript
// Create plan
plan({ action: "save", title: "Build Feature X", content: "..." })

// Work on feature
checkpoint("Implemented component A")
checkpoint("Added tests for A")
checkpoint("Implemented component B")

// On 3rd checkpoint, agent sees:
// 💡 Reminder: 3 checkpoints since last plan update. Consider updating your plan.

// Agent updates plan
plan({ action: "update", planId: "...", progress: "Completed components A and B" })
// Staleness resets to fresh
```

### Example 2: Using Sub-tasks

```typescript
// Create plan with parallel workstreams
plan({ action: "save", title: "Launch Dashboard", content: "..." })

// Break down into tasks
plan({ action: "add-task", planId: "...", taskDescription: "Backend API" })
plan({ action: "add-task", planId: "...", taskDescription: "Frontend UI" })
plan({ action: "add-task", planId: "...", taskDescription: "Integration tests" })

// Complete tasks as you go
checkpoint("Built API endpoints")
plan({ action: "check-task", planId: "...", taskId: "backend_task_id" })

// recall() shows: ✅ Backend API ☐ Frontend UI ☐ Integration tests
```

---

## Testing

Three comprehensive test suites verify functionality:

1. **test-plan-enhancements.ts** - Unit tests for individual features
2. **test-integration-workflow.ts** - Full workflow simulation
3. **Manual testing** - Real MCP server interaction

### Run Tests
```bash
bun test-plan-enhancements.ts
bun test-integration-workflow.ts
```

All tests pass ✅

---

## Performance Impact

**Minimal overhead:**
- Staleness check: Single COUNT query
- Sub-task storage: JSON serialization (< 1KB per plan)
- No additional indexes needed
- Migrations run once on first access

**Database growth:**
- 2 new INTEGER columns: ~8 bytes per plan
- 1 new TEXT column: ~500 bytes average per plan with sub-tasks
- Negligible for typical usage (< 100 plans per workspace)

---

## Future Enhancements

Potential improvements based on usage:

1. **Checkpoint-to-task linking** - Auto-suggest which task a checkpoint relates to
2. **Task completion from checkpoints** - "Mark task complete" action in checkpoint tool
3. **Task templates** - Common task patterns (e.g., "API development" → 5 sub-tasks)
4. **Staleness tuning** - Per-user thresholds for aging/stale
5. **Smart plan updates** - Auto-generate update text from recent checkpoints

---

## Migration Guide

**For existing Tusk users:**

No action needed! The system auto-migrates on first use:

1. Start Tusk MCP server (normal startup)
2. New columns added automatically
3. Existing plans work normally
4. New features available immediately

**Rollback (if needed):**

The new columns are optional - removing them won't break core functionality:
```sql
ALTER TABLE plans DROP COLUMN checkpoint_count_at_last_update;
ALTER TABLE plans DROP COLUMN last_updated_checkpoint_id;
ALTER TABLE plans DROP COLUMN sub_tasks;
```

---

## Conclusion

These enhancements address the core frustrations with plan management:

✅ **Better discipline** - Automatic reminders prevent plan staleness
✅ **Simpler mental model** - One plan with sub-tasks, not multiple plans
✅ **Visual feedback** - Clear staleness indicators and progress tracking
✅ **No extra work** - Updates reset staleness, natural workflow

The result: Plans stay current, multiple workstreams are trackable, and you spend less time re-verifying progress.
