#!/usr/bin/env bun
/**
 * Tusk Conversation Start Hook - Session Context Setup
 *
 * Automatically restores relevant context when starting new conversations,
 * especially useful for continuing work after compaction or session restart.
 *
 * This hook implements SMART CONTEXT CONTINUITY!
 */

import { spawnSync } from "bun";
import { logSuccess, logError, logSkip, findTuskCli } from "./hook-logger.ts";

interface SessionContext {
  workspaceInfo: string;
  recentWork: string[];
  activeTopics: string[];
  timeOfDay: string;
}

function getWorkspaceContext(): string {
  try {
    // Get git status for current context
    const gitResult = spawnSync(["git", "status", "--porcelain"], { stdout: "pipe", stderr: "pipe" });
    if (gitResult.success) {
      const stdout = new TextDecoder().decode(gitResult.stdout);
      const changes = stdout.trim().split('\n').filter(line => line.trim()).length;

      // Get current branch
      const branchResult = spawnSync(["git", "branch", "--show-current"], { stdout: "pipe", stderr: "pipe" });
      const branch = branchResult.success
        ? new TextDecoder().decode(branchResult.stdout).trim()
        : "unknown";

      if (changes > 0) {
        return `Git: ${branch} branch, ${changes} uncommitted changes`;
      } else {
        return `Git: ${branch} branch, clean working tree`;
      }
    }
  } catch {
    // Not a git repo or git not available
  }

  try {
    // Get current directory context
    const pwd = process.cwd();
    const dirName = pwd.split('/').pop() || pwd;
    return `Working in: ${dirName}`;
  } catch {
    return "Starting new session";
  }
}

function getTimeContext(): string {
  const now = new Date();
  const hour = now.getHours();

  if (hour < 6) return "late night";
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  if (hour < 22) return "evening";
  return "late night";
}

function detectSessionType(context: SessionContext): string {
  const { workspaceInfo, timeOfDay } = context;

  // Check if this looks like a continuation
  if (workspaceInfo.includes("uncommitted changes")) {
    return "work-continuation";
  }

  // Check if it's a new day
  if (timeOfDay === "morning") {
    return "daily-startup";
  }

  return "new-session";
}

async function getRecentContext(): Promise<string[]> {
  const cliPath = findTuskCli(import.meta.path);
  if (!cliPath) return [];

  try {
    // Get recent checkpoints from current workspace
    const result = spawnSync([
      "bun", cliPath, "recall",
      "--days", "1",
      "--workspace", "current"
    ], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      const output = new TextDecoder().decode(result.stdout);
      // Extract key recent activities (simplified parsing)
      const lines = output.split('\n').filter(line =>
        line.includes('•') && !line.includes('Found 0')
      );
      return lines.slice(0, 3); // Last 3 activities
    }
  } catch {
    // Failed to get context, continue without it
  }

  return [];
}

async function main() {
  try {
    // Build session context
    const context: SessionContext = {
      workspaceInfo: getWorkspaceContext(),
      recentWork: await getRecentContext(),
      activeTopics: [], // Could be enhanced to detect active topics
      timeOfDay: getTimeContext(),
    };

    const sessionType = detectSessionType(context);

    // Create contextual checkpoint
    let description = `Session started (${sessionType}) - ${context.timeOfDay}`;

    if (context.workspaceInfo) {
      description += ` | ${context.workspaceInfo}`;
    }

    if (context.recentWork.length > 0) {
      description += ` | Continuing from recent work`;
    }

    const cliPath = findTuskCli(import.meta.path);
    if (!cliPath) {
      logError("conversation_start", "CLI not found");
      process.exit(0);
    }

    // Create session start checkpoint with contextual tags
    const tags = ["session-start", sessionType, context.timeOfDay];

    const result = spawnSync([
      "bun", cliPath, "checkpoint", description,
      "--tags", tags.join(",")
    ], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logSuccess("conversation_start", `${sessionType} (${context.timeOfDay})`);

      // If we have recent context, also suggest a recall
      if (context.recentWork.length > 0) {
        console.error(`💡 Context available: ${context.recentWork.length} recent activities found`);
        console.error(`   Consider: Use /recall to restore context from recent work`);
      }
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logError("conversation_start", errorOutput);
    }
  } catch (error) {
    logError("conversation_start", String(error));
  }

  process.exit(0);
}

main();