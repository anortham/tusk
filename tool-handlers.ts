/**
 * MCP Tool Handler Functions for Tusk Journal System
 * Handler functions for checkpoint, recall, and standup tools
 */

import { getGitContext, getStatusSummary } from "./git.js";
import { generateId, saveEntry, getRecentEntries, searchEntries, getWorkspaceSummary, getCurrentWorkspace } from "./journal.js";
import { generateStandup } from "./standup.js";
import { CheckpointSchema, RecallSchema, StandupSchema } from "./schemas.js";
import { clusterSimilarCheckpoints, mergeCheckpointCluster } from "./similarity-utils.js";
import { sortByRelevance, filterByRelevance } from "./relevance-scoring.js";
import type { JournalEntry } from "./types.js";

/**
 * Handle checkpoint tool - save progress to journal
 */
export async function handleCheckpoint(args: any) {
  const { description, tags } = CheckpointSchema.parse(args);

  // Capture git context automatically
  const gitInfo = getGitContext();

  // Create journal entry
  const entry: JournalEntry = {
    id: generateId(),
    timestamp: new Date().toISOString(),
    description,
    project: gitInfo.project,
    gitBranch: gitInfo.branch,
    gitCommit: gitInfo.commit,
    files: gitInfo.files,
    tags,
  };

  // Save to journal
  await saveEntry(entry);

  // Generate success response
  const gitStatus = getStatusSummary();

  return {
    content: [
      {
        type: "text",
        text: `✅ **Checkpoint saved**

📝 **Progress:** ${description}
🆔 **ID:** ${entry.id}
⏰ **Time:** ${new Date().toLocaleString()}
${gitInfo.project ? `📁 **Project:** ${gitInfo.project}` : ""}
${gitInfo.branch ? `🌿 **Git:** ${gitStatus}` : ""}
${tags && tags.length > 0 ? `🏷️ **Tags:** ${tags.join(", ")}` : ""}

Your progress is now safely captured and will survive Claude sessions! 🐘

💡 **Next:** Use recall() when starting your next session to restore this context.`,
      },
    ],
  };
}

/**
 * Handle recall tool - restore previous context
 */
export async function handleRecall(args: any) {
  const {
    days, from, to, search, project, workspace, listWorkspaces,
    deduplicate, similarityThreshold, summarize, groupBy, relevanceThreshold, maxEntries
  } = RecallSchema.parse(args);

  // Handle workspace listing if requested
  if (listWorkspaces) {
    const workspaces = await getWorkspaceSummary();
    if (workspaces.length === 0) {
      return {
        content: [
          {
            type: "text",
            text: `📂 **No workspaces found**

No workspaces have been detected. Start by creating checkpoints in different projects to see workspace organization.

💡 **Tip:** Use \`checkpoint("your progress description")\` to start capturing your work!`,
          },
        ],
      };
    }

    const workspaceLines: string[] = [];
    workspaceLines.push(`📂 **Found ${workspaces.length} workspace${workspaces.length === 1 ? '' : 's'}:**`);
    workspaceLines.push("");

    workspaces.forEach(ws => {
      workspaceLines.push(`📁 **${ws.name}**`);
      workspaceLines.push(`   • Path: ${ws.path}`);
      workspaceLines.push(`   • Entries: ${ws.entryCount}`);
      if (ws.lastActivity) {
        workspaceLines.push(`   • Last activity: ${ws.lastActivity}`);
      }
      if (ws.projects.length > 0) {
        workspaceLines.push(`   • Projects: ${ws.projects.join(', ')}`);
      }
      workspaceLines.push("");
    });

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

    // Get workspace info for diagnostics
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

  const originalCount = entries.length;

  // Apply relevance filtering
  if (relevanceThreshold > 0) {
    entries = filterByRelevance(entries, relevanceThreshold);
  }

  // Apply deduplication if enabled
  if (deduplicate) {
    const clusters = clusterSimilarCheckpoints(entries, similarityThreshold);
    entries = clusters.map(cluster => mergeCheckpointCluster(cluster));
  }

  // Apply grouping and limit results
  // (Additional processing logic would go here)

  return {
    content: [
      {
        type: "text",
        text: "🧠 **Context Restored** " + `(${entries.length} entries found)` + "\n\n" +
              entries.map(entry => `• ${entry.description}`).join("\n"),
      },
    ],
  };
}

/**
 * Handle standup tool - generate formatted progress reports
 */
export async function handleStandup(args: any) {
  const { style, days, includeMetrics, includeFiles, workspace } = StandupSchema.parse(args);

  // Get recent entries for the standup period
  const entries = await getRecentEntries({
    days,
    workspace: workspace || 'current'
  });

  if (entries.length === 0) {
    return {
      content: [
        {
          type: "text",
          text: `📋 **No standup data**

No journal entries found for the last ${days} day${days === 1 ? '' : 's'}.

💡 **Tip:** Use \`checkpoint("your progress description")\` to start capturing your work!`,
        },
      ],
    };
  }

  // Generate standup report
  const standupOptions = {
    style,
    days,
    includeMetrics,
    includeFiles,
    workspace: workspace || 'current'
  };
  const standupContent = await generateStandup(standupOptions);

  return {
    content: [
      {
        type: "text",
        text: standupContent,
      },
    ],
  };
}