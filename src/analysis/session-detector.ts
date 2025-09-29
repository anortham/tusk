/**
 * Session Detection Algorithm for Tusk Journal System
 * Identifies session boundaries and groups entries into logical work sessions
 */

import type { CheckpointEntry } from "../core/types.js";

export interface SessionBoundary {
  sessionStart: string; // timestamp
  sessionEnd?: string; // timestamp, undefined for current session
  sessionId?: string; // Claude Code session ID if available
  entryCount: number;
  duration?: number; // in hours
  sessionType: 'work' | 'quick-restart' | 'continuation';
}

export interface SessionInfo {
  sessionId: string;
  boundaries: SessionBoundary;
  entries: CheckpointEntry[];
  summary?: string;
}

/**
 * Configuration for session detection algorithm
 */
export interface SessionDetectionConfig {
  // Time-based detection
  sessionGapHours: number;           // Default: 2 hours
  quickRestartMinutes: number;       // Default: 5 minutes (merge session-starts within this window)

  // Entry type classification
  sessionMarkerTypes: string[];      // Entry types that indicate session boundaries

  // Quality filtering
  minEntriesForSession: number;      // Default: 2 (sessions with fewer entries are considered noise)
  maxSessionHours: number;           // Default: 12 (sessions longer than this are split)
}

export const DEFAULT_SESSION_CONFIG: SessionDetectionConfig = {
  sessionGapHours: 2.0,
  quickRestartMinutes: 5,
  sessionMarkerTypes: ['session-marker'],
  minEntriesForSession: 2,
  maxSessionHours: 12,
};

/**
 * Main session detection class
 */
export class SessionDetector {
  constructor(private config: SessionDetectionConfig = DEFAULT_SESSION_CONFIG) {}

  /**
   * Detect session boundaries from a list of checkpoint entries
   */
  detectSessions(entries: CheckpointEntry[]): SessionInfo[] {
    if (entries.length === 0) return [];

    // Sort entries by timestamp
    const sortedEntries = [...entries].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const sessions: SessionInfo[] = [];
    let currentSessionEntries: CheckpointEntry[] = [];
    let sessionStartTime: string = sortedEntries[0]!.timestamp;
    let currentSessionId: string | undefined = sortedEntries[0]!.sessionId;

    for (let i = 0; i < sortedEntries.length; i++) {
      const entry = sortedEntries[i]!;
      const prevEntry = i > 0 ? (sortedEntries[i - 1] || null) : null;

      // Check if this entry starts a new session
      const isNewSession = this.isNewSession(entry, prevEntry);

      if (isNewSession && currentSessionEntries.length > 0) {
        // Finalize the previous session
        const sessionEnd = prevEntry?.timestamp || currentSessionEntries[currentSessionEntries.length - 1]?.timestamp;
        sessions.push(this.createSessionInfo(
          currentSessionId || this.generateSessionId(sessionStartTime),
          sessionStartTime,
          sessionEnd,
          currentSessionEntries
        ));

        // Start new session
        currentSessionEntries = [entry];
        sessionStartTime = entry.timestamp;
        currentSessionId = entry.sessionId;
      } else {
        // Add to current session
        currentSessionEntries.push(entry);

        // Update session ID if we have a more specific one
        if (entry.sessionId && !currentSessionId) {
          currentSessionId = entry.sessionId;
        }
      }
    }

    // Finalize the last session
    if (currentSessionEntries.length > 0) {
      sessions.push(this.createSessionInfo(
        currentSessionId || this.generateSessionId(sessionStartTime),
        sessionStartTime,
        undefined, // Current session, no end time
        currentSessionEntries
      ));
    }

    return this.postProcessSessions(sessions);
  }

  /**
   * Determine if an entry starts a new session
   */
  private isNewSession(entry: CheckpointEntry, prevEntry: CheckpointEntry | null): boolean {
    if (!prevEntry) return false; // First entry doesn't start a new session

    const currentTime = new Date(entry.timestamp).getTime();
    const prevTime = new Date(prevEntry.timestamp).getTime();
    const hoursDiff = (currentTime - prevTime) / (1000 * 60 * 60);

    // Time-based session boundary
    if (hoursDiff >= this.config.sessionGapHours) {
      return true;
    }

    // Explicit session marker
    if (entry.entryType && this.config.sessionMarkerTypes.includes(entry.entryType)) {
      // Check for quick restart (multiple session-starts within 5 minutes)
      const minutesDiff = (currentTime - prevTime) / (1000 * 60);
      if (minutesDiff >= this.config.quickRestartMinutes) {
        return true;
      }
    }

    // Different Claude Code session ID
    if (entry.sessionId && prevEntry.sessionId && entry.sessionId !== prevEntry.sessionId) {
      return true;
    }

    return false;
  }

  /**
   * Create a session info object
   */
  private createSessionInfo(
    sessionId: string,
    startTime: string,
    endTime: string | undefined,
    entries: CheckpointEntry[]
  ): SessionInfo {
    const startTimestamp = new Date(startTime).getTime();
    const endTimestamp = endTime ? new Date(endTime).getTime() : Date.now();
    const durationHours = (endTimestamp - startTimestamp) / (1000 * 60 * 60);

    // Determine session type
    let sessionType: 'work' | 'quick-restart' | 'continuation' = 'work';
    if (entries.length <= 3 && durationHours < 0.5) {
      sessionType = 'quick-restart';
    } else if (entries.some(e => e.description.toLowerCase().includes('continuation'))) {
      sessionType = 'continuation';
    }

    return {
      sessionId,
      boundaries: {
        sessionStart: startTime,
        sessionEnd: endTime,
        sessionId,
        entryCount: entries.length,
        duration: durationHours,
        sessionType,
      },
      entries: [...entries],
      summary: this.generateSessionSummary(entries),
    };
  }

  /**
   * Generate a simple session summary
   */
  private generateSessionSummary(entries: CheckpointEntry[]): string {
    const achievements = entries.filter(e =>
      e.description.toLowerCase().includes('completed') ||
      e.description.toLowerCase().includes('fixed') ||
      e.description.toLowerCase().includes('implemented')
    ).length;

    const technologies = new Set<string>();
    const projects = new Set<string>();

    entries.forEach(entry => {
      if (entry.project) projects.add(entry.project);
      entry.tags?.forEach(tag => {
        if (tag.includes('-')) technologies.add(tag);
      });
    });

    const parts: string[] = [];
    if (achievements > 0) parts.push(`${achievements} achievements`);
    if (projects.size > 0) parts.push(`${Array.from(projects).join(', ')}`);
    if (technologies.size > 0) parts.push(`technologies: ${Array.from(technologies).slice(0, 3).join(', ')}`);

    return parts.join(' • ') || `${entries.length} entries`;
  }

  /**
   * Post-process sessions to handle edge cases
   */
  private postProcessSessions(sessions: SessionInfo[]): SessionInfo[] {
    return sessions
      .filter(session => {
        // Filter out noise sessions (too few entries)
        if (session.entries.length < this.config.minEntriesForSession) {
          return false;
        }
        return true;
      })
      .map(session => {
        // Split overly long sessions
        if (session.boundaries.duration && session.boundaries.duration > this.config.maxSessionHours) {
          // Could implement session splitting here if needed
        }
        return session;
      });
  }

  /**
   * Generate a session ID when none is available
   */
  private generateSessionId(timestamp: string): string {
    const date = new Date(timestamp);
    return `session_${date.toISOString().slice(0, 19).replace(/[-:]/g, '')}_${Math.random().toString(36).slice(2, 6)}`;
  }

  /**
   * Get the most recent complete session
   */
  getLastCompleteSession(entries: CheckpointEntry[]): SessionInfo | null {
    const sessions = this.detectSessions(entries);
    const completeSessions = sessions.filter(s => s.boundaries.sessionEnd !== undefined);
    return completeSessions.length > 0 ? completeSessions[completeSessions.length - 1]! : null;
  }

  /**
   * Get the current active session
   */
  getCurrentSession(entries: CheckpointEntry[]): SessionInfo | null {
    const sessions = this.detectSessions(entries);
    const currentSessions = sessions.filter(s => s.boundaries.sessionEnd === undefined);
    return currentSessions.length > 0 ? currentSessions[0]! : null;
  }

  /**
   * Get session boundaries for efficient querying
   */
  getSessionBoundaries(entries: CheckpointEntry[]): SessionBoundary[] {
    return this.detectSessions(entries).map(session => session.boundaries);
  }
}