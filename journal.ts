/**
 * Journal System Main Entry Point
 * Re-exports from modular components for backward compatibility
 */

// Export types
export type {
  CheckpointEntry,
  JournalEntry,
  WorkspaceInfo,
  QueryOptions,
  StandupEntry,
  RelevanceWeights
} from "./types.js";

export { DEFAULT_RELEVANCE_WEIGHTS } from "./types.js";

// Export similarity utilities
export {
  calculateLevenshteinDistance,
  calculateSimilarityScore,
  calculateSemanticSimilarity,
  clusterSimilarCheckpoints,
  mergeCheckpointCluster
} from "./similarity-utils.js";

// Export relevance scoring utilities
export {
  calculateRelevanceScore,
  sortByRelevance,
  filterByRelevance
} from "./relevance-scoring.js";

// Export workspace utilities
export {
  detectWorkspace,
  findGitRoot,
  findPackageRoot,
  normalizePath,
  hashPath
} from "./workspace-utils.js";

// Export core database functionality
export { JournalDB } from "./journal-db.js";

// Create default database instance and re-export key functions
import { JournalDB } from "./journal-db.js";

// Default instance for backward compatibility
let defaultJournal: JournalDB | null = null;

function getDefaultJournal(): JournalDB {
  if (!defaultJournal) {
    defaultJournal = new JournalDB();
  }
  return defaultJournal;
}

// Utility functions for backward compatibility
export function generateId(): string {
  const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `${timestamp}_${randomSuffix}`;
}

// Re-export database operations
export async function saveEntry(entry: any): Promise<void> {
  return getDefaultJournal().saveCheckpoint(entry);
}

export async function getRecentEntries(filter: any = {}): Promise<any[]> {
  return getDefaultJournal().getRecentCheckpoints(filter);
}

export async function searchEntries(query: string, options: any = {}): Promise<any[]> {
  const { limit = 20, workspace = 'current' } = options;
  return getDefaultJournal().searchCheckpoints(query, { limit, workspace });
}

export async function getWorkspaceSummary(): Promise<any[]> {
  return getDefaultJournal().getWorkspaceSummary();
}

export function getCurrentWorkspace(): { id: string; path: string; name: string } {
  return getDefaultJournal().getCurrentWorkspace();
}

export async function getJournalStats(): Promise<any> {
  return getDefaultJournal().getJournalStats();
}

// Test utility to reset the default journal instance
export function __resetDefaultJournal(): void {
  defaultJournal = null;
}