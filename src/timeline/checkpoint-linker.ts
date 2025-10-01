/**
 * Checkpoint Linker
 * Links transcript archives to related checkpoint entries
 */

import type { TranscriptArchive, CheckpointSummary } from "./types.js";
import type { CheckpointEntry } from "../core/types.js";
import { JournalDB } from "../core/journal-db.js";

const CHECKPOINT_WINDOW_MS = 15 * 60 * 1000; // ±15 minutes

/**
 * Link checkpoints to a transcript archive
 * Finds all checkpoints within ±15 minutes of the transcript timestamp
 */
export async function linkCheckpointsToArchive(
  archive: TranscriptArchive,
  db: JournalDB
): Promise<CheckpointSummary[]> {
  const startTime = new Date(archive.timestamp.getTime() - CHECKPOINT_WINDOW_MS);
  const endTime = new Date(archive.timestamp.getTime() + CHECKPOINT_WINDOW_MS);

  const entries = await db.getRecentCheckpoints({
    from: startTime.toISOString(),
    to: endTime.toISOString(),
    limit: 100,
  });

  return entries.map(entryToCheckpointSummary);
}

/**
 * Link checkpoints to multiple archives at once (batch operation)
 */
export async function linkCheckpointsToArchives(
  archives: TranscriptArchive[],
  db: JournalDB
): Promise<void> {
  for (const archive of archives) {
    archive.checkpoints = await linkCheckpointsToArchive(archive, db);

    // Extract key topics from checkpoint tags
    if (archive.checkpoints) {
      const allTags = archive.checkpoints.flatMap(cp => cp.tags || []);
      archive.keyTopics = [...new Set(allTags)].slice(0, 5); // Top 5 unique tags
    }

    // Extract git commits mentioned in checkpoints
    if (archive.checkpoints) {
      const commits = archive.checkpoints
        .filter(cp => cp.gitCommit)
        .map(cp => ({
          hash: cp.gitCommit!,
          shortHash: cp.gitCommit!.substring(0, 7),
          message: extractCommitMessage(cp.description),
        }));

      archive.commits = Array.from(
        new Map(commits.map(c => [c.hash, c])).values()
      );
    }
  }
}

/**
 * Convert CheckpointEntry to CheckpointSummary
 */
function entryToCheckpointSummary(entry: CheckpointEntry): CheckpointSummary {
  return {
    id: entry.id || '',
    timestamp: entry.timestamp,
    description: entry.description,
    tags: entry.tags || [],
    project: entry.project,
    gitBranch: entry.gitBranch,
    gitCommit: entry.gitCommit,
  };
}

/**
 * Extract commit message from checkpoint description
 * Looks for patterns like "Git commit: message" or "Committed X"
 */
function extractCommitMessage(description: string): string {
  // Look for "Git commit:" pattern
  const commitMatch = description.match(/Git commit:.*?[\r\n]/);
  if (commitMatch) {
    return commitMatch[0].replace(/Git commit:\s*/, '').trim();
  }

  // Look for "Committed X" pattern
  const committedMatch = description.match(/Committed (.+?)[\r\n.]/);
  if (committedMatch && committedMatch[1]) {
    return committedMatch[1].trim();
  }

  // Default: use first line
  const firstLine = description.split('\n')[0];
  return firstLine ? firstLine.substring(0, 100) : description.substring(0, 100);
}

/**
 * Extract key insights from checkpoint descriptions
 * Looks for important patterns and highlights
 */
export function extractKeyInsights(checkpoints: CheckpointSummary[]): string[] {
  const insights: string[] = [];

  for (const checkpoint of checkpoints) {
    const desc = checkpoint.description;

    // Look for "Fixed", "Implemented", "Discovered" patterns
    const patterns = [
      /(?:Fixed|Solved|Resolved)\s+(.+?)[\r\n.]/i,
      /(?:Implemented|Added|Created)\s+(.+?)[\r\n.]/i,
      /(?:Discovered|Found|Learned)\s+(.+?)[\r\n.]/i,
      /💡\s*(.+?)[\r\n.]/,
    ];

    for (const pattern of patterns) {
      const match = desc.match(pattern);
      if (match && match[1]) {
        insights.push(match[1].trim());
        break; // Only one insight per checkpoint
      }
    }
  }

  // Return up to 3 key insights
  return insights.slice(0, 3);
}
