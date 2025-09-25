#!/usr/bin/env bun
/**
 * Tusk Pre-Compact Hook
 *
 * Automatically saves a checkpoint before compaction starts to preserve context.
 * This prevents loss of work progress when Claude Code compacts the conversation.
 */

import { spawnSync } from "bun";
import { appendFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const HOOKS_LOG_PATH = join(homedir(), ".tusk", "hooks.log");

function logHookActivity(message: string) {
  try {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [pre_compact] ${message}\n`;
    appendFileSync(HOOKS_LOG_PATH, logEntry);
  } catch (error) {
    console.error(`⚠️ Failed to write to hooks log: ${error}`);
  }
}

async function main() {
  logHookActivity("Pre-compact hook triggered");

  try {
    const now = new Date();
    const description = `Auto-saved before compaction to preserve context - ${now.toLocaleString()}`;

    logHookActivity(`Creating pre-compact checkpoint: ${description}`);

    // Use the tusk CLI with absolute path
    const result = spawnSync(["bun", "/Users/murphy/Source/tusk/cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logHookActivity(`✅ Pre-compact checkpoint saved successfully: ${description}`);
      console.error(`✅ Pre-compact checkpoint saved: ${description}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logHookActivity(`❌ Pre-compact checkpoint failed: ${errorOutput}`);
      console.error(`⚠️ Pre-compact checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logHookActivity(`❌ Pre-compact hook error: ${error}`);
    console.error(`⚠️ Pre-compact checkpoint error: ${error}`);
  }

  logHookActivity("Pre-compact hook completed");
  // Always exit successfully to not block compaction
  process.exit(0);
}

main();