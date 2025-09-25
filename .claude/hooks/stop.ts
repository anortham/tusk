#!/usr/bin/env bun
/**
 * Tusk Stop Hook - Work Completion Detection
 *
 * Analyzes Claude's responses to detect when work is completed and automatically
 * saves a checkpoint to capture the final state.
 */

import { spawnSync } from "bun";
import { appendFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const HOOKS_LOG_PATH = join(homedir(), ".tusk", "hooks.log");

function logHookActivity(message: string) {
  try {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [stop] ${message}\n`;
    appendFileSync(HOOKS_LOG_PATH, logEntry);
  } catch (error) {
    console.error(`⚠️ Failed to write to hooks log: ${error}`);
  }
}

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
  logHookActivity("Hook triggered");

  try {
    const args = process.argv.slice(2);
    logHookActivity(`Args received: ${JSON.stringify(args)}`);

    const dataIndex = args.indexOf('--data');

    if (dataIndex === -1 || !args[dataIndex + 1]) {
      logHookActivity("No --data argument found, exiting");
      process.exit(0);
    }

    const data = JSON.parse(args[dataIndex + 1]);
    const assistantMessage = data.assistant_message || {};
    const content = assistantMessage.content || '';

    logHookActivity(`Assistant message content length: ${content.length}`);
    logHookActivity(`Content preview: ${content.substring(0, 100)}...`);

    // Check if this looks like completion
    if (!detectCompletionPatterns(content)) {
      logHookActivity("No completion patterns detected, skipping");
      process.exit(0);
    }

    logHookActivity("Completion patterns detected!");

    const keyContent = extractKeyContent(content);
    const description = `Work completed: ${keyContent}`;

    logHookActivity(`Creating checkpoint with description: ${description}`);

    // Save checkpoint using tusk CLI with absolute path
    const result = spawnSync(["bun", "/Users/murphy/Source/tusk/cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logHookActivity(`✅ Checkpoint saved successfully: ${description}`);
      console.error(`✅ Completion checkpoint saved: ${description}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logHookActivity(`❌ Checkpoint failed: ${errorOutput}`);
      console.error(`⚠️ Completion checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logHookActivity(`❌ Hook error: ${error}`);
    console.error(`⚠️ Stop hook error: ${error}`);
  }

  logHookActivity("Hook completed");
  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();