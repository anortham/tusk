#!/usr/bin/env bun
/**
 * Tusk Pre-Compact Hook
 *
 * Automatically saves a checkpoint before compaction starts to preserve context.
 * This prevents loss of work progress when Claude Code compacts the conversation.
 */

import { spawnSync } from "bun";

async function main() {
  try {
    const now = new Date();
    const description = `Auto-saved before compaction to preserve context - ${now.toLocaleString()}`;

    // Use the tusk CLI with absolute path
    const result = spawnSync(["bun", "/Users/murphy/Source/tusk/cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      console.error(`✅ Pre-compact checkpoint saved: ${description}`);
    } else {
      const error = new TextDecoder().decode(result.stderr);
      console.error(`⚠️ Pre-compact checkpoint failed: ${error}`);
    }
  } catch (error) {
    console.error(`⚠️ Pre-compact checkpoint error: ${error}`);
  }

  // Always exit successfully to not block compaction
  process.exit(0);
}

main();