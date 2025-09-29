/**
 * Data Processing Utilities for Tusk Journal System
 * Functions for grouping, summarizing, and formatting journal entries
 */

import type { JournalEntry } from "../core/types.js";

/**
 * Generate executive summary from journal entries
 */
export function generateExecutiveSummary(entries: JournalEntry[]): string {
  if (entries.length === 0) {
    return "No activities to summarize.";
  }

  const projects = [...new Set(entries.map(e => e.project).filter(Boolean))];
  const tags = [...new Set(entries.flatMap(e => e.tags || []))];
  const completedItems = entries.filter(e =>
    e.description.toLowerCase().includes('completed') ||
    e.description.toLowerCase().includes('finished') ||
    e.description.toLowerCase().includes('done') ||
    (e.tags || []).some(tag => tag.toLowerCase().includes('completed'))
  );

  const summary = [
    `## Executive Summary (${entries.length} entries)`,
    "",
    `**Key Projects:** ${projects.length > 0 ? projects.join(", ") : "General development"}`,
    "",
    `**Completed Items:** ${completedItems.length}`,
    `**Total Activities:** ${entries.length}`,
    "",
    `**Most Active Tags:** ${tags.slice(0, 5).join(", ")}`,
    "",
    "**Recent Progress:**",
    ...entries.slice(0, 3).map(e => `• ${e.description}`),
    "",
    "**Key Insights:**",
    `• ${completedItems.length > 0 ? `${completedItems.length} items completed` : "Work in progress across multiple areas"}`,
    `• ${projects.length} project${projects.length === 1 ? '' : 's'} active`,
    `• Focus areas: ${tags.slice(0, 3).join(", ")}`
  ];

  return summary.join("\n");
}

/**
 * Apply grouping strategy to entries
 */
export function applyGroupingStrategy(entries: JournalEntry[], strategy: string): Record<string, JournalEntry[]> {
  switch (strategy) {
    case "project":
      return groupByProject(entries);
    case "topic":
      return groupByTopic(entries);
    case "session":
      return groupBySession(entries);
    case "relevance":
      return groupByRelevance(entries);
    case "chronological":
    default:
      return groupByDate(entries);
  }
}

/**
 * Group entries by project
 */
export function groupByProject(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  const groups: Record<string, JournalEntry[]> = {};

  for (const entry of entries) {
    const project = entry.project || "General";
    if (!groups[project]) {
      groups[project] = [];
    }
    groups[project]!.push(entry);
  }

  return groups;
}

/**
 * Group entries by topic based on tags and keywords
 */
export function groupByTopic(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  const groups: Record<string, JournalEntry[]> = {};

  for (const entry of entries) {
    // Determine topic from tags or description keywords
    let topic = "General";

    if (entry.tags && entry.tags.length > 0) {
      // Use first tag as primary topic
      topic = entry.tags[0]!;
    } else {
      // Extract topic from description keywords
      const desc = entry.description.toLowerCase();
      if (desc.includes("bug") || desc.includes("fix")) {
        topic = "Bug Fixes";
      } else if (desc.includes("feature") || desc.includes("implement")) {
        topic = "Features";
      } else if (desc.includes("test")) {
        topic = "Testing";
      } else if (desc.includes("refactor")) {
        topic = "Refactoring";
      }
    }

    if (!groups[topic]) {
      groups[topic] = [];
    }
    groups[topic]!.push(entry);
  }

  return groups;
}

/**
 * Group entries by session (time-based clustering)
 */
export function groupBySession(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  const groups: Record<string, JournalEntry[]> = {};
  const sortedEntries = [...entries].sort((a, b) =>
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  let sessionNumber = 1;
  let currentSession: JournalEntry[] = [];
  let lastTimestamp: Date | null = null;

  for (const entry of sortedEntries) {
    const entryTime = new Date(entry.timestamp);

    // If more than 2 hours gap, start new session
    if (lastTimestamp && (entryTime.getTime() - lastTimestamp.getTime()) > 2 * 60 * 60 * 1000) {
      if (currentSession.length > 0) {
        groups[`Session ${sessionNumber}`] = currentSession;
        sessionNumber++;
        currentSession = [];
      }
    }

    currentSession.push(entry);
    lastTimestamp = entryTime;
  }

  // Add final session
  if (currentSession.length > 0) {
    groups[`Session ${sessionNumber}`] = currentSession;
  }

  return groups;
}

/**
 * Group entries by date
 */
export function groupByDate(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  const groups: Record<string, JournalEntry[]> = {};

  for (const entry of entries) {
    const date = new Date(entry.timestamp).toLocaleDateString();
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date]!.push(entry);
  }

  return groups;
}

/**
 * Group entries by relevance score ranges
 */
export function groupByRelevance(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  const groups: Record<string, JournalEntry[]> = {
    "High Relevance (0.8+)": [],
    "Medium Relevance (0.5-0.8)": [],
    "Low Relevance (<0.5)": []
  };

  for (const entry of entries) {
    // Simple relevance calculation based on recency and keywords
    const daysDiff = (Date.now() - new Date(entry.timestamp).getTime()) / (1000 * 60 * 60 * 24);
    const recencyScore = Math.max(0, 1 - daysDiff / 7); // Decay over week

    const hasImportantTags = (entry.tags || []).some(tag =>
      ['critical', 'important', 'milestone', 'completed'].includes(tag.toLowerCase())
    );

    const relevanceScore = recencyScore + (hasImportantTags ? 0.3 : 0);

    if (relevanceScore >= 0.8) {
      groups["High Relevance (0.8+)"]!.push(entry);
    } else if (relevanceScore >= 0.5) {
      groups["Medium Relevance (0.5-0.8)"]!.push(entry);
    } else {
      groups["Low Relevance (<0.5)"]!.push(entry);
    }
  }

  return groups;
}

/**
 * Format timestamp as "time ago" string
 */
export function formatTimeAgo(timestamp: string): string {
  const now = new Date();
  const entryTime = new Date(timestamp);
  const diffMs = now.getTime() - entryTime.getTime();

  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMinutes < 1) {
    return "just now";
  } else if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    return entryTime.toLocaleDateString();
  }
}