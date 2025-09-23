#!/usr/bin/env bun

/**
 * Tusk MCP Server
 * Simple developer journal and standup tool with persistent memory
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ToolSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { GetPromptResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import {
  saveEntry,
  getRecentEntries,
  searchEntries,
  generateId,
  getJournalStats
} from "./journal.js";
import type { JournalEntry } from "./journal.js";
import { getGitContext, getStatusSummary } from "./git.js";
import { generateStandup } from "./standup.js";
import type { StandupStyle } from "./standup.js";

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
    instructions: `# Tusk-Bun Behavioral Instructions

You are an AI agent with access to tusk tools for persistent memory across sessions. These instructions guide your PROACTIVE behavior to build valuable context data.

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
  search: z.string().optional().describe("Search term to filter entries"),
  project: z.string().optional().describe("Filter by specific project name"),
  workspace: z.string().optional().describe("Filter by specific workspace ID ('current' for current workspace, 'all' for all workspaces)"),
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
        description: "Save work progress. Your memory across Claude sessions. Use this to capture important moments, breakthroughs, or progress that should be remembered later.",
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
      } satisfies typeof ToolSchema,
      {
        name: "recall",
        description: "Restore context from previous work. ALWAYS use this at the start of sessions to recover important context that might have been lost due to Claude crashes or compaction.",
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
          },
        },
      } satisfies typeof ToolSchema,
      {
        name: "standup",
        description: "Generate beautiful standup reports from your journal. Perfect for team meetings, progress summaries, or understanding what you've accomplished recently.",
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
      } satisfies typeof ToolSchema,
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

Your progress is now safely captured and will survive Claude sessions! 🐘`,
      },
    ],
  };
}

/**
 * Handle recall tool - restore previous context
 */
async function handleRecall(args: any) {
  const { days, search, project, workspace } = RecallSchema.parse(args);

  // Get entries based on filters
  const entries = search
    ? await searchEntries(search, { workspace: workspace || 'current' })
    : await getRecentEntries({ days, project, workspace: workspace || 'current' });

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

  // Format the entries for display
  const contextLines: string[] = [];
  contextLines.push(`🧠 **Context Restored** (${entries.length} entries found)`);
  contextLines.push("");

  // Group by project
  const projectGroups = entries.reduce((groups, entry) => {
    const proj = entry.project || "General";
    if (!groups[proj]) groups[proj] = [];
    groups[proj].push(entry);
    return groups;
  }, {} as Record<string, JournalEntry[]>);

  for (const [projectName, projectEntries] of Object.entries(projectGroups)) {
    if (Object.keys(projectGroups).length > 1) {
      contextLines.push(`📁 **${projectName}:**`);
    }

    projectEntries.slice(0, 8).forEach(entry => {
      const time = formatTimeAgo(entry.timestamp);
      const gitInfo = entry.gitBranch ? ` (${entry.gitBranch})` : "";
      const tags = entry.tags && entry.tags.length > 0 ? ` [${entry.tags.join(", ")}]` : "";

      contextLines.push(`   • ${entry.description}${gitInfo}${tags} ${time}`);
    });

    if (projectEntries.length > 8) {
      contextLines.push(`   ... and ${projectEntries.length - 8} more entries`);
    }
    contextLines.push("");
  }

  // Add summary
  const stats = await getJournalStats();
  contextLines.push(`📊 **Journal Stats:** ${stats.totalEntries} total entries, ${stats.entriesThisWeek} this week, ${stats.entriesThisMonth} this month`);

  if (stats.projects.length > 0) {
    contextLines.push(`🗂️ **Projects:** ${stats.projects.join(", ")}`);
  }

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