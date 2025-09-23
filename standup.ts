/**
 * Standup report generator for tusk-bun
 * Ports the beautiful formatting from the original goldfish standup tool
 */

import { getRecentEntries } from "./journal.js";
import type { JournalEntry } from "./journal.js";

export type StandupStyle = "meeting" | "written" | "executive" | "metrics";

export interface StandupOptions {
  style: StandupStyle;
  days: number;
  includeMetrics?: boolean;
  includeFiles?: boolean;
  workspace?: string | 'current' | 'all';
}

export interface StandupData {
  timeRange: string;
  totalCheckpoints: number;
  projects: string[];
  highlights: string[];
  nextSteps: string[];
  recentCheckpoints: JournalEntry[];
  gitBranches: string[];
  workspaces: string[];
}

/**
 * Generate a standup report from journal entries
 */
export async function generateStandup(options: StandupOptions): Promise<string> {
  const { style, days, workspace } = options;

  // Get recent entries
  const entries = await getRecentEntries({ days, workspace });
  const data = await aggregateStandupData(entries, days);

  switch (style) {
    case "meeting":
      return formatMeetingStyle(data, options);
    case "written":
      return formatWrittenStyle(data, options);
    case "executive":
      return formatExecutiveStyle(data, options);
    case "metrics":
      return formatMetricsStyle(data, options);
    default:
      return formatMeetingStyle(data, options);
  }
}

/**
 * Aggregate data from journal entries for standup reporting
 */
async function aggregateStandupData(entries: JournalEntry[], days: number): Promise<StandupData> {
  const timeRange = getTimeRangeLabel(days);
  const projects = [...new Set(entries.map(e => e.project).filter(Boolean))] as string[];
  const gitBranches = [...new Set(entries.map(e => e.gitBranch).filter(Boolean))] as string[];
  const workspaces = [...new Set(entries.map(e => e.workspaceName).filter(Boolean))] as string[];

  // Extract highlights and potential next steps
  const highlights: string[] = [];
  const nextSteps: string[] = [];

  for (const entry of entries) {
    // Simple heuristics to identify highlights and next steps
    const desc = entry.description.toLowerCase();

    if (desc.includes("fixed") || desc.includes("completed") || desc.includes("implemented") ||
        desc.includes("finished") || desc.includes("solved") || desc.includes("achieved")) {
      highlights.push(entry.description);
    }

    if (desc.includes("next") || desc.includes("todo") || desc.includes("need to") ||
        desc.includes("should") || desc.includes("plan to") || desc.includes("will")) {
      nextSteps.push(entry.description);
    }

    // Add tagged items
    if (entry.tags) {
      if (entry.tags.includes("highlight") || entry.tags.includes("achievement")) {
        highlights.push(entry.description);
      }
      if (entry.tags.includes("next") || entry.tags.includes("todo")) {
        nextSteps.push(entry.description);
      }
    }
  }

  return {
    timeRange,
    totalCheckpoints: entries.length,
    projects,
    highlights: [...new Set(highlights)].slice(0, 8),
    nextSteps: [...new Set(nextSteps)].slice(0, 5),
    recentCheckpoints: entries.slice(0, 10),
    gitBranches,
    workspaces,
  };
}

/**
 * Format standup in meeting style (classic standup format)
 */
function formatMeetingStyle(data: StandupData, options: StandupOptions): string {
  const output: string[] = [];

  output.push(`🏃‍♂️ **Daily Standup** (${data.timeRange})`);

  if (data.workspaces.length > 1) {
    output.push(`🗂️ Workspaces: ${data.workspaces.join(", ")}`);
  }

  if (data.projects.length > 0) {
    output.push(`📍 Projects: ${data.projects.join(", ")}`);
  }

  if (data.gitBranches.length > 0) {
    output.push(`🌿 Branches: ${data.gitBranches.join(", ")}`);
  }

  output.push("");

  if (options.includeMetrics) {
    output.push("📊 **Quick Stats:**");
    output.push(`   • ${data.totalCheckpoints} checkpoints recorded`);
    output.push(`   • ${data.projects.length} projects active`);
    if (data.workspaces.length > 1) {
      output.push(`   • ${data.workspaces.length} workspaces involved`);
    }
    output.push(`   • ${data.highlights.length} key achievements`);
    output.push("");
  }

  // What I accomplished (from recent checkpoints)
  if (data.recentCheckpoints.length > 0) {
    output.push("✅ **What I accomplished:**");
    data.recentCheckpoints.slice(0, 6).forEach(checkpoint => {
      const time = formatRelativeTime(checkpoint.timestamp);
      const prefix = checkpoint.project ? `[${checkpoint.project}]` : "";
      output.push(`   • ${prefix} ${checkpoint.description} ${time}`);
    });
    output.push("");
  }

  // Key highlights
  if (data.highlights.length > 0) {
    output.push("⭐ **Key highlights:**");
    data.highlights.slice(0, 5).forEach(highlight => {
      output.push(`   • ${highlight}`);
    });
    output.push("");
  }

  // Next steps
  if (data.nextSteps.length > 0) {
    output.push("🚀 **Next steps:**");
    data.nextSteps.slice(0, 3).forEach(step => {
      output.push(`   • ${step}`);
    });
    output.push("");
  }

  // File activity (if enabled)
  if (options.includeFiles) {
    const allFiles = data.recentCheckpoints
      .flatMap(c => c.files || [])
      .filter(Boolean);
    const topFiles = [...new Set(allFiles)].slice(0, 5);

    if (topFiles.length > 0) {
      output.push("📁 **Active files:**");
      topFiles.forEach(file => {
        output.push(`   • ${file}`);
      });
      output.push("");
    }
  }

  return output.join("\n").trim();
}

/**
 * Format standup in written style (narrative format)
 */
function formatWrittenStyle(data: StandupData, options: StandupOptions): string {
  const output: string[] = [];

  output.push(`📝 **Work Summary** - ${data.timeRange}`);

  if (data.workspaces.length > 1) {
    output.push(`Workspaces: ${data.workspaces.join(", ")}`);
  }

  if (data.projects.length > 0) {
    output.push(`Projects: ${data.projects.join(", ")}`);
  }

  output.push("");

  if (options.includeMetrics) {
    output.push(
      `During ${data.timeRange}, I completed ${data.totalCheckpoints} work sessions across ${data.projects.length} project${data.projects.length === 1 ? "" : "s"}. ` +
      `Achieved ${data.highlights.length} key milestone${data.highlights.length === 1 ? "" : "s"} with ${data.nextSteps.length} action item${data.nextSteps.length === 1 ? "" : "s"} identified for follow-up.`
    );
    output.push("");
  }

  if (data.highlights.length > 0) {
    output.push("**Key Accomplishments:**");
    data.highlights.forEach(highlight => {
      output.push(`• ${highlight}`);
    });
    output.push("");
  }

  if (data.recentCheckpoints.length > 0) {
    output.push("**Recent Work:**");
    data.recentCheckpoints.slice(0, 8).forEach(checkpoint => {
      const time = formatRelativeTime(checkpoint.timestamp);
      output.push(`• ${checkpoint.description} ${time}`);
    });
    output.push("");
  }

  if (data.nextSteps.length > 0) {
    output.push("**Upcoming Actions:**");
    data.nextSteps.forEach(step => {
      output.push(`• ${step}`);
    });
  }

  return output.join("\n").trim();
}

/**
 * Format standup in executive style (high-level summary)
 */
function formatExecutiveStyle(data: StandupData, options: StandupOptions): string {
  const output: string[] = [];

  output.push(`🎯 **Executive Summary** - ${data.timeRange}`);

  if (data.workspaces.length > 1) {
    output.push(`Workspaces: ${data.workspaces.join(" • ")}`);
  }

  if (data.projects.length > 0) {
    output.push(`Portfolio: ${data.projects.join(" • ")}`);
  }

  output.push("");

  // High-level impact
  if (options.includeMetrics) {
    const activityLevel = data.totalCheckpoints >= 5 ? "High" : data.totalCheckpoints >= 2 ? "Medium" : "Low";
    output.push(
      `**Impact:** Delivered ${data.highlights.length} key achievement${data.highlights.length === 1 ? "" : "s"} ` +
      `across ${data.projects.length} strategic initiative${data.projects.length === 1 ? "" : "s"} ` +
      `with ${activityLevel.toLowerCase()} development velocity (${data.totalCheckpoints} work sessions).`
    );
    output.push("");
  }

  // Strategic focus
  if (data.projects.length > 0) {
    output.push("**Strategic Focus:**");
    data.projects.slice(0, 3).forEach((project, index) => {
      const projectCheckpoints = data.recentCheckpoints.filter(c => c.project === project);
      output.push(`${index + 1}. ${project} - ${projectCheckpoints.length} active session${projectCheckpoints.length === 1 ? "" : "s"}`);
    });
    output.push("");
  }

  // Key wins
  if (data.highlights.length > 0) {
    output.push("**Key Wins:**");
    data.highlights.slice(0, 5).forEach((highlight, index) => {
      output.push(`${index + 1}. ${highlight}`);
    });
    output.push("");
  }

  // Forward outlook
  if (data.nextSteps.length > 0) {
    output.push("**Forward Outlook:**");
    output.push(`Priority actions: ${data.nextSteps.slice(0, 3).join(" • ")}`);
  }

  return output.join("\n").trim();
}

/**
 * Format standup in metrics style (dashboard format)
 */
function formatMetricsStyle(data: StandupData, options: StandupOptions): string {
  const output: string[] = [];

  output.push(`📈 **Metrics Dashboard** - ${data.timeRange}`);
  output.push("");

  output.push("**Productivity Metrics:**");
  output.push(`├─ Checkpoints recorded: ${data.totalCheckpoints}`);
  output.push(`├─ Active projects: ${data.projects.length}`);
  if (data.workspaces.length > 0) {
    output.push(`├─ Workspaces involved: ${data.workspaces.length}`);
  }
  output.push(`├─ Key achievements: ${data.highlights.length}`);
  output.push(`├─ Git branches: ${data.gitBranches.length}`);
  output.push(`└─ Action items identified: ${data.nextSteps.length}`);
  output.push("");

  // Project breakdown
  if (data.projects.length > 0) {
    output.push("**Project Activity:**");
    data.projects.forEach(project => {
      const projectCheckpoints = data.recentCheckpoints.filter(c => c.project === project);
      const percentage = Math.round((projectCheckpoints.length / data.totalCheckpoints) * 100);
      const bar = "█".repeat(Math.floor(percentage / 10)) + "░".repeat(10 - Math.floor(percentage / 10));
      output.push(`├─ ${project}: ${projectCheckpoints.length} sessions (${percentage}%) [${bar}]`);
    });
    output.push("");
  }

  // Time distribution
  output.push("**Activity Timeline:**");
  const timeGroups = groupCheckpointsByTime(data.recentCheckpoints);
  Object.entries(timeGroups).forEach(([timeLabel, count]) => {
    const bar = "▓".repeat(count) + "░".repeat(Math.max(0, 10 - count));
    output.push(`├─ ${timeLabel}: ${count} checkpoint${count === 1 ? "" : "s"} [${bar}]`);
  });

  return output.join("\n").trim();
}

/**
 * Get a human-readable time range label
 */
function getTimeRangeLabel(days: number): string {
  if (days === 1) return "last 24 hours";
  if (days === 7) return "past week";
  if (days === 30) return "past month";
  return `last ${days} days`;
}

/**
 * Format relative time for display
 */
function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) return "(just now)";
  if (diffHours < 24) return `(${diffHours}h ago)`;
  if (diffDays === 1) return "(yesterday)";
  if (diffDays < 7) return `(${diffDays}d ago)`;
  return `(${Math.floor(diffDays / 7)}w ago)`;
}

/**
 * Group checkpoints by time periods for metrics display
 */
function groupCheckpointsByTime(checkpoints: JournalEntry[]): Record<string, number> {
  const groups: Record<string, number> = {
    "Today": 0,
    "Yesterday": 0,
    "This week": 0,
    "Earlier": 0,
  };

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

  checkpoints.forEach(checkpoint => {
    const checkpointDate = new Date(checkpoint.timestamp);

    if (checkpointDate >= today) {
      groups["Today"]++;
    } else if (checkpointDate >= yesterday) {
      groups["Yesterday"]++;
    } else if (checkpointDate >= weekAgo) {
      groups["This week"]++;
    } else {
      groups["Earlier"]++;
    }
  });

  return groups;
}