/**
 * Type definitions for Tusk Journal System
 * Core interfaces and types used throughout the application
 */

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

  // Session tracking fields
  sessionId?: string;
  entryType?: 'user-request' | 'session-marker' | 'auto-save' | 'progress' | 'completion';
  confidenceScore?: number; // 0.0-1.0 for auto-captured entries

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

// Relevance scoring interfaces
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

// Plan management types
export interface PlanSubTask {
  id: string;
  description: string;
  completed: boolean;
  checkpointIds: string[];  // Associated checkpoint IDs
  createdAt: number;
  completedAt?: number;
}

export interface Plan {
  id: string;
  workspace_id: string;
  title: string;
  content: string;
  status: 'active' | 'completed' | 'archived';
  progress_notes?: string;
  sub_tasks?: string;  // JSON serialized PlanSubTask[]
  checkpoint_count_at_last_update?: number;
  last_updated_checkpoint_id?: string;
  created_at: number;
  updated_at: number;
  completed_at?: number;
  is_active: boolean;
}

export interface PlanStalenessInfo {
  checkpointsSinceUpdate: number;
  staleness: 'fresh' | 'aging' | 'stale';
  daysSinceUpdate: number;
}

// Type aliases for backward compatibility
export type JournalEntry = CheckpointEntry;