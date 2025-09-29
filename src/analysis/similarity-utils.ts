/**
 * Similarity and Clustering Utilities for Tusk Journal System
 * Functions for calculating similarity between entries and clustering similar checkpoints
 */

import type { CheckpointEntry } from "../core/types.js";

// ===== DEDUPLICATION AND SIMILARITY UTILITIES =====

/**
 * Calculate Levenshtein distance between two strings
 */
export function calculateLevenshteinDistance(str1: string, str2: string): number {
  const matrix = Array(str2.length + 1).fill(null).map(() => Array(str1.length + 1).fill(0)) as number[][];

  for (let i = 0; i <= str1.length; i++) {
    matrix[0]![i] = i;
  }

  for (let j = 0; j <= str2.length; j++) {
    matrix[j]![0] = j;
  }

  for (let j = 1; j <= str2.length; j++) {
    for (let i = 1; i <= str1.length; i++) {
      const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
      matrix[j]![i] = Math.min(
        matrix[j]![i - 1]! + 1,     // insertion
        matrix[j - 1]![i]! + 1,     // deletion
        matrix[j - 1]![i - 1]! + cost // substitution
      );
    }
  }

  return matrix[str2.length]![str1.length]!;
}

/**
 * Calculate similarity score between two strings (0-1, higher = more similar)
 */
export function calculateSimilarityScore(str1: string, str2: string): number {
  const maxLength = Math.max(str1.length, str2.length);
  if (maxLength === 0) return 1.0;

  const distance = calculateLevenshteinDistance(str1.toLowerCase(), str2.toLowerCase());
  return 1.0 - (distance / maxLength);
}

/**
 * Calculate semantic similarity between two checkpoint descriptions
 */
export function calculateSemanticSimilarity(entry1: CheckpointEntry, entry2: CheckpointEntry): number {
  // Normalize descriptions for comparison
  const normalize = (text: string) => text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const desc1 = normalize(entry1.description);
  const desc2 = normalize(entry2.description);

  // Base similarity on description
  let similarity = calculateSimilarityScore(desc1, desc2);

  // Boost similarity if same project
  if (entry1.project && entry2.project && entry1.project === entry2.project) {
    similarity = Math.min(1.0, similarity + 0.1);
  }

  // Boost similarity if overlapping tags
  const tags1 = new Set(entry1.tags || []);
  const tags2 = new Set(entry2.tags || []);
  const tagOverlap = [...tags1].filter(tag => tags2.has(tag)).length;
  const totalUniqueTags = new Set([...tags1, ...tags2]).size;

  if (totalUniqueTags > 0) {
    const tagSimilarity = tagOverlap / totalUniqueTags;
    similarity = Math.min(1.0, similarity + (tagSimilarity * 0.15));
  }

  // Boost similarity if similar git context
  if (entry1.gitBranch && entry2.gitBranch && entry1.gitBranch === entry2.gitBranch) {
    similarity = Math.min(1.0, similarity + 0.05);
  }

  return similarity;
}

/**
 * Group checkpoints by similarity clusters
 */
export function clusterSimilarCheckpoints(
  entries: CheckpointEntry[],
  similarityThreshold: number = 0.7
): CheckpointEntry[][] {
  const clusters: CheckpointEntry[][] = [];
  const processed = new Set<string>();

  for (const entry of entries) {
    if (!entry.id || processed.has(entry.id)) continue;

    const cluster = [entry];
    processed.add(entry.id);

    // Find similar entries
    for (const other of entries) {
      if (!other.id || processed.has(other.id) || entry.id === other.id) continue;

      const similarity = calculateSemanticSimilarity(entry, other);
      if (similarity >= similarityThreshold) {
        cluster.push(other);
        processed.add(other.id);
      }
    }

    clusters.push(cluster);
  }

  return clusters;
}

/**
 * Merge similar checkpoint entries into a consolidated entry
 */
export function mergeCheckpointCluster(cluster: CheckpointEntry[]): CheckpointEntry {
  if (cluster.length === 1) {
    const entry = cluster[0];
    if (!entry) throw new Error("Invalid cluster: empty entry");
    return entry;
  }

  // Sort by timestamp (most recent first)
  const sorted = cluster.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  const primary = sorted[0];
  if (!primary) throw new Error("Invalid cluster: no primary entry");

  // Collect unique information from all entries
  const allTags = [...new Set(cluster.flatMap(e => e.tags || []))];
  const allFiles = [...new Set(cluster.flatMap(e => e.files || []))];
  const allProjects = [...new Set(cluster.map(e => e.project).filter(Boolean))] as string[];
  const allBranches = [...new Set(cluster.map(e => e.gitBranch).filter(Boolean))] as string[];
  const allCommits = [...new Set(cluster.map(e => e.gitCommit).filter(Boolean))] as string[];

  // Create enhanced description showing consolidation
  const uniqueDescriptions = [...new Set(cluster.map(e => e.description))];
  let consolidatedDescription = primary.description;

  if (uniqueDescriptions.length > 1) {
    // If descriptions are different, show the primary one with count
    consolidatedDescription = `${primary.description} [consolidated from ${cluster.length} similar entries]`;
  } else {
    // If descriptions are the same, just add count
    consolidatedDescription = `${primary.description} [${cluster.length} occurrences]`;
  }

  return {
    ...primary,
    description: consolidatedDescription,
    tags: allTags,
    files: allFiles,
    project: allProjects[0] || primary.project, // Use primary project
    gitBranch: allBranches[0] || primary.gitBranch, // Use primary branch
    gitCommit: allCommits[0] || primary.gitCommit, // Use primary commit
    // Add metadata about consolidation
    consolidationInfo: {
      mergedEntries: cluster.length,
      mergedIds: cluster.map(e => e.id).filter(Boolean) as string[],
      timeSpan: {
        earliest: cluster.reduce((earliest, e) =>
          new Date(e.timestamp) < new Date(earliest.timestamp) ? e : earliest
        ).timestamp,
        latest: primary.timestamp
      }
    }
  };
}