/**
 * Timeline Types
 * Core interfaces for transcript archive timeline viewer
 */

export interface TranscriptArchive {
  path: string;
  filename: string;
  timestamp: Date;
  trigger: 'auto' | 'manual';
  sizeBytes: number;
  sizeMB: number;
  sessionId?: string;
  checkpoints?: CheckpointSummary[];
  commits?: GitCommitSummary[];
  keyTopics?: string[];
}

export interface CheckpointSummary {
  id: string;
  timestamp: string;
  description: string;
  tags: string[];
  project?: string;
  gitBranch?: string;
  gitCommit?: string;
}

export interface GitCommitSummary {
  hash: string;
  shortHash: string;
  message: string;
  timestamp?: string;
}

export interface TimelineSession {
  startTime: Date;
  endTime: Date;
  archives: TranscriptArchive[];
  totalSizeBytes: number;
  totalSizeMB: number;
  checkpointCount: number;
  commitCount: number;
  topics: string[];
  keyInsights: string[];
}

export interface TimelineDay {
  date: string;
  displayDate: string;
  sessions: TimelineSession[];
  totalSize: number;
  checkpointCount: number;
  commitCount: number;
}

export interface TimelineOptions {
  days?: number;
  date?: string;
  aroundCheckpoint?: string;
  verbose?: boolean;
}
