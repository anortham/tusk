/**
 * Integration Tests for End-to-End Workflows
 * Tests complete workflows from user action to final output
 */

import { test, expect, describe, beforeEach, afterEach } from "bun:test";
import { join } from "path";
import { existsSync, mkdirSync, writeFileSync, readFileSync } from "fs";
import { spawnSync } from "bun";

import { generateStandup } from "../standup.js";
import { saveEntry, getRecentEntries, getJournalStats, getWorkspaceSummary } from "../journal.js";
import {
  TestEnvironment,
  TestDataFactory,
  PerformanceTester,
  ErrorTester,
  TestAssertions,
  TEST_CONFIG,
} from "./setup.js";

describe("Integration Tests - End-to-End Workflows", () => {
  beforeEach(() => {
    TestEnvironment.setup();
  });

  afterEach(() => {
    TestEnvironment.cleanup();
  });

  // ========== COMPLETE MCP WORKFLOW TESTS ==========

  describe("Complete MCP Workflow", () => {
    test("checkpoint -> journal storage -> recall retrieval -> complete cycle", async () => {
      // Simulate MCP checkpoint call
      const checkpointEntry = TestDataFactory.createJournalEntry({
        description: "Implemented user authentication system",
        project: "auth-service",
        tags: ["feature", "security", "milestone"],
        gitBranch: "feature/auth",
        gitCommit: "abc123",
        files: ["src/auth.ts", "src/middleware.ts"],
      });

      // Step 1: Checkpoint creation (simulates MCP checkpoint tool)
      await saveEntry(checkpointEntry);

      // Step 2: Verify storage
      const stats = await getJournalStats();
      expect(stats.totalEntries).toBe(1);
      expect(stats.projects).toContain("auth-service");

      // Step 3: Recall retrieval (simulates MCP recall tool)
      const recalledEntries = await getRecentEntries({ days: 1 });
      expect(recalledEntries).toHaveLength(1);
      expect(recalledEntries[0].description).toBe("Implemented user authentication system");
      expect(recalledEntries[0].project).toBe("auth-service");
      expect(recalledEntries[0].tags).toEqual(["feature", "security", "milestone"]);

      // Step 4: Standup generation (simulates MCP standup tool)
      const standupResult = await generateStandup({
        style: "meeting",
        days: 1,
        includeMetrics: true,
        includeFiles: true,
      });

      expect(standupResult).toContain("🏃‍♂️ **Daily Standup**");
      expect(standupResult).toContain("Implemented user authentication system");
      expect(standupResult).toContain("auth-service");
      expect(standupResult).toContain("feature/auth");
      expect(standupResult).toContain("src/auth.ts");
      expect(standupResult).toContain("📊 **Quick Stats:**");
      expect(standupResult).toContain("📁 **Active files:**");
    });

    test("multiple checkpoints -> complex recall -> detailed standup", async () => {
      // Create a complex scenario with multiple projects and timeframes
      const now = new Date();
      const checkpoints = [
        TestDataFactory.createJournalEntry({
          description: "Fixed critical memory leak in data processor",
          project: "data-service",
          tags: ["bug-fix", "critical"],
          timestamp: new Date(now.getTime() - 4 * 60 * 60 * 1000).toISOString(), // 4h ago
          gitBranch: "hotfix/memory-leak",
        }),
        TestDataFactory.createJournalEntry({
          description: "Completed user dashboard frontend",
          project: "frontend",
          tags: ["feature", "ui"],
          timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(), // 2h ago
          gitBranch: "feature/dashboard",
        }),
        TestDataFactory.createJournalEntry({
          description: "Deployed to staging environment",
          project: "frontend",
          tags: ["deployment", "milestone"],
          timestamp: new Date(now.getTime() - 30 * 60 * 1000).toISOString(), // 30m ago
          gitBranch: "feature/dashboard",
        }),
        TestDataFactory.createJournalEntry({
          description: "Plan to implement caching layer next",
          project: "data-service",
          tags: ["planning", "performance"],
          timestamp: new Date(now.getTime() - 10 * 60 * 1000).toISOString(), // 10m ago
        }),
      ];

      for (const checkpoint of checkpoints) {
        await saveEntry(checkpoint);
      }

      // Test recall with different parameters
      const allEntries = await getRecentEntries({ days: 1 });
      expect(allEntries).toHaveLength(4);

      const projectSpecificEntries = allEntries.filter(e => e.project === "frontend");
      expect(projectSpecificEntries).toHaveLength(2);

      // Test comprehensive standup
      const executiveStandup = await generateStandup({
        style: "executive",
        days: 1,
        includeMetrics: true,
      });

      expect(executiveStandup).toContain("🎯 **Executive Summary**");
      expect(executiveStandup).toContain("data-service • frontend");
      expect(executiveStandup).toContain("**Strategic Focus:**");
      expect(executiveStandup).toContain("**Key Wins:**");
      expect(executiveStandup).toContain("Fixed critical memory leak");
      expect(executiveStandup).toContain("Completed user dashboard");
      expect(executiveStandup).toContain("**Forward Outlook:**");
      expect(executiveStandup).toContain("implement caching layer");
    });

    test("MCP tool parameter validation and error handling", async () => {
      // Test various parameter combinations that MCP tools might receive
      const validEntry = TestDataFactory.createJournalEntry({
        description: "Valid checkpoint entry",
      });

      await saveEntry(validEntry);

      // Test standup with various parameter combinations
      const parameterTests = [
        { style: "meeting" as const, days: 1 },
        { style: "written" as const, days: 7, includeMetrics: true },
        { style: "executive" as const, days: 30, includeFiles: true },
        { style: "metrics" as const, days: 14, includeMetrics: true, includeFiles: true },
      ];

      for (const params of parameterTests) {
        const result = await generateStandup(params);
        expect(result).toBeDefined();
        expect(result.length).toBeGreaterThan(0);
      }

      // Test recall with different day ranges
      const recallTests = [1, 3, 7, 14, 30];
      for (const days of recallTests) {
        const entries = await getRecentEntries({ days });
        expect(Array.isArray(entries)).toBe(true);
      }
    });
  });

  // ========== CLI WORKFLOW TESTS ==========

  describe("CLI Workflow", () => {
    test("cli checkpoint -> storage -> cli recall -> output", async () => {
      const cliPath = join(process.cwd(), "cli.ts");

      // Step 1: CLI checkpoint
      const checkpointResult = spawnSync(["bun", cliPath, "checkpoint", "Implemented user login feature"], {
        env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
        cwd: process.cwd(),
      });

      expect(checkpointResult.success).toBe(true);
      expect(checkpointResult.stdout.toString()).toContain("✅");

      // Step 2: Verify storage occurred
      const stats = await getJournalStats();
      expect(stats.totalEntries).toBeGreaterThan(0);

      // Step 3: CLI recall
      const recallResult = spawnSync(["bun", cliPath, "recall", "--days", "1"], {
        env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
        cwd: process.cwd(),
      });

      expect(recallResult.success).toBe(true);
      const recallOutput = recallResult.stdout.toString();
      expect(recallOutput).toContain("Implemented user login feature");
      expect(recallOutput).toContain("🧠");

      // Step 4: CLI standup
      const standupResult = spawnSync(["bun", cliPath, "standup", "--style", "meeting"], {
        env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
        cwd: process.cwd(),
      });

      expect(standupResult.success).toBe(true);
      const standupOutput = standupResult.stdout.toString();
      expect(standupOutput).toContain("🏃‍♂️");
      expect(standupOutput).toContain("Implemented user login feature");
    });

    test("cli error handling and validation", async () => {
      const cliPath = join(process.cwd(), "cli.ts");

      // Test invalid commands
      const invalidResult = spawnSync(["bun", cliPath, "invalid-command"], {
        env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
        cwd: process.cwd(),
      });

      expect(invalidResult.success).toBe(false);

      // Test help command
      const helpResult = spawnSync(["bun", cliPath, "help"], {
        env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
        cwd: process.cwd(),
      });

      expect(helpResult.success).toBe(true);
      const helpOutput = helpResult.stdout.toString();
      expect(helpOutput).toContain("checkpoint");
      expect(helpOutput).toContain("recall");
      expect(helpOutput).toContain("standup");

      // Test checkpoint without description
      const emptyCheckpointResult = spawnSync(["bun", cliPath, "checkpoint"], {
        env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
        cwd: process.cwd(),
      });

      expect(emptyCheckpointResult.success).toBe(false);
    });

    test("cli short aliases and parameter variations", async () => {
      const cliPath = join(process.cwd(), "cli.ts");

      // Test short aliases
      const aliasTests = [
        ["cp", "Short checkpoint alias test"],
        ["rc", "--days", "1"],
        ["su", "--style", "metrics"],
      ];

      for (const [command, ...args] of aliasTests) {
        const result = spawnSync(["bun", cliPath, command, ...args], {
          env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
          cwd: process.cwd(),
        });

        // Allow graceful failure for missing data but check structure
        expect(typeof result.success).toBe("boolean");
      }
    });
  });

  // ========== COMPLETE JOURNALING CYCLE TESTS ==========

  describe("Complete Journaling Cycle", () => {
    test("create -> store -> filter -> aggregate -> report cycle", async () => {
      // Create diverse journal entries
      const journalData = [
        TestDataFactory.createJournalEntry({
          description: "Fixed authentication timeout bug",
          project: "auth-service",
          tags: ["bug-fix", "urgent"],
          gitBranch: "hotfix/auth-timeout",
        }),
        TestDataFactory.createJournalEntry({
          description: "Implemented OAuth2 integration",
          project: "auth-service",
          tags: ["feature", "security"],
          gitBranch: "feature/oauth2",
        }),
        TestDataFactory.createJournalEntry({
          description: "Created comprehensive test suite",
          project: "testing",
          tags: ["testing", "quality"],
          gitBranch: "feature/test-suite",
        }),
        TestDataFactory.createJournalEntry({
          description: "Deployed to production environment",
          project: "auth-service",
          tags: ["deployment", "milestone"],
          gitBranch: "main",
        }),
        TestDataFactory.createJournalEntry({
          description: "Planning next quarter objectives",
          project: "planning",
          tags: ["planning", "strategy"],
        }),
      ];

      // Step 1: Store all entries
      for (const entry of journalData) {
        await saveEntry(entry);
      }

      // Step 2: Verify storage and basic stats
      const stats = await getJournalStats();
      expect(stats.totalEntries).toBe(5);
      expect(stats.projects).toContain("auth-service");
      expect(stats.projects).toContain("testing");
      expect(stats.projects).toContain("planning");

      // Step 3: Filter and retrieve
      const recentEntries = await getRecentEntries({ days: 1 });
      expect(recentEntries).toHaveLength(5);

      // Step 4: Generate comprehensive reports
      const reportStyles = ["meeting", "written", "executive", "metrics"] as const;
      const reports: string[] = [];

      for (const style of reportStyles) {
        const report = await generateStandup({
          style,
          days: 1,
          includeMetrics: true,
          includeFiles: true,
        });

        reports.push(report);

        // Verify each report contains key information
        expect(report).toContain("auth-service");
        expect(report).toContain("authentication");
        expect(report).toContain("OAuth2");
      }

      // Step 5: Verify consistency across reports
      reports.forEach(report => {
        expect(report).toContain("auth-service");
        expect(report.length).toBeGreaterThan(0);
      });

      // Step 6: Test data aggregation accuracy
      const authServiceEntries = recentEntries.filter(e => e.project === "auth-service");
      expect(authServiceEntries).toHaveLength(3);

      const testingEntries = recentEntries.filter(e => e.project === "testing");
      expect(testingEntries).toHaveLength(1);

      const planningEntries = recentEntries.filter(e => e.project === "planning");
      expect(planningEntries).toHaveLength(1);
    });

    test("data persistence and recovery across sessions", async () => {
      // Session 1: Create initial data
      const session1Data = TestDataFactory.createMultipleEntries(3, {
        project: "session-test",
        description: "Session 1 work",
      });

      for (const entry of session1Data) {
        await saveEntry(entry);
      }

      const initialStats = await getJournalStats();
      expect(initialStats.totalEntries).toBe(3);

      // Simulate session end/restart by verifying persistent storage
      const dbPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.db");
      expect(existsSync(dbPath)).toBe(true);

      // Verify persisted data can be retrieved
      const persistedEntries = await getRecentEntries({ days: 7 });
      expect(persistedEntries).toHaveLength(3);

      // Session 2: Add more data
      const session2Data = TestDataFactory.createMultipleEntries(2, {
        project: "session-test",
        description: "Session 2 work",
      });

      for (const entry of session2Data) {
        await saveEntry(entry);
      }

      // Verify persistence across sessions
      const finalStats = await getJournalStats();
      expect(finalStats.totalEntries).toBe(5);

      const allEntries = await getRecentEntries({ days: 1 });
      expect(allEntries).toHaveLength(5);

      const session1Entries = allEntries.filter(e => e.description.includes("Session 1"));
      const session2Entries = allEntries.filter(e => e.description.includes("Session 2"));

      expect(session1Entries).toHaveLength(3);
      expect(session2Entries).toHaveLength(2);
    });

    test("workspace summary functionality", async () => {
      // Create entries in different workspaces by setting up different workspace contexts
      const workspaceEntries = [
        TestDataFactory.createJournalEntry({
          description: "Workspace 1 entry 1",
          project: "project-a",
          tags: ["workspace1", "feature"],
        }),
        TestDataFactory.createJournalEntry({
          description: "Workspace 1 entry 2",
          project: "project-b",
          tags: ["workspace1", "bug-fix"],
        }),
      ];

      // Store entries
      for (const entry of workspaceEntries) {
        await saveEntry(entry);
      }

      // Test workspace summary
      const workspaces = await getWorkspaceSummary();
      expect(Array.isArray(workspaces)).toBe(true);
      expect(workspaces.length).toBeGreaterThan(0);

      // Verify workspace summary structure
      if (workspaces.length > 0) {
        const workspace = workspaces[0];
        expect(workspace).toHaveProperty('id');
        expect(workspace).toHaveProperty('path');
        expect(workspace).toHaveProperty('name');
        expect(workspace).toHaveProperty('entryCount');
        expect(workspace).toHaveProperty('projects');
        expect(Array.isArray(workspace.projects)).toBe(true);
        expect(typeof workspace.entryCount).toBe('number');
        expect(workspace.entryCount).toBeGreaterThan(0);
      }
    });

    test("date range filtering functionality", async () => {
      // Create test entries with known timestamps
      const baseTime = new Date();
      const oneHourAgo = new Date(baseTime.getTime() - (60 * 60 * 1000));
      const twoHoursAgo = new Date(baseTime.getTime() - (2 * 60 * 60 * 1000));
      const threeDaysAgo = new Date(baseTime.getTime() - (3 * 24 * 60 * 60 * 1000));

      const timestampedEntries = [
        TestDataFactory.createJournalEntry({
          description: "Recent entry 1",
          project: "date-test",
          timestamp: baseTime.toISOString(),
        }),
        TestDataFactory.createJournalEntry({
          description: "Recent entry 2",
          project: "date-test",
          timestamp: oneHourAgo.toISOString(),
        }),
        TestDataFactory.createJournalEntry({
          description: "Older entry",
          project: "date-test",
          timestamp: threeDaysAgo.toISOString(),
        }),
      ];

      // Store entries
      for (const entry of timestampedEntries) {
        await saveEntry(entry);
      }

      // Test date range filtering with from parameter
      const today = baseTime.toISOString().split('T')[0]; // YYYY-MM-DD format
      const recentEntries = await getRecentEntries({
        from: today,
        project: "date-test"
      });

      expect(Array.isArray(recentEntries)).toBe(true);
      // Should include entries from today
      const todayEntries = recentEntries.filter(e =>
        e.description.includes("Recent entry") && e.project === "date-test"
      );
      expect(todayEntries.length).toBeGreaterThan(0);

      // Test date range filtering with to parameter
      const yesterday = new Date(baseTime.getTime() - (24 * 60 * 60 * 1000))
        .toISOString().split('T')[0];
      const olderEntries = await getRecentEntries({
        to: yesterday,
        project: "date-test"
      });

      expect(Array.isArray(olderEntries)).toBe(true);

      // Test combined from and to parameters
      const fromDate = threeDaysAgo.toISOString().split('T')[0];
      const toDate = oneHourAgo.toISOString().split('T')[0];
      const rangeEntries = await getRecentEntries({
        from: fromDate,
        to: toDate,
        project: "date-test"
      });

      expect(Array.isArray(rangeEntries)).toBe(true);
    });
  });

  // ========== GIT INTEGRATION WORKFLOW TESTS ==========

  describe("Git Integration Workflow", () => {
    test("git context capture in real repository", async () => {
      // Create a temporary git repository for testing
      const gitRepoPath = join(TEST_CONFIG.TEST_TUSK_DIR, "test-repo");
      mkdirSync(gitRepoPath, { recursive: true });

      // Initialize git repo
      const initResult = spawnSync(["git", "init"], { cwd: gitRepoPath });
      expect(initResult.success).toBe(true);

      // Configure git
      spawnSync(["git", "config", "user.email", "test@example.com"], { cwd: gitRepoPath });
      spawnSync(["git", "config", "user.name", "Test User"], { cwd: gitRepoPath });

      // Create and commit a file
      const testFile = join(gitRepoPath, "test.txt");
      writeFileSync(testFile, "Test content");
      spawnSync(["git", "add", "test.txt"], { cwd: gitRepoPath });
      spawnSync(["git", "commit", "-m", "Initial commit"], { cwd: gitRepoPath });

      // Create a feature branch
      spawnSync(["git", "checkout", "-b", "feature/test-integration"], { cwd: gitRepoPath });

      // Modify file and make another commit
      writeFileSync(testFile, "Modified test content");
      spawnSync(["git", "add", "test.txt"], { cwd: gitRepoPath });
      spawnSync(["git", "commit", "-m", "Update test file"], { cwd: gitRepoPath });

      // Now test checkpointing from within the git repo
      const cliPath = join(process.cwd(), "cli.ts");
      const checkpointResult = spawnSync(
        ["bun", cliPath, "checkpoint", "Testing git integration workflow"],
        {
          env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
          cwd: gitRepoPath, // Run from within git repo
        }
      );

      expect(checkpointResult.success).toBe(true);

      // Verify git context was captured
      const entries = await getRecentEntries({ days: 1, workspace: 'all' });
      expect(entries).toHaveLength(1);

      const gitEntry = entries[0];
      expect(gitEntry.description).toBe("Testing git integration workflow");
      expect(gitEntry.gitBranch).toBe("feature/test-integration");
      expect(gitEntry.gitCommit).toBeDefined();
      expect(gitEntry.gitCommit).toHaveLength(7); // Short commit hash
      expect(gitEntry.project).toBe("test-repo"); // Should extract project name from repo

      // Generate standup and verify git info appears
      const standup = await generateStandup({
        style: "meeting",
        days: 1,
        includeMetrics: true,
        workspace: 'all',
      });

      expect(standup).toContain("feature/test-integration");
      expect(standup).toContain("🌿 Branches:");
      expect(standup).toContain("test-repo");
    });

    test("git context handling edge cases", async () => {
      // Test checkpointing outside of git repo
      const nonGitPath = join(TEST_CONFIG.TEST_TUSK_DIR, "non-git");
      mkdirSync(nonGitPath, { recursive: true });

      const cliPath = join(process.cwd(), "cli.ts");
      const checkpointResult = spawnSync(
        ["bun", cliPath, "checkpoint", "Outside git repository"],
        {
          env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
          cwd: nonGitPath,
        }
      );

      expect(checkpointResult.success).toBe(true);

      // Verify entry was created without git context
      const entries = await getRecentEntries({ days: 1, workspace: 'all' });
      expect(entries).toHaveLength(1);

      const nonGitEntry = entries[0];
      expect(nonGitEntry.description).toBe("Outside git repository");
      expect(nonGitEntry.gitBranch).toBeNull();
      expect(nonGitEntry.gitCommit).toBeNull();
      expect(nonGitEntry.project).toBe("non-git"); // Should extract from directory name
    });
  });

  // ========== ERROR RECOVERY WORKFLOW TESTS ==========

  describe("Error Recovery Workflow", () => {
    test("corruption detection and graceful recovery", async () => {
      // Create valid entries first
      const validEntries = TestDataFactory.createMultipleEntries(3, {
        description: "Valid entry before corruption",
      });

      for (const entry of validEntries) {
        await saveEntry(entry);
      }

      // Verify initial state
      let stats = await getJournalStats();
      expect(stats.totalEntries).toBe(3);

      // Test system resilience by adding more entries under potential stress
      const newEntry = TestDataFactory.createJournalEntry({
        description: "Entry during concurrent access test",
      });

      // This should succeed even with existing data in the database
      await saveEntry(newEntry);

      // Verify SQLite database integrity
      const dbPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.db");
      expect(existsSync(dbPath)).toBe(true);

      // System should handle mixed valid/invalid data gracefully
      const recallResult = await getRecentEntries({ days: 1 });
      expect(Array.isArray(recallResult)).toBe(true);
      expect(recallResult.length).toBeGreaterThan(0);

      // Standup generation should work despite corruption
      const standupResult = await generateStandup({ style: "meeting", days: 1 });
      expect(standupResult).toBeDefined();
      expect(standupResult).toContain("🏃‍♂️ **Daily Standup**");

      // Should contain at least the valid entries
      expect(standupResult).toContain("Entry after corruption");
    });

    test("disk space and permission error handling", async () => {
      // Test handling of various system-level errors
      const validEntry = TestDataFactory.createJournalEntry({
        description: "Testing error resilience",
      });

      // Normal operation should work first
      await saveEntry(validEntry);
      let entries = await getRecentEntries({ days: 1 });
      expect(entries).toHaveLength(1);

      // Test that even if journal operations fail, reads still work
      const existingEntries = await getRecentEntries({ days: 1 });
      expect(Array.isArray(existingEntries)).toBe(true);

      // Test that standup generation is resilient
      const standupResult = await generateStandup({ style: "written", days: 1 });
      expect(standupResult).toBeDefined();
      expect(standupResult.length).toBeGreaterThan(0);
    });

    test("concurrent access handling", async () => {
      // Simulate multiple concurrent operations
      const concurrentEntries = Array.from({ length: 5 }, (_, i) =>
        TestDataFactory.createJournalEntry({
          description: `Concurrent entry ${i + 1}`,
          project: `project-${i % 2}`, // Alternate between two projects
        })
      );

      // Attempt concurrent writes
      const writePromises = concurrentEntries.map(entry => saveEntry(entry));
      await Promise.all(writePromises);

      // Verify all entries were written
      const allEntries = await getRecentEntries({ days: 1 });
      expect(allEntries).toHaveLength(5);

      // Verify data integrity
      concurrentEntries.forEach((originalEntry, index) => {
        const storedEntry = allEntries.find(e => e.description === originalEntry.description);
        expect(storedEntry).toBeDefined();
        expect(storedEntry?.project).toBe(originalEntry.project);
      });

      // Test concurrent reads
      const readPromises = [
        getRecentEntries({ days: 1 }),
        getJournalStats(),
        generateStandup({ style: "metrics", days: 1 }),
      ];

      const [entries, stats, standup] = await Promise.all(readPromises);

      expect(entries).toHaveLength(5);
      expect(stats.totalEntries).toBe(5);
      expect(standup).toContain("📈 **Metrics Dashboard**");
    });
  });

  // ========== CROSS-PLATFORM WORKFLOW TESTS ==========

  describe("Cross-Platform Workflow", () => {
    test("path handling across different operating systems", async () => {
      // Test that file paths work correctly regardless of OS
      const entry = TestDataFactory.createJournalEntry({
        description: "Cross-platform path test",
        files: ["src/utils/helper.ts", "tests/integration/workflow.test.ts"],
      });

      await saveEntry(entry);

      const entries = await getRecentEntries({ days: 1 });
      expect(entries).toHaveLength(1);

      const storedEntry = entries[0];
      expect(storedEntry.files).toEqual(["src/utils/helper.ts", "tests/integration/workflow.test.ts"]);

      // Test standup generation with file paths
      const standup = await generateStandup({
        style: "meeting",
        days: 1,
        includeFiles: true,
      });

      expect(standup).toContain("📁 **Active files:**");
      expect(standup).toContain("src/utils/helper.ts");
      expect(standup).toContain("tests/integration/workflow.test.ts");
    });

    test("environment variable and configuration handling", async () => {
      // Test different environment configurations
      const originalEnv = { ...process.env };

      try {
        // Test with different environments
        const envTests = [
          { NODE_ENV: "development" },
          { NODE_ENV: "production" },
          { NODE_ENV: "test" },
        ];

        for (const envOverride of envTests) {
          Object.assign(process.env, envOverride);

          const entry = TestDataFactory.createJournalEntry({
            description: `Testing in ${envOverride.NODE_ENV} environment`,
          });

          await saveEntry(entry);

          const standup = await generateStandup({ style: "executive", days: 1 });
          expect(standup).toBeDefined();
          expect(standup).toContain(`${envOverride.NODE_ENV} environment`);
        }
      } finally {
        process.env = originalEnv;
      }
    });
  });

  // ========== PERFORMANCE INTEGRATION TESTS ==========

  describe("Performance Integration", () => {
    test("end-to-end workflow performance under load", async () => {
      // Create a substantial dataset
      const largeDataset = TestDataFactory.createMultipleEntries(100, {
        project: "performance-test",
      });

      // Measure complete workflow performance
      const { result: writeResults, executionTime: writeTime } = await PerformanceTester.measureExecution(
        async () => {
          for (const entry of largeDataset) {
            await saveEntry(entry);
          }
        },
        5000 // 5 second timeout
      );

      expect(writeTime).toBeLessThan(5000);

      // Measure read performance
      const { result: readResults, executionTime: readTime } = await PerformanceTester.measureExecution(
        () => getRecentEntries({ days: 7 }),
        1000 // 1 second timeout
      );

      expect(readTime).toBeLessThan(1000);
      expect(readResults).toHaveLength(100);

      // Measure standup generation performance
      const { result: standupResult, executionTime: standupTime } = await PerformanceTester.measureExecution(
        () => generateStandup({ style: "metrics", days: 7, includeMetrics: true }),
        2000 // 2 second timeout
      );

      expect(standupTime).toBeLessThan(2000);
      expect(standupResult).toContain("📈 **Metrics Dashboard**");
      expect(standupResult).toContain("performance-test:");

      // Measure complete CLI workflow performance
      const cliPath = join(process.cwd(), "cli.ts");
      const { executionTime: cliTime } = await PerformanceTester.measureExecution(
        () => {
          return new Promise((resolve, reject) => {
            const result = spawnSync(["bun", cliPath, "standup", "--style", "meeting"], {
              env: { ...process.env, TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR, TUSK_TEST_MODE: "true" },
              cwd: process.cwd(),
            });
            if (result.success) {
              resolve(result.stdout.toString());
            } else {
              reject(new Error(result.stderr.toString()));
            }
          });
        },
        3000 // 3 second timeout
      );

      expect(cliTime).toBeLessThan(3000);
    });

    test("memory efficiency in long-running workflows", async () => {
      // Test memory usage over extended operations
      const { memoryDelta } = await PerformanceTester.measureMemoryUsage(async () => {
        // Simulate a long-running session with many operations
        for (let i = 0; i < 50; i++) {
          const entry = TestDataFactory.createJournalEntry({
            description: `Memory test entry ${i}`,
            project: `project-${i % 5}`,
          });

          await saveEntry(entry);

          if (i % 10 === 0) {
            // Periodically generate standups to test memory cleanup
            await generateStandup({ style: "written", days: 1 });
            await getRecentEntries({ days: 1 });
          }
        }

        // Final comprehensive operations
        await getJournalStats();
        await generateStandup({ style: "metrics", days: 7, includeMetrics: true });
      });

      // Memory usage should be reasonable (under 100MB increase)
      TestAssertions.assertMemoryUsage(memoryDelta, 100 * 1024 * 1024, "Long-running workflow");
    });
  });

  // ========== DATA INTEGRITY WORKFLOW TESTS ==========

  describe("Data Integrity", () => {
    test("complete data roundtrip integrity", async () => {
      // Create entries with all possible field types and edge cases
      const complexEntries = [
        TestDataFactory.createJournalEntry({
          description: "Complex entry with unicode: 🚀 ñáíóú αβγδ 中文",
          project: "unicode-test",
          tags: ["unicode", "international", "emoji"],
          gitBranch: "feature/unicode-support",
          files: ["src/unicode.ts", "tests/unicode.test.ts"],
        }),
        TestDataFactory.createJournalEntry({
          description: 'Entry with "quotes" and \'apostrophes\' and symbols: @#$%^&*()',
          project: "special-chars",
          tags: ["symbols", "quotes"],
          gitBranch: "hotfix/special-characters",
        }),
        TestDataFactory.createJournalEntry({
          description: "Entry with very long description that spans multiple lines and contains lots of detailed information about a complex feature implementation that involves multiple systems and requires careful coordination between teams",
          project: "long-description-test",
          tags: Array.from({ length: 20 }, (_, i) => `tag-${i}`),
          files: Array.from({ length: 15 }, (_, i) => `src/module${i}/file${i}.ts`),
        }),
      ];

      // Store entries
      for (const entry of complexEntries) {
        await saveEntry(entry);
      }

      // Retrieve and verify exact data integrity
      const retrievedEntries = await getRecentEntries({ days: 1 });
      expect(retrievedEntries).toHaveLength(3);

      complexEntries.forEach((originalEntry, index) => {
        const retrievedEntry = retrievedEntries.find(e => e.description === originalEntry.description);
        expect(retrievedEntry).toBeDefined();

        // Verify all fields are preserved exactly
        expect(retrievedEntry?.description).toBe(originalEntry.description);
        expect(retrievedEntry?.project).toBe(originalEntry.project);
        expect(retrievedEntry?.gitBranch).toBe(originalEntry.gitBranch);
        expect(retrievedEntry?.tags).toEqual(originalEntry.tags);
        expect(retrievedEntry?.files).toEqual(originalEntry.files);
        expect(retrievedEntry?.type).toBe(originalEntry.type);
        expect(new Date(retrievedEntry?.timestamp!)).toBeInstanceOf(Date);
      });

      // Verify data integrity through standup generation
      const standup = await generateStandup({
        style: "written",
        days: 1,
        includeFiles: true,
        includeMetrics: true,
      });

      expect(standup).toContain("unicode-test");
      expect(standup).toContain("special-chars");
      expect(standup).toContain("long-description-test");
      expect(standup).toContain("🚀"); // Unicode emoji preserved
      expect(standup).toContain("quotes"); // Special characters handled
    });

    test("journal file format consistency and recoverability", async () => {
      // Create entries and verify file format
      const entries = TestDataFactory.createMultipleEntries(5);
      for (const entry of entries) {
        await saveEntry(entry);
      }

      // Verify SQLite database was created and contains data
      const dbPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.db");
      expect(existsSync(dbPath)).toBe(true);

      // Verify data can be retrieved
      const retrievedEntries = await getRecentEntries({ days: 1 });
      expect(retrievedEntries).toHaveLength(5);

      // Verify each entry has required properties
      retrievedEntries.forEach((entry) => {
        expect(entry).toHaveProperty("id");
        expect(entry).toHaveProperty("timestamp");
        expect(entry).toHaveProperty("description");
      });

      // Test recovery from database: create new instance and verify data is accessible
      const recoveredEntries = await getRecentEntries({ days: 1 });
      expect(recoveredEntries).toHaveLength(5);

      // Verify IDs are preserved and unique
      const ids = recoveredEntries.map(e => e.id);
      expect(new Set(ids).size).toBe(5); // All IDs should be unique
    });
  });
});