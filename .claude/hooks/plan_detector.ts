#!/usr/bin/env bun
/**
 * Tusk Plan Detector Hook - ExitPlanMode Detection
 *
 * Detects when Claude exits plan mode and reminds to save the plan
 * using the mcp__tusk__plan tool to prevent loss during compaction.
 *
 * This is THE CRITICAL hook for preserving planning work.
 */

import { logHookActivity } from "./hook-logger.ts";

async function main() {
  try {
    // Read JSON input from stdin
    const stdinBuffer = [];
    for await (const chunk of process.stdin) {
      stdinBuffer.push(chunk);
    }
    const inputData = JSON.parse(Buffer.concat(stdinBuffer).toString());

    // Extract tool information
    const toolName = inputData.tool_name || '';
    const toolInput = inputData.tool_input || {};

    // Only process ExitPlanMode tool usage
    if (toolName !== 'ExitPlanMode') {
      process.exit(0);
    }

    // Extract the plan content
    const planContent = toolInput.plan || '';

    if (!planContent || planContent.length < 50) {
      // Plan too short, probably not worth saving
      process.exit(0);
    }

    // Extract a brief summary from the plan
    const firstLine = planContent.split('\n')
      .find(line => line.trim().length > 0)
      ?.trim()
      .substring(0, 80) || 'your plan';

    // Inject a clear, actionable reminder
    console.error(`
📋 **IMPORTANT: Save Your Plan!**

You just created a plan that needs to be preserved across sessions.

**Use the plan tool immediately:**

\`\`\`
mcp__tusk__plan({
  action: "save",
  title: "Brief description of your plan",
  content: "Your full plan details..."
})
\`\`\`

**Why this matters:**
- Plans survive context compaction
- Recall will show your active plan automatically
- Track progress over time
- Never lose your roadmap

**Don't let this planning work disappear!**
`);

    logHookActivity("plan_detector", "ExitPlanMode detected", `Plan preview: ${firstLine}`);
  } catch (error) {
    // Silently fail - don't block Claude's workflow
  }

  process.exit(0);
}

main();
