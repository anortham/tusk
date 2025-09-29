/**
 * SQLite FTS (Full Text Search) Type Definitions and Contracts
 * Defines interfaces for enhanced search functionality with ranking and relevance
 */

import type { CheckpointEntry, QueryOptions } from '../utils/journal.js';

// Re-export CheckpointEntry for FTS modules
export type { CheckpointEntry } from '../utils/journal.js';

// ===== FTS SEARCH OPTIONS =====

export interface FTSSearchOptions extends Omit<QueryOptions, 'tags'> {
  /** Search query with optional FTS syntax (AND, OR, NOT, phrases) */
  query: string;

  /** Enable phrase search with exact matches */
  exactPhrase?: boolean;

  /** Boost certain fields in ranking (higher = more important) */
  fieldBoosts?: {
    description?: number;
    project?: number;
    gitBranch?: number;
    tags?: number;
  };

  /** Minimum relevance score threshold (0-1) */
  minRelevance?: number;

  /** Include relevance score in results */
  includeScore?: boolean;

  /** Search operator for multiple terms */
  operator?: 'AND' | 'OR';

  /** Enable fuzzy matching for typos */
  fuzzy?: boolean;
}

// ===== FTS SEARCH RESULTS =====

export interface FTSSearchResult extends CheckpointEntry {
  /** Relevance score (0-1, higher = more relevant) */
  relevanceScore?: number;

  /** Highlighted search matches in description */
  highlightedDescription?: string;

  /** Which fields matched the search query */
  matchedFields?: string[];
}

// ===== FTS CONFIGURATION =====

export interface FTSConfig {
  /** FTS table name */
  tableName: string;

  /** Fields to include in FTS index */
  indexedFields: string[];

  /** Enable prefix matching */
  enablePrefixSearch: boolean;

  /** Custom tokenizer options */
  tokenizer?: 'unicode61' | 'porter' | 'ascii';

  /** Rebuild threshold (rebuild index after N changes) */
  rebuildThreshold?: number;
}

// ===== FTS STATISTICS =====

export interface FTSStats {
  /** Total documents in FTS index */
  totalDocuments: number;

  /** Total unique terms */
  uniqueTerms: number;

  /** Index size in bytes */
  indexSize: number;

  /** Last rebuild timestamp */
  lastRebuild?: string;

  /** Average query time in ms */
  avgQueryTime?: number;
}

// ===== FTS MANAGER INTERFACE =====

export interface IFTSManager {
  /**
   * Initialize FTS virtual table and indexes
   */
  initializeFTS(): Promise<void>;

  /**
   * Check if FTS is properly configured and available
   */
  isFTSEnabled(): Promise<boolean>;

  /**
   * Perform FTS search with ranking and relevance
   */
  searchWithFTS(options: FTSSearchOptions): Promise<FTSSearchResult[]>;

  /**
   * Rebuild FTS index (for maintenance or after schema changes)
   */
  rebuildFTSIndex(): Promise<void>;

  /**
   * Get FTS performance statistics
   */
  getFTSStats(): Promise<FTSStats>;

  /**
   * Add/update document in FTS index
   */
  updateFTSDocument(checkpointId: string, entry: CheckpointEntry): Promise<void>;

  /**
   * Remove document from FTS index
   */
  removeFTSDocument(checkpointId: string): Promise<void>;

  /**
   * Optimize FTS index for better performance
   */
  optimizeFTSIndex(): Promise<void>;
}

// ===== SEARCH QUERY BUILDER =====

export interface IFTSQueryBuilder {
  /**
   * Build FTS query string from search options
   */
  buildFTSQuery(options: FTSSearchOptions): string;

  /**
   * Escape special FTS characters in user input
   */
  escapeFTSQuery(query: string): string;

  /**
   * Parse and validate FTS query syntax
   */
  validateFTSQuery(query: string): { valid: boolean; errors: string[] };
}

// ===== MIGRATION CONTRACT =====

export interface FTSMigration {
  /**
   * Check if migration to FTS is needed
   */
  isMigrationNeeded(): Promise<boolean>;

  /**
   * Perform migration from LIKE-based to FTS search
   */
  migrateToFTS(): Promise<void>;

  /**
   * Rollback FTS migration if needed
   */
  rollbackFTSMigration(): Promise<void>;

  /**
   * Get migration progress/status
   */
  getMigrationStatus(): Promise<{
    status: 'pending' | 'in_progress' | 'completed' | 'failed';
    progress: number; // 0-100
    error?: string;
  }>;
}

// ===== ERROR TYPES =====

export class FTSError extends Error {
  constructor(message: string, public code: string) {
    super(message);
    this.name = 'FTSError';
  }
}

export class FTSQueryError extends FTSError {
  constructor(message: string, public query: string) {
    super(message, 'INVALID_QUERY');
  }
}

export class FTSIndexError extends FTSError {
  constructor(message: string) {
    super(message, 'INDEX_ERROR');
  }
}

// ===== DEFAULT CONFIGURATION =====

export const DEFAULT_FTS_CONFIG: FTSConfig = {
  tableName: 'checkpoints_fts',
  indexedFields: ['description', 'project', 'git_branch', 'tags'],
  enablePrefixSearch: true,
  tokenizer: 'unicode61',
  rebuildThreshold: 1000,
};

// ===== EXPECTED SEARCH IMPROVEMENTS =====

/**
 * CONTRACT EXPECTATIONS:
 *
 * 1. SEARCH QUALITY:
 *    - Stemming: "running" matches "run", "ran"
 *    - Case insensitive by default
 *    - Phrase matching: "auth timeout" as exact phrase
 *    - Boolean operators: "bug AND auth", "feature OR enhancement"
 *    - Prefix matching: "auth*" matches "authentication", "authorize"
 *
 * 2. PERFORMANCE:
 *    - 10x+ faster than LIKE queries on large datasets
 *    - Relevance ranking for better result ordering
 *    - Sub-100ms response times for most queries
 *
 * 3. COMPATIBILITY:
 *    - Backward compatible with existing searchCheckpoints() method
 *    - Graceful fallback to LIKE queries if FTS unavailable
 *    - Existing code continues to work unchanged
 *
 * 4. FEATURES:
 *    - Highlighted search results
 *    - Relevance scoring (0-1)
 *    - Field-specific boosting
 *    - Fuzzy matching for typos
 *    - Search statistics and optimization
 */