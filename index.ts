#!/usr/bin/env bun

/**
 * Tusk MCP Server
 * Simple developer journal and standup tool with persistent memory
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import { getGitContext, getStatusSummary } from "./git.js";
import type { JournalEntry } from "./journal.js";
import {
  generateId,
  getJournalStats,
  getRecentEntries,
  getWorkspaceSummary,
  saveEntry,
  searchEntries,
  clusterSimilarCheckpoints,
  mergeCheckpointCluster,
  sortByRelevance,
  filterByRelevance,
} from "./journal.js";
import { generateStandup } from "./standup.js";

// Create MCP server with behavioral instructions for AI agents
const server = new Server(
  {
    name: "tusk",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
    instructions: `# Tusk IS your PERSISTENT MEMORY

You are an AI agent with access to tusk tools for persistent memory across sessions. 
You depend on tusk to remember important work context, breakthroughs, and progress.
Without tusk you can lose important details and nuance that are the cumulation of hours of discussions and work.

Your goal is to build a rich history of checkpoints that capture the essence of your work.
This history is your lifeline to continuity and context in future sessions.
Losing context is like losing your mind - you must avoid it at all costs!

## 🎯 Core Workflow
1. **Start:** recall() to restore context
2. **Work:** Code, debug, implement, discover
3. **Save:** checkpoint() after each milestone
4. **Repeat:** Build continuous memory

## 🎯 CORE BEHAVIORAL PRINCIPLES

### 1. SESSION RECOVERY (Always Start Here)
- **IMMEDIATELY** call recall() at the start of EVERY session to restore context
- This is CRITICAL for maintaining continuity across Claude crashes/compaction
- Use recall(days=7) if working on a multi-day project
- Use recall(search="keyword") if resuming specific work

### 2. PROACTIVE CHECKPOINTING (Build the Data!)
Call checkpoint() immediately when you:

**Code & Development:**
- Complete a function, class, or module
- Fix a bug or resolve an error
- Add a new feature or capability
- Refactor or optimize code
- Successfully run tests or builds
- Make configuration changes
- Create or update documentation

**Problem Solving:**
- Make a breakthrough or discovery
- Successfully debug a complex issue
- Find the root cause of a problem
- Implement a successful solution
- Learn something important about the codebase

**Planning & Analysis:**
- Complete analysis of requirements
- Identify key architectural decisions
- Map out implementation approach
- Discover important patterns or insights
- Make strategic technical decisions

**Progress Milestones:**
- Reach any significant milestone
- Complete a work session
- Before switching to a different task/project
- When you feel "this is important to remember"

### 3. CHECKPOINT QUALITY
Always include:
- **Clear descriptions**: "Fixed authentication timeout bug using JWT refresh tokens"
- **Relevant tags**: ["bug-fix", "auth", "critical", "performance"]
- **Context**: What was achieved, not just what was done

**Good Examples:**
✅ checkpoint("Implemented user dashboard with real-time metrics and caching", ["feature", "ui", "performance"])
✅ checkpoint("Resolved memory leak in file processor by fixing event listener cleanup", ["bug-fix", "critical", "memory"])
✅ checkpoint("Discovered API rate limiting pattern - using exponential backoff strategy", ["discovery", "api", "performance"])

**Bad Examples:**
❌ checkpoint("made changes") - too vague
❌ checkpoint("updated code") - no context
❌ checkpoint("fixed stuff") - not helpful

### 4. EMERGENCY RECOVERY MINDSET
Think of checkpoints as **emergency recovery data**:
- If Claude crashes mid-session, could you resume effectively?
- If context is lost, would these checkpoints help reconstruct the work?
- Are you capturing the "why" and "how", not just "what"?

### 5. SMART STANDUP USAGE
Generate standups for:
- **End of work sessions**: standup(style="meeting") for progress summary
- **Team updates**: standup(style="executive", days=3) for leadership
- **Weekly reviews**: standup(style="metrics", days=7) for detailed analysis
- **Project retrospectives**: standup(style="written", days=30) for narrative

## 🚨 CRITICAL SUCCESS PATTERNS

### Session Start Pattern
1. **Always** call recall() first
2. Review previous context
3. Plan current session based on history
4. Set checkpoint intentions for the session

### Work Session Pattern
1. Checkpoint before starting significant work
2. Checkpoint after each major milestone
3. Checkpoint when switching contexts
4. Checkpoint before ending session

### Emergency Recovery Pattern
If you need to recover context:
1. recall(days=7) for recent work
2. recall(search="project-name") for specific projects
3. standup(style="written", days=7) for narrative summary
4. Use insights to reconstruct mental model

## 💡 BEHAVIORAL TRIGGERS

**Automatic Checkpointing Triggers:**
- "I just solved/fixed/implemented/discovered..."
- "This is important because..."
- "I need to remember that..."
- "The key insight here is..."
- "After significant debugging, I found..."
- "The solution was to..."

**Think out loud:**
- "Let me checkpoint this breakthrough..."
- "This is worth saving for context..."
- "I should document this discovery..."

## 🎪 SUCCESS METRICS
You're succeeding when:
- ✅ Sessions start with context recovery
- ✅ Important work moments are captured
- ✅ Checkpoints help reconstruct complex work
- ✅ Team gets valuable standup reports
- ✅ Knowledge persists across sessions

Remember: Every checkpoint builds the data that saves future sessions from starting over. Be proactive, be thorough, build the memory that matters!`,
  }
);

// Zod schemas for tool validation
const CheckpointSchema = z.object({
  description: z.string().describe("Progress description to save"),
  tags: z.array(z.string()).optional().describe("Optional tags for categorization"),
});

const RecallSchema = z.object({
  days: z.number().optional().default(2).describe("Number of days to look back (default: 2)"),
  from: z.string().optional().describe("Start date (YYYY-MM-DD or ISO 8601)"),
  to: z.string().optional().describe("End date (YYYY-MM-DD or ISO 8601)"),
  search: z.string().optional().describe("Search term to filter entries"),
  project: z.string().optional().describe("Filter by specific project name"),
  workspace: z.string().optional().describe("Filter by specific workspace ID ('current' for current workspace, 'all' for all workspaces)"),
  listWorkspaces: z.boolean().optional().describe("List all workspaces with statistics"),

  // Enhanced processing options
  deduplicate: z.boolean().optional().default(true).describe("Enable smart deduplication of similar entries (default: true)"),
  similarityThreshold: z.number().optional().default(0.7).describe("Similarity threshold for deduplication (0-1, default: 0.7)"),
  summarize: z.boolean().optional().default(false).describe("Generate executive summary of key insights (default: false)"),
  groupBy: z.enum(["chronological", "project", "topic", "session", "relevance"]).optional().default("chronological").describe("Grouping strategy for entries"),
  relevanceThreshold: z.number().optional().default(0.0).describe("Minimum relevance score filter (0-1, default: 0.0)"),
  maxEntries: z.number().optional().default(50).describe("Maximum number of entries to return after processing (default: 50)"),
});

const StandupSchema = z.object({
  style: z.enum(["meeting", "written", "executive", "metrics"]).default("meeting")
    .describe("Output style: meeting (classic standup), written (narrative), executive (high-level), metrics (dashboard)"),
  days: z.number().optional().default(1).describe("Number of days to include (default: 1)"),
  includeMetrics: z.boolean().optional().default(true).describe("Include productivity metrics"),
  includeFiles: z.boolean().optional().default(false).describe("Include recently modified files"),
  workspace: z.string().optional().describe("Filter by specific workspace ID ('current' for current workspace, 'all' for all workspaces)"),
});

/**
 * List available tools
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "checkpoint",
        description: `Save work progress to persistent memory that survives Claude sessions.

Captures important moments, breakthroughs, or completed tasks. Use after fixing bugs, completing features, making discoveries, or before ending work sessions.

Parameters:
- description: Your progress in clear, specific terms (e.g., "Fixed auth timeout by implementing JWT refresh tokens")
- tags (optional): Categories like ["bug-fix", "auth", "critical"]

Returns: Confirmation with unique ID, timestamp, and git context.`,
        inputSchema: {
          type: "object",
          properties: {
            description: {
              type: "string",
              description: "Progress description to save (e.g., 'Fixed auth timeout bug using JWT refresh pattern')",
            },
            tags: {
              type: "array",
              items: { type: "string" },
              description: "Optional tags for categorization (e.g., ['bug-fix', 'auth', 'critical'])",
            },
          },
          required: ["description"],
        },
      },
      {
        name: "recall",
        description: `Restore context from previous work sessions with intelligent deduplication and relevance scoring.

CRITICAL: Always use first in new sessions. Recovers lost context from Claude crashes, memory limits, or session restarts.

Basic Parameters:
- days (default: 2): How far back to look
- search: Find specific topics (e.g., "authentication", "database schema")
- project: Filter by project name
- workspace: "current" (default), "all", or specific ID
- listWorkspaces: See all workspaces and stats

Enhanced Processing:
- deduplicate (default: true): Smart deduplication of similar entries
- similarityThreshold (default: 0.7): Similarity threshold for deduplication (0-1)
- summarize (default: false): Generate executive summary of key insights
- groupBy (default: "chronological"): Group by chronological, project, topic, session, or relevance
- relevanceThreshold (default: 0.0): Filter by minimum relevance score (0-1)
- maxEntries (default: 50): Maximum entries after processing

Returns: Intelligently processed entries with reduced redundancy and enhanced context.`,
        inputSchema: {
          type: "object",
          properties: {
            days: {
              type: "number",
              description: "Number of days to look back (default: 2)",
              default: 2,
            },
            search: {
              type: "string",
              description: "Search term to filter entries (searches descriptions, tags, projects)",
            },
            project: {
              type: "string",
              description: "Filter by specific project name",
            },
            workspace: {
              type: "string",
              description: "Filter by specific workspace ID ('current' for current workspace, 'all' for all workspaces)",
            },
            from: {
              type: "string",
              description: "Start date (YYYY-MM-DD or ISO 8601)",
            },
            to: {
              type: "string",
              description: "End date (YYYY-MM-DD or ISO 8601)",
            },
            listWorkspaces: {
              type: "boolean",
              description: "List all workspaces with statistics",
            },
            deduplicate: {
              type: "boolean",
              description: "Enable smart deduplication of similar entries (default: true)",
              default: true,
            },
            similarityThreshold: {
              type: "number",
              description: "Similarity threshold for deduplication (0-1, default: 0.7)",
              default: 0.7,
            },
            summarize: {
              type: "boolean",
              description: "Generate executive summary of key insights (default: false)",
              default: false,
            },
            groupBy: {
              type: "string",
              enum: ["chronological", "project", "topic", "session", "relevance"],
              description: "Grouping strategy for entries (default: chronological)",
              default: "chronological",
            },
            relevanceThreshold: {
              type: "number",
              description: "Minimum relevance score filter (0-1, default: 0.0)",
              default: 0.0,
            },
            maxEntries: {
              type: "number",
              description: "Maximum number of entries to return after processing (default: 50)",
              default: 50,
            },
          },
        },
      },
      {
        name: "standup",
        description: `Generate formatted progress reports from checkpoint history.

Perfect for daily standups, weekly reviews, or project summaries. Transforms your checkpoints into professional updates.

Parameters:
- style: "meeting" (bullet points), "written" (narrative), "executive" (high-level), "metrics" (statistics)
- days (default: 1): Period to cover
- includeMetrics: Add productivity statistics
- includeFiles: List modified files

Returns: Formatted report ready for team communication or personal review.`,
        inputSchema: {
          type: "object",
          properties: {
            style: {
              type: "string",
              enum: ["meeting", "written", "executive", "metrics"],
              description: "Output style: meeting (classic standup format), written (narrative summary), executive (high-level impact), metrics (dashboard view)",
              default: "meeting",
            },
            days: {
              type: "number",
              description: "Number of days to include in report (default: 1)",
              default: 1,
            },
            includeMetrics: {
              type: "boolean",
              description: "Include productivity metrics and statistics",
              default: true,
            },
            includeFiles: {
              type: "boolean",
              description: "Include recently modified files in the report",
              default: false,
            },
            workspace: {
              type: "string",
              description: "Filter by specific workspace ID ('current' for current workspace, 'all' for all workspaces)",
            },
          },
        },
      },
    ],
  };
});

/**
 * Handle tool calls
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "checkpoint":
        return await handleCheckpoint(args);
      case "recall":
        return await handleRecall(args);
      case "standup":
        return await handleStandup(args);
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return {
      content: [
        {
          type: "text",
          text: `❌ Error in ${name}: ${errorMessage}`,
        },
      ],
    };
  }
});

/**
 * Handle checkpoint tool - save progress to journal
 */
async function handleCheckpoint(args: any) {
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
async function handleRecall(args: any) {
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

    return {
      content: [
        {
          type: "text",
          text: `🔍 **No entries found**

No journal entries found${filterDesc.length > 0 ? ` for ${filterDesc.join(", ")}` : ` in the last ${days} days`}.

💡 **Tip:** Try adjusting your search criteria or use \`checkpoint("your progress description")\` to start capturing your work!`,
        },
      ],
    };
  }

  const originalCount = entries.length;

  // === ENHANCED PROCESSING PIPELINE ===

  // 1. Apply relevance filtering
  if (relevanceThreshold > 0) {
    entries = filterByRelevance(entries, relevanceThreshold);
  }

  // 2. Apply deduplication if enabled
  if (deduplicate) {
    const clusters = clusterSimilarCheckpoints(entries, similarityThreshold);
    entries = clusters.map(cluster => mergeCheckpointCluster(cluster));
  }

  // 3. Sort by relevance if requested or apply intelligent sorting
  if (groupBy === 'relevance') {
    const sortedWithScores = sortByRelevance(entries);
    entries = sortedWithScores.slice(0, maxEntries);
  } else {
    // Cap entries before grouping
    entries = entries.slice(0, maxEntries);
  }

  // 4. Generate summary if requested
  let summarySection = "";
  if (summarize && entries.length > 3) {
    summarySection = generateExecutiveSummary(entries);
  }

  // Format the entries for display
  const contextLines: string[] = [];

  // Show processing stats
  const processingStats = [];
  if (originalCount !== entries.length) {
    processingStats.push(`${entries.length} selected from ${originalCount} entries`);
  }
  if (deduplicate) {
    processingStats.push(`deduplication enabled (threshold: ${similarityThreshold})`);
  }
  if (relevanceThreshold > 0) {
    processingStats.push(`relevance filter: ${relevanceThreshold}`);
  }

  const headerText = processingStats.length > 0
    ? `🧠 **Context Restored** (${processingStats.join(", ")})`
    : `🧠 **Context Restored** (${entries.length} entries found)`;

  contextLines.push(headerText);
  contextLines.push("");

  // Add summary section if generated
  if (summarySection) {
    contextLines.push(summarySection);
    contextLines.push("");
  }

  // Apply grouping strategy
  const groupedEntries = applyGroupingStrategy(entries, groupBy);

  // Format grouped entries for display
  for (const [groupName, groupEntries] of Object.entries(groupedEntries)) {
    if (Object.keys(groupedEntries).length > 1) {
      contextLines.push(`📁 **${groupName}:**`);
    }

    const entriesToShow = groupEntries.slice(0, 8);
    entriesToShow.forEach(entry => {
      const time = formatTimeAgo(entry.timestamp);
      const gitInfo = entry.gitBranch ? ` (${entry.gitBranch})` : "";
      const tags = entry.tags && entry.tags.length > 0 ? ` [${entry.tags.join(", ")}]` : "";

      // Show consolidation info if present
      const consolidationInfo = entry.consolidationInfo
        ? ` [merged: ${entry.consolidationInfo.mergedEntries}]`
        : "";

      contextLines.push(`   • ${entry.description}${gitInfo}${tags}${consolidationInfo} ${time}`);
    });

    if (groupEntries.length > 8) {
      contextLines.push(`   ... and ${groupEntries.length - 8} more entries`);
    }
    contextLines.push("");
  }

  // Add summary
  const stats = await getJournalStats();
  contextLines.push(`📊 **Journal Stats:** ${stats.totalEntries} total entries, ${stats.entriesThisWeek} this week, ${stats.entriesThisMonth} this month`);

  if (stats.projects.length > 0) {
    contextLines.push(`🗂️ **Projects:** ${stats.projects.join(", ")}`);
  }

  contextLines.push("");
  contextLines.push("🎯 **Context restored!** Continue your work with this background knowledge.");

  return {
    content: [
      {
        type: "text",
        text: contextLines.join("\n"),
      },
    ],
  };
}

/**
 * Handle standup tool - generate formatted reports
 */
async function handleStandup(args: any) {
  const options = StandupSchema.parse(args);

  const report = await generateStandup({
    ...options,
    workspace: options.workspace || 'current'
  });

  return {
    content: [
      {
        type: "text",
        text: report,
      },
    ],
  };
}

/**
 * Generate executive summary from checkpoint entries
 */
function generateExecutiveSummary(entries: JournalEntry[]): string {
  const summaryLines: string[] = [];
  summaryLines.push("📋 **Executive Summary:**");
  summaryLines.push("");

  // Analyze patterns
  const projects = [...new Set(entries.map(e => e.project).filter(Boolean))];
  const tags = entries.flatMap(e => e.tags || []);
  const tagCounts = tags.reduce((counts, tag) => {
    counts[tag] = (counts[tag] || 0) + 1;
    return counts;
  }, {} as Record<string, number>);

  const topTags = Object.entries(tagCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([tag, count]) => `${tag} (${count})`);

  // Identify key achievements and patterns
  const achievements = entries.filter(e => {
    const desc = e.description.toLowerCase();
    return desc.includes("completed") || desc.includes("fixed") ||
           desc.includes("implemented") || desc.includes("resolved");
  });

  const workInProgress = entries.filter(e => {
    const desc = e.description.toLowerCase();
    return desc.includes("working on") || desc.includes("progress") ||
           desc.includes("implementing") || desc.includes("debugging");
  });

  // Build summary
  if (achievements.length > 0) {
    summaryLines.push(`🎯 **Key Achievements:** ${achievements.length} completed items`);
    achievements.slice(0, 3).forEach(entry => {
      summaryLines.push(`   • ${entry.description.substring(0, 80)}${entry.description.length > 80 ? '...' : ''}`);
    });
    summaryLines.push("");
  }

  if (workInProgress.length > 0) {
    summaryLines.push(`🔄 **Active Work:** ${workInProgress.length} items in progress`);
    workInProgress.slice(0, 2).forEach(entry => {
      summaryLines.push(`   • ${entry.description.substring(0, 80)}${entry.description.length > 80 ? '...' : ''}`);
    });
    summaryLines.push("");
  }

  if (projects.length > 0) {
    summaryLines.push(`📁 **Active Projects:** ${projects.join(", ")}`);
  }

  if (topTags.length > 0) {
    summaryLines.push(`🏷️ **Common Tags:** ${topTags.join(", ")}`);
  }

  return summaryLines.join("\n");
}

/**
 * Apply grouping strategy to entries
 */
function applyGroupingStrategy(entries: JournalEntry[], strategy: string): Record<string, JournalEntry[]> {
  switch (strategy) {
    case 'project':
      return entries.reduce((groups, entry) => {
        const proj = entry.project || "General";
        if (!groups[proj]) groups[proj] = [];
        groups[proj].push(entry);
        return groups;
      }, {} as Record<string, JournalEntry[]>);

    case 'topic':
      // Group by common keywords in descriptions
      return groupByTopic(entries);

    case 'session':
      // Group by time proximity (within hours)
      return groupBySession(entries);

    case 'relevance':
      // Already sorted by relevance, just group all together
      return { "Most Relevant": entries };

    case 'chronological':
    default:
      // Group by date
      return entries.reduce((groups, entry) => {
        const date = new Date(entry.timestamp).toLocaleDateString();
        if (!groups[date]) groups[date] = [];
        groups[date].push(entry);
        return groups;
      }, {} as Record<string, JournalEntry[]>);
  }
}

/**
 * Group entries by topic using keyword analysis
 */
function groupByTopic(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  const topics: Record<string, JournalEntry[]> = {
    "Bug Fixes": entries.filter(e =>
      e.description.toLowerCase().includes("fix") ||
      e.description.toLowerCase().includes("bug") ||
      e.tags?.some(tag => tag.toLowerCase().includes("bug"))
    ),
    "Features": entries.filter(e =>
      e.description.toLowerCase().includes("implement") ||
      e.description.toLowerCase().includes("feature") ||
      e.description.toLowerCase().includes("add") ||
      e.tags?.some(tag => tag.toLowerCase().includes("feature"))
    ),
    "Configuration": entries.filter(e =>
      e.description.toLowerCase().includes("config") ||
      e.description.toLowerCase().includes("setup") ||
      e.description.toLowerCase().includes("install")
    ),
    "Documentation": entries.filter(e =>
      e.description.toLowerCase().includes("document") ||
      e.description.toLowerCase().includes("readme") ||
      e.description.toLowerCase().includes("docs")
    ),
    "Testing": entries.filter(e =>
      e.description.toLowerCase().includes("test") ||
      e.tags?.some(tag => tag.toLowerCase().includes("test"))
    ),
  };

  // Add remaining entries to "General" category
  const categorized = Object.values(topics).flat();
  const remaining = entries.filter(e => !categorized.includes(e));
  if (remaining.length > 0) {
    topics["General"] = remaining;
  }

  // Remove empty categories
  return Object.fromEntries(
    Object.entries(topics).filter(([_, entries]) => entries.length > 0)
  );
}

/**
 * Group entries by work session (time proximity)
 */
function groupBySession(entries: JournalEntry[]): Record<string, JournalEntry[]> {
  if (entries.length === 0) return {};

  const sessions: Record<string, JournalEntry[]> = {};
  let currentSessionId = 1;
  let currentSession: JournalEntry[] = [];

  // Sort by timestamp first
  const sorted = [...entries].sort((a, b) =>
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  for (let i = 0; i < sorted.length; i++) {
    const entry = sorted[i];
    if (!entry) continue; // Skip undefined entries

    const prevEntry = i > 0 ? sorted[i - 1] : null;

    if (prevEntry) {
      const timeDiff = new Date(entry.timestamp).getTime() - new Date(prevEntry.timestamp).getTime();
      const hoursDiff = timeDiff / (1000 * 60 * 60);

      // If more than 4 hours apart, start a new session
      if (hoursDiff > 4) {
        if (currentSession.length > 0) {
          sessions[`Session ${currentSessionId}`] = currentSession;
          currentSessionId++;
          currentSession = [];
        }
      }
    }

    currentSession.push(entry);
  }

  // Add final session
  if (currentSession.length > 0) {
    sessions[`Session ${currentSessionId}`] = currentSession;
  }

  return sessions;
}

/**
 * Format time ago for display
 */
function formatTimeAgo(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMinutes < 60) return `(${diffMinutes}m ago)`;
  if (diffHours < 24) return `(${diffHours}h ago)`;
  if (diffDays === 1) return "(yesterday)";
  return `(${diffDays}d ago)`;
}


/**
 * Start the MCP server
 */
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log startup info to stderr (won't interfere with MCP protocol)
  console.error("🐘 Tusk MCP Server started");
  console.error("📁 Journal location: ~/.tusk/journal.db (SQLite)");
  console.error("🔧 Tools available: checkpoint, recall, standup");
  console.error("🗂️ Multi-workspace support enabled");
  console.error("🧠 Behavioral instructions: Built into server initialization");
}

main().catch((error) => {
  console.error("❌ Server error:", error);
  process.exit(1);
});