/**
 * Session Clusterer
 * Groups transcript archives into logical sessions based on time gaps
 */

import type { TranscriptArchive, TimelineSession, TimelineDay } from "./types.js";
import { extractKeyInsights } from "./checkpoint-linker.js";

const SESSION_GAP_MS = 60 * 60 * 1000; // 1 hour gap = new session

/**
 * Cluster archives into sessions
 * Archives within 1 hour of each other are grouped together
 */
export function clusterIntoSessions(archives: TranscriptArchive[]): TimelineSession[] {
  if (archives.length === 0) {
    return [];
  }

  // Sort by timestamp (oldest first for clustering)
  const sorted = [...archives].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const sessions: TimelineSession[] = [];
  const firstArchive = sorted[0];
  if (!firstArchive) {
    return []; // Empty array
  }

  let currentSession: TranscriptArchive[] = [firstArchive];

  for (let i = 1; i < sorted.length; i++) {
    const prevArchive = sorted[i - 1];
    const currArchive = sorted[i];
    if (!prevArchive || !currArchive) continue;

    const gap = currArchive.timestamp.getTime() - prevArchive.timestamp.getTime();

    if (gap <= SESSION_GAP_MS) {
      // Same session
      currentSession.push(currArchive);
    } else {
      // New session - save current and start new
      sessions.push(createSession(currentSession));
      currentSession = [currArchive];
    }
  }

  // Don't forget the last session
  if (currentSession.length > 0) {
    sessions.push(createSession(currentSession));
  }

  return sessions;
}

/**
 * Create a TimelineSession from a group of archives
 */
function createSession(archives: TranscriptArchive[]): TimelineSession {
  const firstArchive = archives[0];
  const lastArchive = archives[archives.length - 1];

  if (!firstArchive || !lastArchive) {
    throw new Error('Cannot create session from empty archives');
  }

  const startTime = firstArchive.timestamp;
  const endTime = lastArchive.timestamp;

  const totalSizeBytes = archives.reduce((sum, a) => sum + a.sizeBytes, 0);
  const totalSizeMB = parseFloat((totalSizeBytes / (1024 * 1024)).toFixed(2));

  // Aggregate checkpoints and commits
  const allCheckpoints = archives.flatMap(a => a.checkpoints || []);
  const allCommits = archives.flatMap(a => a.commits || []);

  // Deduplicate commits by hash
  const uniqueCommits = Array.from(
    new Map(allCommits.map(c => [c.hash, c])).values()
  );

  // Extract topics from checkpoints
  const allTags = allCheckpoints.flatMap(cp => cp.tags);
  const topicCounts = new Map<string, number>();
  for (const tag of allTags) {
    topicCounts.set(tag, (topicCounts.get(tag) || 0) + 1);
  }

  // Sort topics by frequency and take top 5
  const topics = Array.from(topicCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([tag]) => tag);

  // Extract key insights
  const keyInsights = extractKeyInsights(allCheckpoints);

  return {
    startTime,
    endTime,
    archives,
    totalSizeBytes,
    totalSizeMB,
    checkpointCount: allCheckpoints.length,
    commitCount: uniqueCommits.length,
    topics,
    keyInsights,
  };
}

/**
 * Group sessions by day
 */
export function groupSessionsByDay(sessions: TimelineSession[]): TimelineDay[] {
  const dayMap = new Map<string, TimelineSession[]>();

  for (const session of sessions) {
    const dateKey = session.startTime.toISOString().split('T')[0]; // YYYY-MM-DD
    if (!dateKey) continue;

    if (!dayMap.has(dateKey)) {
      dayMap.set(dateKey, []);
    }
    dayMap.get(dateKey)!.push(session);
  }

  // Convert to TimelineDay objects
  const days: TimelineDay[] = [];

  for (const [dateKey, daySessions] of dayMap.entries()) {
    if (!dateKey) continue;

    const date = new Date(dateKey);
    const displayDate = formatDisplayDate(date);

    const totalSize = daySessions.reduce((sum, s) => sum + s.totalSizeBytes, 0);
    const checkpointCount = daySessions.reduce((sum, s) => sum + s.checkpointCount, 0);
    const commitCount = daySessions.reduce((sum, s) => sum + s.commitCount, 0);

    days.push({
      date: dateKey,
      displayDate,
      sessions: daySessions,
      totalSize,
      checkpointCount,
      commitCount,
    });
  }

  // Sort by date (newest first)
  days.sort((a, b) => b.date.localeCompare(a.date));

  return days;
}

/**
 * Format date for display
 */
function formatDisplayDate(date: Date): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const compareDate = new Date(date);
  compareDate.setHours(0, 0, 0, 0);

  if (compareDate.getTime() === today.getTime()) {
    return "Today";
  } else if (compareDate.getTime() === yesterday.getTime()) {
    return "Yesterday";
  } else {
    return date.toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
  }
}

/**
 * Generate session title based on content
 */
export function generateSessionTitle(session: TimelineSession): string {
  // Use first key insight if available
  const firstInsight = session.keyInsights[0];
  if (firstInsight) {
    return firstInsight;
  }

  // Use most common topic
  if (session.topics.length > 0) {
    return `${session.topics[0]} work`;
  }

  // Fallback to generic title
  return "Development session";
}
