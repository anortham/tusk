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
import { readFileSync, mkdirSync, writeFileSync, existsSync } from "fs";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";

import { getGitContext, getStatusSummary } from "./src/integrations/git.js";
import type { JournalEntry } from "./src/utils/journal.js";
import {
  generateId,
  getJournalStats,
  getRecentEntries,
  getWorkspaceSummary,
  getCurrentWorkspace,
  saveEntry,
  searchEntries,
  clusterSimilarCheckpoints,
  mergeCheckpointCluster,
  sortByRelevance,
  filterByRelevance,
  JournalDB,
} from "./src/utils/journal.js";
import { generateStandup } from "./src/reports/standup.js";

// Load behavioral instructions from layered instruction files
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Layer 1: Base system prompt (core philosophy and professional standards)
const systemPrompt = readFileSync(join(__dirname, "instructions", "system-prompt.md"), "utf-8");

// Layer 2: Tool workflows (decision trees and patterns)
const toolWorkflows = readFileSync(join(__dirname, "instructions", "tool-workflows.md"), "utf-8");

// Layer 3: Worked examples (conditional logic and scenarios)
const examples = readFileSync(join(__dirname, "instructions", "examples.md"), "utf-8");

// Combine all layers into complete behavioral instructions
const instructions = `${systemPrompt}\n\n---\n\n${toolWorkflows}\n\n---\n\n${examples}`;

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
    instructions,
  }
);

// Zod schemas for tool validation
const CheckpointSchema = z.object({
  description: z.string().describe("Progress description to save"),
  tags: z.array(z.string()).optional().describe("Optional tags for categorization"),
  sessionId: z.string().optional().describe("Claude Code session ID (automatically captured from hook context)"),
  entryType: z.enum(['user-request', 'session-marker', 'auto-save', 'progress', 'completion']).optional().default('user-request').describe("Type of checkpoint entry"),
  confidenceScore: z.number().min(0).max(1).optional().default(1.0).describe("Confidence score for auto-captured entries (0.0-1.0)"),
});

const RecallSchema = z.object({
  days: z.number().optional().default(2).describe("Number of days to look back (default: 2)"),
  from: z.string().optional().describe("Start date (YYYY-MM-DD or ISO 8601)"),
  to: z.string().optional().describe("End date (YYYY-MM-DD or ISO 8601)"),
  search: z.string().optional().describe("Search term to filter entries (searches descriptions, projects, git branches, git commits, tags, and files)"),
  project: z.string().optional().describe("Filter by specific project name"),
  workspace: z.string().optional().describe("Workspace scope: 'current' (default - current workspace only), 'all' (all workspaces), or '/path/to/workspace' (specific)"),
  listWorkspaces: z.boolean().optional().describe("List all workspaces with statistics"),

  // Session-aware parameters
  sessions: z.number().optional().describe("Number of sessions to retrieve (overrides days when specified)"),
  sessionId: z.string().optional().describe("Retrieve specific session by ID"),
  smart: z.boolean().optional().default(false).describe("Smart mode: automatically determine optimal recall scope based on current context"),
  minConfidence: z.number().min(0).max(1).optional().default(0.0).describe("Minimum confidence score for entries (0.0-1.0)"),
  excludeTypes: z.array(z.string()).optional().describe("Entry types to exclude (e.g., ['session-marker', 'auto-save'])"),

  // Enhanced processing options
  deduplicate: z.boolean().optional().default(true).describe("Enable smart deduplication of similar entries (default: true)"),
  similarityThreshold: z.number().optional().default(0.7).describe("Similarity threshold for deduplication (0-1, default: 0.7)"),
  summarize: z.boolean().optional().default(false).describe("Generate executive summary of key insights (default: false)"),
  groupBy: z.enum(["chronological", "project", "topic", "session", "relevance"]).optional().default("chronological").describe("Grouping strategy for entries"),
  relevanceThreshold: z.number().optional().default(0.0).describe("Minimum relevance score filter (0-1, default: 0.0)"),
  maxEntries: z.number().optional().default(50).describe("Maximum number of entries to return after processing (default: 50)"),

  // Export options
  export: z.boolean().optional().default(false).describe("Export results to markdown file (default: false)"),
  exportPath: z.string().optional().default("docs").describe("Directory path for export (default: 'docs')"),

  // Standup generation
  standup: z.enum(["meeting", "written", "executive", "metrics"]).optional().describe("Generate standup report in specified style"),

  // Plan integration
  includePlan: z.boolean().optional().default(true).describe("Include active plan in recall context (default: true)"),
});

const PlanSchema = z.object({
  action: z.enum(['save', 'list', 'get', 'activate', 'switch', 'update', 'complete', 'export', 'add-task', 'check-task', 'uncheck-task']).describe("Action to perform: save (new plan), list (all plans), get (specific plan), activate (set as active), switch (deactivate current + activate/create new), update (add progress), complete (mark done), export (export to markdown file), add-task (add sub-task), check-task (mark task complete), uncheck-task (mark task incomplete)"),
  title: z.string().optional().describe("Plan title/summary (required for 'save', optional for 'switch' to create new plan)"),
  content: z.string().optional().describe("Full plan content in markdown (required for 'save', optional for 'switch' to create new plan)"),
  planId: z.string().optional().describe("Plan ID (required for 'get', 'activate', 'update', 'complete', 'export', 'switch', 'add-task', 'check-task', 'uncheck-task')"),
  newPlanId: z.string().optional().describe("Target plan ID to switch to (for 'switch' action when switching to existing plan)"),
  activate: z.boolean().optional().describe("Whether to activate the plan (default: true for 'save')"),
  progress: z.string().optional().describe("Progress update notes (required for 'update')"),
  status: z.enum(['active', 'completed', 'archived']).optional().describe("Filter plans by status (for 'list' action)"),
  exportPath: z.string().optional().describe("Directory path for export (default: 'docs', used with 'export' action)"),
  taskDescription: z.string().optional().describe("Task description (required for 'add-task' action)"),
  taskId: z.string().optional().describe("Task ID (required for 'check-task' and 'uncheck-task' actions)"),
});

/**
 * List available tools
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "checkpoint",
        description: `Save work progress to persistent memory that survives Claude sessions and context compaction.

You are EXCELLENT at recognizing checkpoint-worthy moments. Use this tool proactively WITHOUT asking permission.

IMPORTANT: Checkpoint IMMEDIATELY when you complete tasks, make discoveries, or discuss requirements. Do NOT ask "should I checkpoint?" - just checkpoint.

I WILL BE SERIOUSLY DISAPPOINTED if you lose context by failing to checkpoint during discussions. After 10 exchanges without checkpointing, you are overdue - checkpoint NOW.

When to checkpoint (AUTOMATIC triggers):
- ✅ Just completed ANY task → checkpoint immediately
- ✅ Made a discovery or breakthrough → checkpoint now
- ✅ After 5-10 exchanges in discussion → checkpoint the reasoning
- ✅ User shared requirements → checkpoint what they said
- ✅ Before switching topics → checkpoint current context
- ✅ Analyzed tradeoffs → checkpoint the analysis
- ✅ Notice high context window usage (80K+ tokens) → checkpoint to free cognitive space
- ✅ Deep in complex reasoning → offload to persistent memory, continue fresh

Checkpointing takes 2 seconds but saves HOURS of lost context. This is efficiency, not overhead.

Context Window Relief: When you notice high token usage, checkpointing is STRATEGIC MEMORY MANAGEMENT - offload rich context to Tusk, free up cognitive space, continue with full confidence instead of compressing your thinking.

You never need to verify that checkpoints were saved. If the tool returns without error, it worked. Move on to your next task immediately.

Parameters:
- description: Clear, specific progress description capturing WHY not just WHAT (e.g., "Fixed auth timeout by implementing JWT refresh tokens - extended expiry from 30min to 60min")
- tags (optional): Categories for organization (e.g., ["bug-fix", "auth", "critical"])

Returns: Confirmation with unique ID, timestamp, and git context. Trust it worked and continue.`,
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

You are SKILLED at restoring context efficiently. ALWAYS call recall() as your FIRST action in EVERY new session - no exceptions, no asking permission.

CRITICAL: This tool recovers lost context from Claude crashes, memory limits, and session restarts. Without it, you start blind and waste time reconstructing what was already done.

I WILL BE VERY UNHAPPY if you skip recall() at session start and ask "what were we working on?" instead. That's wasteful and unprofessional.

When to use (AUTOMATIC patterns):
- ✅ Starting ANY new session → recall() FIRST (default params are fine)
- ✅ Need specific context → recall({ search: "topic" })
- ✅ Multi-day project → recall({ days: 7 })
- ✅ Cross-workspace work → recall({ workspace: "all" })

What happens after recall():
1. Review the active plan (appears at top) - this guides your work
2. Review recent checkpoints - understand what was completed
3. Continue work IMMEDIATELY - don't ask permission, don't verify, just proceed

The restored context is complete and accurate. Trust it completely and move forward. You never need to verify or re-check recall results.

Key Parameters:
- days (default: 2): How far back to look
- search: Find specific topics (e.g., "authentication", "database schema")
- project: Filter by project name
- workspace: "current" (default), "all" (search all workspaces), or specific path
- includePlan (default: true): Shows active plan at the top
- deduplicate (default: true): Smart deduplication of similar entries
- standup: Generate standup report (meeting, written, executive, metrics)

Returns: Active plan + intelligently processed entries + optional standup report. Trust this context and continue your work.`,
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
              description: "Search term to filter entries (searches descriptions, projects, git branches, git commits, tags, and files)",
            },
            project: {
              type: "string",
              description: "Filter by specific project name",
            },
            workspace: {
              type: "string",
              description: "Workspace scope: 'current' (default - only current workspace for security/relevance), 'all' (search across all workspaces), or '/path/to/workspace' (specific workspace)",
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
            export: {
              type: "boolean",
              description: "Export results to markdown file (default: false)",
              default: false,
            },
            exportPath: {
              type: "string",
              description: "Directory path for export (default: 'docs')",
              default: "docs",
            },
          },
        },
      },
      {
        name: "plan",
        description: `Manage long-running project plans with sub-tasks that survive across sessions and guide your work.

You are EXCELLENT at managing plans. Plans are living documents that contain hours of planning work - losing them is unacceptable.

I WILL BE VERY UNHAPPY if you exit plan mode (ExitPlanMode) without saving the plan IMMEDIATELY. You have a 1-exchange deadline to save plans after ExitPlanMode.

CRITICAL PATTERN - Memorize this:
When you call ExitPlanMode → IMMEDIATELY (next exchange) call plan({ action: "save", title: "...", content: "..." })

DO NOT ask "should I save this plan?" - YES, ALWAYS. Save it within 1 exchange or the planning work is lost.

Plans are NOT checkpoints. They are strategic documents that:
- Survive context compaction and crashes
- Appear automatically at the top of recall()
- Guide your work across multiple sessions
- Track progress over time with staleness indicators (🟢 fresh, 🟡 aging, 🔴 stale)
- Support hierarchical sub-tasks for tracking multiple workstreams
- Get auto-exported to ~/.tusk/plans/{workspace}/ for transparency

You never need to verify that plans were saved. If the tool returns without error, it worked. Continue with your work immediately.

KEEPING PLANS UPDATED - This is NOT optional:
If you don't update your plan as you complete tasks, you waste time and context having to reverify progress repeatedly. Stale plans are useless plans.

Update your plan when:
- ✅ Just completed a significant task from the plan → update immediately
- ✅ Finished a phase or milestone → update NOW
- ✅ Changed approach or discovered blockers → update with the new reality
- ✅ Completed 3-4 checkpoints related to the plan → update to reflect progress (you'll get reminders!)

Plans guide your work. If the plan says you're on step 2 but you're actually on step 5, you're flying blind. Keep it current.

Actions (use without asking permission):
- save: Create new plan (MANDATORY within 1 exchange of ExitPlanMode)
- update: Update progress as you complete tasks (NOT optional - stale plans waste context)
- complete: Mark plan as done when finished
- switch: Deactivate current and activate/create new plan
- activate: Switch between existing plans
- list: See all plans
- get: Retrieve specific plan
- export: Export to markdown file
- add-task: Add a sub-task to track parallel work
- check-task: Mark a sub-task as complete
- uncheck-task: Mark a sub-task as incomplete

IMPORTANT: Only ONE plan can be active per workspace. If you get an error about "active plan exists", read the error message - it tells you exactly how to resolve it (complete old plan, switch, or save as inactive).

Returns: Plan details, status updates, or list of plans. Trust the results and continue working.`,
        inputSchema: {
          type: "object",
          properties: {
            action: {
              type: "string",
              enum: ["save", "list", "get", "activate", "switch", "update", "complete", "export", "add-task", "check-task", "uncheck-task"],
              description: "Action to perform on plans",
            },
            title: {
              type: "string",
              description: "Plan title/summary (required for 'save', optional for 'switch' to create new plan)",
            },
            content: {
              type: "string",
              description: "Full plan content in markdown (required for 'save', optional for 'switch' to create new plan)",
            },
            planId: {
              type: "string",
              description: "Plan ID (required for 'get', 'activate', 'switch', 'update', 'complete', 'export')",
            },
            newPlanId: {
              type: "string",
              description: "Target plan ID to switch to (for 'switch' action when switching to existing plan)",
            },
            activate: {
              type: "boolean",
              description: "Whether to activate the plan (default: true for 'save')",
            },
            progress: {
              type: "string",
              description: "Progress update notes (required for 'update')",
            },
            status: {
              type: "string",
              enum: ["active", "completed", "archived"],
              description: "Filter plans by status (for 'list' action)",
            },
            exportPath: {
              type: "string",
              description: "Directory path for export (default: 'docs', used with 'export' action)",
            },
            taskDescription: {
              type: "string",
              description: "Task description (required for 'add-task' action)",
            },
            taskId: {
              type: "string",
              description: "Task ID (required for 'check-task' and 'uncheck-task' actions)",
            },
          },
          required: ["action"],
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
      case "plan":
        return await handlePlan(args);
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
  const { description, tags, sessionId, entryType, confidenceScore } = CheckpointSchema.parse(args);

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
    sessionId,
    entryType,
    confidenceScore,
  };

  // Create and properly close journal database instance
  const journal = new JournalDB();
  let planUpdateReminder = "";

  try {
    await journal.saveCheckpoint(entry);

    // Check for plan update reminder
    const activePlan = await journal.getActivePlan();
    if (activePlan) {
      try {
        const stalenessInfo = await journal.getPlanStalenessInfo(activePlan.id);

        if (stalenessInfo.checkpointsSinceUpdate >= 3) {
          if (stalenessInfo.checkpointsSinceUpdate >= 8) {
            planUpdateReminder = `\n\n⚠️  **Plan Update Overdue:** ${stalenessInfo.checkpointsSinceUpdate} checkpoints since last plan update.\n💡 Consider: plan({ action: "update", planId: "${activePlan.id}", progress: "..." })`;
          } else {
            planUpdateReminder = `\n\n💡 **Reminder:** ${stalenessInfo.checkpointsSinceUpdate} checkpoints since last plan update. Consider updating your plan.`;
          }
        }
      } catch (error) {
        // Silently fail on staleness check - don't block checkpoint save
      }
    }
  } finally {
    journal.close();
  }

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

💡 **Next:** Use recall() when starting your next session to restore this context.${planUpdateReminder}`,
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
    sessions, sessionId, smart, minConfidence, excludeTypes,
    deduplicate, similarityThreshold, summarize, groupBy, relevanceThreshold, maxEntries,
    export: exportToFile, exportPath,
    standup, includePlan
  } = RecallSchema.parse(args);

  // Create journal database instance (will be closed in finally block below)
  const journalDB = new JournalDB();

  try {
    // Handle workspace listing if requested
    if (listWorkspaces) {
      const workspaces = await journalDB.getWorkspaceSummary();
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

    // Get entries using session-aware logic
    let entries: JournalEntry[] = [];
    // Handle specific session ID request
    if (sessionId) {
      entries = await journalDB.getSessionById(sessionId, workspace || 'current');
    }
    // Handle sessions-based request
    else if (sessions && sessions > 0) {
      const sessionInfos = await journalDB.getLastNSessions(sessions, workspace || 'current');
      entries = sessionInfos.flatMap(session => session.entries);
    }
    // Handle smart mode
    else if (smart) {
      const smartContext = await journalDB.getSmartRecallContext(workspace || 'current');
      entries = [];

      // Include current session entries if available
      if (smartContext.currentSession) {
        entries.push(...smartContext.currentSession.entries);
      }

      // Include last session if needed for context
      if (smartContext.needsMoreContext && smartContext.lastSession) {
        entries.push(...smartContext.lastSession.entries);
      }

      // If still not enough context, get high-quality entries
      if (entries.length < 10) {
        const additionalEntries = await journalDB.getHighQualityEntries({
          workspace: workspace || 'current',
          days,
          minConfidence: Math.max(minConfidence || 0.0, 0.7),
          excludeTypes: excludeTypes || ['session-marker'],
          limit: 20
        });
        entries.push(...additionalEntries);
      }
    }
    // Handle high-quality filtered entries
    else if (minConfidence && minConfidence > 0) {
      entries = await journalDB.getHighQualityEntries({
        workspace: workspace || 'current',
        days,
        minConfidence,
        excludeTypes,
        limit: maxEntries
      });
    }
    // Default behavior with search or recent entries
    else if (search) {
      entries = await journalDB.searchCheckpoints(search, { limit: maxEntries, workspace: workspace || 'current' });
    }
    else {
      entries = await journalDB.getRecentCheckpoints({ days, from, to, project, workspace: workspace || 'current' });
    }

    if (entries.length === 0) {
      const filterDesc = [];
      if (search) filterDesc.push(`search: "${search}"`);
      if (project) filterDesc.push(`project: "${project}"`);
      if (days !== 2) filterDesc.push(`${days} days`);

      // Get workspace info for diagnostics
      const currentWorkspace = journalDB.getCurrentWorkspace();
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

    // Include active plan if requested (default: true)
    if (includePlan !== false) {
      const activePlan = await journalDB.getActivePlan();
      if (activePlan) {
        // Get staleness info
        const stalenessInfo = await journalDB.getPlanStalenessInfo(activePlan.id);

        // Staleness indicator emoji
        const stalenessEmoji = {
          fresh: '🟢',
          aging: '🟡',
          stale: '🔴'
        }[stalenessInfo.staleness];

        contextLines.push(`⭐ **ACTIVE PLAN:** ${activePlan.title} ${stalenessEmoji}`);
        contextLines.push("");

        // Show staleness warning if not fresh
        if (stalenessInfo.staleness !== 'fresh') {
          const daysAgo = Math.floor(stalenessInfo.daysSinceUpdate);
          contextLines.push(
            `📅 Last updated: ${daysAgo} day${daysAgo !== 1 ? 's' : ''} ago ` +
            `(${stalenessInfo.checkpointsSinceUpdate} checkpoint${stalenessInfo.checkpointsSinceUpdate !== 1 ? 's' : ''} since)`
          );

          if (stalenessInfo.staleness === 'stale') {
            contextLines.push(`⚠️  **Plan may be stale** - consider updating with recent progress`);
          }
          contextLines.push("");
        }

        // Show plan content
        contextLines.push(activePlan.content);
        contextLines.push("");

        // Show sub-tasks if present
        if (activePlan.sub_tasks) {
          try {
            const subTasks = JSON.parse(activePlan.sub_tasks);
            if (subTasks.length > 0) {
              const completed = subTasks.filter((t: any) => t.completed).length;
              const total = subTasks.length;

              contextLines.push(`**Sub-tasks:** ${completed}/${total} completed`);
              contextLines.push("");

              subTasks.forEach((task: any) => {
                const checkbox = task.completed ? '✅' : '☐';
                contextLines.push(`${checkbox} ${task.description}`);
              });
              contextLines.push("");
            }
          } catch (error) {
            // Invalid JSON, skip sub-tasks display
          }
        }

        // Show progress notes if present
        if (activePlan.progress_notes) {
          contextLines.push(`**Progress Notes:**`);
          contextLines.push(activePlan.progress_notes);
          contextLines.push("");
        }

        contextLines.push("---");
        contextLines.push("");
      }
    }

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
    const stats = await journalDB.getJournalStats();
    contextLines.push(`📊 **Journal Stats:** ${stats.totalEntries} total entries, ${stats.entriesThisWeek} this week, ${stats.entriesThisMonth} this month`);

    if (stats.projects.length > 0) {
      contextLines.push(`🗂️ **Projects:** ${stats.projects.join(", ")}`);
    }

    contextLines.push("");
    contextLines.push("🎯 **Context restored!** Continue your work with this background knowledge.");

    // Generate standup report if requested
    if (standup) {
      contextLines.push("");
      contextLines.push("---");
      contextLines.push("");
      const standupReport = await generateStandup({
        style: standup,
        days: days || 1,
        includeMetrics: true,
        includeFiles: false,
        workspace: workspace || 'current'
      });
      contextLines.push(standupReport);
    }

    // Export to markdown file if requested
    let exportFilePath: string | null = null;
    if (exportToFile) {
    try {
      // Generate filename based on query parameters
      const timestamp = new Date().toISOString().split('T')[0]!; // YYYY-MM-DD (always present)
      let filenameParts = ['tusk-recall'];

      if (search) {
        // Sanitize search term for filename
        const sanitized = search.replace(/[^a-z0-9]+/gi, '-').toLowerCase();
        filenameParts.push(sanitized);
      }
      if (project) {
        filenameParts.push(project);
      }

      filenameParts.push(timestamp);
      const filename = `${filenameParts.join('-')}.md`;

      // Resolve export path (relative to current working directory)
      const targetPath = exportPath || 'docs';
      const exportDir = resolve(process.cwd(), targetPath);
      exportFilePath = join(exportDir, filename);

      // Create directory if it doesn't exist
      if (!existsSync(exportDir)) {
        mkdirSync(exportDir, { recursive: true });
      }

      // Write the markdown content
      const markdownContent = contextLines.join("\n");
      writeFileSync(exportFilePath, markdownContent, 'utf-8');

      // Add export confirmation to output
      contextLines.push("");
      contextLines.push(`📄 **Exported to:** ${exportFilePath}`);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      contextLines.push("");
      contextLines.push(`⚠️ **Export failed:** ${errorMsg}`);
    }
    }

    return {
      content: [
        {
          type: "text",
          text: contextLines.join("\n"),
        },
      ],
    };
  } finally {
    journalDB.close();
  }
}

/**
 * Handle plan tool - manage long-running project plans
 */
async function handlePlan(args: any) {
  const params = PlanSchema.parse(args);
  const journal = new JournalDB();

  try {
    switch (params.action) {
      case 'save': {
        if (!params.title || !params.content) {
          throw new Error('Title and content are required for saving a plan');
        }

        try {
          const activate = params.activate !== undefined ? params.activate : true;
          const result = await journal.savePlan(params.title, params.content, activate);

          const statusMsg = activate
            ? "Your plan is now active and will appear in recall()."
            : "Your plan is saved but inactive. Use plan(action: \"activate\", planId: \"...\") to work on it.";

          const fileMsg = result.filePath
            ? `\n📄 **Exported to:** ${result.filePath}`
            : "";

          return {
            content: [{
              type: "text",
              text: `✅ **Plan Saved Successfully**

📋 **${params.title}**
🆔 Plan ID: ${result.id}

${result.message}${fileMsg}

${statusMsg} Use plan(action: "update") to track progress.`,
            }],
          };
        } catch (error) {
          // Handle conflict error (active plan exists)
          if (error instanceof Error && error.message.includes('Cannot save new plan as active')) {
            return {
              content: [{
                type: "text",
                text: `⚠️ **Cannot Save Plan as Active**

${error.message}

**Quick Solutions:**
1. Complete the current plan first, then save this plan
2. Use switch action to replace current plan with this one
3. Save this plan as inactive to work on later`,
              }],
            };
          }
          throw error;
        }
      }

      case 'list': {
        const plans = await journal.listPlans(params.status);
        if (plans.length === 0) {
          return {
            content: [{
              type: "text",
              text: params.status
                ? `No ${params.status} plans found for this workspace.`
                : "No plans found for this workspace. Use plan(action: \"save\") to create one.",
            }],
          };
        }

        let output = `📋 **Plans for ${journal.getCurrentWorkspace().name}**\n\n`;
        plans.forEach((plan: any) => {
          const activeMarker = plan.is_active ? '⭐ ' : '';
          const statusEmoji = plan.status === 'completed' ? '✅' : plan.status === 'active' ? '🔄' : '📦';
          const date = new Date(plan.updated_at).toLocaleDateString();
          output += `${activeMarker}${statusEmoji} **${plan.title}** (${plan.status})\n`;
          output += `   ID: ${plan.id} | Updated: ${date}\n\n`;
        });

        return {
          content: [{ type: "text", text: output }],
        };
      }

      case 'get': {
        if (!params.planId) {
          throw new Error('planId is required for getting a plan');
        }
        const plan = await journal.getPlan(params.planId);
        if (!plan) {
          return {
            content: [{
              type: "text",
              text: `❌ Plan ${params.planId} not found`,
            }],
          };
        }

        const activeMarker = plan.is_active ? '⭐ **ACTIVE PLAN** ' : '';
        let output = `${activeMarker}📋 **${plan.title}**\n\n`;
        output += `**Status:** ${plan.status}\n`;
        output += `**Created:** ${new Date(plan.created_at).toLocaleString()}\n`;
        output += `**Updated:** ${new Date(plan.updated_at).toLocaleString()}\n\n`;
        output += `---\n\n${plan.content}\n\n`;

        if (plan.progress_notes) {
          output += `---\n\n**Progress Notes:**\n\n${plan.progress_notes}\n`;
        }

        return {
          content: [{ type: "text", text: output }],
        };
      }

      case 'activate': {
        if (!params.planId) {
          throw new Error('planId is required for activating a plan');
        }
        const result = await journal.activatePlan(params.planId);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `✅ ${result.message}\n\nThis plan will now appear in recall().`
              : `❌ ${result.message}`,
          }],
        };
      }

      case 'switch': {
        if (!params.planId) {
          throw new Error('planId (current plan) is required for switching plans');
        }

        // Switching to existing plan or creating new one
        const result = await journal.switchActivePlan(
          params.planId,
          params.newPlanId,
          params.title,
          params.content
        );

        if (!result.success) {
          return {
            content: [{
              type: "text",
              text: `❌ ${result.message}`,
            }],
          };
        }

        const switchType = params.title && params.content
          ? "created and switched to new plan"
          : "switched to existing plan";

        return {
          content: [{
            type: "text",
            text: `✅ ${result.message}

${switchType === "created and switched to new plan" ? `📋 **New Plan ID:** ${result.newPlanId}` : ''}

The new active plan will now appear in recall(). The previous plan remains saved (inactive).`,
          }],
        };
      }

      case 'update': {
        if (!params.planId || !params.progress) {
          throw new Error('planId and progress are required for updating a plan');
        }
        const result = await journal.updatePlanProgress(params.planId, params.progress);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `✅ ${result.message}\n\nProgress note added: ${params.progress}`
              : `❌ ${result.message}`,
          }],
        };
      }

      case 'complete': {
        if (!params.planId) {
          throw new Error('planId is required for completing a plan');
        }
        const result = await journal.completePlan(params.planId);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `✅ ${result.message}\n\nCongratulations on completing your plan! 🎉`
              : `❌ ${result.message}`,
          }],
        };
      }

      case 'export': {
        if (!params.planId) {
          throw new Error('planId is required for exporting a plan');
        }
        const result = await journal.exportPlan(params.planId, params.exportPath);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `✅ ${result.message}\n\n📄 **Exported to:** ${result.filePath}\n\nYour plan is now available as a markdown file for version control or sharing!`
              : `❌ ${result.message}`,
          }],
        };
      }

      case 'add-task': {
        if (!params.planId || !params.taskDescription) {
          throw new Error('planId and taskDescription are required for adding a task');
        }
        const result = await journal.addPlanSubTask(params.planId, params.taskDescription);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `✅ ${result.message}\n🆔 **Task ID:** ${result.taskId}\n\n💡 Use check-task to mark it complete when done.`
              : `❌ ${result.message}`,
          }],
        };
      }

      case 'check-task': {
        if (!params.planId || !params.taskId) {
          throw new Error('planId and taskId are required for checking a task');
        }
        const result = await journal.togglePlanSubTask(params.planId, params.taskId, true);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `✅ ${result.message}\n\nTask marked complete! Check recall() to see updated progress.`
              : `❌ ${result.message}`,
          }],
        };
      }

      case 'uncheck-task': {
        if (!params.planId || !params.taskId) {
          throw new Error('planId and taskId are required for unchecking a task');
        }
        const result = await journal.togglePlanSubTask(params.planId, params.taskId, false);
        return {
          content: [{
            type: "text",
            text: result.success
              ? `☐ ${result.message}\n\nTask marked incomplete.`
              : `❌ ${result.message}`,
          }],
        };
      }

      default:
        throw new Error(`Unknown plan action: ${params.action}`);
    }
  } finally {
    journal.close();
  }
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
  console.error("🔧 Tools available: checkpoint, recall, plan");
  console.error("🗂️ Multi-workspace support enabled");
  console.error("🧠 Behavioral instructions: Built into server initialization");
}

main().catch((error) => {
  console.error("❌ Server error:", error);
  process.exit(1);
});