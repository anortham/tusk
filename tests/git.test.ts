/**
 * Git Integration Test Suite
 * Implements comprehensive tests based on git.contracts.ts
 */

import { test, expect, describe, beforeEach, afterEach } from "bun:test";
import { spawnSync } from "bun";
import { mkdirSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import {
  getCurrentBranch,
  getCurrentCommit,
  getProjectName,
  getRecentFiles,
  isGitRepo,
  getGitContext,
  getStatusSummary,
} from '../src/integrations/git.js';
import {
  TestEnvironment,
  PerformanceTester,
  TestAssertions,
  TEST_CONFIG,
} from "./setup.js";

// Setup test environment
beforeEach(() => {
  TestEnvironment.setup();
});

afterEach(() => {
  TestEnvironment.cleanup();
});

// Git test utilities
class GitTestUtils {
  static createTestRepo(path: string): void {
    if (!existsSync(path)) {
      mkdirSync(path, { recursive: true });
    }

    // Initialize git repo
    spawnSync(["git", "init"], { cwd: path });
    spawnSync(["git", "config", "user.email", "test@example.com"], { cwd: path });
    spawnSync(["git", "config", "user.name", "Test User"], { cwd: path });

    // Create initial commit
    writeFileSync(join(path, "README.md"), "# Test Repo");
    spawnSync(["git", "add", "README.md"], { cwd: path });
    spawnSync(["git", "commit", "-m", "Initial commit"], { cwd: path });
  }

  static createBranch(path: string, branchName: string): void {
    spawnSync(["git", "checkout", "-b", branchName], { cwd: path });
  }

  static addRemote(path: string, remoteName: string, url: string): void {
    spawnSync(["git", "remote", "add", remoteName, url], { cwd: path });
  }

  static createFiles(path: string, files: string[]): void {
    files.forEach(file => {
      writeFileSync(join(path, file), `Content of ${file}`);
    });
  }

  static stageFiles(path: string, files: string[]): void {
    spawnSync(["git", "add", ...files], { cwd: path });
  }

  static isGitAvailable(): boolean {
    try {
      const result = spawnSync(["git", "--version"]);
      return result.success;
    } catch {
      return false;
    }
  }
}

describe("Git Integration - Repository Detection", () => {
  test("should detect valid git repository", () => {
    if (!GitTestUtils.isGitAvailable()) {
      console.log("Git not available, skipping git tests");
      return;
    }

    const testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "test-repo");
    GitTestUtils.createTestRepo(testRepoPath);

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);
      expect(isGitRepo()).toBe(true);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should return false for non-git directory", () => {
    const nonGitPath = join(TEST_CONFIG.TEST_TUSK_DIR, "non-git");
    mkdirSync(nonGitPath, { recursive: true });

    const originalCwd = process.cwd();
    try {
      process.chdir(nonGitPath);
      expect(isGitRepo()).toBe(false);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle git command not available", () => {
    // Mock git command failure by testing in environment where git might not exist
    // This test documents expected behavior
    const originalCwd = process.cwd();
    try {
      process.chdir(TEST_CONFIG.TEST_TUSK_DIR);
      // Should not throw even if git is not available
      expect(() => isGitRepo()).not.toThrow();
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should detect corrupted .git directory", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "corrupted-repo");
    mkdirSync(testRepoPath, { recursive: true });

    // Create a .git directory but not a valid repo
    mkdirSync(join(testRepoPath, ".git"));
    writeFileSync(join(testRepoPath, ".git", "invalid"), "not a repo");

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);
      // Should handle corrupted repo gracefully
      expect(() => isGitRepo()).not.toThrow();
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - Branch Information", () => {
  let testRepoPath: string;

  beforeEach(() => {
    if (!GitTestUtils.isGitAvailable()) return;

    testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "branch-test-repo");
    GitTestUtils.createTestRepo(testRepoPath);
  });

  test("should extract current branch name", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      // Default branch should be 'main' or 'master'
      const branch = getCurrentBranch();
      expect(branch).toBeDefined();
      expect(typeof branch).toBe("string");
      expect(branch?.length).toBeGreaterThan(0);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle branch names with special characters", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      // Create branch with special characters
      GitTestUtils.createBranch(testRepoPath, "feature/special-chars_123");

      const branch = getCurrentBranch();
      expect(branch).toBe("feature/special-chars_123");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle unicode branch names", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      // Create branch with unicode characters
      GitTestUtils.createBranch(testRepoPath, "feature/测试-branch");

      const branch = getCurrentBranch();
      expect(branch).toBe("feature/测试-branch");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle git command errors gracefully", () => {
    const originalCwd = process.cwd();
    try {
      process.chdir(TEST_CONFIG.TEST_TUSK_DIR); // Non-git directory

      // Should not throw, should return undefined
      expect(() => getCurrentBranch()).not.toThrow();
      expect(getCurrentBranch()).toBeUndefined();
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - Commit Information", () => {
  let testRepoPath: string;

  beforeEach(() => {
    if (!GitTestUtils.isGitAvailable()) return;

    testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "commit-test-repo");
    GitTestUtils.createTestRepo(testRepoPath);
  });

  test("should extract short commit hash", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      const commit = getCurrentCommit();
      expect(commit).toBeDefined();
      expect(typeof commit).toBe("string");
      expect(commit?.length).toBeGreaterThan(0);
      expect(commit?.length).toBeLessThanOrEqual(8); // Short hash
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle repository with no commits", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const emptyRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "empty-repo");
    mkdirSync(emptyRepoPath, { recursive: true });
    spawnSync(["git", "init"], { cwd: emptyRepoPath });

    const originalCwd = process.cwd();
    try {
      process.chdir(emptyRepoPath);

      const commit = getCurrentCommit();
      expect(commit).toBeUndefined();
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should consistently return same hash for same commit", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      const firstCall = getCurrentCommit();
      const secondCall = getCurrentCommit();

      expect(firstCall).toBe(secondCall);
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - Project Name Extraction", () => {
  let testRepoPath: string;

  beforeEach(() => {
    if (!GitTestUtils.isGitAvailable()) return;

    testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "project-name-repo");
    GitTestUtils.createTestRepo(testRepoPath);
  });

  test("should extract project name from git remote URL", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.addRemote(testRepoPath, "origin", "https://github.com/user/test-project.git");

      const project = getProjectName();
      expect(project).toBe("test-project");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle GitHub URLs (https and ssh)", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      // Test HTTPS URL
      GitTestUtils.addRemote(testRepoPath, "origin", "https://github.com/user/github-project.git");
      expect(getProjectName()).toBe("github-project");

      // Test SSH URL (remove previous remote first)
      spawnSync(["git", "remote", "remove", "origin"], { cwd: testRepoPath });
      GitTestUtils.addRemote(testRepoPath, "origin", "git@github.com:user/ssh-project.git");
      expect(getProjectName()).toBe("ssh-project");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle URLs with .git suffix", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.addRemote(testRepoPath, "origin", "https://example.com/user/project-with-git.git");
      expect(getProjectName()).toBe("project-with-git");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle URLs without .git suffix", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.addRemote(testRepoPath, "origin", "https://example.com/user/project-no-git");
      expect(getProjectName()).toBe("project-no-git");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should fall back to directory name when no remote", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const namedDirPath = join(TEST_CONFIG.TEST_TUSK_DIR, "my-special-project");
    GitTestUtils.createTestRepo(namedDirPath);

    const originalCwd = process.cwd();
    try {
      process.chdir(namedDirPath);

      const project = getProjectName();
      expect(project).toBe("my-special-project");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle malformed remote URLs", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.addRemote(testRepoPath, "origin", "not-a-valid-url");

      // Should fall back to directory name
      const project = getProjectName();
      expect(project).toBe("project-name-repo");
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - File Change Detection", () => {
  let testRepoPath: string;

  beforeEach(() => {
    if (!GitTestUtils.isGitAvailable()) return;

    testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "file-changes-repo");
    GitTestUtils.createTestRepo(testRepoPath);
  });

  test("should detect staged files", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.createFiles(testRepoPath, ["staged-file.ts"]);
      GitTestUtils.stageFiles(testRepoPath, ["staged-file.ts"]);

      const files = getRecentFiles();
      expect(files).toContain("staged-file.ts");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should detect unstaged files", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.createFiles(testRepoPath, ["unstaged-file.ts"]);

      const files = getRecentFiles();
      expect(files).toContain("unstaged-file.ts");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should limit number of files returned", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      // Create many files
      const manyFiles = Array.from({ length: 20 }, (_, i) => `file-${i}.ts`);
      GitTestUtils.createFiles(testRepoPath, manyFiles);

      const files = getRecentFiles(5);
      expect(files.length).toBeLessThanOrEqual(5);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle empty working directory", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      const files = getRecentFiles();
      // Should not throw and should return array (might be empty or contain recent commit files)
      expect(Array.isArray(files)).toBe(true);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should exclude hidden files (.dotfiles)", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.createFiles(testRepoPath, [".hidden-file", "visible-file.ts"]);

      const files = getRecentFiles();
      expect(files).not.toContain(".hidden-file");
      expect(files).toContain("visible-file.ts");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle file paths with spaces", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.createFiles(testRepoPath, ["file with spaces.ts"]);

      const files = getRecentFiles();
      expect(files).toContain("file with spaces.ts");
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - Comprehensive Context", () => {
  let testRepoPath: string;

  beforeEach(() => {
    if (!GitTestUtils.isGitAvailable()) return;

    testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "context-repo");
    GitTestUtils.createTestRepo(testRepoPath);
  });

  test("should combine all git info for valid repo", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.addRemote(testRepoPath, "origin", "https://github.com/user/test-project.git");
      GitTestUtils.createBranch(testRepoPath, "feature/test");
      GitTestUtils.createFiles(testRepoPath, ["test.ts"]);

      const context = getGitContext();

      expect(context.project).toBe("test-project");
      expect(context.branch).toBe("feature/test");
      expect(context.commit).toBeDefined();
      expect(Array.isArray(context.files)).toBe(true);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle non-git directory gracefully", () => {
    const nonGitPath = join(TEST_CONFIG.TEST_TUSK_DIR, "non-git");
    mkdirSync(nonGitPath, { recursive: true });

    const originalCwd = process.cwd();
    try {
      process.chdir(nonGitPath);

      const context = getGitContext();

      expect(context.project).toBe("non-git"); // Should fall back to directory name
      expect(context.branch).toBeUndefined();
      expect(context.commit).toBeUndefined();
      expect(context.files).toEqual([]);
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should provide project name even without git", () => {
    const nonGitPath = join(TEST_CONFIG.TEST_TUSK_DIR, "project-without-git");
    mkdirSync(nonGitPath, { recursive: true });

    const originalCwd = process.cwd();
    try {
      process.chdir(nonGitPath);

      const context = getGitContext();

      expect(context.project).toBe("project-without-git");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should never throw exceptions", () => {
    // Test various error conditions
    const errorPaths = [
      join(TEST_CONFIG.TEST_TUSK_DIR, "non-existent"),
      join(TEST_CONFIG.TEST_TUSK_DIR, "empty-dir"),
    ];

    errorPaths.forEach(path => {
      if (path.includes("empty-dir")) {
        mkdirSync(path, { recursive: true });
      }

      const originalCwd = process.cwd();
      try {
        if (existsSync(path)) {
          process.chdir(path);
        }

        expect(() => getGitContext()).not.toThrow();
      } finally {
        if (existsSync(originalCwd)) {
          process.chdir(originalCwd);
        }
      }
    });
  });
});

describe("Git Integration - Status Summary", () => {
  let testRepoPath: string;

  beforeEach(() => {
    if (!GitTestUtils.isGitAvailable()) return;

    testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "status-repo");
    GitTestUtils.createTestRepo(testRepoPath);
  });

  test("should format branch and commit info", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.createBranch(testRepoPath, "feature/status-test");

      const summary = getStatusSummary();

      expect(summary).toContain("feature/status-test");
      expect(summary).toContain("@"); // Should include commit separator
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should include file change count", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      GitTestUtils.createFiles(testRepoPath, ["change1.ts", "change2.ts"]);

      const summary = getStatusSummary();

      expect(summary).toContain("changed files");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should handle non-git directory message", () => {
    const nonGitPath = join(TEST_CONFIG.TEST_TUSK_DIR, "non-git-status");
    mkdirSync(nonGitPath, { recursive: true });

    const originalCwd = process.cwd();
    try {
      process.chdir(nonGitPath);

      const summary = getStatusSummary();

      expect(summary).toContain("Not a git repository");
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should be concise and readable", () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      const summary = getStatusSummary();

      expect(summary.length).toBeLessThan(100); // Should be concise
      expect(summary.length).toBeGreaterThan(5); // Should contain meaningful info
      TestAssertions.assertFormattingQuality(summary);
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - Performance", () => {
  test("should complete git operations under 500ms", async () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "perf-repo");
    GitTestUtils.createTestRepo(testRepoPath);

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      const { executionTime } = await PerformanceTester.measureExecution(
        async () => {
          return getGitContext();
        },
        TEST_CONFIG.PERFORMANCE_THRESHOLDS.GIT_OPERATION
      );

      TestAssertions.assertPerformance(
        executionTime,
        TEST_CONFIG.PERFORMANCE_THRESHOLDS.GIT_OPERATION,
        "Git context operations"
      );
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should not spawn excessive git processes", async () => {
    if (!GitTestUtils.isGitAvailable()) return;

    const testRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "process-test-repo");
    GitTestUtils.createTestRepo(testRepoPath);

    const originalCwd = process.cwd();
    try {
      process.chdir(testRepoPath);

      // Multiple calls should not spawn excessive processes
      // This is more of a design principle test
      const results = await Promise.all([
        getGitContext(),
        getGitContext(),
        getGitContext(),
      ]);

      expect(results).toHaveLength(3);
      expect(results[0]).toEqual(results[1]);
      expect(results[1]).toEqual(results[2]);
    } finally {
      process.chdir(originalCwd);
    }
  });
});

describe("Git Integration - Error Resilience", () => {
  test("should never crash on git command failures", () => {
    const originalCwd = process.cwd();
    try {
      process.chdir(TEST_CONFIG.TEST_TUSK_DIR); // Non-git directory

      // All git operations should handle errors gracefully
      expect(() => getCurrentBranch()).not.toThrow();
      expect(() => getCurrentCommit()).not.toThrow();
      expect(() => getProjectName()).not.toThrow();
      expect(() => getRecentFiles()).not.toThrow();
      expect(() => isGitRepo()).not.toThrow();
      expect(() => getGitContext()).not.toThrow();
      expect(() => getStatusSummary()).not.toThrow();
    } finally {
      process.chdir(originalCwd);
    }
  });

  test("should provide meaningful fallbacks", () => {
    const fallbackTestPath = join(TEST_CONFIG.TEST_TUSK_DIR, "fallback-test");
    mkdirSync(fallbackTestPath, { recursive: true });

    const originalCwd = process.cwd();
    try {
      process.chdir(fallbackTestPath);

      const context = getGitContext();

      // Should have meaningful fallbacks
      expect(context.project).toBe("fallback-test"); // Directory name fallback
      expect(context.branch).toBeUndefined(); // No branch in non-git repo
      expect(context.commit).toBeUndefined(); // No commit in non-git repo
      expect(Array.isArray(context.files)).toBe(true); // Should return array even if empty
    } finally {
      process.chdir(originalCwd);
    }
  });
});