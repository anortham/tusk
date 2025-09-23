#!/usr/bin/env bun

/**
 * Migration script from Python tusk to tusk-bun
 * Imports existing checkpoints from ~/.coa/tusk/ into the new JSONL format
 */

import { existsSync, readdirSync, statSync } from "fs";
import { join, basename } from "path";
import { homedir } from "os";
import { JournalEntry, saveEntry, getTuskDir } from "./journal.js";

interface PythonCheckpoint {
  id: string;
  workspace_id?: string;
  project_id?: string;
  project_path?: string;
  description: string;
  session_id?: string;
  git_branch?: string;
  git_commit?: string;
  work_context?: any;
  active_files?: string[];
  created_at: string;
  highlights?: string[];
}

/**
 * Get the Python tusk data directory
 */
function getPythonTuskDir(): string | null {
  const possiblePaths = [
    join(homedir(), ".coa", "tusk"),
    join(homedir(), ".tusk"),
  ];

  for (const path of possiblePaths) {
    if (existsSync(path)) {
      return path;
    }
  }

  return null;
}

/**
 * Find all checkpoint JSON files in the Python tusk directory
 */
function findCheckpointFiles(baseDir: string): string[] {
  const checkpointFiles: string[] = [];

  try {
    // Look for checkpoints directory structure: workspaces/*/checkpoints/*/*/*.json
    const workspacesDir = join(baseDir, "workspaces");
    if (!existsSync(workspacesDir)) {
      return checkpointFiles;
    }

    const workspaces = readdirSync(workspacesDir);

    for (const workspace of workspaces) {
      const workspaceDir = join(workspacesDir, workspace);
      if (!statSync(workspaceDir).isDirectory()) continue;

      const checkpointsDir = join(workspaceDir, "checkpoints");
      if (!existsSync(checkpointsDir)) continue;

      // Recursively find all .json files in checkpoints directory
      const findJsonFiles = (dir: string): void => {
        const items = readdirSync(dir);
        for (const item of items) {
          const itemPath = join(dir, item);
          const stats = statSync(itemPath);

          if (stats.isDirectory()) {
            findJsonFiles(itemPath);
          } else if (item.endsWith(".json")) {
            checkpointFiles.push(itemPath);
          }
        }
      };

      findJsonFiles(checkpointsDir);
    }
  } catch (error) {
    console.error("Error finding checkpoint files:", error);
  }

  return checkpointFiles;
}

/**
 * Load and parse a Python checkpoint file
 */
async function loadPythonCheckpoint(filePath: string): Promise<PythonCheckpoint | null> {
  try {
    const file = Bun.file(filePath);
    const content = await file.text();
    return JSON.parse(content) as PythonCheckpoint;
  } catch (error) {
    console.error(`Failed to load checkpoint ${filePath}:`, error);
    return null;
  }
}

/**
 * Convert Python checkpoint to tusk-bun journal entry
 */
function convertToJournalEntry(checkpoint: PythonCheckpoint): JournalEntry {
  // Extract tags from highlights or work context
  const tags: string[] = [];
  if (checkpoint.highlights && checkpoint.highlights.length > 0) {
    tags.push("highlight");
  }

  // Determine project name
  let project = checkpoint.project_id;
  if (!project && checkpoint.project_path) {
    project = basename(checkpoint.project_path);
  }

  return {
    id: checkpoint.id,
    type: "checkpoint",
    timestamp: checkpoint.created_at,
    description: checkpoint.description,
    project,
    gitBranch: checkpoint.git_branch,
    gitCommit: checkpoint.git_commit,
    files: checkpoint.active_files,
    tags: tags.length > 0 ? tags : undefined,
  };
}

/**
 * Main migration function
 */
async function migrate(options: { dryRun?: boolean; verbose?: boolean } = {}) {
  const { dryRun = false, verbose = false } = options;

  console.log("🐘 Tusk-Bun Migration Tool");
  console.log("==========================");

  // Find Python tusk directory
  const pythonDir = getPythonTuskDir();
  if (!pythonDir) {
    console.log("❌ No Python tusk installation found");
    console.log("   Looked in:");
    console.log("   • ~/.coa/tusk");
    console.log("   • ~/.tusk");
    console.log("\n💡 If you have tusk installed elsewhere, run:");
    console.log("   PYTHON_TUSK_DIR=/path/to/tusk bun run migrate.ts");
    return;
  }

  console.log(`📂 Found Python tusk at: ${pythonDir}`);

  // Find checkpoint files
  const checkpointFiles = findCheckpointFiles(pythonDir);
  console.log(`🔍 Found ${checkpointFiles.length} checkpoint files`);

  if (checkpointFiles.length === 0) {
    console.log("✨ Nothing to migrate!");
    return;
  }

  // Create tusk-bun directory
  const tuskBunDir = getTuskDir();
  console.log(`📁 Target directory: ${tuskBunDir}`);

  if (dryRun) {
    console.log("\n🧪 DRY RUN - No files will be modified");
  }

  // Process each checkpoint
  let successCount = 0;
  let errorCount = 0;

  console.log("\n📝 Processing checkpoints...");

  for (const filePath of checkpointFiles) {
    try {
      if (verbose) {
        console.log(`   Processing: ${basename(filePath)}`);
      }

      const pythonCheckpoint = await loadPythonCheckpoint(filePath);
      if (!pythonCheckpoint) {
        errorCount++;
        continue;
      }

      const journalEntry = convertToJournalEntry(pythonCheckpoint);

      if (!dryRun) {
        await saveEntry(journalEntry);
      }

      successCount++;

      if (verbose) {
        console.log(`   ✅ ${journalEntry.description.substring(0, 60)}...`);
      }
    } catch (error) {
      errorCount++;
      if (verbose) {
        console.error(`   ❌ Error processing ${basename(filePath)}:`, error);
      }
    }
  }

  console.log("\n📊 Migration Results:");
  console.log(`   ✅ Successfully migrated: ${successCount}`);
  console.log(`   ❌ Errors: ${errorCount}`);
  console.log(`   📈 Success rate: ${Math.round((successCount / checkpointFiles.length) * 100)}%`);

  if (!dryRun && successCount > 0) {
    console.log(`\n🎉 Migration complete! Your checkpoints are now available in tusk-bun.`);
    console.log(`📁 Journal location: ${join(tuskBunDir, "journal.jsonl")}`);
    console.log(`\n💡 Try running: recall() to see your imported checkpoints`);
  }
}

/**
 * CLI interface
 */
async function main() {
  const args = process.argv.slice(2);
  const options = {
    dryRun: args.includes("--dry-run") || args.includes("-n"),
    verbose: args.includes("--verbose") || args.includes("-v"),
  };

  // Check for custom Python tusk directory
  if (process.env.PYTHON_TUSK_DIR) {
    console.log(`📂 Using custom Python tusk directory: ${process.env.PYTHON_TUSK_DIR}`);
  }

  if (args.includes("--help") || args.includes("-h")) {
    console.log(`
🐘 Tusk-Bun Migration Tool

Migrates checkpoints from Python tusk to tusk-bun format.

Usage:
  bun run migrate.ts [options]

Options:
  --dry-run, -n     Show what would be migrated without making changes
  --verbose, -v     Show detailed progress information
  --help, -h        Show this help message

Environment Variables:
  PYTHON_TUSK_DIR   Custom path to Python tusk installation

Examples:
  bun run migrate.ts --dry-run     # Preview migration
  bun run migrate.ts --verbose     # Migrate with detailed output
  PYTHON_TUSK_DIR=/custom/path bun run migrate.ts
`);
    return;
  }

  await migrate(options);
}

// Run if called directly
if (import.meta.main) {
  main().catch((error) => {
    console.error("❌ Migration failed:", error);
    process.exit(1);
  });
}