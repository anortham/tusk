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
import { existsSync } from "fs";
import { join, resolve, dirname } from "path";
import { logHookActivity, logSuccess, logError } from "./hook-logger.ts";

async function main() {
  try {
    const now = new Date();
    const description = `Auto-saved before compaction to preserve context - ${now.toLocaleString()}`;

    // Save checkpoint using tusk CLI with cross-platform path resolution
    const hookDir = dirname(import.meta.path);
    const tuskRoot = resolve(hookDir, '../..');
    const cliPath = join(tuskRoot, 'cli.ts');

    // Verify CLI exists before attempting to run
    if (!existsSync(cliPath)) {
      logError("pre_compact", `CLI not found at ${cliPath}`);
      console.error(`⚠️ Tusk CLI not found at ${cliPath}`);
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