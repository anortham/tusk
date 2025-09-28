/**
 * SQLite-based Journal with Multi-Workspace and Cross-Platform Support
 * Provides persistent storage for developer checkpoints with workspace isolation
 */

import { Database } from "bun:sqlite";
import { existsSync, mkdirSync, readFileSync, statSync, realpathSync } from "fs";
import { homedir } from "os";
import { join, normalize, resolve, dirname, basename } from "path";
import { createHash } from "crypto";
import { spawnSync } from "bun";
import { FTSManager } from "./fts-manager.js";
import type { FTSSearchOptions, FTSSearchResult } from "./fts-types.js";

// Types for the SQLite journal implementation
export interface CheckpointEntry {
  id?: string;
  timestamp: string;
  description: string;
  project?: string;
  gitBranch?: string;
  gitCommit?: string;
  tags?: string[];
  files?: string[];

  // Workspace context (populated automatically)
  workspaceId?: string;
  workspacePath?: string;
  workspaceName?: string;

  // Sync fields for future API integration
  syncStatus?: 'local' | 'pending' | 'synced' | 'failed';
  remoteId?: string;
  lastSyncedAt?: string;
  version?: number;

  // Metadata
  createdAt?: string;
  updatedAt?: string;

  // Deduplication metadata (for consolidated entries)
  consolidationInfo?: {
    mergedEntries: number;
    mergedIds: string[];
    timeSpan: {
      earliest: string;
      latest: string;
    };
  };
}

export interface WorkspaceInfo {
  workspaceId: string;
  workspacePath: string;
  workspaceName: string;
  detectionMethod: 'git' | 'package' | 'cwd';
}

export interface QueryOptions {
  workspace?: string | 'current' | 'all';
  days?: number;
  from?: string;
  to?: string;
  project?: string;
  tags?: string[];
  limit?: number;
  offset?: number;
}

export interface StandupEntry {
  id?: string;
  date: string;
  style: string;
  content: string;
  checkpointIds: string[];
  workspaceId?: string;
  syncStatus?: 'local' | 'pending' | 'synced' | 'failed';
  remoteId?: string;
  lastSyncedAt?: string;
}

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
    this.workspaceInfo = this.detectWorkspace(cwd);
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

    // Optimize for performance
    this.db.run("PRAGMA synchronous = NORMAL");
    this.db.run("PRAGMA cache_size = 10000");
    this.db.run("PRAGMA temp_store = MEMORY");
  }

  /**
   * Initialize database schema with workspace support
   */
  private initializeSchema(): void {
    // Create checkpoints table with workspace isolation
    this.db.run(`
      CREATE TABLE IF NOT EXISTS checkpoints (
        -- Identity
        id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        workspace_path TEXT NOT NULL,
        workspace_name TEXT,

        -- Core fields
        timestamp TEXT NOT NULL,
        description TEXT NOT NULL,
        project TEXT,
        git_branch TEXT,
        git_commit TEXT,
        tags TEXT, -- JSON array
        files TEXT, -- JSON array with normalized paths

        -- Sync fields for future API
        sync_status TEXT DEFAULT 'local',
        remote_id TEXT,
        last_synced_at TEXT,
        version INTEGER DEFAULT 1,

        -- Metadata
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

        -- Composite primary key for workspace isolation
        PRIMARY KEY (workspace_id, id)
      )
    `);

    // Create standups table
    this.db.run(`
      CREATE TABLE IF NOT EXISTS standups (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        date TEXT NOT NULL,
        style TEXT NOT NULL,
        content TEXT NOT NULL,
        checkpoint_ids TEXT, -- JSON array

        -- Sync fields
        sync_status TEXT DEFAULT 'local',
        remote_id TEXT,
        last_synced_at TEXT,

        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create sync_log table for future API integration
    this.db.run(`
      CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        status TEXT NOT NULL,
        error TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create indexes for performance
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

      // Standup indexes
      "CREATE INDEX IF NOT EXISTS idx_standup_workspace_date ON standups(workspace_id, date DESC)",

      // Sync log indexes
      "CREATE INDEX IF NOT EXISTS idx_sync_log_workspace ON sync_log(workspace_id, timestamp DESC)",
    ];

    for (const indexSQL of indexes) {
      this.db.run(indexSQL);
    }
  }

  /**
   * Detect workspace context using git root, package.json, or cwd
   */
  private detectWorkspace(cwd: string): WorkspaceInfo {
    const normalizedCwd = this.normalizePath(cwd);

    // Try to find git repository root
    const gitRoot = this.findGitRoot(normalizedCwd);
    if (gitRoot) {
      return {
        workspaceId: this.hashPath(gitRoot),
        workspacePath: gitRoot,
        workspaceName: basename(gitRoot),
        detectionMethod: 'git',
      };
    }

    // Try to find package.json directory
    const packageRoot = this.findPackageRoot(normalizedCwd);
    if (packageRoot) {
      const packageName = this.getPackageName(packageRoot);
      return {
        workspaceId: this.hashPath(packageRoot),
        workspacePath: packageRoot,
        workspaceName: packageName || basename(packageRoot),
        detectionMethod: 'package',
      };
    }

    // Fall back to current working directory
    return {
      workspaceId: this.hashPath(normalizedCwd),
      workspacePath: normalizedCwd,
      workspaceName: basename(normalizedCwd),
      detectionMethod: 'cwd',
    };
  }

  /**
   * Find git repository root by walking up the directory tree
   */
  private findGitRoot(startPath: string): string | null {
    let currentPath = startPath;

    while (currentPath !== dirname(currentPath)) {
      const gitPath = join(currentPath, '.git');
      if (existsSync(gitPath)) {
        return this.normalizePath(currentPath);
      }
      currentPath = dirname(currentPath);
    }

    return null;
  }

  /**
   * Find package.json directory by walking up the directory tree
   */
  private findPackageRoot(startPath: string): string | null {
    let currentPath = startPath;

    while (currentPath !== dirname(currentPath)) {
      const packagePath = join(currentPath, 'package.json');
      if (existsSync(packagePath)) {
        return this.normalizePath(currentPath);
      }
      currentPath = dirname(currentPath);
    }

    return null;
  }

  /**
   * Get package name from package.json
   */
  private getPackageName(packageRoot: string): string | null {
    try {
      const packagePath = join(packageRoot, 'package.json');
      const packageContent = readFileSync(packagePath, 'utf-8');
      const packageJson = JSON.parse(packageContent);
      return packageJson.name || null;
    } catch {
      return null;
    }
  }

  /**
   * Normalize path for cross-platform consistency
   */
  normalizePath(path: string): string {
    // Check if it's already an absolute path (Windows or Unix)
    const isWindowsAbsolute = /^[A-Za-z]:[\\\/]/.test(path);
    const isUnixAbsolute = path.startsWith('/');
    const isUncPath = path.startsWith('\\\\') || path.startsWith('//');

    let resolved: string;

    if (isWindowsAbsolute || isUnixAbsolute || isUncPath) {
      // Already absolute, just normalize
      resolved = normalize(path);
    } else {
      // Relative path, resolve against cwd
      resolved = resolve(path);
    }

    // Resolve symlinks for consistent workspace detection
    try {
      if (existsSync(resolved)) {
        // Use realpathSync to properly resolve all symlinks in the path
        resolved = realpathSync(resolved);
      }
      // On macOS, normalize /private/var to /var for consistency
      if (process.platform === 'darwin' && resolved.startsWith('/private/var/')) {
        resolved = resolved.replace('/private/var/', '/var/');
      }
    } catch {
      // If we can't resolve the path, just use the resolved version
    }

    // Always use forward slashes for consistency
    return resolved.replace(/\\/g, '/');
  }

  /**
   * Create consistent hash for a path (case-insensitive on Windows)
   */
  hashPath(path: string): string {
    const normalized = this.normalizePath(path);
    // Make case-insensitive on Windows
    const forHashing = process.platform === 'win32' ? normalized.toLowerCase() : normalized;
    return createHash('sha256')
      .update(forHashing)
      .digest('hex')
      .slice(0, 12);
  }

  /**
   * Normalize file paths in arrays for cross-platform storage
   */
  private normalizePaths(paths: string[]): string[] {
    return paths.map(path => {
      const normalizedPath = this.normalizePath(path);
      // Convert absolute paths to relative paths from workspace root
      if (normalizedPath.startsWith(this.workspacePath)) {
        return normalizedPath.substring(this.workspacePath.length + 1); // +1 to remove leading slash
      }
      return normalizedPath;
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
      $files: JSON.stringify(this.normalizePaths(entry.files || [])),
      $sync_status: entry.syncStatus || 'local',
      $version: entry.version || 1,
      $created_at: now,
      $updated_at: now,
    });
  }

  /**
   * Save multiple checkpoints in a batch operation
   */
  async saveCheckpointBatch(entries: CheckpointEntry[]): Promise<void> {
    const insertStmt = this.db.prepare(`
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

    const batchInsert = this.db.transaction((entries: CheckpointEntry[]) => {
      const now = new Date().toISOString();

      for (const entry of entries) {
        // Validate entry
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

        insertStmt.run({
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
          $files: JSON.stringify(this.normalizePaths(entry.files || [])),
          $sync_status: entry.syncStatus || 'local',
          $version: entry.version || 1,
          $created_at: now,
          $updated_at: now,
        });
      }
    });

    batchInsert(entries);
  }

  /**
   * Get recent checkpoints with workspace-aware filtering
   */
  async getRecentCheckpoints(options: QueryOptions = {}): Promise<CheckpointEntry[]> {
    const {
      workspace = 'current',
      days = 7,
      from,
      to,
      project,
      tags,
      limit = 1000,
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

    // Add date filtering with from/to range support
    if (from && to) {
      query += ` AND datetime(timestamp) BETWEEN datetime($from) AND datetime($to)`;
      params.$from = from;
      params.$to = to;
    } else if (from) {
      query += ` AND datetime(timestamp) >= datetime($from)`;
      params.$from = from;
    } else if (to) {
      query += ` AND datetime(timestamp) <= datetime($to)`;
      params.$to = to;
    } else {
      // Default to days-based filtering when no date range specified
      query += ` AND datetime(timestamp) > datetime('now', '-' || $days || ' days')`;
      params.$days = days;
    }

    // Add workspace filtering
    if (workspace === 'current') {
      query += ' AND workspace_id = $workspace_id';
      params.$workspace_id = this.workspaceId;
    } else if (workspace !== 'all' && workspace) {
      // Specific workspace path
      const targetWorkspaceId = this.hashPath(workspace);
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

    // Add ordering, limit, and offset
    query += ` ORDER BY timestamp DESC LIMIT $limit OFFSET $offset`;
    params.$limit = limit;
    params.$offset = offset;

    const stmt = this.db.prepare(query);
    const rows = stmt.all(params) as any[];

    return rows.map(row => ({
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
    }));
  }

  /**
   * Get summary of all workspaces
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
        workspace_name,
        workspace_path,
        COUNT(*) as checkpoint_count,
        MAX(timestamp) as last_activity
      FROM checkpoints
      GROUP BY workspace_id
      ORDER BY last_activity DESC
    `;

    const rows = this.db.prepare(query).all() as any[];

    // Get projects for each workspace
    const workspacesWithProjects = rows.map(row => {
      const projectsQuery = `
        SELECT DISTINCT project
        FROM checkpoints
        WHERE workspace_id = ? AND project IS NOT NULL
        ORDER BY project
      `;
      const projectRows = this.db.prepare(projectsQuery).all(row.workspace_id) as any[];
      const projects = projectRows.map(p => p.project);

      return {
        id: row.workspace_id,
        path: row.workspace_path,
        name: row.workspace_name,
        entryCount: row.checkpoint_count,
        lastActivity: row.last_activity,
        projects,
      };
    });

    return workspacesWithProjects;
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
   * Enhanced FTS search with full options support
   */
  async searchWithFTS(options: FTSSearchOptions): Promise<FTSSearchResult[]> {
    if (!this.ftsEnabled) {
      throw new Error('FTS not available - use searchCheckpoints() for automatic fallback');
    }

    // Set current workspace context
    if (options.workspace === 'current') {
      options.workspace = this.workspaceId;
    }

    return this.ftsManager.searchWithFTS(options);
  }

  /**
   * Get FTS statistics and status
   */
  async getFTSStats() {
    if (!this.ftsEnabled) {
      return null;
    }
    return this.ftsManager.getFTSStats();
  }

  /**
   * Check if FTS is enabled and available
   */
  isFTSEnabled(): boolean {
    return this.ftsEnabled;
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
      const targetWorkspaceId = this.hashPath(workspace);
      sql += ' AND workspace_id = $workspace_id';
      params.$workspace_id = targetWorkspaceId;
    }

    sql += ' ORDER BY timestamp DESC LIMIT $limit OFFSET $offset';
    params.$limit = limit;
    params.$offset = offset;

    const stmt = this.db.prepare(sql);
    const rows = stmt.all(params) as any[];

    return rows.map(row => ({
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

  // Testing/debugging methods

  /**
   * Get list of database tables (for testing)
   */
  async getTables(): Promise<string[]> {
    const query = "SELECT name FROM sqlite_master WHERE type='table'";
    const rows = this.db.prepare(query).all() as any[];
    return rows.map(row => row.name);
  }

  /**
   * Get current journal mode (for testing)
   */
  async getJournalMode(): Promise<string> {
    const result = this.db.prepare("PRAGMA journal_mode").get() as any;
    return result.journal_mode;
  }

  /**
   * Get busy timeout (for testing)
   */
  async getBusyTimeout(): Promise<number> {
    const result = this.db.prepare("PRAGMA busy_timeout").get() as any;
    return result.timeout;
  }

  /**
   * Get list of indexes (for testing)
   */
  async getIndexes(): Promise<string[]> {
    const query = "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'";
    const rows = this.db.prepare(query).all() as any[];
    return rows.map(row => row.name);
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

// Backward compatibility exports to match existing journal.ts API
export type JournalEntry = CheckpointEntry;

export function generateId(): string {
  const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const randomSuffix = Math.random().toString(36).slice(2, 8);
  return `${timestamp}_${randomSuffix}`;
}

// Default instance for backward compatibility
let defaultJournal: JournalDB | null = null;

function getDefaultJournal(): JournalDB {
  if (!defaultJournal) {
    // Check if we're in test mode
    const isTestMode = process.env.TUSK_TEST_MODE === 'true';
    const testDir = process.env.TUSK_TEST_DIR;

    if (isTestMode && testDir) {
      // Use test directory for database file
      const testDbPath = join(testDir, 'journal.db');
      defaultJournal = new JournalDB({ dbPath: testDbPath });
    } else {
      defaultJournal = new JournalDB();
    }
  }
  return defaultJournal;
}

// Test utility to reset the default journal instance
export function __resetDefaultJournal(): void {
  defaultJournal = null;
}

export async function saveEntry(entry: JournalEntry): Promise<void> {
  return getDefaultJournal().saveCheckpoint(entry);
}

export async function getRecentEntries(filter: { days?: number; from?: string; to?: string; project?: string; workspace?: string | 'current' | 'all' } = {}): Promise<JournalEntry[]> {
  return getDefaultJournal().getRecentCheckpoints({
    days: filter.days,
    from: filter.from,
    to: filter.to,
    project: filter.project,
    workspace: filter.workspace || 'current',
  });
}

export async function searchEntries(query: string, options: { limit?: number; workspace?: string | 'current' | 'all' } = {}): Promise<JournalEntry[]> {
  const { limit = 20, workspace = 'current' } = options;
  return getDefaultJournal().searchCheckpoints(query, { limit, workspace });
}

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

// ===== RELEVANCE SCORING SYSTEM =====

export interface RelevanceWeights {
  recency: number;      // Weight for how recent the entry is (0-1)
  tags: number;         // Weight for tag importance (0-1)
  completion: number;   // Weight for completion indicators (0-1)
  gitActivity: number;  // Weight for git commit activity (0-1)
  uniqueness: number;   // Weight for unique/non-duplicate content (0-1)
}

export const DEFAULT_RELEVANCE_WEIGHTS: RelevanceWeights = {
  recency: 0.3,
  tags: 0.2,
  completion: 0.25,
  gitActivity: 0.1,
  uniqueness: 0.15,
};

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

export async function getJournalStats(): Promise<{
  totalEntries: number;
  entriesThisWeek: number;
  entriesThisMonth: number;
  projects: string[];
  workspaces: number;
  oldestEntry?: string;
  newestEntry?: string;
}> {
  return getDefaultJournal().getJournalStats();
}

export async function getWorkspaceSummary(): Promise<Array<{
  id: string;
  path: string;
  name: string;
  entryCount: number;
  lastActivity?: string;
  projects: string[];
}>> {
  return getDefaultJournal().getWorkspaceSummary();
}

export function getCurrentWorkspace(): { id: string; path: string; name: string } {
  return getDefaultJournal().getCurrentWorkspace();
}