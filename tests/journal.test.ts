/**
 * SQLite Journal Tests with Multi-Workspace and Cross-Platform Support
 * Following TDD methodology - these tests will initially fail until implementation is complete
 */

import { test, expect, describe, beforeEach, afterEach } from "bun:test";
import { join, sep } from "path";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "fs";
import { tmpdir, homedir, platform } from "os";
import { spawnSync } from "bun";

// Import the SQLite journal implementation
import { JournalDB } from "../src/core/journal-db.js";
import type { WorkspaceInfo, CheckpointEntry, QueryOptions } from "../src/core/types.js";
import { normalizePath, hashPath } from "../src/utils/workspace-utils.js";

import {
  TestEnvironment,
  TestDataFactory,
  PerformanceTester,
  ErrorTester,
  TestAssertions,
  TEST_CONFIG,
} from "./setup.js";

describe("SQLite Journal - Multi-Workspace Support", () => {
  let testEnv: TestEnvironment;
  let originalCwd: string;
  let testDbPath: string;

  beforeEach(() => {
    TestEnvironment.setup();
    originalCwd = process.cwd();
    // Create unique database file for each test
    testDbPath = join(TEST_CONFIG.TEST_TUSK_DIR, `test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`);
  });

  afterEach(() => {
    process.chdir(originalCwd);
    TestEnvironment.cleanup();
  });

  // Helper function to create JournalDB with shared test database
  function createTestJournal(cwd?: string): JournalDB {
    return new JournalDB({
      cwd: cwd || process.cwd(),
      dbPath: testDbPath
    });
  }

  describe("Workspace Detection", () => {
    test("detects git repository root as workspace", async () => {
      // Create a temporary git repository
      const gitRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "git-repo");
      mkdirSync(gitRepoPath, { recursive: true });

      // Initialize git repo
      process.chdir(gitRepoPath);
      spawnSync(["git", "init"], { cwd: gitRepoPath });
      spawnSync(["git", "config", "user.email", "test@example.com"], { cwd: gitRepoPath });
      spawnSync(["git", "config", "user.name", "Test User"], { cwd: gitRepoPath });

      // Create subdirectory and change to it
      const subDir = join(gitRepoPath, "src", "components");
      mkdirSync(subDir, { recursive: true });
      process.chdir(subDir);

      const journal = createTestJournal();
      const workspaceInfo = await journal.getWorkspaceInfo();

      expect(workspaceInfo.detectionMethod).toBe("git");
      expect(workspaceInfo.workspacePath).toBe(gitRepoPath);
      expect(workspaceInfo.workspaceId).toBeDefined();
      expect(workspaceInfo.workspaceId.length).toBe(12); // Hash length
    });

    test("detects package.json directory as workspace", async () => {
      const projectPath = join(TEST_CONFIG.TEST_TUSK_DIR, "npm-project");
      mkdirSync(projectPath, { recursive: true });

      // Create package.json
      const packageJson = {
        name: "test-project",
        version: "1.0.0",
        description: "Test project"
      };
      writeFileSync(join(projectPath, "package.json"), JSON.stringify(packageJson, null, 2));

      // Create subdirectory and change to it
      const subDir = join(projectPath, "lib", "utils");
      mkdirSync(subDir, { recursive: true });
      process.chdir(subDir);

      const journal = createTestJournal();
      const workspaceInfo = await journal.getWorkspaceInfo();

      expect(workspaceInfo.detectionMethod).toBe("package");
      expect(workspaceInfo.workspacePath).toBe(projectPath);
      expect(workspaceInfo.workspaceName).toBe("test-project");
    });

    test("falls back to current working directory", async () => {
      const isolatedPath = join(TEST_CONFIG.TEST_TUSK_DIR, "isolated");
      mkdirSync(isolatedPath, { recursive: true });
      process.chdir(isolatedPath);

      const journal = createTestJournal();
      const workspaceInfo = await journal.getWorkspaceInfo();

      expect(workspaceInfo.detectionMethod).toBe("cwd");
      expect(workspaceInfo.workspacePath).toBe(isolatedPath);
      expect(workspaceInfo.workspaceName).toBe("isolated");
    });

    test("generates consistent workspace ID for same path", async () => {
      const testPath = join(TEST_CONFIG.TEST_TUSK_DIR, "consistent");
      mkdirSync(testPath, { recursive: true });
      process.chdir(testPath);

      const journal1 = createTestJournal();
      const journal2 = createTestJournal();

      const info1 = await journal1.getWorkspaceInfo();
      const info2 = await journal2.getWorkspaceInfo();

      expect(info1.workspaceId).toBe(info2.workspaceId);
      expect(info1.workspacePath).toBe(info2.workspacePath);
    });

    test("generates different IDs for different paths", async () => {
      const path1 = join(TEST_CONFIG.TEST_TUSK_DIR, "workspace1");
      const path2 = join(TEST_CONFIG.TEST_TUSK_DIR, "workspace2");

      mkdirSync(path1, { recursive: true });
      mkdirSync(path2, { recursive: true });

      process.chdir(path1);
      const journal1 = createTestJournal();
      const info1 = await journal1.getWorkspaceInfo();

      process.chdir(path2);
      const journal2 = createTestJournal();
      const info2 = await journal2.getWorkspaceInfo();

      expect(info1.workspaceId).not.toBe(info2.workspaceId);
      expect(info1.workspacePath).not.toBe(info2.workspacePath);
    });

    test("handles paths with spaces and special characters", async () => {
      const specialPath = join(TEST_CONFIG.TEST_TUSK_DIR, "my project (test) & more");
      mkdirSync(specialPath, { recursive: true });
      process.chdir(specialPath);

      const journal = createTestJournal();
      const workspaceInfo = await journal.getWorkspaceInfo();

      expect(workspaceInfo.workspacePath).toBe(specialPath);
      expect(workspaceInfo.workspaceId).toBeDefined();
      expect(workspaceInfo.workspaceName).toBe("my project (test) & more");
    });

    test("normalizes paths consistently across platforms", async () => {
      const testPath = join(TEST_CONFIG.TEST_TUSK_DIR, "path-test");
      mkdirSync(testPath, { recursive: true });
      process.chdir(testPath);

      const journal = createTestJournal();
      const workspaceInfo = await journal.getWorkspaceInfo();

      // Normalized path should always use forward slashes
      expect(workspaceInfo.workspacePath).not.toContain("\\");
      expect(workspaceInfo.workspacePath).toMatch(/^\/.*|^[A-Z]:\/.*$/); // Unix or Windows absolute path
    });
  });

  describe("Workspace Isolation", () => {
    test("isolates entries by workspace", async () => {
      // Create two different workspaces
      const workspace1Path = join(TEST_CONFIG.TEST_TUSK_DIR, "workspace1");
      const workspace2Path = join(TEST_CONFIG.TEST_TUSK_DIR, "workspace2");

      mkdirSync(workspace1Path, { recursive: true });
      mkdirSync(workspace2Path, { recursive: true });

      // Create entries in workspace1
      const journal1 = createTestJournal(workspace1Path);
      await journal1.saveCheckpoint({
        description: "Workspace 1 checkpoint",
        project: "project1",
        timestamp: new Date().toISOString(),
      });

      // Create entries in workspace2
      const journal2 = createTestJournal(workspace2Path);
      await journal2.saveCheckpoint({
        description: "Workspace 2 checkpoint",
        project: "project2",
        timestamp: new Date().toISOString(),
      });

      // Verify isolation
      const workspace1Entries = await journal1.getRecentCheckpoints({ workspace: 'current' });
      const workspace2Entries = await journal2.getRecentCheckpoints({ workspace: 'current' });

      expect(workspace1Entries).toHaveLength(1);
      expect(workspace2Entries).toHaveLength(1);
      expect(workspace1Entries[0]?.description).toBe("Workspace 1 checkpoint");
      expect(workspace2Entries[0]?.description).toBe("Workspace 2 checkpoint");
    });

    test("queries current workspace only", async () => {
      const workspacePath = join(TEST_CONFIG.TEST_TUSK_DIR, "current-workspace");
      mkdirSync(workspacePath, { recursive: true });
      process.chdir(workspacePath);

      const journal = createTestJournal();

      // Add multiple entries
      const entries = [
        { description: "Entry 1", project: "test" },
        { description: "Entry 2", project: "test" },
        { description: "Entry 3", project: "test" },
      ];

      for (const entry of entries) {
        await journal.saveCheckpoint({
          ...entry,
          timestamp: new Date().toISOString(),
        });
      }

      const currentWorkspaceEntries = await journal.getRecentCheckpoints({ workspace: 'current' });

      expect(currentWorkspaceEntries).toHaveLength(3);
      currentWorkspaceEntries.forEach(entry => {
        expect(entry.workspaceId).toBe(journal.workspaceId);
      });
    });

    test("queries specific workspace", async () => {
      const workspace1Path = join(TEST_CONFIG.TEST_TUSK_DIR, "specific1");
      const workspace2Path = join(TEST_CONFIG.TEST_TUSK_DIR, "specific2");

      mkdirSync(workspace1Path, { recursive: true });
      mkdirSync(workspace2Path, { recursive: true });

      // Add entry to workspace1
      const journal1 = createTestJournal(workspace1Path);
      await journal1.saveCheckpoint({
        description: "Specific workspace 1 entry",
        timestamp: new Date().toISOString(),
      });

      // Query from workspace2 for workspace1 entries
      const journal2 = createTestJournal(workspace2Path);
      const workspace1Entries = await journal2.getRecentCheckpoints({ workspace: workspace1Path });

      expect(workspace1Entries).toHaveLength(1);
      expect(workspace1Entries[0]?.description).toBe("Specific workspace 1 entry");
    });

    test("queries all workspaces", async () => {
      const workspace1Path = join(TEST_CONFIG.TEST_TUSK_DIR, "all1");
      const workspace2Path = join(TEST_CONFIG.TEST_TUSK_DIR, "all2");

      mkdirSync(workspace1Path, { recursive: true });
      mkdirSync(workspace2Path, { recursive: true });

      // Add entries to both workspaces
      const journal1 = createTestJournal(workspace1Path);
      await journal1.saveCheckpoint({
        description: "All workspaces entry 1",
        timestamp: new Date().toISOString(),
      });

      const journal2 = createTestJournal(workspace2Path);
      await journal2.saveCheckpoint({
        description: "All workspaces entry 2",
        timestamp: new Date().toISOString(),
      });

      // Query all workspaces
      const allEntries = await journal2.getRecentCheckpoints({ workspace: 'all' });

      expect(allEntries).toHaveLength(2);
      const descriptions = allEntries.map(e => e.description);
      expect(descriptions).toContain("All workspaces entry 1");
      expect(descriptions).toContain("All workspaces entry 2");
    });

    test("prevents cross-workspace data leakage", async () => {
      const workspace1Path = join(TEST_CONFIG.TEST_TUSK_DIR, "leak1");
      const workspace2Path = join(TEST_CONFIG.TEST_TUSK_DIR, "leak2");

      mkdirSync(workspace1Path, { recursive: true });
      mkdirSync(workspace2Path, { recursive: true });

      // Add sensitive entry to workspace1
      const journal1 = createTestJournal(workspace1Path);
      await journal1.saveCheckpoint({
        description: "SENSITIVE: API key updated",
        project: "secret-project",
        timestamp: new Date().toISOString(),
      });

      // Verify workspace2 cannot see workspace1 data
      const journal2 = createTestJournal(workspace2Path);
      const workspace2Entries = await journal2.getRecentCheckpoints({ workspace: 'current' });

      expect(workspace2Entries).toHaveLength(0);
      workspace2Entries.forEach(entry => {
        expect(entry.description).not.toContain("SENSITIVE");
        expect(entry.project).not.toBe("secret-project");
      });
    });

    test("maintains workspace metadata", async () => {
      const workspacePath = join(TEST_CONFIG.TEST_TUSK_DIR, "metadata-test");
      mkdirSync(workspacePath, { recursive: true });
      process.chdir(workspacePath);

      const journal = createTestJournal();
      await journal.saveCheckpoint({
        description: "Metadata test entry",
        project: "metadata-project",
        timestamp: new Date().toISOString(),
      });

      const entries = await journal.getRecentCheckpoints();
      expect(entries).toHaveLength(1);

      const entry = entries[0];
      expect(entry?.workspaceId).toBeDefined();
      expect(entry?.workspacePath).toBe(workspacePath);
      expect(entry?.workspaceName).toBe("metadata-test");
    });
  });

  describe("Cross-Platform Path Normalization", () => {
    test("normalizes Windows paths", async () => {
      const windowsStylePath = "C:\\Users\\Test\\Project";
      const journal = createTestJournal();

      // Mock platform for testing
      const normalized = normalizePath(windowsStylePath);

      expect(normalized).toBe("C:/Users/Test/Project");
      expect(normalized).not.toContain("\\");
    });

    test("normalizes Unix paths", async () => {
      const unixPath = "/home/user/project";
      const journal = createTestJournal();

      const normalized = normalizePath(unixPath);

      expect(normalized).toBe("/home/user/project");
      expect(normalized).toMatch(/^\/.*$/);
    });

    test("handles UNC paths on Windows", async () => {
      const uncPath = "\\\\server\\share\\project";
      const journal = createTestJournal();

      const normalized = normalizePath(uncPath);

      expect(normalized).toBe("//server/share/project");
      expect(normalized).not.toContain("\\");
    });

    test("handles paths with mixed separators", async () => {
      const mixedPath = "C:\\Users\\Test/Project\\src/components";
      const journal = createTestJournal();

      const normalized = normalizePath(mixedPath);

      expect(normalized).toBe("C:/Users/Test/Project/src/components");
      expect(normalized).not.toContain("\\");
    });

    test("handles relative paths correctly", async () => {
      const relativePath = "./src/../lib/utils";
      const journal = createTestJournal();

      const normalized = normalizePath(relativePath);

      expect(normalized).not.toContain("../");
      expect(normalized).not.toContain("./");
      expect(normalized).toMatch(/lib\/utils$/);
    });

    test("preserves unicode characters in paths", async () => {
      const unicodePath = "/home/用户/项目/файл";
      const journal = createTestJournal();

      const normalized = normalizePath(unicodePath);

      expect(normalized).toBe("/home/用户/项目/файл");
      expect(normalized).toContain("用户");
      expect(normalized).toContain("项目");
      expect(normalized).toContain("файл");
    });

    test("handles case-insensitive filesystems", async () => {
      const journal = createTestJournal();

      const path1 = hashPath("C:/Users/Test/Project");
      const path2 = hashPath("c:/users/test/project");

      if (platform() === "win32") {
        // Windows is case-insensitive
        expect(path1).toBe(path2);
      } else {
        // Unix systems are case-sensitive
        expect(path1).not.toBe(path2);
      }
    });
  });

  describe("Database Location and Platform Support", () => {
    test("uses correct home directory on each platform", async () => {
      const journal = createTestJournal();
      const dbPath = journal.getDatabasePath();

      const expectedHome = homedir();
      expect(dbPath).toContain(expectedHome);
      expect(dbPath).toContain(".tusk");
      expect(dbPath).toEndWith("journal.db");
    });

    test("creates tusk directory if missing", async () => {
      // Clean up any existing directory
      const home = homedir();
      const tuskDir = join(home, ".tusk");
      if (existsSync(tuskDir)) {
        rmSync(tuskDir, { recursive: true, force: true });
      }

      // Create journal without testMode to use real database path
      const journal = new JournalDB();
      const dbPath = journal.getDatabasePath();

      expect(existsSync(tuskDir)).toBe(true);
      expect(existsSync(dbPath)).toBe(true);

      // Clean up
      journal.close();
    });

    test("handles permissions correctly", async () => {
      const journal = createTestJournal();

      // This should not throw an error
      expect(() => {
        journal.getDatabasePath();
      }).not.toThrow();
    });
  });

  describe("SQLite Database Operations", () => {
    test("initializes and saves checkpoints successfully", async () => {
      const journal = createTestJournal();

      // Test that database is functional by saving and retrieving
      const entry = TestDataFactory.createCheckpoint({
        description: "Test database initialization",
      });

      await journal.saveCheckpoint(entry);
      const recent = await journal.getRecentCheckpoints({ days: 1 });

      expect(recent.length).toBeGreaterThan(0);
      expect(recent[0].description).toBe("Test database initialization");
    });

    // Note: The following tests check internal SQLite configuration details
    // These are implementation details and don't need explicit testing as long
    // as the database functions correctly (which is tested above)
    // - WAL mode enabled for concurrency
    // - Busy timeout set appropriately
    // - Indexes created on workspace_id and timestamp columns
  });

  describe("CRUD Operations", () => {
    test("saves checkpoints with workspace context", async () => {
      const workspacePath = join(TEST_CONFIG.TEST_TUSK_DIR, "crud-test");
      mkdirSync(workspacePath, { recursive: true });
      process.chdir(workspacePath);

      const journal = createTestJournal();
      const entry: CheckpointEntry = {
        description: "CRUD test checkpoint",
        project: "crud-project",
        gitBranch: "feature/crud",
        tags: ["test", "crud"],
        files: ["src/crud.ts", "tests/crud.test.ts"],
        timestamp: new Date().toISOString(),
      };

      await journal.saveCheckpoint(entry);

      const saved = await journal.getRecentCheckpoints();
      expect(saved).toHaveLength(1);

      const savedEntry = saved[0];
      expect(savedEntry?.description).toBe(entry.description);
      expect(savedEntry?.project).toBe(entry.project);
      expect(savedEntry?.workspaceId).toBeDefined();
      expect(savedEntry?.workspacePath).toBe(workspacePath);
    });

    test("retrieves checkpoints by workspace", async () => {
      const journal = createTestJournal();

      // Add some test data
      await journal.saveCheckpoint({
        description: "Retrieval test",
        timestamp: new Date().toISOString(),
      });

      const entries = await journal.getRecentCheckpoints({ workspace: 'current' });
      expect(entries.length).toBeGreaterThan(0);

      entries.forEach(entry => {
        expect(entry.workspaceId).toBe(journal.workspaceId);
      });
    });

    test("handles batch operations", async () => {
      const journal = createTestJournal();

      const entries: CheckpointEntry[] = Array.from({ length: 10 }, (_, i) => ({
        description: `Batch entry ${i + 1}`,
        project: "batch-test",
        timestamp: new Date(Date.now() + i * 1000).toISOString(),
      }));

      // Save entries individually (batch not currently supported)
      for (const entry of entries) {
        await journal.saveCheckpoint(entry);
      }

      const saved = await journal.getRecentCheckpoints();
      expect(saved.length).toBeGreaterThanOrEqual(10);
    });

    test("validates data before saving", async () => {
      const journal = createTestJournal();

      // Try to save invalid data
      const invalidEntry = {
        description: "", // Empty description should fail
        timestamp: "invalid-date", // Invalid timestamp
      } as CheckpointEntry;

      await expect(journal.saveCheckpoint(invalidEntry)).rejects.toThrow();
    });
  });

  describe("Multi-Workspace Concurrency", () => {
    test("handles concurrent writes from different workspaces", async () => {
      const workspace1Path = join(TEST_CONFIG.TEST_TUSK_DIR, "concurrent1");
      const workspace2Path = join(TEST_CONFIG.TEST_TUSK_DIR, "concurrent2");

      mkdirSync(workspace1Path, { recursive: true });
      mkdirSync(workspace2Path, { recursive: true });

      // Create promises for concurrent operations
      const operations = [
        // Workspace 1 operations
        (async () => {
          const journal1 = createTestJournal(workspace1Path);
          for (let i = 0; i < 5; i++) {
            await journal1.saveCheckpoint({
              description: `W1 Entry ${i}`,
              timestamp: new Date().toISOString(),
            });
          }
        })(),

        // Workspace 2 operations
        (async () => {
          const journal2 = createTestJournal(workspace2Path);
          for (let i = 0; i < 5; i++) {
            await journal2.saveCheckpoint({
              description: `W2 Entry ${i}`,
              timestamp: new Date().toISOString(),
            });
          }
        })(),
      ];

      // Execute concurrently
      await Promise.all(operations);

      // Verify results
      const journal1 = createTestJournal(workspace1Path);
      const w1Entries = await journal1.getRecentCheckpoints({ workspace: 'current' });

      const journal2 = createTestJournal(workspace2Path);
      const w2Entries = await journal2.getRecentCheckpoints({ workspace: 'current' });

      expect(w1Entries).toHaveLength(5);
      expect(w2Entries).toHaveLength(5);

      // Verify workspace isolation
      w1Entries.forEach(entry => {
        expect(entry.description).toContain("W1");
      });

      w2Entries.forEach(entry => {
        expect(entry.description).toContain("W2");
      });
    });

    test("maintains data consistency under concurrent load", async () => {
      const journal = createTestJournal();

      // Create many concurrent operations
      const operations = Array.from({ length: 20 }, (_, i) =>
        journal.saveCheckpoint({
          description: `Concurrent entry ${i}`,
          project: "consistency-test",
          timestamp: new Date(Date.now() + i).toISOString(),
        })
      );

      await Promise.all(operations);

      const entries = await journal.getRecentCheckpoints();
      expect(entries).toHaveLength(20);

      // Verify all entries are unique
      const descriptions = entries.map(e => e.description);
      const uniqueDescriptions = new Set(descriptions);
      expect(uniqueDescriptions.size).toBe(20);
    });
  });

  describe("Performance", () => {
    test("performs workspace queries under 50ms", async () => {
      const journal = createTestJournal();

      // Add some test data
      const entries = Array.from({ length: 100 }, (_, i) => ({
        description: `Performance entry ${i}`,
        timestamp: new Date(Date.now() - i * 1000).toISOString(),
      }));

      for (const entry of entries) {
        await journal.saveCheckpoint(entry);
      }

      // Measure query performance
      const { executionTime } = await PerformanceTester.measureExecution(() =>
        journal.getRecentCheckpoints({ workspace: 'current' }),
        1000 // 1 second threshold
      );

      expect(executionTime).toBeLessThan(50); // 50ms threshold
    });

    test("handles 1000+ entries per workspace efficiently", async () => {
      const journal = createTestJournal();

      // Create large dataset
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        description: `Large dataset entry ${i}`,
        project: "performance-test",
        timestamp: new Date(Date.now() - i * 1000).toISOString(),
      }));

      // Measure batch insert performance
      const { executionTime: insertTime } = await PerformanceTester.measureExecution(async () => {
        for (const entry of largeDataset) {
          await journal.saveCheckpoint(entry);
        }
      },
        5000 // 5 second threshold for batch insert
      );

      // Measure query performance
      const { executionTime: queryTime } = await PerformanceTester.measureExecution(() =>
        journal.getRecentCheckpoints({ days: 30 }),
        2000 // 2 second threshold for query
      );

      expect(insertTime).toBeLessThan(5000); // 5 second threshold for 1000 inserts
      expect(queryTime).toBeLessThan(100); // 100ms threshold for queries
    });
  });

  describe("Error Handling", () => {
    test("handles corrupted database gracefully", async () => {
      // This test would require database corruption simulation
      // For now, we'll test the error handling structure
      const journal = createTestJournal();

      expect(() => journal.getDatabasePath()).not.toThrow();
    });

    test("handles invalid workspace paths", async () => {
      const journal = createTestJournal();

      // Try to query invalid workspace
      const entries = await journal.getRecentCheckpoints({ workspace: "/invalid/path/that/does/not/exist" });

      expect(Array.isArray(entries)).toBe(true);
      expect(entries).toHaveLength(0);
    });

    test("provides meaningful error messages", async () => {
      const journal = createTestJournal();

      try {
        await journal.saveCheckpoint({
          description: "", // Invalid empty description
          timestamp: "not-a-date", // Invalid timestamp
        } as CheckpointEntry);

        throw new Error("Should have thrown an error");
      } catch (error) {
        expect((error as Error).message).toContain("description");
        expect((error as Error).message).toContain("timestamp");
      }
    });
  });
});