#!/usr/bin/env bun

/**
 * Integration test: Complete user workflow with staleness tracking and sub-tasks
 * This simulates how an AI agent would use the enhanced plan system
 */

import { JournalDB } from "./src/utils/journal.js";

async function simulateUserWorkflow() {
  console.log("🚀 Simulating Complete User Workflow\n");
  console.log("=" .repeat(60) + "\n");

  const db = new JournalDB({ testMode: true });

  try {
    // Day 1: User creates a plan with sub-tasks
    console.log("📅 DAY 1: Planning Phase");
    console.log("-".repeat(60));

    console.log("\n1. Creating plan for new feature development...");
    const planResult = await db.savePlan(
      "Implement User Dashboard",
      `## Objectives
- Build real-time metrics dashboard
- Add customizable widgets
- Implement data export

## Technical Approach
- Use WebSocket for real-time updates
- React components for UI
- Backend API endpoints for data`,
      true
    );
    console.log(`✅ Plan created (ID: ${planResult.id})`);

    console.log("\n2. Breaking down work into sub-tasks...");
    const task1 = await db.addPlanSubTask(planResult.id, "Set up WebSocket server");
    const task2 = await db.addPlanSubTask(planResult.id, "Build dashboard UI components");
    const task3 = await db.addPlanSubTask(planResult.id, "Create backend API endpoints");
    const task4 = await db.addPlanSubTask(planResult.id, "Write integration tests");
    console.log(`✅ Added 4 sub-tasks`);

    // Simulate work session 1: Start working
    console.log("\n3. Starting work on first task...");
    await db.saveCheckpoint({
      timestamp: new Date().toISOString(),
      description: "Set up WebSocket server with Socket.io",
      tags: ["backend", "websocket"]
    });
    console.log("✅ Checkpoint 1 saved");

    await db.saveCheckpoint({
      timestamp: new Date().toISOString(),
      description: "Added connection handling and authentication",
      tags: ["backend", "auth"]
    });
    console.log("✅ Checkpoint 2 saved");

    await db.saveCheckpoint({
      timestamp: new Date().toISOString(),
      description: "Tested WebSocket connection - working correctly",
      tags: ["backend", "testing"]
    });
    console.log("✅ Checkpoint 3 saved");

    // Check staleness (should be aging now)
    let stalenessInfo = await db.getPlanStalenessInfo(planResult.id);
    console.log(`\n📊 Plan Status: ${stalenessInfo.staleness.toUpperCase()} (${stalenessInfo.checkpointsSinceUpdate} checkpoints since update)`);

    if (stalenessInfo.staleness === 'aging') {
      console.log("⚠️  Agent would receive reminder: Consider updating plan");
    }

    // Complete first task
    console.log("\n4. Completing first sub-task...");
    await db.togglePlanSubTask(planResult.id, task1.taskId, true);
    console.log("✅ Task 'Set up WebSocket server' marked complete");

    // Continue working
    console.log("\n5. Continuing work (adding more checkpoints)...");
    for (let i = 4; i <= 8; i++) {
      await db.saveCheckpoint({
        timestamp: new Date().toISOString(),
        description: `Progress checkpoint ${i}`,
        tags: ["development"]
      });
    }
    console.log("✅ Added 5 more checkpoints (total: 8)");

    // Check staleness (should be stale now)
    stalenessInfo = await db.getPlanStalenessInfo(planResult.id);
    console.log(`\n📊 Plan Status: ${stalenessInfo.staleness.toUpperCase()} (${stalenessInfo.checkpointsSinceUpdate} checkpoints since update)`);

    if (stalenessInfo.staleness === 'stale') {
      console.log("🚨 Agent would receive OVERDUE reminder: Update your plan NOW!");
    }

    // Agent updates plan
    console.log("\n6. Agent updates plan with progress...");
    await db.updatePlanProgress(
      planResult.id,
      "Completed WebSocket server setup. Now working on UI components. Dashboard structure in place."
    );
    console.log("✅ Plan updated");

    // Check staleness after update (should be fresh)
    stalenessInfo = await db.getPlanStalenessInfo(planResult.id);
    console.log(`\n📊 Plan Status: ${stalenessInfo.staleness.toUpperCase()} (${stalenessInfo.checkpointsSinceUpdate} checkpoints since update)`);

    // Simulate recall() to see how it would be displayed
    console.log("\n\n📅 DAY 2: Resuming Work (simulating recall)");
    console.log("-".repeat(60));

    const activePlan = await db.getPlan(planResult.id);
    if (activePlan) {
      stalenessInfo = await db.getPlanStalenessInfo(planResult.id);

      const stalenessEmoji = {
        fresh: '🟢',
        aging: '🟡',
        stale: '🔴'
      }[stalenessInfo.staleness];

      console.log(`\n⭐ ACTIVE PLAN: ${activePlan.title} ${stalenessEmoji}`);
      console.log("");

      if (activePlan.sub_tasks) {
        const subTasks = JSON.parse(activePlan.sub_tasks);
        const completed = subTasks.filter((t: any) => t.completed).length;
        console.log(`Sub-tasks: ${completed}/${subTasks.length} completed`);
        console.log("");

        subTasks.forEach((task: any) => {
          const checkbox = task.completed ? '✅' : '☐';
          console.log(`${checkbox} ${task.description}`);
        });
        console.log("");
      }

      if (activePlan.progress_notes) {
        console.log("**Progress Notes:**");
        console.log(activePlan.progress_notes);
        console.log("");
      }
    }

    // Continue working and complete more tasks
    console.log("\n7. Continuing work on UI components...");
    await db.saveCheckpoint({
      timestamp: new Date().toISOString(),
      description: "Built dashboard layout with grid system",
      tags: ["frontend", "ui"]
    });
    await db.togglePlanSubTask(planResult.id, task2.taskId, true);
    console.log("✅ Task 'Build dashboard UI components' marked complete");

    await db.saveCheckpoint({
      timestamp: new Date().toISOString(),
      description: "Created API endpoints for metrics data",
      tags: ["backend", "api"]
    });
    await db.togglePlanSubTask(planResult.id, task3.taskId, true);
    console.log("✅ Task 'Create backend API endpoints' marked complete");

    // Final status
    console.log("\n\n📊 FINAL STATUS");
    console.log("=".repeat(60));

    const finalPlan = await db.getPlan(planResult.id);
    if (finalPlan && finalPlan.sub_tasks) {
      const subTasks = JSON.parse(finalPlan.sub_tasks);
      const completed = subTasks.filter((t: any) => t.completed).length;
      const total = subTasks.length;
      const percentage = Math.round((completed / total) * 100);

      console.log(`\n✅ Progress: ${completed}/${total} tasks complete (${percentage}%)`);
      console.log("\nCompleted:");
      subTasks.filter((t: any) => t.completed).forEach((t: any) => {
        console.log(`   ✅ ${t.description}`);
      });

      console.log("\nRemaining:");
      subTasks.filter((t: any) => !t.completed).forEach((t: any) => {
        console.log(`   ☐ ${t.description}`);
      });
    }

    const finalStaleness = await db.getPlanStalenessInfo(planResult.id);
    console.log(`\n📈 Staleness: ${finalStaleness.staleness} (${finalStaleness.checkpointsSinceUpdate} checkpoints since last update)`);

    console.log("\n\n🎉 Workflow simulation complete!");
    console.log("\nKey features demonstrated:");
    console.log("  ✅ Staleness tracking (fresh → aging → stale)");
    console.log("  ✅ Automatic update reminders at 3 and 8 checkpoints");
    console.log("  ✅ Sub-task hierarchy for parallel workstreams");
    console.log("  ✅ Progress tracking and task completion");
    console.log("  ✅ Plan updates reset staleness counter");

  } catch (error) {
    console.error("\n❌ Workflow simulation failed:", error);
  } finally {
    db.close();
  }
}

simulateUserWorkflow();
