/**
 * Enhanced Recall Handler with Context Intelligence
 *
 * Provides sophisticated context restoration using:
 * - Context-type aware prioritization
 * - Intelligent grouping and summarization
 * - Adaptive length management
 * - Query-aware filtering
 */

import { RecallSchema } from "../core/schemas.js";
import { searchEntries, getRecentEntries, getCurrentWorkspace } from "../utils/journal.js";
import { manageContextLength, groupContextByIntelligence, calculateEnhancedRelevanceScore } from "./enhanced-relevance-scoring.js";
import { clusterSimilarCheckpoints, mergeCheckpointCluster } from "../analysis/similarity-utils.js";
import type { CheckpointEntry } from "../core/types.js";

interface CurrentWorkContext {
  activeProject?: string;
  recentTechnologies?: string[];
  currentWorkType?: string;
  gitBranch?: string;
  timeOfDay: string;
}

/**
 * Detect current work context for relevance scoring
 */
async function detectCurrentWorkContext(): Promise<CurrentWorkContext> {
  const context: CurrentWorkContext = {
    timeOfDay: getCurrentTimeOfDay()
  };

  try {
    // Get recent entries to detect current work patterns
    const recentEntries = await getRecentEntries({ days: 1, workspace: 'current' });

    if (recentEntries.length > 0) {
      // Extract active project
      const projects = recentEntries.map(e => e.project).filter(Boolean);
      if (projects.length > 0) {
        context.activeProject = getMostFrequent(projects);
      }

      // Extract recent technologies
      const techTags = recentEntries
        .flatMap(e => e.tags || [])
        .filter(tag => tag.startsWith('tech-'))
        .map(tag => tag.replace('tech-', ''));
      context.recentTechnologies = [...new Set(techTags)];

      // Extract current work type
      const workTypes = recentEntries
        .flatMap(e => e.tags || [])
        .filter(tag => ['feature-development', 'bug-fix', 'refactoring', 'testing', 'performance'].includes(tag));
      if (workTypes.length > 0) {
        context.currentWorkType = getMostFrequent(workTypes);
      }
    }

    // Try to get git context
    const { spawnSync } = await import("bun");
    const gitResult = spawnSync(["git", "branch", "--show-current"], { stdout: "pipe", stderr: "pipe" });
    if (gitResult.success) {
      context.gitBranch = new TextDecoder().decode(gitResult.stdout).trim();
    }
  } catch (error) {
    // Context detection failed, continue with basic context
  }

  return context;
}

function getCurrentTimeOfDay(): string {
  const hour = new Date().getHours();
  if (hour < 6) return "late-night";
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  if (hour < 22) return "evening";
  return "late-night";
}

function getMostFrequent<T>(items: T[]): T | undefined {
  const counts = new Map<T, number>();
  for (const item of items) {
    counts.set(item, (counts.get(item) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
}

/**
 * Generate intelligent context presentation
 */
function formatIntelligentContext(grouped: ReturnType<typeof groupContextByIntelligence>, summary: string, currentContext: CurrentWorkContext): string {
  const sections: string[] = [];

  // Add current context summary
  const contextInfo: string[] = [];
  if (currentContext.activeProject) contextInfo.push(`📁 Project: ${currentContext.activeProject}`);
  if (currentContext.gitBranch) contextInfo.push(`🌿 Branch: ${currentContext.gitBranch}`);
  if (currentContext.currentWorkType) contextInfo.push(`🔧 Focus: ${currentContext.currentWorkType}`);
  if (currentContext.recentTechnologies?.length) {
    contextInfo.push(`💻 Tech: ${currentContext.recentTechnologies.slice(0, 3).join(', ')}`);
  }

  if (contextInfo.length > 0) {
    sections.push(`🧠 **Current Context** (${currentContext.timeOfDay})\n${contextInfo.join(' | ')}\n`);
  }

  // Critical Insights Section
  if (grouped.criticalInsights.length > 0) {
    sections.push("🔍 **Critical Insights & Discoveries**");
    grouped.criticalInsights.forEach(entry => {
      const insight = extractInsightType(entry);
      sections.push(`• ${insight}: ${truncateForDisplay(entry.description, 120)}`);
    });
    sections.push("");
  }

  // Recent Milestones Section
  if (grouped.recentMilestones.length > 0) {
    sections.push("🏗️ **Recent Development Milestones**");
    grouped.recentMilestones.forEach(entry => {
      const milestone = formatMilestone(entry);
      sections.push(`• ${milestone}`);
    });
    sections.push("");
  }

  // Current Work Section
  if (grouped.currentWork.length > 0) {
    sections.push("⚡ **Current Work & Progress**");
    grouped.currentWork.forEach(entry => {
      sections.push(`• ${truncateForDisplay(entry.description, 100)}`);
    });
    sections.push("");
  }

  // Background Context (if any)
  if (grouped.background.length > 0) {
    sections.push("📋 **Background Context**");
    sections.push(`• ${grouped.background.length} additional context items available`);
    sections.push("");
  }

  // Add summary
  sections.push(`📊 **Context Summary**: ${summary}`);

  return sections.join("\n");
}

function extractInsightType(entry: CheckpointEntry): string {
  const tags = entry.tags || [];
  if (tags.includes('discovery')) return '🔍 Discovery';
  if (tags.includes('solution')) return '💡 Solution';
  if (tags.includes('diagnosis')) return '🩺 Diagnosis';
  if (tags.includes('architecture')) return '🏗️ Architecture';
  if (entry.description.toLowerCase().includes('claude insight')) return '🧠 Insight';
  return '💭 Insight';
}

function formatMilestone(entry: CheckpointEntry): string {
  if (entry.description.includes('Git commit:')) {
    const commit = entry.description.replace('Git commit: ', '');
    return `🔧 ${truncateForDisplay(commit, 80)}`;
  }

  const tags = entry.tags || [];
  if (tags.includes('bug-fix')) return `🐛 ${truncateForDisplay(entry.description, 80)}`;
  if (tags.includes('feature-development')) return `✨ ${truncateForDisplay(entry.description, 80)}`;
  if (tags.includes('refactoring')) return `♻️ ${truncateForDisplay(entry.description, 80)}`;

  return `📝 ${truncateForDisplay(entry.description, 80)}`;
}

function truncateForDisplay(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + "...";
}

/**
 * Enhanced recall handler with context intelligence
 */
export async function handleEnhancedRecall(args: any) {
  const {
    days,
    from,
    to,
    search,
    project,
    workspace,
    deduplicate,
    similarityThreshold,
    summarize,
    groupBy,
    relevanceThreshold,
    maxEntries
  } = RecallSchema.parse(args);

  // Get current work context for intelligent scoring
  const currentContext = await detectCurrentWorkContext();

  // Handle workspace display for "no results" case
  if (workspace === 'list') {
    const workspaceLines = [`🏠 **Current Workspace**: ${getCurrentWorkspace().name}`];

    return {
      content: [
        {
          type: "text",
          text: workspaceLines.join("\n").trim(),
        },
      ],
    };
  }

  // Get entries based on filters
  let entries = search
    ? await searchEntries(search, { workspace: workspace || 'current' })
    : await getRecentEntries({ days, from, to, project, workspace: workspace || 'current' });

  if (entries.length === 0) {
    const filterDesc = [];
    if (search) filterDesc.push(`search: "${search}"`);
    if (project) filterDesc.push(`project: "${project}"`);
    if (days !== 2) filterDesc.push(`${days} days`);

    const currentWorkspace = getCurrentWorkspace();
    const workspaceScope = workspace || 'current';

    let workspaceInfo = '';
    if (workspaceScope === 'current') {
      workspaceInfo = `\n🏠 **Searched workspace:** ${currentWorkspace.name} (${currentWorkspace.path})`;
    } else if (workspaceScope === 'all') {
      workspaceInfo = `\n🌐 **Searched scope:** All workspaces`;
    } else {
      workspaceInfo = `\n📁 **Searched workspace:** ${workspaceScope}`;
    }

    const suggestions = workspaceScope === 'current'
      ? `\n💡 **Try:** Use \`workspace: 'all'\` to search across all workspaces, or use \`checkpoint("your progress description")\` to start capturing work in this workspace.`
      : `\n💡 **Tip:** Try adjusting your search criteria or use \`checkpoint("your progress description")\` to start capturing your work!`;

    return {
      content: [
        {
          type: "text",
          text: `🔍 **No entries found**

No journal entries found${filterDesc.length > 0 ? ` for ${filterDesc.join(", ")}` : ` in the last ${days} days`}.${workspaceInfo}${suggestions}`,
        },
      ],
    };
  }

  // Apply enhanced relevance filtering
  if (relevanceThreshold > 0) {
    entries = entries.filter(entry =>
      calculateEnhancedRelevanceScore(entry, undefined, currentContext) >= relevanceThreshold
    );
  }

  // Apply intelligent deduplication if enabled
  if (deduplicate) {
    const clusters = clusterSimilarCheckpoints(entries, similarityThreshold);
    entries = clusters.map(cluster => mergeCheckpointCluster(cluster));
  }

  // Apply intelligent context length management
  const maxTokens = Math.min(maxEntries * 50, 4000); // Estimate 50 tokens per entry
  const { entries: managedEntries, summary } = manageContextLength(entries, maxTokens);

  // Group context intelligently
  const grouped = groupContextByIntelligence(managedEntries);

  // Format output with intelligence
  const formattedContext = formatIntelligentContext(grouped, summary, currentContext);

  return {
    content: [
      {
        type: "text",
        text: formattedContext,
      },
    ],
  };
}