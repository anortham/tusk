#!/usr/bin/env bun
/**
 * Test Environment Setup Script
 * Prepares the testing environment and validates test dependencies
 */

import { existsSync, mkdirSync, rmSync, writeFileSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

interface SetupOptions {
  clean?: boolean;
  verbose?: boolean;
  validateDeps?: boolean;
}

class TestEnvironmentSetup {
  private options: SetupOptions;
  private testDir: string;

  constructor(options: SetupOptions = {}) {
    this.options = {
      clean: true,
      verbose: false,
      validateDeps: true,
      ...options,
    };
    this.testDir = join(tmpdir(), "tusk-test-setup");
  }

  async run(): Promise<void> {
    this.log("🧪 Setting up test environment...");

    if (this.options.clean) {
      await this.cleanPreviousRuns();
    }

    if (this.options.validateDeps) {
      await this.validateDependencies();
    }

    await this.createTestDirectories();
    await this.validateTestFiles();
    await this.setupTestData();
    await this.validateBunConfiguration();

    this.log("✅ Test environment setup complete!");
    this.printSummary();
  }

  private async cleanPreviousRuns(): Promise<void> {
    this.log("🧹 Cleaning previous test runs...");

    const cleanupPaths = [
      "coverage",
      "test-results",
      ".test-cache",
      this.testDir,
    ];

    for (const path of cleanupPaths) {
      if (existsSync(path)) {
        rmSync(path, { recursive: true, force: true });
        this.log(`   Removed: ${path}`);
      }
    }
  }

  private async validateDependencies(): Promise<void> {
    this.log("📦 Validating test dependencies...");

    // Check Bun version
    const bunVersion = await this.getBunVersion();
    this.log(`   Bun version: ${bunVersion}`);

    if (!bunVersion || !this.isVersionCompatible(bunVersion, "1.0.0")) {
      throw new Error("Bun version 1.0.0 or higher is required");
    }

    // Check TypeScript
    try {
      const { spawn } = require("bun");
      const result = spawn(["tsc", "--version"]);
      const tsVersion = await new Response(result.stdout).text();
      this.log(`   TypeScript version: ${tsVersion.trim()}`);
    } catch {
      this.log("   ⚠️  TypeScript not found (optional)");
    }

    // Validate test framework dependencies
    this.validateTestFramework();
  }

  private async getBunVersion(): Promise<string> {
    try {
      return Bun.version;
    } catch {
      return "unknown";
    }
  }

  private isVersionCompatible(current: string, required: string): boolean {
    const parseVersion = (v: string) => v.split(".").map(Number);
    const currentParts = parseVersion(current);
    const requiredParts = parseVersion(required);

    for (let i = 0; i < Math.max(currentParts.length, requiredParts.length); i++) {
      const curr = currentParts[i] || 0;
      const req = requiredParts[i] || 0;

      if (curr > req) return true;
      if (curr < req) return false;
    }

    return true;
  }

  private validateTestFramework(): void {
    // Check if test files exist
    const criticalTestFiles = [
      "tests/setup.ts",
      "tests/journal.test.ts",
      "tests/git.test.ts",
      "tests/mcp-server.test.ts",
      "tests/cli.test.ts",
      "tests/standup.test.ts",
      "tests/integration.test.ts",
    ];

    let missingFiles = 0;
    for (const file of criticalTestFiles) {
      if (!existsSync(file)) {
        this.log(`   ❌ Missing: ${file}`);
        missingFiles++;
      } else {
        this.log(`   ✅ Found: ${file}`);
      }
    }

    if (missingFiles > 0) {
      throw new Error(`${missingFiles} critical test files are missing`);
    }
  }

  private async createTestDirectories(): Promise<void> {
    this.log("📁 Creating test directories...");

    const testDirs = [
      "coverage",
      "test-results",
      ".test-cache",
      this.testDir,
      join(this.testDir, "journals"),
      join(this.testDir, "git-repos"),
      join(this.testDir, "temp"),
    ];

    for (const dir of testDirs) {
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
        this.log(`   Created: ${dir}`);
      }
    }
  }

  private async validateTestFiles(): Promise<void> {
    this.log("🔍 Validating test file syntax...");

    const testFiles = [
      "tests/setup.ts",
      "tests/journal.test.ts",
      "tests/git.test.ts",
      "tests/mcp-server.test.ts",
      "tests/cli.test.ts",
      "tests/standup.test.ts",
      "tests/integration.test.ts",
    ];

    for (const file of testFiles) {
      try {
        await import(`../../${file}`);
        this.log(`   ✅ Valid: ${file}`);
      } catch (error) {
        this.log(`   ❌ Invalid: ${file} - ${error}`);
        throw new Error(`Test file validation failed: ${file}`);
      }
    }
  }

  private async setupTestData(): Promise<void> {
    this.log("📝 Setting up test data...");

    // Create sample test configuration
    const testConfig = {
      environment: "test",
      timestamp: new Date().toISOString(),
      testDirectory: this.testDir,
      bunVersion: await this.getBunVersion(),
    };

    const configPath = join(this.testDir, "test-config.json");
    writeFileSync(configPath, JSON.stringify(testConfig, null, 2));
    this.log(`   Created test config: ${configPath}`);

    // Create sample journal entries for testing
    const sampleEntries = [
      {
        id: "test_setup_1",
        type: "checkpoint",
        timestamp: new Date().toISOString(),
        description: "Test environment setup validation",
        project: "test-setup",
        tags: ["test", "setup"],
      },
    ];

    const journalPath = join(this.testDir, "journals", "sample.jsonl");
    const journalContent = sampleEntries.map(entry => JSON.stringify(entry)).join("\n");
    writeFileSync(journalPath, journalContent);
    this.log(`   Created sample journal: ${journalPath}`);
  }

  private async validateBunConfiguration(): Promise<void> {
    this.log("⚙️  Validating Bun configuration...");

    // Check if bunfig.toml exists
    if (existsSync("bunfig.toml")) {
      this.log("   ✅ Found bunfig.toml");
    } else {
      this.log("   ⚠️  bunfig.toml not found (optional)");
    }

    // Validate package.json test scripts
    try {
      const packageJson = await Bun.file("package.json").json();
      const testScripts = Object.keys(packageJson.scripts || {})
        .filter(script => script.startsWith("test"));

      if (testScripts.length > 0) {
        this.log(`   ✅ Found ${testScripts.length} test scripts: ${testScripts.join(", ")}`);
      } else {
        this.log("   ⚠️  No test scripts found in package.json");
      }
    } catch (error) {
      this.log(`   ❌ Error reading package.json: ${error}`);
    }
  }

  private printSummary(): void {
    console.log("\n📊 Test Environment Summary:");
    console.log(`   Test Directory: ${this.testDir}`);
    console.log(`   Bun Version: ${Bun.version}`);
    console.log(`   Node Version: ${process.version}`);
    console.log(`   Platform: ${process.platform}`);
    console.log(`   Architecture: ${process.arch}`);
    console.log("\n🚀 Ready to run tests! Try:");
    console.log("   bun test                 # Run all tests");
    console.log("   bun run test:unit        # Run unit tests only");
    console.log("   bun run test:integration # Run integration tests");
    console.log("   bun run test:coverage    # Run with coverage");
  }

  private log(message: string): void {
    if (this.options.verbose || process.env.VERBOSE) {
      console.log(message);
    }
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);
  const options: SetupOptions = {
    clean: !args.includes("--no-clean"),
    verbose: args.includes("--verbose") || args.includes("-v"),
    validateDeps: !args.includes("--skip-deps"),
  };

  if (args.includes("--help") || args.includes("-h")) {
    console.log(`
Test Environment Setup Script

Usage: bun run tests/scripts/setup-test-env.ts [options]

Options:
  --no-clean      Skip cleaning previous test runs
  --skip-deps     Skip dependency validation
  --verbose, -v   Enable verbose output
  --help, -h      Show this help message

Examples:
  bun run test:setup
  bun run test:setup --verbose
  bun run test:setup --no-clean --skip-deps
`);
    process.exit(0);
  }

  try {
    const setup = new TestEnvironmentSetup(options);
    await setup.run();
  } catch (error) {
    console.error("❌ Test environment setup failed:", error);
    process.exit(1);
  }
}

// Run if this script is executed directly
if (import.meta.main) {
  main();
}

export { TestEnvironmentSetup, type SetupOptions };