/**
 * SQLite FTS Manager Implementation
 * Provides full-text search capabilities with ranking and relevance scoring
 */

import type { Database } from "bun:sqlite";
import type {
  CheckpointEntry,
  IFTSManager,
  FTSSearchOptions,
  FTSSearchResult,
  FTSStats,
  FTSConfig,
  IFTSQueryBuilder
} from './fts-types.js';
import {
  FTSError,
  FTSQueryError,
  FTSIndexError,
  DEFAULT_FTS_CONFIG
} from './fts-types.js';

/**
 * SQLite FTS Manager - Handles full-text search with ranking and relevance
 */
export class FTSManager implements IFTSManager {
  private db: Database;
  private config: FTSConfig;
  private queryBuilder: FTSQueryBuilder;
  private isInitialized: boolean = false;
  private currentWorkspaceId: string;

  constructor(db: Database, currentWorkspaceId: string, config: Partial<FTSConfig> = {}) {
    this.db = db;
    this.currentWorkspaceId = currentWorkspaceId;
    this.config = { ...DEFAULT_FTS_CONFIG, ...config };
    this.queryBuilder = new FTSQueryBuilder();
  }

  /**
   * Initialize FTS virtual table and indexes
   */
  async initializeFTS(): Promise<void> {
    try {
      // Bun's SQLite always has FTS5 compiled in - proceed directly to table creation
      // Create FTS virtual table
      const createFTSTable = `
        CREATE VIRTUAL TABLE IF NOT EXISTS ${this.config.tableName}
        USING fts5(
          id UNINDEXED,
          workspace_id UNINDEXED,
          description,
          project,
          git_branch,
          tags,
          timestamp UNINDEXED,
          content='checkpoints',
          content_rowid='rowid',
          tokenize='${this.config.tokenizer}'
        )
      `;

      this.db.run(createFTSTable);

      // Create triggers to keep FTS table in sync with checkpoints
      this.createFTSTriggers();

      // Populate FTS table with existing data
      await this.populateInitialFTSData();

      // Create supporting indexes for performance
      this.createSupportingIndexes();

      this.isInitialized = true;

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new FTSIndexError(`Failed to initialize FTS: ${message}`);
    }
  }

  /**
   * Create triggers to automatically maintain FTS index
   */
  private createFTSTriggers(): void {
    // Insert trigger
    const insertTrigger = `
      CREATE TRIGGER IF NOT EXISTS fts_insert_trigger
      AFTER INSERT ON checkpoints
      BEGIN
        INSERT INTO ${this.config.tableName} (
          id, workspace_id, description, project, git_branch, tags, timestamp
        ) VALUES (
          NEW.id, NEW.workspace_id, NEW.description, NEW.project, NEW.git_branch, NEW.tags, NEW.timestamp
        );
      END
    `;

    // Update trigger
    const updateTrigger = `
      CREATE TRIGGER IF NOT EXISTS fts_update_trigger
      AFTER UPDATE ON checkpoints
      BEGIN
        DELETE FROM ${this.config.tableName} WHERE id = OLD.id AND workspace_id = OLD.workspace_id;
        INSERT INTO ${this.config.tableName} (
          id, workspace_id, description, project, git_branch, tags, timestamp
        ) VALUES (
          NEW.id, NEW.workspace_id, NEW.description, NEW.project, NEW.git_branch, NEW.tags, NEW.timestamp
        );
      END
    `;

    // Delete trigger
    const deleteTrigger = `
      CREATE TRIGGER IF NOT EXISTS fts_delete_trigger
      AFTER DELETE ON checkpoints
      BEGIN
        DELETE FROM ${this.config.tableName} WHERE id = OLD.id AND workspace_id = OLD.workspace_id;
      END
    `;

    this.db.run(insertTrigger);
    this.db.run(updateTrigger);
    this.db.run(deleteTrigger);
  }

  /**
   * Populate FTS table with existing checkpoint data
   */
  private async populateInitialFTSData(): Promise<void> {
    // Clear existing FTS data
    this.db.run(`DELETE FROM ${this.config.tableName}`);

    // Insert all existing checkpoints
    const insertFTSData = `
      INSERT INTO ${this.config.tableName} (
        id, workspace_id, description, project, git_branch, tags, timestamp
      )
      SELECT id, workspace_id, description, project, git_branch, tags, timestamp
      FROM checkpoints
    `;

    this.db.run(insertFTSData);
  }

  /**
   * Create supporting indexes for FTS performance
   */
  private createSupportingIndexes(): void {
    // Index for workspace filtering in FTS results
    const workspaceIndex = `
      CREATE INDEX IF NOT EXISTS idx_fts_workspace_timestamp
      ON ${this.config.tableName}(workspace_id, timestamp DESC)
    `;

    try {
      this.db.run(workspaceIndex);
    } catch (error) {
      // FTS5 tables may not support traditional indexes
      console.warn('Could not create FTS workspace index:', error);
    }
  }

  /**
   * Check if FTS is properly configured and available
   */
  async isFTSEnabled(): Promise<boolean> {
    try {
      if (!this.isInitialized) {
        return false;
      }

      // Check if FTS table exists and is accessible
      const tableCheck = this.db.prepare(`
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
      `).get(this.config.tableName);

      return !!tableCheck;
    } catch (error) {
      return false;
    }
  }

  /**
   * Perform FTS search with ranking and relevance
   */
  async searchWithFTS(options: FTSSearchOptions): Promise<FTSSearchResult[]> {
    if (!await this.isFTSEnabled()) {
      throw new FTSError("FTS not available", "FTS_NOT_ENABLED");
    }

    try {
      // Validate and build FTS query
      const ftsQuery = this.queryBuilder.buildFTSQuery(options);

      // Build SQL query with FTS and ranking
      const sql = this.buildSearchSQL(options, ftsQuery);
      const params = this.buildSearchParams(options, ftsQuery);

      // Execute FTS search
      const stmt = this.db.prepare(sql);
      const rows = stmt.all(params) as any[];

      // Convert to FTS search results
      return rows.map(row => this.rowToFTSResult(row, options));

    } catch (error) {
      if (error instanceof FTSQueryError) {
        throw error;
      }
      const message = error instanceof Error ? error.message : String(error);
      throw new FTSError(`FTS search failed: ${message}`, "SEARCH_ERROR");
    }
  }

  /**
   * Build SQL query for FTS search with ranking
   */
  private buildSearchSQL(options: FTSSearchOptions, ftsQuery: string): string {
    const { workspace, limit = 50, offset = 0, includeScore = false } = options;

    let sql = `
      SELECT
        c.id, c.workspace_id, c.workspace_path, c.workspace_name,
        c.timestamp, c.description, c.project, c.git_branch, c.git_commit,
        c.tags, c.files, c.sync_status, c.remote_id, c.last_synced_at, c.version,
        c.created_at, c.updated_at
    `;

    // Add relevance score if requested
    if (includeScore) {
      sql += `, rank AS relevance_score`;
    }

    sql += `
      FROM ${this.config.tableName} fts
      JOIN checkpoints c ON (c.id = fts.id AND c.workspace_id = fts.workspace_id)
      WHERE fts MATCH $fts_query
    `;

    // Add workspace filtering
    if (workspace === 'current' || (workspace && workspace !== 'all')) {
      sql += ' AND c.workspace_id = $workspace_id';
    }

    // Add minimum relevance filtering
    if (options.minRelevance && includeScore) {
      sql += ' AND rank >= $min_relevance';
    }

    // Order by relevance (rank) - lower rank = more relevant in FTS5
    sql += ' ORDER BY rank ASC';

    // Add pagination
    sql += ' LIMIT $limit OFFSET $offset';

    return sql;
  }

  /**
   * Build parameters for FTS search query
   */
  private buildSearchParams(options: FTSSearchOptions, ftsQuery: string): Record<string, any> {
    const params: Record<string, any> = {
      $fts_query: ftsQuery,
      $limit: options.limit || 50,
      $offset: options.offset || 0
    };

    // Add workspace parameter
    if (options.workspace === 'current') {
      params.$workspace_id = this.currentWorkspaceId;
    } else if (options.workspace && options.workspace !== 'all') {
      params.$workspace_id = options.workspace;
    }

    // Add minimum relevance parameter
    if (options.minRelevance) {
      params.$min_relevance = options.minRelevance;
    }

    return params;
  }

  /**
   * Convert database row to FTS search result
   */
  private rowToFTSResult(row: any, options: FTSSearchOptions): FTSSearchResult {
    const result: FTSSearchResult = {
      id: row.id,
      workspaceId: row.workspace_id,
      workspacePath: row.workspace_path,
      workspaceName: row.workspace_name,
      timestamp: row.timestamp,
      description: row.description,
      project: row.project,
      gitBranch: row.git_branch,
      gitCommit: row.git_commit,
      tags: row.tags ? JSON.parse(row.tags) : [],
      files: row.files ? JSON.parse(row.files) : [],
      syncStatus: row.sync_status,
      remoteId: row.remote_id,
      lastSyncedAt: row.last_synced_at,
      version: row.version,
      createdAt: row.created_at,
      updatedAt: row.updated_at
    };

    // Add relevance score if included
    if (options.includeScore && row.relevance_score !== undefined) {
      // Convert FTS5 rank to 0-1 relevance score (lower rank = higher relevance)
      result.relevanceScore = Math.max(0, Math.min(1, 1 - (row.relevance_score / 100)));
    }

    // Add highlighted description
    if (row.description) {
      result.highlightedDescription = this.highlightMatches(
        row.description,
        options.query
      );
    }

    // Identify matched fields (simplified - could be enhanced)
    result.matchedFields = this.identifyMatchedFields(row, options.query);

    return result;
  }

  /**
   * Highlight search matches in text
   */
  private highlightMatches(text: string, query: string): string {
    // Simple highlighting - could be enhanced with proper FTS highlighting
    const terms = query.split(/\s+/).filter(term =>
      !['AND', 'OR', 'NOT'].includes(term.toUpperCase())
    );

    let highlighted = text;
    for (const term of terms) {
      const cleanTerm = term.replace(/[*"()]/g, '');
      if (cleanTerm) {
        const regex = new RegExp(`(${cleanTerm})`, 'gi');
        highlighted = highlighted.replace(regex, '<mark>$1</mark>');
      }
    }

    return highlighted;
  }

  /**
   * Identify which fields matched the search query
   */
  private identifyMatchedFields(row: any, query: string): string[] {
    const fields: string[] = [];
    const queryLower = query.toLowerCase();

    if (row.description && row.description.toLowerCase().includes(queryLower)) {
      fields.push('description');
    }
    if (row.project && row.project.toLowerCase().includes(queryLower)) {
      fields.push('project');
    }
    if (row.git_branch && row.git_branch.toLowerCase().includes(queryLower)) {
      fields.push('git_branch');
    }
    if (row.tags && row.tags.toLowerCase().includes(queryLower)) {
      fields.push('tags');
    }

    return fields;
  }

  /**
   * Rebuild FTS index (for maintenance or after schema changes)
   */
  async rebuildFTSIndex(): Promise<void> {
    if (!await this.isFTSEnabled()) {
      throw new FTSError("FTS not available", "FTS_NOT_ENABLED");
    }

    try {
      // Use FTS5 rebuild command
      this.db.run(`INSERT INTO ${this.config.tableName}(${this.config.tableName}) VALUES('rebuild')`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new FTSIndexError(`Failed to rebuild FTS index: ${message}`);
    }
  }

  /**
   * Get FTS performance statistics
   */
  async getFTSStats(): Promise<FTSStats> {
    if (!await this.isFTSEnabled()) {
      throw new FTSError("FTS not available", "FTS_NOT_ENABLED");
    }

    try {
      // Get document count
      const docCount = this.db.prepare(`SELECT COUNT(*) as count FROM ${this.config.tableName}`).get() as any;

      // Get index size (approximation)
      const indexSize = this.db.prepare(`
        SELECT page_count * page_size as size
        FROM pragma_page_count('${this.config.tableName}'), pragma_page_size
      `).get() as any;

      return {
        totalDocuments: docCount.count,
        uniqueTerms: 0, // TODO: Could query FTS internal tables for this
        indexSize: indexSize?.size || 0,
        lastRebuild: undefined, // TODO: Track rebuild timestamp
        avgQueryTime: undefined // TODO: Track query performance
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new FTSError(`Failed to get FTS stats: ${message}`, "STATS_ERROR");
    }
  }

  /**
   * Add/update document in FTS index
   */
  async updateFTSDocument(checkpointId: string, entry: CheckpointEntry): Promise<void> {
    // This is handled automatically by triggers, but could be called manually
    if (!await this.isFTSEnabled()) {
      return; // Fail silently if FTS not available
    }

    try {
      // Delete existing entry if any
      this.db.run(`
        DELETE FROM ${this.config.tableName}
        WHERE id = ? AND workspace_id = ?
      `, [checkpointId, entry.workspaceId || '']);

      // Insert new entry
      const stmt = this.db.prepare(`
        INSERT INTO ${this.config.tableName} (
          id, workspace_id, description, project, git_branch, tags, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      stmt.run(
        checkpointId,
        entry.workspaceId || '',
        entry.description,
        entry.project || '',
        entry.gitBranch || '',
        JSON.stringify(entry.tags || []),
        entry.timestamp
      );
    } catch (error) {
      // Don't throw - FTS updates should not break main functionality
      console.warn('FTS document update failed:', error);
    }
  }

  /**
   * Remove document from FTS index
   */
  async removeFTSDocument(checkpointId: string): Promise<void> {
    // This is handled automatically by triggers
    if (!await this.isFTSEnabled()) {
      return;
    }

    try {
      this.db.run(`DELETE FROM ${this.config.tableName} WHERE id = ?`, [checkpointId]);
    } catch (error) {
      console.warn('FTS document removal failed:', error);
    }
  }

  /**
   * Optimize FTS index for better performance
   */
  async optimizeFTSIndex(): Promise<void> {
    if (!await this.isFTSEnabled()) {
      throw new FTSError("FTS not available", "FTS_NOT_ENABLED");
    }

    try {
      // Use FTS5 optimize command
      this.db.run(`INSERT INTO ${this.config.tableName}(${this.config.tableName}) VALUES('optimize')`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new FTSIndexError(`Failed to optimize FTS index: ${message}`);
    }
  }
}

/**
 * FTS Query Builder - Handles query construction and validation
 */
export class FTSQueryBuilder implements IFTSQueryBuilder {
  /**
   * Build FTS query string from search options
   */
  buildFTSQuery(options: FTSSearchOptions): string {
    let query = options.query.trim();

    if (!query) {
      throw new FTSQueryError("Search query cannot be empty", query);
    }

    // Validate query syntax
    const validation = this.validateFTSQuery(query);
    if (!validation.valid) {
      throw new FTSQueryError(`Invalid query: ${validation.errors.join(', ')}`, query);
    }

    // Handle exact phrase matching
    if (options.exactPhrase && !query.includes('"')) {
      query = `"${query}"`;
    }

    // Handle operator preference
    if (options.operator && !query.includes(' AND ') && !query.includes(' OR ')) {
      const terms = query.split(/\s+/);
      if (terms.length > 1) {
        query = terms.join(` ${options.operator} `);
      }
    }

    // Handle prefix matching
    if (!query.includes('*') && !query.includes('"')) {
      // Add prefix matching to terms that don't have special syntax
      const terms = query.split(/\s+/);
      const prefixTerms = terms.map(term => {
        if (!['AND', 'OR', 'NOT'].includes(term.toUpperCase()) &&
            !term.includes('*') && !term.includes('"')) {
          return `${term}*`;
        }
        return term;
      });
      query = prefixTerms.join(' ');
    }

    return query;
  }

  /**
   * Escape special FTS characters in user input
   */
  escapeFTSQuery(query: string): string {
    // Escape FTS5 special characters: " * ( ) AND OR NOT
    return query.replace(/[*"()]/g, '\\$&')
                .replace(/\b(AND|OR|NOT)\b/gi, '\\$&');
  }

  /**
   * Parse and validate FTS query syntax
   */
  validateFTSQuery(query: string): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check for empty query
    if (!query.trim()) {
      errors.push("Query cannot be empty");
      return { valid: false, errors };
    }

    // Check for unmatched quotes
    const quoteCount = (query.match(/"/g) || []).length;
    if (quoteCount % 2 !== 0) {
      errors.push("Unmatched quotes in query");
    }

    // Check for unmatched parentheses
    let parenBalance = 0;
    for (const char of query) {
      if (char === '(') parenBalance++;
      if (char === ')') parenBalance--;
      if (parenBalance < 0) {
        errors.push("Unmatched closing parenthesis");
        break;
      }
    }
    if (parenBalance > 0) {
      errors.push("Unmatched opening parenthesis");
    }

    // Check for invalid operator usage
    if (/\b(AND|OR|NOT)\s*$/.test(query.trim())) {
      errors.push("Query cannot end with an operator");
    }

    if (/^\s*(AND|OR|NOT)\b/.test(query.trim())) {
      errors.push("Query cannot start with an operator");
    }

    return { valid: errors.length === 0, errors };
  }
}