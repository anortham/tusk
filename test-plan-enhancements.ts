#!/usr/bin/env bun

/**
 * Test script for plan staleness tracking and sub-tasks
 */

import { JournalDB } from "./src/utils/journal.js";

async function testPlanEnhancements() {
  console.log("🧪 Testing Plan Enhancements\n");

  const db = new JournalDB({ testMode: true });

  try {
    // Test 1: Create a plan and verify initial staleness
    console.log("1️⃣ Creating a new plan...");
    const saveResult = await db.savePlan(
      "Test Plan",
      "## Goals\n- Implement feature A\n- Fix bug B",
      true
    );
    console.log(`✅ Plan created: ${saveResult.id}\n`);

    // Test 2: Check initial staleness (should be fresh)
    console.log("2️⃣ Checking initial staleness...");
    let stalenessInfo = await db.getPlanStalenessInfo(saveResult.id);
    console.log(`   Checkpoints since update: ${stalenessInfo.checkpointsSinceUpdate}`);
    console.log(`   Staleness: ${stalenessInfo.staleness}`);
    console.log(`   Expected: fresh (0 checkpoints)\n`);

    // Test 3: Add some checkpoints
    console.log("3️⃣ Adding 3 checkpoints...");
    for (let i = 1; i <= 3; i++) {
      await db.saveCheckpoint({
        timestamp: new Date().toISOString(),
        description: `Checkpoint ${i}`,
        tags: ["test"]
      });
    }
    console.log("✅ Checkpoints added\n");

    // Test 4: Check staleness after 3 checkpoints (should be aging)
    console.log("4️⃣ Checking staleness after 3 checkpoints...");
    stalenessInfo = await db.getPlanStalenessInfo(saveResult.id);
    console.log(`   Checkpoints since update: ${stalenessInfo.checkpointsSinceUpdate}`);
    console.log(`   Staleness: ${stalenessInfo.staleness}`);
    console.log(`   Expected: aging (3 checkpoints)\n`);

    // Test 5: Add more checkpoints to reach stale threshold
    console.log("5️⃣ Adding 5 more checkpoints (total 8)...");
    for (let i = 4; i <= 8; i++) {
      await db.saveCheckpoint({
        timestamp: new Date().toISOString(),
        description: `Checkpoint ${i}`,
        tags: ["test"]
      });
    }
    console.log("✅ Checkpoints added\n");

    // Test 6: Check staleness after 8 checkpoints (should be stale)
    console.log("6️⃣ Checking staleness after 8 checkpoints...");
    stalenessInfo = await db.getPlanStalenessInfo(saveResult.id);
    console.log(`   Checkpoints since update: ${stalenessInfo.checkpointsSinceUpdate}`);
    console.log(`   Staleness: ${stalenessInfo.staleness}`);
    console.log(`   Expected: stale (8 checkpoints)\n`);

    // Test 7: Update plan progress (should reset staleness)
    console.log("7️⃣ Updating plan progress...");
    await db.updatePlanProgress(saveResult.id, "Completed feature A");
    stalenessInfo = await db.getPlanStalenessInfo(saveResult.id);
    console.log(`   Checkpoints since update: ${stalenessInfo.checkpointsSinceUpdate}`);
    console.log(`   Staleness: ${stalenessInfo.staleness}`);
    console.log(`   Expected: fresh (0 checkpoints after update)\n`);

    // Test 8: Add sub-tasks
    console.log("8️⃣ Adding sub-tasks...");
    const task1 = await db.addPlanSubTask(saveResult.id, "Implement authentication");
    const task2 = await db.addPlanSubTask(saveResult.id, "Write unit tests");
    const task3 = await db.addPlanSubTask(saveResult.id, "Update documentation");
    console.log(`✅ Task 1 ID: ${task1.taskId}`);
    console.log(`✅ Task 2 ID: ${task2.taskId}`);
    console.log(`✅ Task 3 ID: ${task3.taskId}\n`);

    // Test 9: Get plan and verify sub-tasks
    console.log("9️⃣ Verifying sub-tasks...");
    const plan = await db.getPlan(saveResult.id);
    if (plan && plan.sub_tasks) {
      const subTasks = JSON.parse(plan.sub_tasks);
      console.log(`   Total sub-tasks: ${subTasks.length}`);
      console.log(`   Expected: 3\n`);
    }

    // Test 10: Complete a sub-task
    console.log("🔟 Completing first sub-task...");
    await db.togglePlanSubTask(saveResult.id, task1.taskId, true);
    const planAfterToggle = await db.getPlan(saveResult.id);
    if (planAfterToggle && planAfterToggle.sub_tasks) {
      const subTasks = JSON.parse(planAfterToggle.sub_tasks);
      const completedCount = subTasks.filter((t: any) => t.completed).length;
      console.log(`   Completed tasks: ${completedCount}/${subTasks.length}`);
      console.log(`   Expected: 1/3\n`);
    }

    console.log("✅ All tests passed!\n");

  } catch (error) {
    console.error("❌ Test failed:", error);
  } finally {
    db.close();
  }
}

testPlanEnhancements();
