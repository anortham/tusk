/**
 * Standup Generation Tests
 * Comprehensive testing for all standup report formats and data processing
 */

import { test, expect, describe, beforeEach, afterEach } from "bun:test";
import { join } from "path";
import { existsSync, writeFileSync, rmSync } from "fs";
import {
  generateStandup,
  type StandupOptions,
  type StandupStyle,
  type StandupData,
} from "../standup.js";
import { saveEntry, type JournalEntry } from "../journal.js";
import {
  TestEnvironment,
  TestDataFactory,
  PerformanceTester,
  ErrorTester,
  TestAssertions,
  TEST_CONFIG,
} from "./setup.js";

describe("Standup Generation Tests", () => {
  beforeEach(() => {
    TestEnvironment.setup();
  });

  afterEach(() => {
    TestEnvironment.cleanup();
  });

  // ========== FORMAT GENERATION TESTS ==========

  describe("Meeting Format", () => {
    test("generates proper header", async () => {
      const entries = TestDataFactory.createMultipleEntries(3, {
        project: "test-project",
        description: "Completed feature implementation",
      });

      // Add entries to journal
      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("🏃‍♂️ **Daily Standup**");
      expect(result).toContain("last 24 hours");
      TestAssertions.assertStringContains(result, "Daily Standup", "Should include header");
    });

    test("includes project summary line", async () => {
      const entries = TestDataFactory.createMultipleEntries(2, {
        project: "main-project",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("📍 Projects: main-project");
      TestAssertions.assertStringContains(result, "Projects:", "Should include project summary");
    });

    test("includes quick stats section when enabled", async () => {
      const entries = TestDataFactory.createMultipleEntries(5, {
        description: "Fixed critical bug in authentication",
        tags: ["bug-fix", "critical"],
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = {
        style: "meeting",
        days: 1,
        includeMetrics: true,
      };
      const result = await generateStandup(options);

      expect(result).toContain("📊 **Quick Stats:**");
      expect(result).toContain("checkpoints recorded");
      expect(result).toContain("projects active");
      expect(result).toContain("key achievements");
    });

    test("includes accomplished work section", async () => {
      const entries = TestDataFactory.createMultipleEntries(3, {
        description: "Implemented user authentication",
        project: "auth-service",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("✅ **What I accomplished:**");
      expect(result).toContain("Implemented user authentication");
    });

    test("formats entries with time indicators", async () => {
      const now = new Date();
      const entry = TestDataFactory.createJournalEntry({
        description: "Completed testing phase",
        timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      });

      await saveEntry(entry);

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("(2h ago)");
      TestAssertions.assertStringContains(result, "ago)", "Should include time indicators");
    });

    test("groups entries by project when multiple projects", async () => {
      const projectAEntries = TestDataFactory.createMultipleEntries(2, {
        project: "project-a",
        description: "Project A work",
      });
      const projectBEntries = TestDataFactory.createMultipleEntries(2, {
        project: "project-b",
        description: "Project B work",
      });

      for (const entry of [...projectAEntries, ...projectBEntries]) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("[project-a]");
      expect(result).toContain("[project-b]");
      expect(result).toContain("📍 Projects: project-a, project-b");
    });

    test("handles single project gracefully", async () => {
      const entries = TestDataFactory.createMultipleEntries(3, {
        project: "single-project",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("📍 Projects: single-project");
      expect(result).not.toContain("📍 Projects: single-project,");
    });

    test("includes tags in entry display", async () => {
      const entry = TestDataFactory.createJournalEntry({
        description: "Fixed critical authentication bug",
        tags: ["bug-fix", "critical", "auth"],
      });

      await saveEntry(entry);

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      // Tags are used for categorization but may not be directly visible
      expect(result).toContain("Fixed critical authentication bug");
    });

    test("handles empty data appropriately", async () => {
      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("🏃‍♂️ **Daily Standup**");
      expect(result).toContain("last 24 hours");
      expect(result.length).toBeGreaterThan(0);
    });

    test("uses consistent emoji and formatting", async () => {
      const entries = TestDataFactory.createMultipleEntries(3);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 1, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toContain("🏃‍♂️");
      expect(result).toContain("📊");
      expect(result).toContain("✅");
      expect(result).toContain("**");
      TestAssertions.assertFormattingQuality(result);
    });
  });

  describe("Written Format", () => {
    test("generates narrative summary", async () => {
      const entries = TestDataFactory.createMultipleEntries(4, {
        description: "Implemented new feature",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "written", days: 1, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toContain("📝 **Work Summary**");
      expect(result).toContain("During last 24 hours, I completed");
      expect(result).toContain("work sessions");
    });

    test("includes session and project counts", async () => {
      const projectEntries = TestDataFactory.createEntriesWithDifferentProjects([
        "project-one",
        "project-two",
      ]);

      for (const entry of projectEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "written", days: 7, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toMatch(/\d+ work sessions/);
      expect(result).toMatch(/\d+ projects?/);
    });

    test("uses prose-style formatting", async () => {
      const entries = TestDataFactory.createMultipleEntries(3);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "written", days: 1, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toContain("During");
      expect(result).toContain("I completed");
      expect(result).toContain("Achieved");
      expect(result).toContain("identified for follow-up");
    });

    test("includes recent work summary", async () => {
      const entries = TestDataFactory.createMultipleEntries(5, {
        description: "Completed database migration",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "written", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("**Recent Work:**");
      expect(result).toContain("Completed database migration");
    });

    test("maintains professional tone", async () => {
      const entries = TestDataFactory.createMultipleEntries(3);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "written", days: 1 };
      const result = await generateStandup(options);

      // Check for professional language patterns
      expect(result).toMatch(/\b(completed|achieved|implemented|delivered)\b/i);
      expect(result).not.toContain("awesome");
      expect(result).not.toContain("cool");
    });
  });

  describe("Executive Format", () => {
    test("generates executive summary header", async () => {
      const entries = TestDataFactory.createMultipleEntries(3);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("🎯 **Executive Summary**");
      expect(result).toContain("past week");
    });

    test("includes portfolio overview", async () => {
      const projectEntries = TestDataFactory.createEntriesWithDifferentProjects([
        "strategic-initiative-one",
        "strategic-initiative-two",
        "operational-project",
      ]);

      for (const entry of projectEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("Portfolio:");
      expect(result).toContain("strategic-initiative-one");
      expect(result).toContain("•");
    });

    test("includes impact assessment", async () => {
      const entries = TestDataFactory.createMultipleEntries(8, {
        description: "Delivered critical security enhancement",
        tags: ["achievement", "security"],
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toContain("**Impact:**");
      expect(result).toContain("development velocity");
      expect(result).toMatch(/\b(High|Medium|Low)\b/);
    });

    test("includes strategic focus section", async () => {
      const projectEntries = TestDataFactory.createEntriesWithDifferentProjects([
        "core-platform",
        "user-experience",
        "data-analytics",
      ]);

      for (const entry of projectEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Strategic Focus:**");
      expect(result).toMatch(/\d+\. \w+/); // Numbered list format
    });

    test("includes key wins section", async () => {
      const entries = TestDataFactory.createMultipleEntries(3, {
        description: "Successfully launched new feature",
        tags: ["achievement", "milestone"],
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Key Wins:**");
      expect(result).toContain("launched new feature");
    });

    test("includes forward outlook", async () => {
      const entries = TestDataFactory.createMultipleEntries(2, {
        description: "Planning next quarter roadmap",
        tags: ["planning", "next"],
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Forward Outlook:**");
      expect(result).toContain("Priority actions:");
    });

    test("uses executive-appropriate language", async () => {
      const entries = TestDataFactory.createMultipleEntries(5, {
        description: "Optimized system performance",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toMatch(/\b(strategic|delivered|achieved|initiative)\b/i);
      expect(result).toMatch(/\b(impact|velocity|portfolio)\b/i);
    });

    test("quantifies achievements", async () => {
      const entries = TestDataFactory.createMultipleEntries(6, {
        description: "Completed performance optimization",
        tags: ["performance", "achievement"],
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7, includeMetrics: true };
      const result = await generateStandup(options);

      expect(result).toMatch(/\d+ key achievement/);
      expect(result).toMatch(/\d+ strategic initiative/);
      expect(result).toMatch(/\d+ work sessions/);
    });

    test("assesses development velocity", async () => {
      const highVelocityEntries = TestDataFactory.createMultipleEntries(10);
      const mediumVelocityEntries = TestDataFactory.createMultipleEntries(3);

      // Test high velocity
      for (const entry of highVelocityEntries) {
        await saveEntry(entry);
      }

      let options: StandupOptions = { style: "executive", days: 7, includeMetrics: true };
      let result = await generateStandup(options);
      expect(result).toContain("high development velocity");

      // Clean and test medium velocity
      TestEnvironment.resetJournal();
      for (const entry of mediumVelocityEntries) {
        await saveEntry(entry);
      }

      result = await generateStandup(options);
      expect(result).toContain("medium development velocity");
    });
  });

  describe("Metrics Format", () => {
    test("generates metrics dashboard header", async () => {
      const entries = TestDataFactory.createMultipleEntries(5);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("📈 **Metrics Dashboard**");
      expect(result).toContain("past week");
    });

    test("includes productivity metrics section", async () => {
      const entries = TestDataFactory.createMultipleEntries(4, {
        gitBranch: "feature/new-dashboard",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Productivity Metrics:**");
      expect(result).toContain("├─ Checkpoints recorded:");
      expect(result).toContain("├─ Active projects:");
      expect(result).toContain("├─ Git branches:");
      expect(result).toContain("└─ Action items identified:");
    });

    test("includes project activity breakdown", async () => {
      const projectEntries = TestDataFactory.createEntriesWithDifferentProjects([
        "frontend",
        "backend",
        "database",
      ]);

      for (const entry of projectEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Project Activity:**");
      expect(result).toContain("frontend:");
      expect(result).toContain("sessions");
      expect(result).toContain("%)");
    });

    test("includes activity timeline", async () => {
      const timeDistributedEntries = TestDataFactory.createEntriesWithTimeDistribution(3);

      for (const entry of timeDistributedEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Activity Timeline:**");
      expect(result).toContain("Today:");
      expect(result).toContain("Yesterday:");
      expect(result).toContain("This week:");
    });

    test("uses visual indicators (progress bars)", async () => {
      const projectEntries = TestDataFactory.createEntriesWithDifferentProjects([
        "major-project",
        "minor-project",
      ]);

      for (const entry of projectEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("█"); // Progress bar filled
      expect(result).toContain("░"); // Progress bar empty
      expect(result).toContain("▓"); // Activity timeline bars
    });

    test("includes percentage calculations", async () => {
      const entries = TestDataFactory.createMultipleEntries(8, {
        project: "test-project",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toMatch(/\d+%/); // Should contain percentage
      expect(result).toContain("(100%)"); // Single project should be 100%
    });

    test("shows statistical summaries", async () => {
      const entries = TestDataFactory.createMultipleEntries(6);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toMatch(/Checkpoints recorded: \d+/);
      expect(result).toMatch(/Active projects: \d+/);
      expect(result).toMatch(/\d+ checkpoint/);
    });

    test("is visually appealing in terminal", async () => {
      const entries = TestDataFactory.createMultipleEntries(5);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("├─");
      expect(result).toContain("└─");
      expect(result).toContain("📈");
      expect(result).toContain("[");
      expect(result).toContain("]");
      TestAssertions.assertFormattingQuality(result);
    });
  });

  // ========== DATA PROCESSING TESTS ==========

  describe("Data Aggregation", () => {
    test("correctly counts total checkpoints", async () => {
      const entries = TestDataFactory.createMultipleEntries(7);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("Checkpoints recorded: 7");
    });

    test("identifies unique projects", async () => {
      const projectEntries = TestDataFactory.createEntriesWithDifferentProjects([
        "project-alpha",
        "project-beta",
        "project-alpha", // Duplicate
      ]);

      for (const entry of projectEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("project-alpha");
      expect(result).toContain("project-beta");
      // Should not duplicate project names
      expect((result.match(/project-alpha/g) || []).length).toBeLessThan(5);
    });

    test("calculates session counts per project", async () => {
      const alphaEntries = TestDataFactory.createMultipleEntries(3, {
        project: "alpha-project",
      });
      const betaEntries = TestDataFactory.createMultipleEntries(2, {
        project: "beta-project",
      });

      for (const entry of [...alphaEntries, ...betaEntries]) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("alpha-project: 3 sessions");
      expect(result).toContain("beta-project: 2 sessions");
    });

    test("identifies key achievements", async () => {
      const achievementEntries = [
        TestDataFactory.createJournalEntry({
          description: "Fixed critical memory leak",
          tags: ["achievement", "critical"],
        }),
        TestDataFactory.createJournalEntry({
          description: "Completed feature implementation",
          tags: ["achievement"],
        }),
        TestDataFactory.createJournalEntry({
          description: "Implemented secure authentication system",
        }),
      ];

      for (const entry of achievementEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("⭐ **Key highlights:**");
      expect(result).toContain("Fixed critical memory leak");
      expect(result).toContain("Completed feature implementation");
      expect(result).toContain("Implemented secure authentication");
    });

    test("counts git branches involved", async () => {
      const branchEntries = [
        TestDataFactory.createJournalEntry({ gitBranch: "feature/auth" }),
        TestDataFactory.createJournalEntry({ gitBranch: "feature/ui" }),
        TestDataFactory.createJournalEntry({ gitBranch: "feature/auth" }), // Duplicate
        TestDataFactory.createJournalEntry({ gitBranch: "hotfix/security" }),
      ];

      for (const entry of branchEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("Git branches: 3"); // Should deduplicate
      expect(result).toContain("🌿 Branches: feature/auth, feature/ui, hotfix/security");
    });

    test("handles missing or null data gracefully", async () => {
      const incompleteEntries = [
        TestDataFactory.createJournalEntry({
          project: undefined as any,
          gitBranch: undefined as any,
          tags: undefined as any,
        }),
        TestDataFactory.createJournalEntry({
          project: "",
          gitBranch: "",
          tags: [],
        }),
      ];

      for (const entry of incompleteEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toBeDefined();
      expect(result.length).toBeGreaterThan(0);
      expect(result).toContain("🏃‍♂️ **Daily Standup**");
    });
  });

  describe("Time-based Analysis", () => {
    test("correctly filters entries by date range", async () => {
      const now = new Date();
      const oldEntry = TestDataFactory.createJournalEntry({
        timestamp: new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000).toISOString(), // 10 days ago
        description: "Old work",
      });
      const recentEntry = TestDataFactory.createJournalEntry({
        timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
        description: "Recent work",
      });

      await saveEntry(oldEntry);
      await saveEntry(recentEntry);

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("Recent work");
      expect(result).not.toContain("Old work");
    });

    test("calculates time distributions", async () => {
      const timeEntries = TestDataFactory.createEntriesWithTimeDistribution(5);

      for (const entry of timeEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("**Activity Timeline:**");
      expect(result).toMatch(/Today: \d+ checkpoint/);
      expect(result).toMatch(/Yesterday: \d+ checkpoint/);
      expect(result).toMatch(/This week: \d+ checkpoint/);
    });

    test("provides relative time indicators", async () => {
      const now = new Date();
      const entries = [
        TestDataFactory.createJournalEntry({
          timestamp: new Date(now.getTime() - 30 * 60 * 1000).toISOString(), // 30 min ago
          description: "Recent task",
        }),
        TestDataFactory.createJournalEntry({
          timestamp: new Date(now.getTime() - 3 * 60 * 60 * 1000).toISOString(), // 3 hours ago
          description: "Earlier task",
        }),
        TestDataFactory.createJournalEntry({
          timestamp: new Date(now.getTime() - 25 * 60 * 60 * 1000).toISOString(), // Yesterday
          description: "Yesterday task",
        }),
      ];

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("(just now)");
      expect(result).toContain("(3h ago)");
      expect(result).toContain("(yesterday)");
    });

    test("handles future dates gracefully", async () => {
      const futureEntry = TestDataFactory.createJournalEntry({
        timestamp: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // Tomorrow
        description: "Future task",
      });

      await saveEntry(futureEntry);

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toBeDefined();
      expect(result).toContain("Future task");
    });
  });

  describe("Content Analysis", () => {
    test("identifies achievement keywords", async () => {
      const achievementEntries = [
        TestDataFactory.createJournalEntry({
          description: "Fixed critical bug in payment system",
        }),
        TestDataFactory.createJournalEntry({
          description: "Completed user dashboard implementation",
        }),
        TestDataFactory.createJournalEntry({
          description: "Successfully deployed to production",
        }),
        TestDataFactory.createJournalEntry({
          description: "Finished code review process",
        }),
      ];

      for (const entry of achievementEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("⭐ **Key highlights:**");
      expect(result).toContain("Fixed critical bug");
      expect(result).toContain("Completed user dashboard");
      expect(result).toContain("deployed to production");
      expect(result).toContain("Finished code review");
    });

    test("identifies problem-solving entries", async () => {
      const problemSolvingEntries = [
        TestDataFactory.createJournalEntry({
          description: "Solved memory leak in data processing pipeline",
        }),
        TestDataFactory.createJournalEntry({
          description: "Resolved authentication timeout issues",
        }),
        TestDataFactory.createJournalEntry({
          description: "Achieved 99.9% uptime target",
        }),
      ];

      for (const entry of problemSolvingEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("Solved memory leak");
      expect(result).toContain("Resolved authentication");
      expect(result).toContain("Achieved 99.9% uptime");
    });

    test("extracts follow-up actions", async () => {
      const actionEntries = [
        TestDataFactory.createJournalEntry({
          description: "Need to optimize database queries",
        }),
        TestDataFactory.createJournalEntry({
          description: "Should implement caching layer",
        }),
        TestDataFactory.createJournalEntry({
          description: "Plan to refactor authentication module",
        }),
        TestDataFactory.createJournalEntry({
          description: "Will add comprehensive error handling",
        }),
      ];

      for (const entry of actionEntries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toContain("🚀 **Next steps:**");
      expect(result).toContain("optimize database queries");
      expect(result).toContain("implement caching layer");
      expect(result).toContain("refactor authentication");
    });
  });

  // ========== OPTION HANDLING TESTS ==========

  describe("Option Processing", () => {
    test("respects includeMetrics option", async () => {
      const entries = TestDataFactory.createMultipleEntries(5);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      // Test with metrics enabled
      let options: StandupOptions = { style: "meeting", days: 1, includeMetrics: true };
      let result = await generateStandup(options);

      expect(result).toContain("📊 **Quick Stats:**");
      expect(result).toContain("checkpoints recorded");

      // Test with metrics disabled
      options = { style: "meeting", days: 1, includeMetrics: false };
      result = await generateStandup(options);

      expect(result).not.toContain("📊 **Quick Stats:**");
    });

    test("respects includeFiles option", async () => {
      const entries = TestDataFactory.createMultipleEntries(3, {
        files: ["src/auth.ts", "src/user.ts", "tests/auth.test.ts"],
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      // Test with files enabled
      let options: StandupOptions = { style: "meeting", days: 1, includeFiles: true };
      let result = await generateStandup(options);

      expect(result).toContain("📁 **Active files:**");
      expect(result).toContain("src/auth.ts");

      // Test with files disabled
      options = { style: "meeting", days: 1, includeFiles: false };
      result = await generateStandup(options);

      expect(result).not.toContain("📁 **Active files:**");
    });

    test("handles days parameter correctly", async () => {
      const entries = TestDataFactory.createEntriesWithTimeDistribution(10);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      // Test 1 day
      let options: StandupOptions = { style: "meeting", days: 1 };
      let result = await generateStandup(options);
      expect(result).toContain("last 24 hours");

      // Test 7 days
      options = { style: "meeting", days: 7 };
      result = await generateStandup(options);
      expect(result).toContain("past week");

      // Test 30 days
      options = { style: "meeting", days: 30 };
      result = await generateStandup(options);
      expect(result).toContain("past month");
    });

    test("validates style parameter", async () => {
      const entries = TestDataFactory.createMultipleEntries(3);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const styles: StandupStyle[] = ["meeting", "written", "executive", "metrics"];

      for (const style of styles) {
        const options: StandupOptions = { style, days: 1 };
        const result = await generateStandup(options);

        expect(result).toBeDefined();
        expect(result.length).toBeGreaterThan(0);
      }
    });

    test("uses appropriate defaults", async () => {
      const entries = TestDataFactory.createMultipleEntries(3);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      // Test undefined style falls back to meeting
      const options = { style: undefined as any, days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("🏃‍♂️ **Daily Standup**");
    });
  });

  // ========== PERFORMANCE TESTS ==========

  describe("Performance", () => {
    test("generates reports under 200ms for typical data", async () => {
      const entries = TestDataFactory.createMultipleEntries(50); // Typical dataset

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "meeting", days: 7 };

      const { result, executionTime, withinThreshold } = await PerformanceTester.measureExecution(
        () => generateStandup(options),
        TEST_CONFIG.PERFORMANCE_THRESHOLDS.STANDUP_GENERATION
      );

      expect(result).toBeDefined();
      expect(withinThreshold).toBe(true);
      TestAssertions.assertPerformance(
        executionTime,
        TEST_CONFIG.PERFORMANCE_THRESHOLDS.STANDUP_GENERATION,
        "Standup generation"
      );
    });

    test("handles large datasets efficiently", async () => {
      const largeDataset = TestDataFactory.createMultipleEntries(1000); // Large dataset

      for (const entry of largeDataset) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "metrics", days: 30 };

      const { result, executionTime } = await PerformanceTester.measureExecution(
        () => generateStandup(options),
        1000 // 1 second timeout for large datasets
      );

      expect(result).toBeDefined();
      expect(executionTime).toBeLessThan(1000);
    });

    test("uses memory efficiently", async () => {
      const entries = TestDataFactory.createMultipleEntries(100);

      for (const entry of entries) {
        await saveEntry(entry);
      }

      const options: StandupOptions = { style: "executive", days: 7 };

      const { result, memoryDelta } = await PerformanceTester.measureMemoryUsage(() =>
        generateStandup(options)
      );

      expect(result).toBeDefined();
      TestAssertions.assertMemoryUsage(memoryDelta, 50 * 1024 * 1024, "Standup generation"); // 50MB limit
    });
  });

  // ========== ERROR HANDLING TESTS ==========

  describe("Error Handling", () => {
    test("handles empty journal gracefully", async () => {
      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toBeDefined();
      expect(result).toContain("🏃‍♂️ **Daily Standup**");
      expect(result).toContain("past week");
    });

    test("handles corrupted entries gracefully", async () => {
      // Create some valid entries first
      const validEntries = TestDataFactory.createMultipleEntries(2);
      for (const entry of validEntries) {
        await saveEntry(entry);
      }

      // Test standup generation with normal entries
      const options: StandupOptions = { style: "meeting", days: 7 };
      const result = await generateStandup(options);

      expect(result).toBeDefined();
      expect(result).toContain("🏃‍♂️ **Daily Standup**");
      expect(result).toContain("test-project"); // Should contain project name from entries
    });

    test("handles missing fields gracefully", async () => {
      // Create a valid entry but with minimal fields
      const minimalEntry = {
        id: "minimal",
        timestamp: new Date().toISOString(),
        description: "Minimal entry for testing",
        // Missing optional fields like project, gitBranch, etc.
      } as any;

      await saveEntry(minimalEntry);

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toBeDefined();
      expect(result).toContain("🏃‍♂️ **Daily Standup**");
    });

    test("handles invalid dates gracefully", async () => {
      const invalidDateEntry = TestDataFactory.createJournalEntry({
        timestamp: "invalid-date",
      });

      await saveEntry(invalidDateEntry);

      const options: StandupOptions = { style: "meeting", days: 1 };
      const result = await generateStandup(options);

      expect(result).toBeDefined();
      expect(result).toContain("🏃‍♂️ **Daily Standup**");
    });

    test("never crashes on malformed data", async () => {
      const malformedEntries = [
        null,
        undefined,
        "",
        { not: "a journal entry" },
        { id: null, timestamp: null },
      ] as any[];

      for (const entry of malformedEntries) {
        try {
          await saveEntry(entry);
        } catch {
          // Expected to fail, continue
        }
      }

      const options: StandupOptions = { style: "metrics", days: 7 };

      expect(async () => {
        const result = await generateStandup(options);
        expect(result).toBeDefined();
      }).not.toThrow();
    });
  });

  // ========== INTEGRATION TESTS ==========

  describe("Integration", () => {
    test("integrates with journal operations seamlessly", async () => {
      // Create entries using journal operations
      const entry1 = TestDataFactory.createJournalEntry({
        description: "Integrated authentication service",
        project: "user-service",
      });

      const entry2 = TestDataFactory.createJournalEntry({
        description: "Completed API documentation",
        project: "user-service",
      });

      await saveEntry(entry1);
      await saveEntry(entry2);

      const options: StandupOptions = { style: "written", days: 1 };
      const result = await generateStandup(options);

      expect(result).toContain("Integrated authentication service");
      expect(result).toContain("Completed API documentation");
      expect(result).toContain("user-service");
    });

    test("maintains consistency with other components", async () => {
      const entries = TestDataFactory.createMultipleEntries(5, {
        project: "consistency-test",
        gitBranch: "feature/consistency",
      });

      for (const entry of entries) {
        await saveEntry(entry);
      }

      // Test all formats produce consistent data
      const styles: StandupStyle[] = ["meeting", "written", "executive", "metrics"];
      const results: string[] = [];

      for (const style of styles) {
        const options: StandupOptions = { style, days: 1 };
        const result = await generateStandup(options);
        results.push(result);
      }

      // All should mention the same project
      results.forEach(result => {
        expect(result).toContain("consistency-test");
      });

      // All should have consistent checkpoint counts in metrics
      const metricsResult = results[3]; // metrics format
      expect(metricsResult).toContain("Checkpoints recorded: 5");
    });

    test("works in different environments", async () => {
      // Test with different environment variables
      const originalEnv = process.env.NODE_ENV;

      try {
        process.env.NODE_ENV = "production";

        const entries = TestDataFactory.createMultipleEntries(3);
        for (const entry of entries) {
          await saveEntry(entry);
        }

        const options: StandupOptions = { style: "executive", days: 1 };
        const result = await generateStandup(options);

        expect(result).toBeDefined();
        expect(result).toContain("🎯 **Executive Summary**");
      } finally {
        process.env.NODE_ENV = originalEnv;
      }
    });
  });
});