/**
 * Zod Schema Definitions for Tusk Journal System
 * Input validation schemas for MCP tool requests
 */

import { z } from "zod";

// Zod schemas for tool validation
export const CheckpointSchema = z.object({
  description: z.string().describe("Progress description to save"),
  tags: z.array(z.string()).optional().describe("Optional tags for categorization"),
});

export const RecallSchema = z.object({
  days: z.number().optional().default(2).describe("Number of days to look back (default: 2)"),
  from: z.string().optional().describe("Start date (YYYY-MM-DD or ISO 8601)"),
  to: z.string().optional().describe("End date (YYYY-MM-DD or ISO 8601)"),
  search: z.string().optional().describe("Search term to filter entries (searches descriptions, projects, git branches, git commits, tags, and files)"),
  project: z.string().optional().describe("Filter by specific project name"),
  workspace: z.string().optional().describe("Workspace scope: 'current' (default - current workspace only), 'all' (all workspaces), or '/path/to/workspace' (specific)"),
  listWorkspaces: z.boolean().optional().describe("List all workspaces with statistics"),

  // Enhanced processing options
  deduplicate: z.boolean().optional().default(true).describe("Enable smart deduplication of similar entries (default: true)"),
  similarityThreshold: z.number().optional().default(0.7).describe("Similarity threshold for deduplication (0-1, default: 0.7)"),
  summarize: z.boolean().optional().default(false).describe("Generate executive summary of key insights (default: false)"),
  groupBy: z.enum(["chronological", "project", "topic", "session", "relevance"]).optional().default("chronological").describe("Grouping strategy for entries"),
  relevanceThreshold: z.number().optional().default(0.0).describe("Minimum relevance score filter (0-1, default: 0.0)"),
  maxEntries: z.number().optional().default(50).describe("Maximum number of entries to return after processing (default: 50)"),
});

export const StandupSchema = z.object({
  style: z.enum(["meeting", "written", "executive", "metrics"]).default("meeting")
    .describe("Output style: meeting (classic standup), written (narrative), executive (high-level), metrics (dashboard)"),
  days: z.number().optional().default(1).describe("Number of days to include (default: 1)"),
  includeMetrics: z.boolean().optional().default(true).describe("Include productivity metrics"),
  includeFiles: z.boolean().optional().default(false).describe("Include recently modified files"),
  workspace: z.string().optional().describe("Filter by specific workspace ID ('current' for current workspace, 'all' for all workspaces)"),
});

// Type exports for TypeScript
export type CheckpointInput = z.infer<typeof CheckpointSchema>;
export type RecallInput = z.infer<typeof RecallSchema>;
export type StandupInput = z.infer<typeof StandupSchema>;