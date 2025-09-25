#!/usr/bin/env bun
/**
 * Tusk Pre-Compact Hook
 *
 * Automatically saves a checkpoint before compaction starts to preserve context.
 * This prevents loss of work progress when Claude Code compacts the conversation.
 *
 * Cross-platform compatible for Windows, macOS, and Linux.
 */

import { spawnSync } from "bun";
import { logSuccess, logError, findTuskCli } from "./hook-logger.ts";

async function main() {
  try {
    const now = new Date();
    const description = `Auto-saved before compaction to preserve context - ${now.toLocaleString()}`;

    // Find tusk CLI using smart path resolution
    const cliPath = findTuskCli(import.meta.path);
    if (!cliPath) {
      logError("pre_compact", "CLI not found in any expected location");
      console.error(`⚠️ Tusk CLI not found. Set TUSK_CLI_PATH environment variable or ensure tusk is in a standard location.`);
      process.exit(0);
    }

    const result = spawnSync(["bun", cliPath, "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logSuccess("pre_compact", "context preserved");
      console.error(`✅ Pre-compact checkpoint saved: ${description}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logError("pre_compact", errorOutput);
      console.error(`⚠️ Pre-compact checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logError("pre_compact", String(error));
    console.error(`⚠️ Pre-compact checkpoint error: ${error}`);
  }

  // Always exit successfully to not block compaction
  process.exit(0);
}

main();