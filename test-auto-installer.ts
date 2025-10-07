#!/usr/bin/env bun

/**
 * Test script for auto-installer
 */

import { autoSetupClaudeIntegration, formatInstallationResult } from "./src/setup/auto-installer.js";
import { existsSync, mkdirSync, rmSync } from "fs";
import { join } from "path";

async function testAutoInstaller() {
  console.log("🧪 Testing Auto-Installer\n");

  // Create a test directory
  const testDir = join(process.cwd(), ".test-auto-install");

  // Clean up if exists
  if (existsSync(testDir)) {
    rmSync(testDir, { recursive: true, force: true });
  }

  mkdirSync(testDir, { recursive: true });

  try {
    console.log("1️⃣ Testing first-time installation...");
    console.log(`   Test directory: ${testDir}\n`);

    const result1 = await autoSetupClaudeIntegration(testDir);

    console.log("Installation Result:");
    console.log(`  Installed: ${result1.installed}`);
    console.log(`  Files added: ${result1.filesAdded.length}`);
    console.log(`  Files skipped: ${result1.filesSkipped.length}`);
    console.log(`  Files updated: ${result1.filesUpdated.length}`);
    console.log(`  Settings merged: ${result1.settingsMerged}`);
    console.log(`  Needs restart: ${result1.needsRestart}`);
    console.log(`  Errors: ${result1.errors.length}\n`);

    if (result1.filesAdded.length > 0) {
      console.log("  Added files:");
      result1.filesAdded.forEach(f => console.log(`    - ${f}`));
      console.log();
    }

    console.log("Formatted output:");
    console.log(formatInstallationResult(result1, null));
    console.log();

    // Check that .claude directory was created
    const claudeDir = join(testDir, ".claude");
    if (existsSync(claudeDir)) {
      console.log("✅ .claude directory created");
    } else {
      console.log("❌ .claude directory NOT created");
    }

    // Check for version file
    const versionFile = join(claudeDir, ".tusk-version");
    if (existsSync(versionFile)) {
      console.log("✅ .tusk-version file created");
    } else {
      console.log("❌ .tusk-version file NOT created");
    }

    // Check for hooks directory
    const hooksDir = join(claudeDir, "hooks");
    if (existsSync(hooksDir)) {
      console.log("✅ hooks/ directory created");
    } else {
      console.log("❌ hooks/ directory NOT created");
    }

    // Check for commands directory
    const commandsDir = join(claudeDir, "commands");
    if (existsSync(commandsDir)) {
      console.log("✅ commands/ directory created");
    } else {
      console.log("❌ commands/ directory NOT created");
    }

    console.log("\n2️⃣ Testing second run (should skip files)...\n");

    const result2 = await autoSetupClaudeIntegration(testDir);

    console.log("Installation Result:");
    console.log(`  Installed: ${result2.installed}`);
    console.log(`  Files added: ${result2.filesAdded.length}`);
    console.log(`  Files skipped: ${result2.filesSkipped.length}`);
    console.log(`  Files updated: ${result2.filesUpdated.length}\n`);

    console.log("Formatted output:");
    console.log(formatInstallationResult(result2, "1.0.0"));
    console.log();

    console.log("\n✅ Test complete!");

  } catch (error) {
    console.error("\n❌ Test failed:", error);
  } finally {
    // Clean up
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true });
      console.log(`\n🧹 Cleaned up test directory`);
    }
  }
}

testAutoInstaller();
