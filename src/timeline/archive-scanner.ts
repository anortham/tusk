/**
 * Archive Scanner
 * Scans transcript backup directory and extracts metadata from filenames
 */

import { readdirSync, statSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import type { TranscriptArchive } from "./types.js";

const TRANSCRIPT_BACKUP_DIR = join(homedir(), ".tusk", "transcript-backups");

/**
 * Parse transcript filename to extract metadata
 * Format: transcript-YYYY-MM-DD-HH-MM-SS-{trigger}.txt
 */
export function parseTranscriptFilename(filename: string): TranscriptArchive | null {
  const pattern = /^transcript-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(auto|manual)\.txt$/;
  const match = filename.match(pattern);

  if (!match) {
    return null;
  }

  const [, year, month, day, hour, minute, second, trigger] = match;

  // Create timestamp (non-null assertions safe because match succeeded)
  const timestamp = new Date(
    parseInt(year!),
    parseInt(month!) - 1, // Month is 0-indexed
    parseInt(day!),
    parseInt(hour!),
    parseInt(minute!),
    parseInt(second!)
  );

  return {
    path: join(TRANSCRIPT_BACKUP_DIR, filename),
    filename,
    timestamp,
    trigger: trigger as 'auto' | 'manual',
    sizeBytes: 0,
    sizeMB: 0,
  };
}

/**
 * Scan transcript backup directory and return all archives
 */
export function scanTranscriptArchives(): TranscriptArchive[] {
  try {
    const files = readdirSync(TRANSCRIPT_BACKUP_DIR);

    const archives: TranscriptArchive[] = [];

    for (const file of files) {
      const archive = parseTranscriptFilename(file);
      if (archive) {
        // Get file size
        try {
          const stats = statSync(archive.path);
          archive.sizeBytes = stats.size;
          archive.sizeMB = parseFloat((stats.size / (1024 * 1024)).toFixed(2));
        } catch {
          // Skip files we can't stat
          continue;
        }

        archives.push(archive);
      }
    }

    // Sort by timestamp (newest first)
    archives.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

    return archives;
  } catch (error) {
    // Directory doesn't exist or can't be read
    return [];
  }
}

/**
 * Get archives within a specific date range
 */
export function getArchivesInRange(
  archives: TranscriptArchive[],
  startDate: Date,
  endDate: Date
): TranscriptArchive[] {
  return archives.filter(archive =>
    archive.timestamp >= startDate && archive.timestamp <= endDate
  );
}

/**
 * Get archives for a specific day
 */
export function getArchivesForDay(
  archives: TranscriptArchive[],
  date: Date
): TranscriptArchive[] {
  const dayStart = new Date(date);
  dayStart.setHours(0, 0, 0, 0);

  const dayEnd = new Date(date);
  dayEnd.setHours(23, 59, 59, 999);

  return getArchivesInRange(archives, dayStart, dayEnd);
}

/**
 * Get archives for the last N days
 */
export function getArchivesForDays(
  archives: TranscriptArchive[],
  days: number
): TranscriptArchive[] {
  const now = new Date();
  const startDate = new Date(now);
  startDate.setDate(startDate.getDate() - days);
  startDate.setHours(0, 0, 0, 0);

  return getArchivesInRange(archives, startDate, now);
}
