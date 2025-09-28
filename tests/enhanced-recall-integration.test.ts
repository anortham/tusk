/**
 * Enhanced Recall Integration Tests
 * Tests for the complete recall functionality including grouping strategies and summary generation
 */

import { test, expect, describe, beforeEach } from "bun:test";

// Import the functions we need to test
import {
  generateId,
  type CheckpointEntry,
} from "../journal.js";

describe("Enhanced Recall Integration", () => {
  // Helper functions from index.ts that we want to test
  function generateExecutiveSummary(entries: CheckpointEntry[]): string {
    const summaryLines: string[] = [];
    summaryLines.push("📋 **Executive Summary:**");
    summaryLines.push("");

    // Analyze patterns
    const projects = [...new Set(entries.map(e => e.project).filter(Boolean))];
    const tags = entries.flatMap(e => e.tags || []);
    const tagCounts = tags.reduce((counts, tag) => {
      counts[tag] = (counts[tag] || 0) + 1;
      return counts;
    }, {} as Record<string, number>);

    const topTags = Object.entries(tagCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([tag, count]) => `${tag} (${count})`);

    // Identify key achievements and patterns
    const achievements = entries.filter(e => {
      const desc = e.description.toLowerCase();
      return desc.includes("completed") || desc.includes("fixed") ||
             desc.includes("implemented") || desc.includes("resolved");
    });

    const workInProgress = entries.filter(e => {
      const desc = e.description.toLowerCase();
      return desc.includes("working on") || desc.includes("progress") ||
             desc.includes("implementing") || desc.includes("debugging");
    });

    // Build summary
    if (achievements.length > 0) {
      summaryLines.push(`🎯 **Key Achievements:** ${achievements.length} completed items`);
      achievements.slice(0, 3).forEach(entry => {
        summaryLines.push(`   • ${entry.description.substring(0, 80)}${entry.description.length > 80 ? '...' : ''}`);
      });
      summaryLines.push("");
    }

    if (workInProgress.length > 0) {
      summaryLines.push(`🔄 **Active Work:** ${workInProgress.length} items in progress`);
      workInProgress.slice(0, 2).forEach(entry => {
        summaryLines.push(`   • ${entry.description.substring(0, 80)}${entry.description.length > 80 ? '...' : ''}`);
      });
      summaryLines.push("");
    }

    if (projects.length > 0) {
      summaryLines.push(`📁 **Active Projects:** ${projects.join(", ")}`);
    }

    if (topTags.length > 0) {
      summaryLines.push(`🏷️ **Common Tags:** ${topTags.join(", ")}`);
    }

    return summaryLines.join("\\n");
  }

  function groupByTopic(entries: CheckpointEntry[]): Record<string, CheckpointEntry[]> {
    const topics: Record<string, CheckpointEntry[]> = {
      "Bug Fixes": entries.filter(e =>
        e.description.toLowerCase().includes("fix") ||
        e.description.toLowerCase().includes("bug") ||
        e.tags?.some(tag => tag.toLowerCase().includes("bug"))
      ),
      "Features": entries.filter(e =>
        e.description.toLowerCase().includes("implement") ||
        e.description.toLowerCase().includes("feature") ||
        e.description.toLowerCase().includes("add") ||
        e.tags?.some(tag => tag.toLowerCase().includes("feature"))
      ),
      "Configuration": entries.filter(e =>
        e.description.toLowerCase().includes("config") ||
        e.description.toLowerCase().includes("setup") ||
        e.description.toLowerCase().includes("install")
      ),
      "Documentation": entries.filter(e =>
        e.description.toLowerCase().includes("document") ||
        e.description.toLowerCase().includes("readme") ||
        e.description.toLowerCase().includes("docs")
      ),
      "Testing": entries.filter(e =>
        e.description.toLowerCase().includes("test") ||
        e.tags?.some(tag => tag.toLowerCase().includes("test"))
      ),
    };

    // Add remaining entries to "General" category
    const categorized = Object.values(topics).flat();
    const remaining = entries.filter(e => !categorized.includes(e));
    if (remaining.length > 0) {
      topics["General"] = remaining;
    }

    // Remove empty categories
    return Object.fromEntries(
      Object.entries(topics).filter(([_, entries]) => entries.length > 0)
    );
  }

  function groupBySession(entries: CheckpointEntry[]): Record<string, CheckpointEntry[]> {
    if (entries.length === 0) return {};

    const sessions: Record<string, CheckpointEntry[]> = {};
    let currentSessionId = 1;
    let currentSession: CheckpointEntry[] = [];

    // Sort by timestamp first
    const sorted = [...entries].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    for (let i = 0; i < sorted.length; i++) {
      const entry = sorted[i];
      if (!entry) continue;

      const prevEntry = i > 0 ? sorted[i - 1] : null;

      if (prevEntry) {
        const timeDiff = new Date(entry.timestamp).getTime() - new Date(prevEntry.timestamp).getTime();
        const hoursDiff = timeDiff / (1000 * 60 * 60);

        // If more than 4 hours apart, start a new session
        if (hoursDiff > 4) {
          if (currentSession.length > 0) {
            sessions[`Session ${currentSessionId}`] = currentSession;
            currentSessionId++;
            currentSession = [];
          }
        }
      }

      currentSession.push(entry);
    }

    // Add final session
    if (currentSession.length > 0) {
      sessions[`Session ${currentSessionId}`] = currentSession;
    }

    return sessions;
  }

  function applyGroupingStrategy(entries: CheckpointEntry[], strategy: string): Record<string, CheckpointEntry[]> {
    switch (strategy) {
      case 'project':
        return entries.reduce((groups, entry) => {
          const proj = entry.project || "General";
          if (!groups[proj]) groups[proj] = [];
          groups[proj].push(entry);
          return groups;
        }, {} as Record<string, CheckpointEntry[]>);

      case 'topic':
        return groupByTopic(entries);

      case 'session':
        return groupBySession(entries);

      case 'relevance':
        return { "Most Relevant": entries };

      case 'chronological':
      default:
        return entries.reduce((groups, entry) => {
          const date = new Date(entry.timestamp).toLocaleDateString();
          if (!groups[date]) groups[date] = [];
          groups[date].push(entry);
          return groups;
        }, {} as Record<string, CheckpointEntry[]>);
    }
  }

  // Test data factory
  function createTestEntry(overrides: Partial<CheckpointEntry> = {}): CheckpointEntry {
    return {
      id: generateId(),
      timestamp: new Date().toISOString(),
      description: "Test checkpoint entry",
      project: "test-project",
      gitBranch: "main",
      gitCommit: "abc123",
      tags: [],  // Don't give default tags to avoid interference
      files: ["test.ts"],
      ...overrides,
    };
  }

  describe("Executive Summary Generation", () => {
    test("generateExecutiveSummary - identifies achievements", () => {
      const entries = [
        createTestEntry({
          description: "Completed authentication system implementation",
          tags: ["feature", "auth"]
        }),
        createTestEntry({
          description: "Fixed critical login bug",
          tags: ["bug-fix", "critical"]
        }),
        createTestEntry({
          description: "Working on user dashboard",
          tags: ["feature", "wip"]
        }),
      ];

      const summary = generateExecutiveSummary(entries);

      expect(summary).toContain("**Key Achievements:** 2 completed items");
      expect(summary).toContain("**Active Work:** 1 items in progress");
      expect(summary).toContain("authentication system implementation");
      expect(summary).toContain("Fixed critical login bug");
    });

    test("generateExecutiveSummary - analyzes project and tag patterns", () => {
      const entries = [
        createTestEntry({
          description: "Fixed bug in frontend",
          project: "web-app",
          tags: ["bug-fix", "frontend"]
        }),
        createTestEntry({
          description: "Fixed bug in backend",
          project: "api-service",
          tags: ["bug-fix", "backend"]
        }),
        createTestEntry({
          description: "Added feature to frontend",
          project: "web-app",
          tags: ["feature", "frontend"]
        }),
      ];

      const summary = generateExecutiveSummary(entries);

      expect(summary).toContain("**Active Projects:** web-app, api-service");
      expect(summary).toContain("**Common Tags:**");
      expect(summary).toContain("bug-fix (2)");
      expect(summary).toContain("frontend (2)");
    });

    test("generateExecutiveSummary - handles empty entries", () => {
      const summary = generateExecutiveSummary([]);

      expect(summary).toContain("Executive Summary:");
      expect(summary).not.toContain("Key Achievements:");
      expect(summary).not.toContain("Active Work:");
    });
  });

  describe("Grouping Strategies", () => {
    test("applyGroupingStrategy - groups by project", () => {
      const entries = [
        createTestEntry({ description: "Frontend work", project: "web-app" }),
        createTestEntry({ description: "Backend work", project: "api-service" }),
        createTestEntry({ description: "More frontend work", project: "web-app" }),
        createTestEntry({ description: "No project work", project: undefined }),
      ];

      const grouped = applyGroupingStrategy(entries, "project");

      expect(Object.keys(grouped)).toHaveLength(3);
      expect(grouped["web-app"]).toHaveLength(2);
      expect(grouped["api-service"]).toHaveLength(1);
      expect(grouped["General"]).toHaveLength(1);
    });

    test("applyGroupingStrategy - groups by topic", () => {
      const entries = [
        createTestEntry({
          description: "Fixed authentication bug",
          tags: ["bug-fix"]
        }),
        createTestEntry({
          description: "Implemented dashboard feature",
          tags: ["feature"]
        }),
        createTestEntry({
          description: "Wrote unit tests",
          tags: ["testing"]
        }),
        createTestEntry({
          description: "Updated configuration files",
        }),
        createTestEntry({
          description: "Random unrelated work that doesn't match patterns",
        }),
      ];

      const grouped = groupByTopic(entries);

      // Verify key categories are present and have expected content
      expect(grouped["Bug Fixes"]).toHaveLength(1);
      expect(grouped["Bug Fixes"]?.[0]?.description).toContain("Fixed authentication bug");

      expect(grouped["Features"]).toHaveLength(1);
      expect(grouped["Features"]?.[0]?.description).toContain("Implemented dashboard feature");

      expect(grouped["Testing"]).toHaveLength(1);
      expect(grouped["Testing"]?.[0]?.description).toContain("Wrote unit tests");

      expect(grouped["Configuration"]).toHaveLength(1);
      expect(grouped["Configuration"]?.[0]?.description).toContain("Updated configuration");

      expect(grouped["General"]).toHaveLength(1);
      expect(grouped["General"]?.[0]?.description).toContain("Random unrelated work");
    });

    test("applyGroupingStrategy - groups by session", () => {
      const baseTime = new Date("2023-01-01T10:00:00Z").getTime();

      const entries = [
        createTestEntry({
          description: "Morning work 1",
          timestamp: new Date(baseTime).toISOString()
        }),
        createTestEntry({
          description: "Morning work 2",
          timestamp: new Date(baseTime + 30 * 60 * 1000).toISOString() // 30 min later
        }),
        createTestEntry({
          description: "Afternoon work",
          timestamp: new Date(baseTime + 6 * 60 * 60 * 1000).toISOString() // 6 hours later
        }),
      ];

      const grouped = groupBySession(entries);

      expect(Object.keys(grouped)).toHaveLength(2);
      expect(grouped["Session 1"]).toHaveLength(2); // Morning work
      expect(grouped["Session 2"]).toHaveLength(1); // Afternoon work
    });

    test("applyGroupingStrategy - groups chronologically", () => {
      const entries = [
        createTestEntry({
          description: "Work on day 1",
          timestamp: "2023-01-01T10:00:00Z"
        }),
        createTestEntry({
          description: "More work on day 1",
          timestamp: "2023-01-01T15:00:00Z"
        }),
        createTestEntry({
          description: "Work on day 2",
          timestamp: "2023-01-02T10:00:00Z"
        }),
      ];

      const grouped = applyGroupingStrategy(entries, "chronological");

      expect(Object.keys(grouped)).toHaveLength(2);
      expect(grouped[new Date("2023-01-01").toLocaleDateString()]).toHaveLength(2);
      expect(grouped[new Date("2023-01-02").toLocaleDateString()]).toHaveLength(1);
    });

    test("applyGroupingStrategy - groups by relevance", () => {
      const entries = [
        createTestEntry({ description: "High relevance work" }),
        createTestEntry({ description: "Medium relevance work" }),
        createTestEntry({ description: "Low relevance work" }),
      ];

      const grouped = applyGroupingStrategy(entries, "relevance");

      expect(Object.keys(grouped)).toHaveLength(1);
      expect(grouped["Most Relevant"]).toHaveLength(3);
    });
  });

  describe("Edge Cases", () => {
    test("groupBySession - handles single entry", () => {
      const entries = [createTestEntry({ description: "Single entry" })];
      const grouped = groupBySession(entries);

      expect(Object.keys(grouped)).toHaveLength(1);
      expect(grouped["Session 1"]).toHaveLength(1);
    });

    test("groupBySession - handles entries with same timestamp", () => {
      const timestamp = new Date().toISOString();
      const entries = [
        createTestEntry({ description: "Entry 1", timestamp }),
        createTestEntry({ description: "Entry 2", timestamp }),
      ];

      const grouped = groupBySession(entries);

      expect(Object.keys(grouped)).toHaveLength(1);
      expect(grouped["Session 1"]).toHaveLength(2);
    });

    test("groupByTopic - handles entries with no matching topics", () => {
      const entries = [
        createTestEntry({ description: "Some random work that doesn't match patterns" }),
        createTestEntry({ description: "Another unclassified entry here" }),
      ];

      const grouped = groupByTopic(entries);

      // Should have General category with the unmatched entries
      expect(grouped["General"]).toBeDefined();
      expect(grouped["General"]).toHaveLength(2);

      // Only General category should be present since no entries match other categories
      expect(Object.keys(grouped)).toEqual(["General"]);
    });

    test("generateExecutiveSummary - handles very long descriptions", () => {
      const longDescription = "A".repeat(200); // Very long description
      const entries = [
        createTestEntry({
          description: `Completed ${longDescription} implementation`
        })
      ];

      const summary = generateExecutiveSummary(entries);

      expect(summary).toContain("**Key Achievements:** 1 completed items");
      // Should truncate long descriptions
      expect(summary).toContain("...");
    });

    test("generateExecutiveSummary - handles many tags", () => {
      const manyTags = Array.from({ length: 10 }, (_, i) => `tag-${i}`);
      const entries = [
        createTestEntry({
          description: "Work with many tags",
          tags: manyTags
        })
      ];

      const summary = generateExecutiveSummary(entries);

      expect(summary).toContain("**Common Tags:**");
      // Should limit to top 5 tags
      const tagMatches = summary.match(/tag-\d+/g);
      expect(tagMatches?.length).toBeLessThanOrEqual(5);
    });
  });
});