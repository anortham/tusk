#!/usr/bin/env bun
/**
 * Advanced Test Runner for tusk-bun
 * Provides sophisticated test execution with reporting and analysis
 */

import { spawn, spawnSync } from "bun";
import { existsSync, mkdirSync, writeFileSync } from "fs";
import { join } from "path";

interface TestRunOptions {
  pattern?: string;
  suite?: string;
  coverage?: boolean;
  watch?: boolean;
  timeout?: number;
  parallel?: boolean;
  verbose?: boolean;
  bail?: boolean;
  reporter?: "default" | "json" | "junit" | "tap";
  outputDir?: string;
}

interface TestResult {
  suite: string;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  coverage?: number;
  errors: string[];
}

interface TestSession {
  startTime: Date;
  endTime?: Date;
  results: TestResult[];
  summary: {
    totalTests: number;
    totalPassed: number;
    totalFailed: number;
    totalSkipped: number;
    totalDuration: number;
    overallCoverage?: number;
  };
}

class TestRunner {
  private options: TestRunOptions;
  private session: TestSession;

  constructor(options: TestRunOptions = {}) {
    this.options = {
      timeout: 30000,
      parallel: true,
      verbose: false,
      bail: false,
      reporter: "default",
      outputDir: "test-results",
      ...options,
    };

    this.session = {
      startTime: new Date(),
      results: [],
      summary: {
        totalTests: 0,
        totalPassed: 0,
        totalFailed: 0,
        totalSkipped: 0,
        totalDuration: 0,
      },
    };
  }

  async run(): Promise<boolean> {
    console.log("🧪 Starting tusk-bun test runner...\n");

    this.printConfiguration();
    await this.setupOutputDirectory();

    if (this.options.suite) {
      return await this.runTestSuite(this.options.suite);
    } else if (this.options.pattern) {
      return await this.runTestPattern(this.options.pattern);
    } else {
      return await this.runAllTests();
    }
  }

  private printConfiguration(): void {
    console.log("⚙️  Test Configuration:");
    console.log(`   Suite: ${this.options.suite || "all"}`);
    console.log(`   Pattern: ${this.options.pattern || "all"}`);
    console.log(`   Coverage: ${this.options.coverage ? "enabled" : "disabled"}`);
    console.log(`   Timeout: ${this.options.timeout}ms`);
    console.log(`   Reporter: ${this.options.reporter}`);
    console.log(`   Output: ${this.options.outputDir}`);
    console.log(`   Parallel: ${this.options.parallel ? "enabled" : "disabled"}`);
    console.log();
  }

  private async setupOutputDirectory(): Promise<void> {
    if (!existsSync(this.options.outputDir!)) {
      mkdirSync(this.options.outputDir!, { recursive: true });
    }
  }

  private async runAllTests(): Promise<boolean> {
    console.log("🏃‍♂️ Running all test suites...\n");

    const suites = [
      { name: "unit", description: "Unit Tests", files: ["tests/*.test.ts"], exclude: ["tests/integration.test.ts"] },
      { name: "integration", description: "Integration Tests", files: ["tests/integration.test.ts"] },
      { name: "contracts", description: "Contract Tests", files: ["tests/contracts/*.ts"] },
    ];

    let allPassed = true;

    for (const suite of suites) {
      console.log(`📦 Running ${suite.description}...`);
      const success = await this.executeBunTest(suite.name, suite.files, suite.exclude);
      allPassed = allPassed && success;

      if (!success && this.options.bail) {
        console.log("🛑 Stopping on first failure (--bail enabled)");
        break;
      }
      console.log();
    }

    this.finishSession();
    return allPassed;
  }

  private async runTestSuite(suiteName: string): Promise<boolean> {
    console.log(`📦 Running test suite: ${suiteName}\n`);

    const suiteDefinitions = {
      unit: { files: ["tests/*.test.ts"], exclude: ["tests/integration.test.ts"] },
      integration: { files: ["tests/integration.test.ts"] },
      contracts: { files: ["tests/contracts/*.ts"] },
      journal: { files: ["tests/journal.test.ts"] },
      git: { files: ["tests/git.test.ts"] },
      mcp: { files: ["tests/mcp-server.test.ts"] },
      cli: { files: ["tests/cli.test.ts"] },
      standup: { files: ["tests/standup.test.ts"] },
      performance: { files: ["tests/*.test.ts"], options: ["--timeout", "60000"] },
      quick: { files: ["tests/journal.test.ts", "tests/git.test.ts"] },
    };

    const suite = suiteDefinitions[suiteName as keyof typeof suiteDefinitions];
    if (!suite) {
      console.error(`❌ Unknown test suite: ${suiteName}`);
      console.log("Available suites:", Object.keys(suiteDefinitions).join(", "));
      return false;
    }

    const success = await this.executeBunTest(suiteName, suite.files, suite.exclude, suite.options);
    this.finishSession();
    return success;
  }

  private async runTestPattern(pattern: string): Promise<boolean> {
    console.log(`🔍 Running tests matching pattern: ${pattern}\n`);

    const success = await this.executeBunTest("pattern", [pattern]);
    this.finishSession();
    return success;
  }

  private async executeBunTest(
    suiteName: string,
    files: string[],
    exclude?: string[],
    extraOptions?: string[]
  ): Promise<boolean> {
    const args = ["test"];

    // Add file patterns
    args.push(...files);

    // Add exclusions
    if (exclude) {
      for (const excludePattern of exclude) {
        args.push("--exclude", excludePattern);
      }
    }

    // Add options
    if (this.options.coverage) {
      args.push("--coverage");
    }

    if (this.options.timeout) {
      args.push("--timeout", this.options.timeout.toString());
    }

    if (this.options.reporter && this.options.reporter !== "default") {
      args.push("--reporter", this.options.reporter);
    }

    if (this.options.verbose) {
      args.push("--verbose");
    }

    if (this.options.bail) {
      args.push("--bail");
    }

    if (extraOptions) {
      args.push(...extraOptions);
    }

    // Execute test
    const startTime = Date.now();

    if (this.options.verbose) {
      console.log(`   Executing: bun ${args.join(" ")}`);
    }

    const result = spawnSync(["bun", ...args], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        TUSK_TEST_MODE: "true",
        NODE_ENV: "test",
      },
      stdio: ["pipe", "pipe", "pipe"],
    });

    const duration = Date.now() - startTime;
    const stdout = result.stdout?.toString() || "";
    const stderr = result.stderr?.toString() || "";

    // Parse results
    const testResult = this.parseTestOutput(suiteName, stdout, stderr, duration, result.success);
    this.session.results.push(testResult);

    // Display results
    this.displayTestResult(testResult);

    // Save output if needed
    if (this.options.outputDir) {
      await this.saveTestOutput(suiteName, stdout, stderr, testResult);
    }

    return result.success || false;
  }

  private parseTestOutput(
    suiteName: string,
    stdout: string,
    stderr: string,
    duration: number,
    success: boolean
  ): TestResult {
    // Basic parsing - can be enhanced with more sophisticated output parsing
    const lines = stdout.split("\n");

    let passed = 0;
    let failed = 0;
    let skipped = 0;
    const errors: string[] = [];

    // Simple parsing for Bun test output
    for (const line of lines) {
      if (line.includes("✓") || line.includes("PASS")) {
        passed++;
      } else if (line.includes("✗") || line.includes("FAIL")) {
        failed++;
        errors.push(line.trim());
      } else if (line.includes("SKIP")) {
        skipped++;
      }
    }

    // If no specific counts found, use basic success/failure
    if (passed === 0 && failed === 0) {
      if (success) {
        passed = 1;
      } else {
        failed = 1;
        if (stderr) {
          errors.push(stderr.slice(0, 200));
        }
      }
    }

    // Try to extract coverage if present
    let coverage: number | undefined;
    const coverageMatch = stdout.match(/Coverage:\s*(\d+(?:\.\d+)?)%/);
    if (coverageMatch) {
      coverage = parseFloat(coverageMatch[1]);
    }

    return {
      suite: suiteName,
      passed,
      failed,
      skipped,
      duration,
      coverage,
      errors,
    };
  }

  private displayTestResult(result: TestResult): void {
    const status = result.failed === 0 ? "✅" : "❌";
    const total = result.passed + result.failed + result.skipped;

    console.log(`${status} ${result.suite}:`);
    console.log(`   Tests: ${total} (${result.passed} passed, ${result.failed} failed, ${result.skipped} skipped)`);
    console.log(`   Duration: ${result.duration}ms`);

    if (result.coverage !== undefined) {
      console.log(`   Coverage: ${result.coverage.toFixed(1)}%`);
    }

    if (result.errors.length > 0) {
      console.log(`   Errors:`);
      for (const error of result.errors.slice(0, 3)) {
        console.log(`     - ${error}`);
      }
      if (result.errors.length > 3) {
        console.log(`     ... and ${result.errors.length - 3} more errors`);
      }
    }
  }

  private async saveTestOutput(
    suiteName: string,
    stdout: string,
    stderr: string,
    result: TestResult
  ): Promise<void> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const outputFile = join(this.options.outputDir!, `${suiteName}-${timestamp}.json`);

    const output = {
      suite: suiteName,
      timestamp: new Date().toISOString(),
      result,
      stdout,
      stderr,
      environment: {
        bunVersion: Bun.version,
        platform: process.platform,
        arch: process.arch,
        nodeVersion: process.version,
      },
    };

    writeFileSync(outputFile, JSON.stringify(output, null, 2));
  }

  private finishSession(): void {
    this.session.endTime = new Date();

    // Calculate summary
    this.session.summary = {
      totalTests: this.session.results.reduce((sum, r) => sum + r.passed + r.failed + r.skipped, 0),
      totalPassed: this.session.results.reduce((sum, r) => sum + r.passed, 0),
      totalFailed: this.session.results.reduce((sum, r) => sum + r.failed, 0),
      totalSkipped: this.session.results.reduce((sum, r) => sum + r.skipped, 0),
      totalDuration: this.session.results.reduce((sum, r) => sum + r.duration, 0),
    };

    // Calculate overall coverage
    const coverageResults = this.session.results.filter(r => r.coverage !== undefined);
    if (coverageResults.length > 0) {
      this.session.summary.overallCoverage =
        coverageResults.reduce((sum, r) => sum + r.coverage!, 0) / coverageResults.length;
    }

    this.displaySessionSummary();
    this.saveSessionReport();
  }

  private displaySessionSummary(): void {
    const { summary } = this.session;
    const duration = this.session.endTime!.getTime() - this.session.startTime.getTime();

    console.log("\n" + "=".repeat(50));
    console.log("📊 Test Session Summary");
    console.log("=".repeat(50));

    const status = summary.totalFailed === 0 ? "✅ PASSED" : "❌ FAILED";
    console.log(`Status: ${status}`);
    console.log(`Tests: ${summary.totalTests} total`);
    console.log(`  ✅ Passed: ${summary.totalPassed}`);
    console.log(`  ❌ Failed: ${summary.totalFailed}`);
    console.log(`  ⏭️  Skipped: ${summary.totalSkipped}`);
    console.log(`Duration: ${duration}ms`);

    if (summary.overallCoverage !== undefined) {
      console.log(`Coverage: ${summary.overallCoverage.toFixed(1)}%`);
    }

    console.log(`Session: ${this.session.startTime.toISOString()} → ${this.session.endTime!.toISOString()}`);
    console.log("=".repeat(50));

    // Show recommendation
    if (summary.totalFailed > 0) {
      console.log("\n💡 Recommendations:");
      console.log("   • Review failed tests and error messages");
      console.log("   • Run specific failing suites: bun run test:debug");
      console.log("   • Check test artifacts in test-results/");
    } else {
      console.log("\n🎉 All tests passed! Great work!");
      if (summary.overallCoverage && summary.overallCoverage < 90) {
        console.log(`💡 Consider improving test coverage (currently ${summary.overallCoverage.toFixed(1)}%)`);
      }
    }
  }

  private saveSessionReport(): void {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const reportFile = join(this.options.outputDir!, `test-session-${timestamp}.json`);

    writeFileSync(reportFile, JSON.stringify(this.session, null, 2));
    console.log(`\n💾 Session report saved: ${reportFile}`);
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);
  const options: TestRunOptions = {};

  // Parse command line arguments
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    switch (arg) {
      case "--suite":
        options.suite = args[++i];
        break;
      case "--pattern":
        options.pattern = args[++i];
        break;
      case "--coverage":
        options.coverage = true;
        break;
      case "--watch":
        options.watch = true;
        break;
      case "--timeout":
        options.timeout = parseInt(args[++i]);
        break;
      case "--reporter":
        options.reporter = args[++i] as any;
        break;
      case "--output-dir":
        options.outputDir = args[++i];
        break;
      case "--verbose":
        options.verbose = true;
        break;
      case "--bail":
        options.bail = true;
        break;
      case "--no-parallel":
        options.parallel = false;
        break;
      case "--help":
      case "-h":
        showHelp();
        process.exit(0);
        break;
    }
  }

  try {
    const runner = new TestRunner(options);
    const success = await runner.run();
    process.exit(success ? 0 : 1);
  } catch (error) {
    console.error("❌ Test runner failed:", error);
    process.exit(1);
  }
}

function showHelp() {
  console.log(`
🧪 Advanced Test Runner for tusk-bun

Usage: bun run tests/scripts/test-runner.ts [options]

Options:
  --suite <name>        Run specific test suite (unit, integration, contracts, etc.)
  --pattern <pattern>   Run tests matching pattern
  --coverage            Enable test coverage reporting
  --watch               Run tests in watch mode
  --timeout <ms>        Set test timeout in milliseconds
  --reporter <type>     Set reporter (default, json, junit, tap)
  --output-dir <dir>    Set output directory for test artifacts
  --verbose             Enable verbose output
  --bail                Stop on first test failure
  --no-parallel         Disable parallel test execution
  --help, -h            Show this help message

Test Suites:
  unit                  Run all unit tests
  integration           Run integration tests
  contracts             Run contract tests
  journal               Run journal-specific tests
  git                   Run git integration tests
  mcp                   Run MCP server tests
  cli                   Run CLI tests
  standup               Run standup generation tests
  performance           Run performance tests
  quick                 Run quick subset of tests

Examples:
  bun run tests/scripts/test-runner.ts --suite unit --coverage
  bun run tests/scripts/test-runner.ts --pattern "*journal*" --verbose
  bun run tests/scripts/test-runner.ts --suite integration --bail
  bun run tests/scripts/test-runner.ts --coverage --reporter json
`);
}

// Run if this script is executed directly
if (import.meta.main) {
  main();
}

export { TestRunner, type TestRunOptions, type TestResult, type TestSession };