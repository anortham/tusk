/**
 * Relevance Scoring Utilities for Tusk Journal System
 * Functions for calculating and applying relevance scores to checkpoint entries
 */

import type { CheckpointEntry, RelevanceWeights } from "../core/types.js";
import { DEFAULT_RELEVANCE_WEIGHTS } from "../core/types.js";

// ===== RELEVANCE SCORING SYSTEM =====

/**
 * Calculate relevance score for a checkpoint entry (0-1, higher = more relevant)
 */
export function calculateRelevanceScore(
  entry: CheckpointEntry,
  weights: RelevanceWeights = DEFAULT_RELEVANCE_WEIGHTS,
  referenceDate: Date = new Date()
): number {
  const entryDate = new Date(entry.timestamp);

  // 1. Recency score (exponential decay)
  const daysDiff = (referenceDate.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24);
  const recencyScore = Math.exp(-daysDiff / 7); // Decay over 7 days

  // 2. Tag importance score
  const importantTags = ['critical', 'important', 'breakthrough', 'milestone', 'completed', 'bug-fix'];
  const tagScore = (entry.tags || []).reduce((score, tag) => {
    if (importantTags.includes(tag.toLowerCase())) {
      return score + 0.3;
    }
    return score + 0.1; // Base score for any tag
  }, 0);
  const normalizedTagScore = Math.min(1, tagScore); // Cap at 1

  // 3. Completion indicators score
  const completionKeywords = ['completed', 'finished', 'fixed', 'implemented', 'resolved', 'deployed', 'done'];
  const desc = entry.description.toLowerCase();
  const completionScore = completionKeywords.some(keyword => desc.includes(keyword)) ? 1.0 : 0.5;

  // 4. Git activity score (has commit/branch info)
  const gitScore = entry.gitCommit ? 1.0 : entry.gitBranch ? 0.7 : 0.3;

  // 5. Uniqueness score (inverse of consolidation)
  const uniquenessScore = entry.consolidationInfo
    ? Math.max(0.3, 1 - (entry.consolidationInfo.mergedEntries - 1) * 0.1)
    : 1.0;

  // Calculate weighted total
  const totalScore = (
    recencyScore * weights.recency +
    normalizedTagScore * weights.tags +
    completionScore * weights.completion +
    gitScore * weights.gitActivity +
    uniquenessScore * weights.uniqueness
  );

  return Math.min(1, totalScore); // Cap at 1
}

/**
 * Sort entries by relevance score in descending order
 */
export function sortByRelevance(
  entries: CheckpointEntry[],
  weights?: RelevanceWeights,
  referenceDate?: Date
): Array<CheckpointEntry & { relevanceScore: number }> {
  return entries
    .map(entry => ({
      ...entry,
      relevanceScore: calculateRelevanceScore(entry, weights, referenceDate)
    }))
    .sort((a, b) => b.relevanceScore - a.relevanceScore);
}

/**
 * Filter entries by minimum relevance threshold
 */
export function filterByRelevance(
  entries: CheckpointEntry[],
  threshold: number = 0.5,
  weights?: RelevanceWeights,
  referenceDate?: Date
): CheckpointEntry[] {
  return entries.filter(entry =>
    calculateRelevanceScore(entry, weights, referenceDate) >= threshold
  );
}