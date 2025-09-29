/**
 * Git context utilities for tusk
 * Captures git branch, commit, and recently modified files
 */

import { spawnSync } from "bun";
import { basename } from "path";

export interface GitInfo {
  branch?: string;
  commit?: string;
  project?: string;
  files?: string[];
}

/**
 * Get current git branch name
 */
export function getCurrentBranch(): string | undefined {
  try {
    const result = spawnSync(["git", "branch", "--show-current"], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success && result.stdout) {
      return new TextDecoder().decode(result.stdout).trim();
    }
  } catch (error) {
    // Not in a git repo or git not available
  }
  return undefined;
}

/**
 * Get latest commit hash (short form)
 */
export function getCurrentCommit(): string | undefined {
  try {
    const result = spawnSync(["git", "rev-parse", "--short", "HEAD"], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success && result.stdout) {
      return new TextDecoder().decode(result.stdout).trim();
    }
  } catch (error) {
    // Not in a git repo or git not available
  }
  return undefined;
}

/**
 * Get project name from git remote or directory name
 */
export function getProjectName(): string | undefined {
  // Try to get from git remote
  try {
    const result = spawnSync(["git", "remote", "get-url", "origin"], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success && result.stdout) {
      const url = new TextDecoder().decode(result.stdout).trim();
      // Extract project name from git URL
      const match = url.match(/\/([^\/]+?)(?:\.git)?$/);
      if (match) {
        return match[1];
      }
    }
  } catch (error) {
    // Fall through to directory name
  }

  // Fall back to current directory name
  try {
    const cwd = process.cwd();
    return basename(cwd);
  } catch (error) {
    return undefined;
  }
}

/**
 * Get recently modified files (unstaged and staged)
 */
export function getRecentFiles(limit: number = 10): string[] {
  const files: string[] = [];

  try {
    // Get modified files (both staged and unstaged)
    const result = spawnSync(["git", "status", "--porcelain"], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success && result.stdout) {
      const lines = new TextDecoder().decode(result.stdout).trim().split("\n");

      for (const line of lines) {
        if (line.length > 3) {
          // Parse git status format: "XY filename"
          const filename = line.substring(3).trim();
          if (filename && !filename.startsWith(".")) {
            files.push(filename);
          }
        }
      }
    }
  } catch (error) {
    // Not in a git repo
  }

  // Also get recently committed files if we don't have many
  if (files.length < 3) {
    try {
      const result = spawnSync([
        "git",
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "HEAD"
      ], {
        stdout: "pipe",
        stderr: "pipe",
      });

      if (result.success && result.stdout) {
        const recentCommitFiles = new TextDecoder()
          .decode(result.stdout)
          .trim()
          .split("\n")
          .filter(f => f.length > 0 && !f.startsWith("."));

        files.push(...recentCommitFiles);
      }
    } catch (error) {
      // Ignore errors from recent commit files
    }
  }

  // Remove duplicates and limit
  return [...new Set(files)].slice(0, limit);
}

/**
 * Check if current directory is a git repository
 */
export function isGitRepo(): boolean {
  try {
    const result = spawnSync(["git", "rev-parse", "--git-dir"], {
      stdout: "pipe",
      stderr: "pipe",
    });
    return result.success;
  } catch (error) {
    return false;
  }
}

/**
 * Get comprehensive git context for a checkpoint
 */
export function getGitContext(): GitInfo {
  if (!isGitRepo()) {
    return {
      project: getProjectName(),
    };
  }

  return {
    branch: getCurrentBranch(),
    commit: getCurrentCommit(),
    project: getProjectName(),
    files: getRecentFiles(),
  };
}

/**
 * Get git status summary for display
 */
export function getStatusSummary(): string {
  if (!isGitRepo()) {
    return "Not a git repository";
  }

  const branch = getCurrentBranch() || "unknown";
  const commit = getCurrentCommit() || "unknown";
  const files = getRecentFiles(3);

  let summary = `${branch}@${commit}`;

  if (files.length > 0) {
    summary += ` (${files.length} changed files)`;
  }

  return summary;
}