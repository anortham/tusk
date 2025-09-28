/**
 * Core Journal Database Operations for Tusk Journal System
 * SQLite-based database with multi-workspace support and cross-platform compatibility
 */

import { Database } from "bun:sqlite";
import { existsSync, mkdirSync } from "fs";
import { homedir } from "os";
import { join } from "path";
import { FTSManager } from "./fts-manager.js";
import type { FTSSearchOptions, FTSSearchResult } from "./fts-types.js";
import type { CheckpointEntry, WorkspaceInfo, QueryOptions, StandupEntry } from "./types.js";
import { detectWorkspace, normalizePaths } from "./workspace-utils.js";

/**
 * SQLite-based Journal Database with Multi-Workspace Support
 */
export class JournalDB {
  private db: Database;
  public readonly workspaceId: string;
  private readonly workspacePath: string;
  private readonly workspaceName: string;
  private readonly workspaceInfo: WorkspaceInfo;
  private ftsManager: FTSManager;
  private ftsEnabled: boolean = false;

  constructor(options: { cwd?: string; testMode?: boolean; dbPath?: string } = {}) {
    // Initialize workspace context
    const cwd = options.cwd || process.cwd();
    this.workspaceInfo = detectWorkspace(cwd);
    this.workspaceId = this.workspaceInfo.workspaceId;
    this.workspacePath = this.workspaceInfo.workspacePath;
    this.workspaceName = this.workspaceInfo.workspaceName;

    // Initialize database
    let dbPath: string;
    if (options.testMode) {
      // Use in-memory database for tests
      dbPath = ':memory:';
    } else if (options.dbPath) {
      dbPath = options.dbPath;
    } else {
      dbPath = this.getDatabasePath();
    }
    this.db = new Database(dbPath);

    // Configure for concurrent access and performance
    this.configureSQLite();

    // Initialize schema
    this.initializeSchema();

    // Initialize FTS manager and setup
    this.ftsManager = new FTSManager(this.db, this.workspaceId);
    this.initializeFTSAsync();
  }

  /**
   * Get the cross-platform database path
   */
  getDatabasePath(): string {
    const home = homedir();
    const tuskDir = join(home, '.tusk');

    // Ensure directory exists
    if (!existsSync(tuskDir)) {
      mkdirSync(tuskDir, { recursive: true });
    }

    return join(tuskDir, 'journal.db');
  }

  /**
   * Configure SQLite for optimal performance and concurrency
   */
  private configureSQLite(): void {
    // Enable WAL mode for better concurrency
    this.db.run("PRAGMA journal_mode = WAL");

    // Set busy timeout for concurrent access
    this.db.run("PRAGMA busy_timeout = 5000");

    // Enable foreign key constraints
    this.db.run("PRAGMA foreign_keys = ON");

    // Optimize for better performance
    this.db.run("PRAGMA synchronous = NORMAL");
    this.db.run("PRAGMA cache_size = 10000");
    this.db.run("PRAGMA temp_store = memory");
  }

  /**
   * Initialize database schema with workspace support
   */
  private initializeSchema(): void {
    // Create checkpoints table with workspace isolation
    this.db.run(`
      CREATE TABLE IF NOT EXISTS checkpoints (
        id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        workspace_path TEXT NOT NULL,
        workspace_name TEXT,
        timestamp TEXT NOT NULL,
        description TEXT NOT NULL,
        project TEXT,
        git_branch TEXT,
        git_commit TEXT,
        tags TEXT,  -- JSON array
        files TEXT, -- JSON array

        -- Sync fields for future API integration
        sync_status TEXT DEFAULT 'local',
        remote_id TEXT,
        last_synced_at TEXT,
        version INTEGER DEFAULT 1,

        -- Metadata
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        -- Composite primary key for workspace isolation
        PRIMARY KEY (workspace_id, id)
      )
    `);

    // Create standalone standups table
    this.db.run(`
      CREATE TABLE IF NOT EXISTS standups (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        date TEXT NOT NULL,
        style TEXT NOT NULL,
        content TEXT NOT NULL,
        checkpoint_ids TEXT, -- JSON array
        sync_status TEXT DEFAULT 'local',
        remote_id TEXT,
        last_synced_at TEXT,
        created_at TEXT NOT NULL
      )
    `);

    // Create indexes for optimal performance
    this.createIndexes();
  }

  /**
   * Initialize FTS asynchronously (non-blocking)
   */
  private async initializeFTSAsync(): Promise<void> {
    try {
      await this.ftsManager.initializeFTS();
      this.ftsEnabled = await this.ftsManager.isFTSEnabled();
      if (this.ftsEnabled) {
        console.error("✅ FTS enabled for enhanced search");
      }
    } catch (error) {
      console.error("⚠️ FTS initialization failed, using LIKE fallback:", error instanceof Error ? error.message : error);
      this.ftsEnabled = false;
    }
  }

  /**
   * Create database indexes for optimal query performance
   */
  private createIndexes(): void {
    const indexes = [
      // Primary workspace queries
      "CREATE INDEX IF NOT EXISTS idx_workspace_timestamp ON checkpoints(workspace_id, timestamp DESC)",
      "CREATE INDEX IF NOT EXISTS idx_workspace_sync ON checkpoints(workspace_id, sync_status)",
      "CREATE INDEX IF NOT EXISTS idx_workspace_project ON checkpoints(workspace_id, project)",

      // Global queries (cross-workspace)
      "CREATE INDEX IF NOT EXISTS idx_global_recent ON checkpoints(timestamp DESC)",
      "CREATE INDEX IF NOT EXISTS idx_global_sync ON checkpoints(sync_status, timestamp DESC)",

      // Search optimization
      "CREATE INDEX IF NOT EXISTS idx_search_workspace ON checkpoints(workspace_id, description, project, git_branch)",

      // Standup indexes
      "CREATE INDEX IF NOT EXISTS idx_standup_workspace ON standups(workspace_id, date DESC)",
    ];

    indexes.forEach(indexSql => {
      try {
        this.db.run(indexSql);
      } catch (error) {
        console.error("Warning: Failed to create index:", error instanceof Error ? error.message : error);
      }
    });
  }

  /**
   * Generate unique ID for entries
   */
  private generateId(): string {
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
    const randomSuffix = Math.random().toString(36).slice(2, 8);
    return `${timestamp}_${randomSuffix}`;
  }

  /**
   * Get workspace information
   */
  async getWorkspaceInfo(): Promise<WorkspaceInfo> {
    return this.workspaceInfo;
  }

  /**
   * Save a checkpoint entry to the database
   */
  async saveCheckpoint(entry: CheckpointEntry): Promise<void> {
    // Validate required fields and collect all errors
    const errors: string[] = [];

    if (!entry.description || entry.description.trim() === '') {
      errors.push('Checkpoint description is required');
    }

    if (!entry.timestamp || isNaN(Date.parse(entry.timestamp))) {
      errors.push('Valid timestamp is required');
    }

    if (errors.length > 0) {
      throw new Error(errors.join('; '));
    }

    const id = entry.id || this.generateId();
    const now = new Date().toISOString();

    const stmt = this.db.prepare(`
      INSERT INTO checkpoints (
        id, workspace_id, workspace_path, workspace_name,
        timestamp, description, project, git_branch, git_commit,
        tags, files, sync_status, version, created_at, updated_at
      ) VALUES (
        $id, $workspace_id, $workspace_path, $workspace_name,
        $timestamp, $description, $project, $git_branch, $git_commit,
        $tags, $files, $sync_status, $version, $created_at, $updated_at
      )
    `);

    stmt.run({
      $id: id,
      $workspace_id: this.workspaceId,
      $workspace_path: this.workspacePath,
      $workspace_name: this.workspaceName,
      $timestamp: entry.timestamp,
      $description: entry.description,
      $project: entry.project || null,
      $git_branch: entry.gitBranch || null,
      $git_commit: entry.gitCommit || null,
      $tags: JSON.stringify(entry.tags || []),
      $files: JSON.stringify(normalizePaths(entry.files || [], this.workspacePath)),
      $sync_status: entry.syncStatus || 'local',
      $version: entry.version || 1,
      $created_at: now,
      $updated_at: now,
    });
  }

  /**
   * Get recent checkpoints based on filters
   */
  async getRecentCheckpoints(options: QueryOptions = {}): Promise<CheckpointEntry[]> {
    const {
      workspace = 'current',
      days = 7,
      from,
      to,
      project,
      tags,
      limit = 50,
      offset = 0
    } = options;

    let query = `
      SELECT
        id, workspace_id, workspace_path, workspace_name,
        timestamp, description, project, git_branch, git_commit,
        tags, files, sync_status, remote_id, last_synced_at, version,
        created_at, updated_at
      FROM checkpoints
      WHERE 1=1
    `;

    const params: Record<string, any> = {};

    // Add workspace filtering
    if (workspace === 'current') {
      query += ' AND workspace_id = $workspace_id';
      params.$workspace_id = this.workspaceId;
    } else if (workspace !== 'all' && workspace) {
      // Specific workspace path
      const { hashPath } = await import('./workspace-utils.js');
      const targetWorkspaceId = hashPath(workspace);
      query += ' AND workspace_id = $workspace_id';
      params.$workspace_id = targetWorkspaceId;
    }
    // For 'all', no workspace filtering

    // Add project filtering
    if (project) {
      query += ' AND project = $project';
      params.$project = project;
    }

    // Add tag filtering
    if (tags && tags.length > 0) {
      const tagConditions = tags.map((_, index) =>
        `json_extract(tags, '$') LIKE '%' || $tag${index} || '%'`
      ).join(' AND ');
      query += ` AND (${tagConditions})`;

      tags.forEach((tag, index) => {
        params[`$tag${index}`] = tag;
      });
    }

    // Add date filtering
    if (from || to || days) {
      if (from && to) {
        query += ' AND date(timestamp) BETWEEN date($from) AND date($to)';
        params.$from = from;
        params.$to = to;
      } else if (from) {
        query += ' AND date(timestamp) >= date($from)';
        params.$from = from;
      } else if (to) {
        query += ' AND date(timestamp) <= date($to)';
        params.$to = to;
      } else if (days) {
        query += ` AND datetime(timestamp) > datetime('now', '-${days} days')`;
      }
    }

    query += ' ORDER BY timestamp DESC LIMIT $limit OFFSET $offset';
    params.$limit = limit;
    params.$offset = offset;

    const stmt = this.db.prepare(query);
    const rows = stmt.all(params) as any[];

    return rows.map(row => this.rowToCheckpointEntry(row));
  }

  /**
   * Search checkpoints across workspaces with FTS support and LIKE fallback
   */
  async searchCheckpoints(query: string, options: QueryOptions = {}): Promise<CheckpointEntry[]> {
    // Try FTS search first if available
    if (this.ftsEnabled) {
      try {
        const ftsOptions: FTSSearchOptions = {
          query,
          workspace: options.workspace || 'current',
          limit: options.limit || 50,
          offset: options.offset || 0
        };

        const ftsResults = await this.ftsManager.searchWithFTS(ftsOptions);
        return ftsResults.map(result => this.ftsResultToCheckpointEntry(result));
      } catch (error) {
        console.error('FTS search failed, falling back to LIKE:', error instanceof Error ? error.message : error);
        // Fall through to LIKE search
      }
    }

    // Fallback to original LIKE-based search
    return this.searchCheckpointsWithLike(query, options);
  }

  /**
   * Original LIKE-based search for fallback compatibility
   */
  private async searchCheckpointsWithLike(query: string, options: QueryOptions = {}): Promise<CheckpointEntry[]> {
    const {
      workspace = 'current',
      limit = 50,
      offset = 0
    } = options;

    let sql = `
      SELECT
        id, workspace_id, workspace_path, workspace_name,
        timestamp, description, project, git_branch, git_commit,
        tags, files, sync_status, remote_id, last_synced_at, version,
        created_at, updated_at
      FROM checkpoints
      WHERE (
        description LIKE '%' || $query || '%' OR
        project LIKE '%' || $query || '%' OR
        git_branch LIKE '%' || $query || '%' OR
        git_commit LIKE '%' || $query || '%' OR
        tags LIKE '%' || $query || '%' OR
        files LIKE '%' || $query || '%'
      )
    `;

    const params: Record<string, any> = { $query: query };

    // Add workspace filtering
    if (workspace === 'current') {
      sql += ' AND workspace_id = $workspace_id';
      params.$workspace_id = this.workspaceId;
    } else if (workspace !== 'all' && workspace) {
      const { hashPath } = await import('./workspace-utils.js');
      const targetWorkspaceId = hashPath(workspace);
      sql += ' AND workspace_id = $workspace_id';
      params.$workspace_id = targetWorkspaceId;
    }

    sql += ' ORDER BY timestamp DESC LIMIT $limit OFFSET $offset';
    params.$limit = limit;
    params.$offset = offset;

    const stmt = this.db.prepare(sql);
    const rows = stmt.all(params) as any[];

    return rows.map(row => this.rowToCheckpointEntry(row));
  }

  /**
   * Get workspace summary with statistics
   */
  async getWorkspaceSummary(): Promise<Array<{
    id: string;
    path: string;
    name: string;
    entryCount: number;
    lastActivity?: string;
    projects: string[];
  }>> {
    const query = `
      SELECT
        workspace_id,
        workspace_path,
        workspace_name,
        COUNT(*) as entry_count,
        MAX(timestamp) as last_activity,
        GROUP_CONCAT(DISTINCT project) as projects
      FROM checkpoints
      WHERE project IS NOT NULL
      GROUP BY workspace_id, workspace_path, workspace_name
      ORDER BY last_activity DESC
    `;

    const rows = this.db.prepare(query).all() as any[];

    return rows.map(row => ({
      id: row.workspace_id,
      path: row.workspace_path,
      name: row.workspace_name,
      entryCount: row.entry_count,
      lastActivity: row.last_activity,
      projects: row.projects ? row.projects.split(',') : []
    }));
  }

  /**
   * Get journal statistics
   */
  async getJournalStats(): Promise<{
    totalEntries: number;
    entriesThisWeek: number;
    entriesThisMonth: number;
    projects: string[];
    workspaces: number;
    oldestEntry?: string;
    newestEntry?: string;
  }> {
    const totalQuery = 'SELECT COUNT(*) as count FROM checkpoints';
    const weekQuery = "SELECT COUNT(*) as count FROM checkpoints WHERE datetime(timestamp) > datetime('now', '-7 days')";
    const monthQuery = "SELECT COUNT(*) as count FROM checkpoints WHERE datetime(timestamp) > datetime('now', '-30 days')";
    const projectsQuery = 'SELECT DISTINCT project FROM checkpoints WHERE project IS NOT NULL';
    const workspacesQuery = 'SELECT COUNT(DISTINCT workspace_id) as count FROM checkpoints';
    const rangeQuery = 'SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM checkpoints';

    const total = (this.db.prepare(totalQuery).get() as any).count;
    const week = (this.db.prepare(weekQuery).get() as any).count;
    const month = (this.db.prepare(monthQuery).get() as any).count;
    const projects = (this.db.prepare(projectsQuery).all() as any[]).map(row => row.project);
    const workspaces = (this.db.prepare(workspacesQuery).get() as any).count;
    const range = this.db.prepare(rangeQuery).get() as any;

    return {
      totalEntries: total,
      entriesThisWeek: week,
      entriesThisMonth: month,
      projects,
      workspaces,
      oldestEntry: range.oldest,
      newestEntry: range.newest,
    };
  }

  /**
   * Convert FTS result to checkpoint entry for backward compatibility
   */
  private ftsResultToCheckpointEntry(result: FTSSearchResult): CheckpointEntry {
    return {
      id: result.id,
      workspaceId: result.workspaceId,
      workspacePath: result.workspacePath,
      workspaceName: result.workspaceName,
      timestamp: result.timestamp,
      description: result.description,
      project: result.project,
      gitBranch: result.gitBranch,
      gitCommit: result.gitCommit,
      tags: result.tags,
      files: result.files,
      syncStatus: result.syncStatus,
      remoteId: result.remoteId,
      lastSyncedAt: result.lastSyncedAt,
      version: result.version,
      createdAt: result.createdAt,
      updatedAt: result.updatedAt
    };
  }

  /**
   * Convert database row to checkpoint entry
   */
  private rowToCheckpointEntry(row: any): CheckpointEntry {
    return {
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
      updatedAt: row.updated_at,
    };
  }

  /**
   * Get current workspace information
   */
  getCurrentWorkspace(): { id: string; path: string; name: string } {
    return {
      id: this.workspaceId,
      path: this.workspacePath,
      name: this.workspaceName,
    };
  }

  /**
   * Close the database connection
   */
  close(): void {
    this.db.close();
  }
}

// Utility functions for backward compatibility
export function generateId(): string {
  const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `${timestamp}_${randomSuffix}`;
}