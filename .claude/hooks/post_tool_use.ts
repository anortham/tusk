#!/usr/bin/env bun
/**
 * Tusk Post Tool Use Hook - Git Commit Detection
 *
 * Automatically detects when Claude performs git commits and saves the commit
 * message as a checkpoint to preserve the detailed commit context.
 */

import { spawnSync } from "bun";
import { appendFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const HOOKS_LOG_PATH = join(homedir(), ".tusk", "hooks.log");

function logHookActivity(message: string) {
  try {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [post_tool_use] ${message}\n`;
    appendFileSync(HOOKS_LOG_PATH, logEntry);
  } catch (error) {
    console.error(`⚠️ Failed to write to hooks log: ${error}`);
  }
}

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
  logHookActivity("Hook triggered");

  try {
    // Read JSON input from stdin
    const stdinBuffer = [];
    for await (const chunk of process.stdin) {
      stdinBuffer.push(chunk);
    }
    const inputData = JSON.parse(Buffer.concat(stdinBuffer).toString());

    logHookActivity(`Input data keys: ${JSON.stringify(Object.keys(inputData))}`);

    // Extract tool information
    const toolName = inputData.tool_name || '';
    const toolInput = inputData.tool_input || {};
    const toolResponse = inputData.tool_response || {};
    const sessionId = inputData.session_id || 'unknown';

    logHookActivity(`Tool: ${toolName}, Session: ${sessionId}`);

    // Only process Bash tool usage
    if (toolName !== 'Bash') {
      logHookActivity(`Not a Bash tool (${toolName}), skipping`);
      process.exit(0);
    }

    const command = toolInput.command || '';
    logHookActivity(`Command: ${command.substring(0, 100)}...`);

    // Check if this is a git commit command
    if (!isGitCommitCommand(command)) {
      logHookActivity("Not a git commit command, skipping");
      process.exit(0);
    }

    // Check if the command was successful
    const success = toolResponse.success !== false && !toolResponse.stderr?.includes('error');
    if (!success) {
      logHookActivity("Git commit appears to have failed, skipping checkpoint");
      process.exit(0);
    }

    // Extract commit message
    const commitMessage = extractCommitMessage(command);
    if (!commitMessage) {
      logHookActivity("Could not extract commit message, using generic description");
    }

    const description = commitMessage
      ? `Git commit: ${commitMessage}`
      : "Git commit completed (could not extract message)";

    logHookActivity(`Creating checkpoint with description: ${description}`);

    // Save checkpoint using tusk CLI
    const result = spawnSync(["bun", "/Users/murphy/Source/tusk/cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logHookActivity(`✅ Checkpoint saved successfully: ${description}`);
      console.error(`✅ Git commit checkpoint saved: ${commitMessage || 'commit completed'}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logHookActivity(`❌ Checkpoint failed: ${errorOutput}`);
      console.error(`⚠️ Git commit checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logHookActivity(`❌ Hook error: ${error}`);
    console.error(`⚠️ Post tool use hook error: ${error}`);
    // Exit successfully to not interfere with Claude
    process.exit(0);
  }

  logHookActivity("Hook completed");
  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();