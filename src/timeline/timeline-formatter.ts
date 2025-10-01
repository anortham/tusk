/**
 * Timeline Formatter
 * Formats timeline data into visually appealing CLI output
 */

import type { TimelineDay, TimelineSession } from "./types.js";
import { generateSessionTitle } from "./session-clusterer.js";

/**
 * Format timeline days for display
 */
export function formatTimeline(days: TimelineDay[], verbose: boolean = false): string {
  if (days.length === 0) {
    return "📭 No transcript archives found.\n\n💡 Transcript backups are created automatically during compaction.";
  }

  const lines: string[] = [];

  for (const day of days) {
    lines.push(formatDay(day, verbose));
    lines.push(""); // Blank line between days
  }

  return lines.join("\n");
}

/**
 * Format a single day
 */
function formatDay(day: TimelineDay, verbose: boolean): string {
  const lines: string[] = [];

  // Day header
  lines.push(`📅 ${day.displayDate} (${day.date})`);

  // Sessions
  for (let i = 0; i < day.sessions.length; i++) {
    const session = day.sessions[i];
    if (!session) continue;

    const isLast = i === day.sessions.length - 1;
    lines.push(...formatSession(session, isLast, verbose));
  }

  return lines.join("\n");
}

/**
 * Format a single session
 */
function formatSession(
  session: TimelineSession,
  isLast: boolean,
  verbose: boolean
): string[] {
  const lines: string[] = [];

  const prefix = isLast ? "└─" : "├─";
  const indent = isLast ? "   " : "│  ";

  // Session header
  const startTime = formatTime(session.startTime);
  const endTime = formatTime(session.endTime);
  const title = generateSessionTitle(session);

  lines.push(
    `${prefix} ${startTime}-${endTime} • ${title} (${session.totalSizeMB}MB)`
  );

  // Checkpoints
  if (session.checkpointCount > 0) {
    lines.push(`${indent}├─ ${session.checkpointCount} checkpoint${session.checkpointCount === 1 ? '' : 's'}`);
  }

  // Commits
  if (session.commitCount > 0) {
    lines.push(`${indent}├─ ${session.commitCount} commit${session.commitCount === 1 ? '' : 's'}`);
  }

  // Topics
  if (session.topics.length > 0) {
    lines.push(`${indent}├─ Topics: ${session.topics.slice(0, 3).join(", ")}`);
  }

  // Key insights
  if (session.keyInsights.length > 0) {
    for (let i = 0; i < session.keyInsights.length; i++) {
      const insight = session.keyInsights[i];
      if (!insight) continue;

      const isLastInsight = i === session.keyInsights.length - 1 &&
                           !verbose; // Only last if not verbose

      const insightPrefix = isLastInsight ? "└─" : "├─";
      lines.push(`${indent}${insightPrefix} 💡 ${truncate(insight, 80)}`);
    }
  }

  // Verbose mode: show individual archives
  if (verbose && session.archives.length > 1) {
    lines.push(`${indent}└─ Archives:`);
    for (const archive of session.archives) {
      const archiveTime = formatTime(archive.timestamp);
      lines.push(`${indent}   • ${archiveTime} - ${archive.trigger} (${archive.sizeMB}MB)`);
    }
  }

  return lines;
}

/**
 * Format time as HH:MM
 */
function formatTime(date: Date): string {
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * Truncate string to max length
 */
function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) {
    return str;
  }
  return str.substring(0, maxLength - 3) + "...";
}

/**
 * Format summary stats
 */
export function formatSummary(days: TimelineDay[]): string {
  if (days.length === 0) {
    return "";
  }

  const totalSessions = days.reduce((sum, d) => sum + d.sessions.length, 0);
  const totalCheckpoints = days.reduce((sum, d) => sum + d.checkpointCount, 0);
  const totalCommits = days.reduce((sum, d) => sum + d.commitCount, 0);
  const totalSize = days.reduce((sum, d) => sum + d.totalSize, 0);
  const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);

  const lines = [
    "",
    "📊 Summary",
    `   • ${days.length} day${days.length === 1 ? '' : 's'}`,
    `   • ${totalSessions} session${totalSessions === 1 ? '' : 's'}`,
    `   • ${totalCheckpoints} checkpoint${totalCheckpoints === 1 ? '' : 's'}`,
    `   • ${totalCommits} commit${totalCommits === 1 ? '' : 's'}`,
    `   • ${totalSizeMB}MB total`,
  ];

  return lines.join("\n");
}
