#!/usr/bin/env bun

/**
 * Tusk CLI interface
 * Allows calling tusk tools from command line and Claude Code hooks
 */

import { saveEntry, getRecentEntries, searchEntries, generateId, getWorkspaceSummary } from "./journal.js";
import type { JournalEntry } from "./journal.js";
import { getGitContext } from "./git.js";
import { generateStandup } from "./standup.js";
import type { StandupStyle } from "./standup.js";

// Parse command line arguments
const [, , command, ...args] = process.argv;

async function main() {
  try {
    switch (command) {
      case 'checkpoint':
      case 'cp':
        await handleCheckpointCLI(args);
        break;

      case 'recall':
      case 'rc':
        await handleRecallCLI(args);
        break;

      case 'standup':
      case 'su':
        await handleStandupCLI(args);
        break;

      case 'help':
      case '--help':
      case '-h':
        showHelp();
        break;
      default:
        console.error(`❌ Unknown command: ${command}`);
        console.error('Run "bun cli.ts help" for usage information.');
        process.exit(1);
    }
  } catch (error) {
    console.error('❌ Error:', error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

async function handleCheckpointCLI(args: string[]) {
  if (args.length === 0) {
    console.error('❌ Description required for checkpoint');
    console.error('Usage: bun cli.ts checkpoint "your progress description" [tag1,tag2]');
    process.exit(1);
  }

  const description = args[0];
  if (!description) {
    console.error('❌ Description required for checkpoint');
    console.error('Usage: bun cli.ts checkpoint "your progress description" [tag1,tag2]');
    process.exit(1);
  }

  const tags = args[1] ? args[1].split(',').map(t => t.trim()) : undefined;

  // Capture git context
  const gitInfo = getGitContext();

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

  await saveEntry(entry);

  console.log('✅ Checkpoint saved');
  console.log(`📝 ${description}`);
  console.log(`🆔 ${entry.id}`);
  if (gitInfo.project) console.log(`📁 ${gitInfo.project}`);
  if (tags) console.log(`🏷️  ${tags.join(', ')}`);
}

async function handleRecallCLI(args: string[]) {
  // Parse optional arguments
  let days = 2;
  let search: string | undefined;
  let project: string | undefined;
  let workspace: string | 'current' | 'all' = 'current';
  let from: string | undefined;
  let to: string | undefined;
  let listWorkspaces = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (!arg) continue; // Skip undefined args

    if (arg.startsWith('--days=')) {
      const daysPart = arg.split('=')[1];
      if (!daysPart) {
        console.error('❌ --days= requires a value. Example: --days=7');
        process.exit(1);
      }
      const parsedDays = parseInt(daysPart);
      if (isNaN(parsedDays)) {
        console.error('❌ Invalid days value. Must be a number.');
        process.exit(1);
      }
      days = parsedDays;
    } else if (arg.startsWith('--search=')) {
      const searchPart = arg.split('=')[1];
      if (!searchPart) {
        console.error('❌ --search= requires a value. Example: --search=auth');
        process.exit(1);
      }
      search = searchPart;
    } else if (arg.startsWith('--project=')) {
      const projectPart = arg.split('=')[1];
      if (!projectPart) {
        console.error('❌ --project= requires a value. Example: --project=myproject');
        process.exit(1);
      }
      project = projectPart;
    } else if (arg.startsWith('--workspace=')) {
      const workspacePart = arg.split('=')[1];
      if (!workspacePart) {
        console.error('❌ --workspace= requires a value. Example: --workspace=current');
        process.exit(1);
      }
      workspace = workspacePart;
    } else if (arg === '--days' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --days requires a value. Example: --days 7');
        process.exit(1);
      }
      const parsedDays = parseInt(nextArg);
      if (isNaN(parsedDays)) {
        console.error('❌ Invalid days value. Must be a number.');
        process.exit(1);
      }
      days = parsedDays;
    } else if (arg === '--search' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --search requires a value. Example: --search auth');
        process.exit(1);
      }
      search = nextArg;
    } else if (arg === '--project' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --project requires a value. Example: --project myproject');
        process.exit(1);
      }
      project = nextArg;
    } else if (arg === '--workspace' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --workspace requires a value. Example: --workspace current');
        process.exit(1);
      }
      workspace = nextArg;
    } else if (arg === '--all-workspaces') {
      workspace = 'all';
    } else if (arg.startsWith('--from=')) {
      const fromPart = arg.split('=')[1];
      if (!fromPart) {
        console.error('❌ --from= requires a value. Example: --from=2024-01-01');
        process.exit(1);
      }
      from = fromPart;
    } else if (arg.startsWith('--to=')) {
      const toPart = arg.split('=')[1];
      if (!toPart) {
        console.error('❌ --to= requires a value. Example: --to=2024-01-31');
        process.exit(1);
      }
      to = toPart;
    } else if (arg === '--from' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --from requires a value. Example: --from 2024-01-01');
        process.exit(1);
      }
      from = nextArg;
    } else if (arg === '--to' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --to requires a value. Example: --to 2024-01-31');
        process.exit(1);
      }
      to = nextArg;
    } else if (arg === '--list-workspaces') {
      listWorkspaces = true;
    }
  }

  // Handle workspace listing if requested
  if (listWorkspaces) {
    const workspaces = await getWorkspaceSummary();
    if (workspaces.length === 0) {
      console.log('📂 No workspaces found');
      return;
    }

    console.log(`📂 Found ${workspaces.length} workspace${workspaces.length === 1 ? '' : 's'}:`);
    console.log('');

    workspaces.forEach(ws => {
      console.log(`📁 ${ws.name}`);
      console.log(`   Path: ${ws.path}`);
      console.log(`   Entries: ${ws.entryCount}`);
      if (ws.lastActivity) {
        console.log(`   Last activity: ${ws.lastActivity}`);
      }
      if (ws.projects.length > 0) {
        console.log(`   Projects: ${ws.projects.join(', ')}`);
      }
      console.log('');
    });
    return;
  }

  const entries = search
    ? await searchEntries(search, { workspace })
    : await getRecentEntries({ days, project, workspace, from, to });

  if (entries.length === 0) {
    console.log('🔍 No entries found');
    return;
  }

  console.log(`🧠 Found ${entries.length} entries:`);
  console.log('');

  // Group by project
  const projectGroups = entries.reduce((groups, entry) => {
    const proj = entry.project || "General";
    if (!groups[proj]) groups[proj] = [];
    groups[proj].push(entry);
    return groups;
  }, {} as Record<string, JournalEntry[]>);

  for (const [projectName, projectEntries] of Object.entries(projectGroups)) {
    if (Object.keys(projectGroups).length > 1) {
      console.log(`📁 **${projectName}:**`);
    }

    projectEntries.slice(0, 8).forEach(entry => {
      const time = formatTimeAgo(entry.timestamp);
      const gitInfo = entry.gitBranch ? ` (${entry.gitBranch})` : "";
      const tags = entry.tags && entry.tags.length > 0 ? ` [${entry.tags.join(", ")}]` : "";

      console.log(`   • ${entry.description}${gitInfo}${tags} ${time}`);
    });

    if (projectEntries.length > 8) {
      console.log(`   ... and ${projectEntries.length - 8} more entries`);
    }
    console.log('');
  }
}

async function handleStandupCLI(args: string[]) {
  // Parse optional arguments
  let style: StandupStyle = "meeting";
  let days = 1;
  let includeMetrics = true;
  let includeFiles = false;
  let workspace: string | 'current' | 'all' = 'current';

  const validStyles: StandupStyle[] = ["meeting", "written", "executive", "metrics"];

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (!arg) continue; // Skip undefined args

    if (arg.startsWith('--style=')) {
      const styleValue = arg.split('=')[1];
      if (!styleValue) {
        console.error('❌ --style= requires a value. Example: --style=meeting');
        process.exit(1);
      }
      if (!validStyles.includes(styleValue as StandupStyle)) {
        console.error(`❌ Invalid style value: ${styleValue}. Must be one of: ${validStyles.join(', ')}`);
        process.exit(1);
      }
      style = styleValue as StandupStyle;
    } else if (arg.startsWith('--days=')) {
      const daysPart = arg.split('=')[1];
      if (!daysPart) {
        console.error('❌ --days= requires a value. Example: --days=7');
        process.exit(1);
      }
      const parsedDays = parseInt(daysPart);
      if (isNaN(parsedDays)) {
        console.error('❌ Invalid days value. Must be a number.');
        process.exit(1);
      }
      days = parsedDays;
    } else if (arg.startsWith('--workspace=')) {
      const workspacePart = arg.split('=')[1];
      if (!workspacePart) {
        console.error('❌ --workspace= requires a value. Example: --workspace=current');
        process.exit(1);
      }
      workspace = workspacePart;
    } else if (arg === '--no-metrics') {
      includeMetrics = false;
    } else if (arg === '--include-files') {
      includeFiles = true;
    } else if (arg === '--all-workspaces') {
      workspace = 'all';
    } else if (arg === '--style' && i + 1 < args.length) {
      const styleValue = args[++i];
      if (!validStyles.includes(styleValue as StandupStyle)) {
        console.error(`❌ Invalid style value: ${styleValue}. Must be one of: ${validStyles.join(', ')}`);
        process.exit(1);
      }
      style = styleValue as StandupStyle;
    } else if (arg === '--days' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --days requires a value. Example: --days 7');
        process.exit(1);
      }
      const parsedDays = parseInt(nextArg);
      if (isNaN(parsedDays)) {
        console.error('❌ Invalid days value. Must be a number.');
        process.exit(1);
      }
      days = parsedDays;
    } else if (arg === '--workspace' && i + 1 < args.length) {
      const nextArg = args[++i];
      if (!nextArg) {
        console.error('❌ --workspace requires a value. Example: --workspace current');
        process.exit(1);
      }
      workspace = nextArg;
    }
  }

  const report = await generateStandup({
    style,
    days,
    includeMetrics,
    includeFiles,
    workspace
  });

  console.log(report);
}

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

function showHelp() {
  console.log(`🐘 Tusk CLI - Developer journal and standup tool

Usage:
  bun cli.ts <command> [options]

Commands:
  checkpoint, cp    Save work progress
  recall, rc        Restore context from previous work
  standup, su       Generate standup reports
  help             Show this help

Examples:
  # Save a checkpoint
  bun cli.ts checkpoint "Fixed auth timeout bug"
  bun cli.ts cp "Added user dashboard" "feature,ui"

  # Recall previous work
  bun cli.ts recall
  bun cli.ts recall --days 7
  bun cli.ts rc --days 7 --search auth
  bun cli.ts recall --project myproject
  bun cli.ts recall --all-workspaces --days 3
  bun cli.ts recall --from 2024-01-01 --to 2024-01-31
  bun cli.ts recall --from 2024-01-01
  bun cli.ts recall --list-workspaces

  # Generate standup
  bun cli.ts standup
  bun cli.ts su --style executive --days 3
  bun cli.ts standup --style metrics --all-workspaces
  bun cli.ts standup --workspace my-workspace-id

Checkpoint Options:
  description       Progress description (required)
  tags             Comma-separated tags (optional)

Recall Options:
  --days N         Number of days to look back (default: 2)
  --from DATE      Start date (YYYY-MM-DD or ISO 8601)
  --to DATE        End date (YYYY-MM-DD or ISO 8601)
  --search TEXT    Search term to filter entries
  --project NAME   Filter by specific project
  --workspace ID   Filter by specific workspace ID (default: current)
  --all-workspaces Include entries from all workspaces
  --list-workspaces List all workspaces with statistics

Standup Options:
  --style TYPE     meeting|written|executive|metrics (default: meeting)
  --days N         Number of days to include (default: 1)
  --workspace ID   Filter by specific workspace ID (default: current)
  --all-workspaces Include entries from all workspaces
  --no-metrics     Exclude productivity metrics
  --include-files  Include recently modified files

For Claude Code hooks, add to your project's CLAUDE.md:
  bun cli.ts checkpoint "Description of what was done"
`);
}

main();