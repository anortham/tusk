/**
 * Enhanced Recall System Tests
 * Tests for deduplication, relevance scoring, grouping, and summarization features
 */

import { test, expect, describe, beforeEach } from "bun:test";
import {
  calculateLevenshteinDistance,
  calculateSimilarityScore,
  calculateSemanticSimilarity,
  clusterSimilarCheckpoints,
  mergeCheckpointCluster,
  calculateRelevanceScore,
  sortByRelevance,
  filterByRelevance,
  type CheckpointEntry,
  type RelevanceWeights,
  DEFAULT_RELEVANCE_WEIGHTS,
} from '../src/utils/journal.js';

describe("Enhanced Recall System", () => {
  // Test data factory
  function createTestEntry(overrides: Partial<CheckpointEntry> = {}): CheckpointEntry {
    return {
      id: `test_${Math.random().toString(36).slice(2)}`,
      timestamp: new Date().toISOString(),
      description: "Test checkpoint entry",
      project: "test-project",
      gitBranch: "main",
      gitCommit: "abc123",
      tags: ["test"],
      files: ["test.ts"],
      ...overrides,
    };
  }

  describe("Similarity Calculations", () => {
    test("calculateLevenshteinDistance - identical strings", () => {
      const distance = calculateLevenshteinDistance("hello", "hello");
      expect(distance).toBe(0);
    });

    test("calculateLevenshteinDistance - completely different strings", () => {
      const distance = calculateLevenshteinDistance("abc", "xyz");
      expect(distance).toBe(3);
    });

    test("calculateLevenshteinDistance - one insertion", () => {
      const distance = calculateLevenshteinDistance("cat", "cats");
      expect(distance).toBe(1);
    });

    test("calculateLevenshteinDistance - one deletion", () => {
      const distance = calculateLevenshteinDistance("cats", "cat");
      expect(distance).toBe(1);
    });

    test("calculateLevenshteinDistance - one substitution", () => {
      const distance = calculateLevenshteinDistance("cat", "bat");
      expect(distance).toBe(1);
    });

    test("calculateSimilarityScore - identical strings", () => {
      const score = calculateSimilarityScore("hello world", "hello world");
      expect(score).toBe(1.0);
    });

    test("calculateSimilarityScore - completely different strings", () => {
      const score = calculateSimilarityScore("abc", "xyz");
      expect(score).toBeLessThan(0.5);
    });

    test("calculateSimilarityScore - similar strings", () => {
      const score = calculateSimilarityScore("fix authentication bug", "fixed auth bug");
      expect(score).toBeGreaterThan(0.4);
      expect(score).toBeLessThan(0.8);
    });

    test("calculateSemanticSimilarity - identical descriptions", () => {
      const entry1 = createTestEntry({ description: "Fixed authentication timeout" });
      const entry2 = createTestEntry({ description: "Fixed authentication timeout" });

      const similarity = calculateSemanticSimilarity(entry1, entry2);
      expect(similarity).toBeGreaterThan(0.9);
    });

    test("calculateSemanticSimilarity - similar descriptions", () => {
      const entry1 = createTestEntry({
        description: "Fixed authentication timeout bug",
        project: "auth-service",
        tags: ["bug-fix", "auth"]
      });
      const entry2 = createTestEntry({
        description: "Resolved auth timeout issue",
        project: "auth-service",
        tags: ["bug-fix", "auth"]
      });

      const similarity = calculateSemanticSimilarity(entry1, entry2);
      expect(similarity).toBeGreaterThan(0.65);
      expect(similarity).toBeLessThan(0.8);
    });

    test("calculateSemanticSimilarity - same project boosts similarity", () => {
      const sameProjectEntry1 = createTestEntry({
        description: "Fixed authentication timeout",
        project: "auth-service",
      });
      const sameProjectEntry2 = createTestEntry({
        description: "Resolved auth timeout",
        project: "auth-service"
      });

      const diffProjectEntry1 = createTestEntry({
        description: "Fixed authentication timeout",
        project: "auth-service",
      });
      const diffProjectEntry2 = createTestEntry({
        description: "Resolved auth timeout",
        project: "user-service"
      });

      const sameProjectSimilarity = calculateSemanticSimilarity(sameProjectEntry1, sameProjectEntry2);
      const diffProjectSimilarity = calculateSemanticSimilarity(diffProjectEntry1, diffProjectEntry2);

      // Same project should have higher similarity due to the +0.1 boost
      expect(sameProjectSimilarity).toBeGreaterThan(diffProjectSimilarity);
      expect(sameProjectSimilarity - diffProjectSimilarity).toBeCloseTo(0.1, 2);
    });

    test("calculateSemanticSimilarity - overlapping tags boost similarity", () => {
      const entry1 = createTestEntry({
        description: "Some work",
        tags: ["critical", "bug-fix", "frontend"]
      });
      const entry2 = createTestEntry({
        description: "Some work",
        tags: ["critical", "bug-fix", "backend"]
      });

      const similarity = calculateSemanticSimilarity(entry1, entry2);
      expect(similarity).toBeGreaterThan(0.9);
    });
  });

  describe("Clustering and Deduplication", () => {
    test("clusterSimilarCheckpoints - no similar entries", () => {
      const entries = [
        createTestEntry({ description: "Fixed authentication bug" }),
        createTestEntry({ description: "Added new feature" }),
        createTestEntry({ description: "Updated documentation" }),
      ];

      const clusters = clusterSimilarCheckpoints(entries, 0.8);
      expect(clusters).toHaveLength(3);
      clusters.forEach(cluster => expect(cluster).toHaveLength(1));
    });

    test("clusterSimilarCheckpoints - with similar entries", () => {
      const entries = [
        createTestEntry({ description: "Fixed authentication timeout" }),
        createTestEntry({ description: "Fixed auth timeout issue" }),
        createTestEntry({ description: "Resolved authentication timeout" }),
        createTestEntry({ description: "Added new feature" }),
      ];

      const clusters = clusterSimilarCheckpoints(entries, 0.6);
      expect(clusters).toHaveLength(2);

      // Find the auth cluster
      const authCluster = clusters.find(c => c.length > 1);
      expect(authCluster).toHaveLength(3);
    });

    test("clusterSimilarCheckpoints - respects similarity threshold", () => {
      const entries = [
        createTestEntry({ description: "Fixed authentication bug" }),
        createTestEntry({ description: "Added new feature completely different" }),
      ];

      const strictClusters = clusterSimilarCheckpoints(entries, 0.9);
      expect(strictClusters).toHaveLength(2); // Separate clusters (very different)

      const looseClusters = clusterSimilarCheckpoints(entries, 0.1);
      expect(looseClusters).toHaveLength(1); // Merged cluster (very loose threshold)
    });

    test("mergeCheckpointCluster - single entry", () => {
      const entry = createTestEntry({ description: "Test entry" });
      const merged = mergeCheckpointCluster([entry]);

      expect(merged).toEqual(entry);
      expect(merged.consolidationInfo).toBeUndefined();
    });

    test("mergeCheckpointCluster - multiple identical entries", () => {
      const entries = [
        createTestEntry({
          description: "Fixed auth bug",
          timestamp: "2023-01-03T10:00:00Z"
        }),
        createTestEntry({
          description: "Fixed auth bug",
          timestamp: "2023-01-01T10:00:00Z"
        }),
        createTestEntry({
          description: "Fixed auth bug",
          timestamp: "2023-01-02T10:00:00Z"
        }),
      ];

      const merged = mergeCheckpointCluster(entries);

      expect(merged.description).toContain("Fixed auth bug [3 occurrences]");
      expect(merged.consolidationInfo?.mergedEntries).toBe(3);
      expect(merged.timestamp).toBe("2023-01-03T10:00:00Z"); // Most recent
    });

    test("mergeCheckpointCluster - multiple different entries", () => {
      const entries = [
        createTestEntry({
          description: "Fixed authentication timeout",
          timestamp: "2023-01-03T10:00:00Z",
          tags: ["auth", "bug-fix"]
        }),
        createTestEntry({
          description: "Resolved auth timeout issue",
          timestamp: "2023-01-01T10:00:00Z",
          tags: ["auth", "critical"]
        }),
      ];

      const merged = mergeCheckpointCluster(entries);

      expect(merged.description).toContain("consolidated from 2 similar entries");
      expect(merged.tags).toContain("auth");
      expect(merged.tags).toContain("bug-fix");
      expect(merged.tags).toContain("critical");
    });

    test("mergeCheckpointCluster - preserves unique information", () => {
      const entries = [
        createTestEntry({
          description: "Fixed bug",
          project: "frontend",
          gitBranch: "feature/fix",
          files: ["app.ts", "auth.ts"]
        }),
        createTestEntry({
          description: "Fixed bug",
          project: "frontend",
          gitBranch: "feature/fix",
          files: ["auth.ts", "utils.ts"]
        }),
      ];

      const merged = mergeCheckpointCluster(entries);

      expect(merged.files).toContain("app.ts");
      expect(merged.files).toContain("auth.ts");
      expect(merged.files).toContain("utils.ts");
      expect(merged.files).toHaveLength(3); // Unique files only
    });
  });

  describe("Relevance Scoring", () => {
    test("calculateRelevanceScore - recent entry scores higher", () => {
      const recentEntry = createTestEntry({
        timestamp: new Date().toISOString() // Now
      });
      const oldEntry = createTestEntry({
        timestamp: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString() // 30 days ago
      });

      const recentScore = calculateRelevanceScore(recentEntry);
      const oldScore = calculateRelevanceScore(oldEntry);

      expect(recentScore).toBeGreaterThan(oldScore);
    });

    test("calculateRelevanceScore - important tags boost score", () => {
      const criticalEntry = createTestEntry({
        tags: ["critical", "bug-fix", "important"]
      });
      const regularEntry = createTestEntry({
        tags: ["feature", "minor"]
      });

      const criticalScore = calculateRelevanceScore(criticalEntry);
      const regularScore = calculateRelevanceScore(regularEntry);

      expect(criticalScore).toBeGreaterThan(regularScore);
    });

    test("calculateRelevanceScore - completion indicators boost score", () => {
      const completedEntry = createTestEntry({
        description: "Completed authentication system implementation"
      });
      const workingEntry = createTestEntry({
        description: "Working on authentication system"
      });

      const completedScore = calculateRelevanceScore(completedEntry);
      const workingScore = calculateRelevanceScore(workingEntry);

      expect(completedScore).toBeGreaterThan(workingScore);
    });

    test("calculateRelevanceScore - git activity boosts score", () => {
      const withCommitEntry = createTestEntry({
        gitCommit: "abc123",
        gitBranch: "feature/auth"
      });
      const withBranchEntry = createTestEntry({
        gitBranch: "feature/auth",
        gitCommit: undefined
      });
      const noGitEntry = createTestEntry({
        gitBranch: undefined,
        gitCommit: undefined
      });

      const commitScore = calculateRelevanceScore(withCommitEntry);
      const branchScore = calculateRelevanceScore(withBranchEntry);
      const noGitScore = calculateRelevanceScore(noGitEntry);

      expect(commitScore).toBeGreaterThan(branchScore);
      expect(branchScore).toBeGreaterThan(noGitScore);
    });

    test("calculateRelevanceScore - consolidated entries have lower uniqueness score", () => {
      const originalEntry = createTestEntry({
        description: "Fixed bug"
      });
      const consolidatedEntry = createTestEntry({
        description: "Fixed bug",
        consolidationInfo: {
          mergedEntries: 5,
          mergedIds: ["1", "2", "3", "4", "5"],
          timeSpan: { earliest: "2023-01-01", latest: "2023-01-05" }
        }
      });

      const originalScore = calculateRelevanceScore(originalEntry);
      const consolidatedScore = calculateRelevanceScore(consolidatedEntry);

      expect(originalScore).toBeGreaterThan(consolidatedScore);
    });

    test("calculateRelevanceScore - custom weights", () => {
      const entry = createTestEntry({
        timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
        tags: ["critical"],
        description: "Completed important feature",
        gitCommit: "abc123"
      });

      const defaultScore = calculateRelevanceScore(entry, DEFAULT_RELEVANCE_WEIGHTS);

      const tagWeightedScore = calculateRelevanceScore(entry, {
        ...DEFAULT_RELEVANCE_WEIGHTS,
        tags: 0.8 // Much higher tag weight
      });

      // Should be different due to different weights
      expect(tagWeightedScore).not.toBe(defaultScore);
    });

    test("sortByRelevance - sorts correctly", () => {
      const entries = [
        createTestEntry({
          description: "Old regular work",
          timestamp: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
        }),
        createTestEntry({
          description: "Recent critical bug fix completed",
          timestamp: new Date().toISOString(),
          tags: ["critical", "bug-fix"]
        }),
        createTestEntry({
          description: "Medium priority work",
          timestamp: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
          tags: ["feature"]
        }),
      ];

      const sorted = sortByRelevance(entries);

      expect(sorted[0]?.relevanceScore).toBeGreaterThan(sorted[1]?.relevanceScore!);
      expect(sorted[1]?.relevanceScore).toBeGreaterThan(sorted[2]?.relevanceScore!);
      expect(sorted[0]?.description).toContain("critical bug fix");
    });

    test("filterByRelevance - filters correctly", () => {
      const entries = [
        createTestEntry({
          description: "High relevance work",
          tags: ["critical", "completed"]
        }),
        createTestEntry({
          description: "Low relevance work",
          timestamp: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
        }),
      ];

      const highThresholdFiltered = filterByRelevance(entries, 0.7);
      const lowThresholdFiltered = filterByRelevance(entries, 0.3);

      expect(highThresholdFiltered.length).toBeLessThan(lowThresholdFiltered.length);
      expect(lowThresholdFiltered).toHaveLength(2); // Both should pass low threshold
    });
  });

  describe("Edge Cases and Error Handling", () => {
    test("calculateSemanticSimilarity - handles empty descriptions", () => {
      const entry1 = createTestEntry({ description: "" });
      const entry2 = createTestEntry({ description: "" });

      const similarity = calculateSemanticSimilarity(entry1, entry2);
      expect(similarity).toBe(1.0); // Empty strings are identical
    });

    test("calculateSemanticSimilarity - handles undefined tags", () => {
      const entry1 = createTestEntry({ description: "test", tags: undefined });
      const entry2 = createTestEntry({ description: "test", tags: undefined });

      const similarity = calculateSemanticSimilarity(entry1, entry2);
      expect(similarity).toBeGreaterThan(0.9);
    });

    test("clusterSimilarCheckpoints - handles empty array", () => {
      const clusters = clusterSimilarCheckpoints([], 0.7);
      expect(clusters).toEqual([]);
    });

    test("clusterSimilarCheckpoints - handles entries without IDs", () => {
      const entriesWithoutIds = [
        createTestEntry({ id: undefined }),
        createTestEntry({ id: "" }),
        createTestEntry({ description: "Valid entry" }),
      ];

      const clusters = clusterSimilarCheckpoints(entriesWithoutIds, 0.7);
      expect(clusters).toHaveLength(1); // Only the valid entry
    });

    test("mergeCheckpointCluster - throws on empty cluster", () => {
      expect(() => mergeCheckpointCluster([])).toThrow("Invalid cluster: no primary entry");
    });

    test("calculateRelevanceScore - handles undefined fields gracefully", () => {
      const minimalEntry = createTestEntry({
        tags: undefined,
        gitBranch: undefined,
        gitCommit: undefined,
        consolidationInfo: undefined
      });

      const score = calculateRelevanceScore(minimalEntry);
      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThan(1);
    });

    test("calculateRelevanceScore - handles invalid timestamps", () => {
      const invalidEntry = createTestEntry({
        timestamp: "invalid-date"
      });

      // Should not throw, but handle gracefully
      expect(() => calculateRelevanceScore(invalidEntry)).not.toThrow();
    });
  });

  describe("Performance Considerations", () => {
    test("clusterSimilarCheckpoints - performance with many entries", () => {
      // Generate 100 test entries with some similar ones
      const entries: CheckpointEntry[] = [];

      for (let i = 0; i < 50; i++) {
        entries.push(createTestEntry({ description: `Unique entry ${i}` }));
      }

      // Add some similar entries
      for (let i = 0; i < 50; i++) {
        entries.push(createTestEntry({ description: "Fixed authentication bug" }));
      }

      const startTime = performance.now();
      const clusters = clusterSimilarCheckpoints(entries, 0.8);
      const endTime = performance.now();

      // Should complete within reasonable time (< 1 second for 100 entries)
      expect(endTime - startTime).toBeLessThan(1000);

      // Should properly cluster the similar auth entries
      const authCluster = clusters.find(c => c.length > 1);
      expect(authCluster).toBeDefined();
      expect(authCluster!.length).toBe(50);
    });

    test("calculateRelevanceScore - performance with complex entries", () => {
      const complexEntry = createTestEntry({
        description: "Very long description ".repeat(50),
        tags: Array.from({ length: 20 }, (_, i) => `tag-${i}`),
        files: Array.from({ length: 50 }, (_, i) => `file-${i}.ts`),
      });

      const startTime = performance.now();
      for (let i = 0; i < 1000; i++) {
        calculateRelevanceScore(complexEntry);
      }
      const endTime = performance.now();

      // Should be fast even for complex entries (< 100ms for 1000 calculations)
      expect(endTime - startTime).toBeLessThan(100);
    });
  });
});