#!/usr/bin/env bun
/**
 * Tusk-Bun Stop Hook - Work Completion Detection
 *
 * Analyzes Claude's responses to detect when work is completed and automatically
 * saves a checkpoint to capture the final state.
 */

import { spawnSync } from "bun";

function detectCompletionPatterns(text: string): boolean {
  const completionPatterns = [
    /\b(completed?|finished|done|resolved|fixed|implemented|deployed)\b/i,
    /\b(all set|ready to go|good to go|successfully)\b/i,
    /\b(final|complete|finish|wrap up|concluded)\b/i,
    /✅|✓|☑️/, // Check marks
    /\b(that should do it|we're done|everything is working)\b/i,
  ];

  return completionPatterns.some(pattern => pattern.test(text));
}

function extractKeyContent(text: string): string {
  // Get first meaningful line
  const lines = text.split('\n');
  const firstMeaningfulLine = lines.find(line =>
    line.trim() && !line.trim().startsWith('#')
  ) || "Work completed";

  // Truncate if too long
  if (firstMeaningfulLine.length > 100) {
    return firstMeaningfulLine.substring(0, 97) + "...";
  }
  return firstMeaningfulLine;
}

async function main() {
  try {
    const args = process.argv.slice(2);
    const dataIndex = args.indexOf('--data');

    if (dataIndex === -1 || !args[dataIndex + 1]) {
      process.exit(0);
    }

    const data = JSON.parse(args[dataIndex + 1]);
    const assistantMessage = data.assistant_message || {};
    const content = assistantMessage.content || '';

    // Check if this looks like completion
    if (!detectCompletionPatterns(content)) {
      process.exit(0);
    }

    const keyContent = extractKeyContent(content);
    const description = `Work completed: ${keyContent}`;

    // Save checkpoint using local tusk CLI
    const result = spawnSync(["bun", "./cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      console.error(`✅ Completion checkpoint saved: ${description}`);
    }
  } catch (error) {
    console.error(`⚠️ Stop hook error: ${error}`);
  }

  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();