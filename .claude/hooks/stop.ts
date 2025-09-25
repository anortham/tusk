#!/usr/bin/env bun
/**
 * Tusk Stop Hook - Work Completion Detection
 *
 * Analyzes Claude's responses to detect when work is completed and automatically
 * saves a checkpoint to capture the final state.
 *
 * Cross-platform compatible for Windows, macOS, and Linux.
 */

import { spawnSync } from "bun";
import { existsSync } from "fs";
import { join, resolve, dirname } from "path";
import { logHookActivity, logSuccess, logError, logSkip } from "./hook-logger.ts";

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
    // Read JSON input from stdin
    const stdinBuffer = [];
    for await (const chunk of process.stdin) {
      stdinBuffer.push(chunk);
    }
    const inputData = JSON.parse(Buffer.concat(stdinBuffer).toString());

    // Try multiple possible paths for assistant content
    let content = '';
    if (inputData.assistant_message?.content) {
      content = inputData.assistant_message.content;
    } else if (inputData.content) {
      content = inputData.content;
    } else if (inputData.message?.content) {
      content = inputData.message.content;
    }

    // Check if this looks like completion
    if (!detectCompletionPatterns(content)) {
      logSkip("stop", "no completion patterns");
      process.exit(0);
    }

    const keyContent = extractKeyContent(content);
    const description = `Work completed: ${keyContent}`;

    // Save checkpoint using tusk CLI with cross-platform path resolution
    const hookDir = dirname(import.meta.path);
    const tuskRoot = resolve(hookDir, '../..');
    const cliPath = join(tuskRoot, 'cli.ts');

    // Verify CLI exists before attempting to run
    if (!existsSync(cliPath)) {
      logError("stop", `CLI not found at ${cliPath}`);
      console.error(`⚠️ Tusk CLI not found at ${cliPath}`);
      process.exit(0);
    }

    const result = spawnSync(["bun", cliPath, "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logSuccess("stop", keyContent);
      console.error(`✅ Completion checkpoint saved: ${description}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logError("stop", errorOutput);
      console.error(`⚠️ Completion checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logError("stop", String(error));
    console.error(`⚠️ Stop hook error: ${error}`);
  }

  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();