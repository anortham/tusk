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

import { handleCheckpoint, handleRecall, handleStandup } from "./tool-handlers.js";

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
  }
);

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
- workspace: "current" (default - current workspace only), "all" (search all workspaces), or specific path
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
  try {
    const { name, arguments: args } = request.params;

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
          text: `❌ Error in ${request.params.name}: ${errorMessage}`,
        },
      ],
    };
  }
});

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