/**
 * Auto-installer for Tusk Claude Code integration files
 *
 * Automatically installs hooks, commands, and settings to project .claude/ directory
 * on MCP server startup. Keeps users' integration files in sync without manual copying.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, statSync, copyFileSync } from "fs";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";

const TUSK_VERSION = "1.1.1"; // Bump when hooks/commands change

export interface InstallationResult {
  installed: boolean;
  filesAdded: string[];
  filesSkipped: string[];
  filesUpdated: string[];
  settingsMerged: boolean;
  needsRestart: boolean;
  errors: string[];
}

interface VersionManifest {
  version: string;
  installedAt: string;
  files: {
    hooks: string[];
    commands: string[];
    settings: boolean;
  };
}

interface ClaudeSettings {
  permissions?: {
    allow?: string[];
    deny?: string[];
    ask?: string[];
  };
  hooks?: {
    [eventType: string]: Array<{
      matcher?: string;
      hooks: Array<{
        type: string;
        command: string;
      }>;
    }>;
  };
}

/**
 * Get the source directory containing .claude/ template files
 */
function getSourceClaudeDir(): string {
  // This file is in src/setup/, so go up to root
  const currentFile = fileURLToPath(import.meta.url);
  const tuskRoot = resolve(dirname(currentFile), "..", "..");
  return join(tuskRoot, ".claude");
}

/**
 * Get or create the target .claude directory in the workspace
 */
function getTargetClaudeDir(cwd: string): string {
  const claudeDir = join(cwd, ".claude");
  if (!existsSync(claudeDir)) {
    mkdirSync(claudeDir, { recursive: true });
  }
  return claudeDir;
}

/**
 * Read the version manifest from target directory
 */
function readVersionManifest(targetDir: string): VersionManifest | null {
  const manifestPath = join(targetDir, ".tusk-version");
  if (!existsSync(manifestPath)) {
    return null;
  }

  try {
    const content = readFileSync(manifestPath, "utf-8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Write the version manifest to target directory
 */
function writeVersionManifest(targetDir: string, manifest: VersionManifest): void {
  const manifestPath = join(targetDir, ".tusk-version");
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf-8");
}

/**
 * Check if a file has been modified by the user since installation
 */
function isFileModified(filePath: string, installedAt: string): boolean {
  if (!existsSync(filePath)) {
    return false;
  }

  try {
    const stats = statSync(filePath);
    const fileModTime = stats.mtime.toISOString();
    return fileModTime > installedAt;
  } catch {
    return false;
  }
}

/**
 * Copy a directory of files (hooks or commands)
 */
function copyDirectoryFiles(
  sourceDir: string,
  targetDir: string,
  fileExtension: string,
  installedAt: string | null,
  skipModified: boolean = true
): { added: string[]; skipped: string[]; updated: string[] } {
  const result = { added: [] as string[], skipped: [] as string[], updated: [] as string[] };

  if (!existsSync(sourceDir)) {
    return result;
  }

  // Ensure target directory exists
  if (!existsSync(targetDir)) {
    mkdirSync(targetDir, { recursive: true });
  }

  const files = readdirSync(sourceDir).filter(f => f.endsWith(fileExtension));

  for (const file of files) {
    const sourcePath = join(sourceDir, file);
    const targetPath = join(targetDir, file);

    // Check if file exists
    if (existsSync(targetPath)) {
      // Check if user modified it
      if (skipModified && installedAt && isFileModified(targetPath, installedAt)) {
        result.skipped.push(file);
        continue;
      }

      // File exists and not modified, update it
      copyFileSync(sourcePath, targetPath);
      result.updated.push(file);
    } else {
      // New file, copy it
      copyFileSync(sourcePath, targetPath);
      result.added.push(file);
    }
  }

  return result;
}

/**
 * Generate hooks configuration for settings.json
 * Uses absolute paths to ensure hooks work regardless of CWD
 */
function generateHooksConfig(targetDir: string): ClaudeSettings["hooks"] {
  // Use absolute path to hooks directory
  const hooksPath = join(targetDir, "hooks");

  return {
    SessionStart: [
      {
        hooks: [
          {
            type: "command",
            command: `bun ${hooksPath}/conversation_start.ts`
          }
        ]
      }
    ],
    PreCompact: [
      {
        hooks: [
          {
            type: "command",
            command: `bun ${hooksPath}/pre_compact.ts`
          }
        ]
      }
    ],
    Stop: [
      {
        hooks: [
          {
            type: "command",
            command: `bun ${hooksPath}/stop.ts`
          },
          {
            type: "command",
            command: `bun ${hooksPath}/post_response.ts`
          }
        ]
      }
    ],
    UserPromptSubmit: [
      {
        hooks: [
          {
            type: "command",
            command: `bun ${hooksPath}/user_prompt_submit.ts`
          },
          {
            type: "command",
            command: `bun ${hooksPath}/enhanced_user_prompt_submit.ts`
          },
          {
            type: "command",
            command: `bun ${hooksPath}/exchange_monitor.ts`
          }
        ]
      }
    ],
    PostToolUse: [
      {
        hooks: [
          {
            type: "command",
            command: `bun ${hooksPath}/post_tool_use.ts`
          },
          {
            type: "command",
            command: `bun ${hooksPath}/plan_detector.ts`
          }
        ]
      }
    ]
  };
}

/**
 * Merge Tusk permissions and hooks into existing settings.json
 */
function mergeSettings(targetDir: string): boolean {
  const settingsPath = join(targetDir, "settings.json");
  const tuskPermissions = {
    allow: [
      "Bash(bun run:*)",
      "Bash(bun test:*)",
      "mcp__tusk__recall",
      "mcp__tusk__plan",
      "mcp__tusk__checkpoint"
    ],
    deny: [],
    ask: []
  };

  let existingSettings: ClaudeSettings = {};

  // Read existing settings if they exist
  if (existsSync(settingsPath)) {
    try {
      const content = readFileSync(settingsPath, "utf-8");
      existingSettings = JSON.parse(content);
    } catch {
      // Invalid JSON, start fresh
    }
  }

  // Merge permissions
  if (!existingSettings.permissions) {
    existingSettings.permissions = {};
  }

  // Merge allow list (deduplicate)
  const existingAllow = existingSettings.permissions.allow || [];
  const mergedAllow = Array.from(new Set([...existingAllow, ...tuskPermissions.allow]));
  existingSettings.permissions.allow = mergedAllow;

  // Merge hooks configuration
  const hooksConfig = generateHooksConfig(targetDir);
  if (!existingSettings.hooks) {
    // No existing hooks, just set ours
    existingSettings.hooks = hooksConfig;
  } else {
    // Merge with existing hooks - Tusk hooks take precedence
    existingSettings.hooks = {
      ...existingSettings.hooks,
      ...hooksConfig
    };
  }

  // Write back
  writeFileSync(settingsPath, JSON.stringify(existingSettings, null, 2), "utf-8");
  return true;
}

/**
 * Main auto-setup function
 * Installs or updates Tusk integration files in the project's .claude/ directory
 */
export async function autoSetupClaudeIntegration(cwd: string): Promise<InstallationResult> {
  const result: InstallationResult = {
    installed: false,
    filesAdded: [],
    filesSkipped: [],
    filesUpdated: [],
    settingsMerged: false,
    needsRestart: false,
    errors: []
  };

  // Check if auto-setup is disabled
  if (process.env.TUSK_AUTO_SETUP === "false") {
    return result;
  }

  try {
    // Get source and target directories
    const sourceClaudeDir = getSourceClaudeDir();
    const targetClaudeDir = getTargetClaudeDir(cwd);

    // Read existing version manifest
    const existingManifest = readVersionManifest(targetClaudeDir);
    const installedAt = existingManifest?.installedAt || null;
    const needsUpdate = !existingManifest || existingManifest.version !== TUSK_VERSION;

    // If version is up to date, skip installation
    if (!needsUpdate) {
      return result;
    }

    // Copy hooks
    const hooksResult = copyDirectoryFiles(
      join(sourceClaudeDir, "hooks"),
      join(targetClaudeDir, "hooks"),
      ".ts",
      installedAt,
      true // Skip user-modified files
    );

    result.filesAdded.push(...hooksResult.added.map(f => `hooks/${f}`));
    result.filesSkipped.push(...hooksResult.skipped.map(f => `hooks/${f}`));
    result.filesUpdated.push(...hooksResult.updated.map(f => `hooks/${f}`));

    // Copy commands
    const commandsResult = copyDirectoryFiles(
      join(sourceClaudeDir, "commands"),
      join(targetClaudeDir, "commands"),
      ".md",
      installedAt,
      true // Skip user-modified files
    );

    result.filesAdded.push(...commandsResult.added.map(f => `commands/${f}`));
    result.filesSkipped.push(...commandsResult.skipped.map(f => `commands/${f}`));
    result.filesUpdated.push(...commandsResult.updated.map(f => `commands/${f}`));

    // Merge settings
    try {
      result.settingsMerged = mergeSettings(targetClaudeDir);
    } catch (error) {
      result.errors.push(`Failed to merge settings: ${error instanceof Error ? error.message : String(error)}`);
    }

    // Write version manifest
    const newManifest: VersionManifest = {
      version: TUSK_VERSION,
      installedAt: new Date().toISOString(),
      files: {
        hooks: [...hooksResult.added, ...hooksResult.updated],
        commands: [...commandsResult.added, ...commandsResult.updated],
        settings: result.settingsMerged
      }
    };

    writeVersionManifest(targetClaudeDir, newManifest);

    // Determine if installation happened
    result.installed = result.filesAdded.length > 0 || result.filesUpdated.length > 0 || result.settingsMerged;
    result.needsRestart = result.installed;

    return result;

  } catch (error) {
    result.errors.push(`Auto-setup failed: ${error instanceof Error ? error.message : String(error)}`);
    return result;
  }
}

/**
 * Format installation result for stderr logging
 */
export function formatInstallationResult(result: InstallationResult, existingVersion: string | null): string {
  const lines: string[] = [];

  if (result.errors.length > 0) {
    lines.push("⚠️  Tusk auto-setup encountered errors:");
    result.errors.forEach(err => lines.push(`   ${err}`));
    return lines.join("\n");
  }

  if (!result.installed) {
    lines.push("✅ Tusk integration files up to date");
    return lines.join("\n");
  }

  // First time installation
  if (!existingVersion) {
    lines.push("📁 Installing Tusk integration files to .claude/...");

    if (result.filesAdded.length > 0) {
      const hookCount = result.filesAdded.filter(f => f.startsWith("hooks/")).length;
      const cmdCount = result.filesAdded.filter(f => f.startsWith("commands/")).length;

      if (hookCount > 0) {
        lines.push(`   ✅ Copied ${hookCount} hooks to .claude/hooks/`);
      }
      if (cmdCount > 0) {
        lines.push(`   ✅ Copied ${cmdCount} commands to .claude/commands/`);
      }
    }

    if (result.settingsMerged) {
      lines.push(`   ✅ Configured permissions and hooks in .claude/settings.json`);
    }

    lines.push("");
    lines.push("⚠️  RESTART REQUIRED: Restart Claude Code to activate hooks and commands");
  }
  // Update scenario
  else {
    lines.push(`📦 Tusk integration files updated (${existingVersion} → ${TUSK_VERSION})`);

    if (result.filesUpdated.length > 0) {
      lines.push(`   ✅ Updated ${result.filesUpdated.length} files`);
    }

    if (result.filesSkipped.length > 0) {
      lines.push(`   ⏭️  Skipped ${result.filesSkipped.length} customized files`);
    }

    lines.push("");
    lines.push("⚠️  RESTART REQUIRED: Restart Claude Code to use updated files");
  }

  return lines.join("\n");
}
