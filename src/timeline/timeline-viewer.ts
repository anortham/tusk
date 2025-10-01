/**
 * Timeline Viewer
 * Main entry point for visualizing transcript archive timeline
 */

import { JournalDB } from "../core/journal-db.js";
import {
  scanTranscriptArchives,
  getArchivesForDays,
  getArchivesForDay,
} from "./archive-scanner.js";
import { linkCheckpointsToArchives } from "./checkpoint-linker.js";
import { clusterIntoSessions, groupSessionsByDay } from "./session-clusterer.js";
import { formatTimeline, formatSummary } from "./timeline-formatter.js";
import type { TimelineOptions } from "./types.js";

/**
 * Generate and display transcript archive timeline
 */
export async function showTimeline(options: TimelineOptions = {}): Promise<string> {
  const {
    days = 7,
    date,
    verbose = false,
  } = options;

  // Scan all transcript archives
  const allArchives = scanTranscriptArchives();

  if (allArchives.length === 0) {
    return "📭 No transcript archives found.\n\n💡 Transcript backups are created automatically during compaction.";
  }

  // Filter archives based on options
  let archives = allArchives;
  if (date) {
    // Show specific date
    const targetDate = new Date(date);
    archives = getArchivesForDay(allArchives, targetDate);
  } else {
    // Show last N days
    archives = getArchivesForDays(allArchives, days);
  }

  if (archives.length === 0) {
    if (date) {
      return `📭 No transcript archives found for ${date}.`;
    }
    return `📭 No transcript archives found in the last ${days} days.`;
  }

  // Link checkpoints to archives
  const db = new JournalDB();
  await linkCheckpointsToArchives(archives, db);

  // Cluster into sessions
  const sessions = clusterIntoSessions(archives);

  // Group by day
  const timelineDays = groupSessionsByDay(sessions);

  // Format output
  const timeline = formatTimeline(timelineDays, verbose);
  const summary = formatSummary(timelineDays);

  return `${timeline}\n${summary}`;
}

/**
 * Get timeline statistics
 */
export function getTimelineStats() {
  const archives = scanTranscriptArchives();

  const totalSize = archives.reduce((sum, a) => sum + a.sizeBytes, 0);
  const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);

  const oldestArchive = archives.length > 0 && archives[archives.length - 1]
    ? archives[archives.length - 1]!.timestamp
    : null;

  const newestArchive = archives.length > 0 && archives[0]
    ? archives[0].timestamp
    : null;

  return {
    count: archives.length,
    totalSizeMB: parseFloat(totalSizeMB),
    oldestArchive,
    newestArchive,
  };
}
