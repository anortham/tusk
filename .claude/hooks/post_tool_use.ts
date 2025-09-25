#!/usr/bin/env bun
/**
 * Tusk Post Tool Use Hook - Git Commit Detection
 *
 * Automatically detects when Claude performs git commits and saves the commit
 * message as a checkpoint to preserve the detailed commit context.
 *
 * Cross-platform compatible for Windows, macOS, and Linux.
 */

import { spawnSync } from "bun";
import { existsSync } from "fs";
import { join, resolve, dirname } from "path";
import { logHookActivity, logSuccess, logError, logSkip } from "./hook-logger.ts";

function extractCommitMessage(command: string): string | null {
  // Match various git commit patterns
  const patterns = [
    // git commit -m "message"
    /git commit[^"]*-m\s*"([^"]+)"/,
    // git commit -m 'message'
    /git commit[^']*-m\s*'([^']+)'/,
    // git commit --message="message"
    /git commit[^"]*--message=?"([^"]+)"/,
    // git commit with heredoc
    /git commit.*-m.*\$\(cat <<['"]*EOF['"]*\s*\n(.*?)\s*EOF/s,
  ];

  for (const pattern of patterns) {
    const match = command.match(pattern);
    if (match) {
      return match[1].trim();
    }
  }

  return null;
}

function isGitCommitCommand(command: string): boolean {
  // Check for git commit patterns
  return /git\s+commit/.test(command) && /-m|--message/.test(command);
}

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
    const toolResponse = inputData.tool_response || {};

    // Only process Bash tool usage
    if (toolName !== 'Bash') {
      logSkip("post_tool_use", `not bash tool (${toolName})`);
      process.exit(0);
    }

    const command = toolInput.command || '';

    // Check if this is a git commit command
    if (!isGitCommitCommand(command)) {
      logSkip("post_tool_use", "not git commit");
      process.exit(0);
    }

    // Check if the command was successful
    const success = toolResponse.success !== false && !toolResponse.stderr?.includes('error');
    if (!success) {
      logSkip("post_tool_use", "commit failed");
      process.exit(0);
    }

    // Extract commit message
    const commitMessage = extractCommitMessage(command);
    const description = commitMessage
      ? `Git commit: ${commitMessage}`
      : "Git commit completed (could not extract message)";

    // Save checkpoint using tusk CLI with cross-platform path resolution
    const hookDir = dirname(import.meta.path);
    const tuskRoot = resolve(hookDir, '../..');
    const cliPath = join(tuskRoot, 'cli.ts');

    // Verify CLI exists before attempting to run
    if (!existsSync(cliPath)) {
      logError("post_tool_use", `CLI not found at ${cliPath}`);
      console.error(`⚠️ Tusk CLI not found at ${cliPath}`);
      process.exit(0);
    }

    const result = spawnSync(["bun", cliPath, "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logSuccess("post_tool_use", commitMessage || 'commit completed');
      console.error(`✅ Git commit checkpoint saved: ${commitMessage || 'commit completed'}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logError("post_tool_use", errorOutput);
      console.error(`⚠️ Git commit checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logError("post_tool_use", String(error));
    console.error(`⚠️ Post tool use hook error: ${error}`);
  }

  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();