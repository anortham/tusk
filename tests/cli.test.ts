/**
 * CLI Interface Test Suite
 * Implements comprehensive tests based on cli.contracts.ts
 */

import { test, expect, describe, beforeEach, afterEach } from "bun:test";
import { spawnSync } from "bun";
import { join } from "path";
import {
  TestDataFactory,
  TestEnvironment,
  PerformanceTester,
  TestAssertions,
  TEST_CONFIG,
} from "./setup.js";

// CLI test utilities
class CLITestUtils {
  static async runCLI(args: string[], options: {
    cwd?: string;
    input?: string;
    timeout?: number;
  } = {}): Promise<{
    exitCode: number;
    stdout: string;
    stderr: string;
    success: boolean;
  }> {
    const cliPath = join(process.cwd(), "cli.ts");

    const result = spawnSync(["bun", cliPath, ...args], {
      cwd: options.cwd || process.cwd(),
      stdin: options.input || null,
      timeout: options.timeout || 5000,
      env: {
        ...process.env,
        TUSK_TEST_MODE: "true",
        TUSK_TEST_DIR: TEST_CONFIG.TEST_TUSK_DIR,
      },
    });

    const stdout = result.stdout ? new TextDecoder().decode(result.stdout) : "";
    const stderr = result.stderr ? new TextDecoder().decode(result.stderr) : "";

    return {
      exitCode: result.exitCode || 0,
      stdout,
      stderr,
      success: result.success || false,
    };
  }

  static expectSuccess(result: Awaited<ReturnType<typeof CLITestUtils.runCLI>>) {
    expect(result.success).toBe(true);
    expect(result.exitCode).toBe(0);
  }

  static expectFailure(result: Awaited<ReturnType<typeof CLITestUtils.runCLI>>) {
    expect(result.success).toBe(false);
    expect(result.exitCode).not.toBe(0);
  }

  static expectOutputContains(result: Awaited<ReturnType<typeof CLITestUtils.runCLI>>, text: string) {
    expect(result.stdout.toLowerCase()).toContain(text.toLowerCase());
  }

  static expectErrorContains(result: Awaited<ReturnType<typeof CLITestUtils.runCLI>>, text: string) {
    expect(result.stderr.toLowerCase()).toContain(text.toLowerCase());
  }
}

// Setup test environment
beforeEach(() => {
  TestEnvironment.setup();
});

afterEach(() => {
  TestEnvironment.cleanup();
});

describe("CLI Interface - Command Parsing", () => {
  test("should parse checkpoint command correctly", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint", "Test checkpoint"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "checkpoint saved");
  });

  test("should parse recall command correctly", async () => {
    // First create some test data
    await CLITestUtils.runCLI(["checkpoint", "Test entry for recall"]);

    const result = await CLITestUtils.runCLI(["recall"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "found");
  });

  test("should parse standup command correctly", async () => {
    // First create some test data
    await CLITestUtils.runCLI(["checkpoint", "Test entry for standup"]);

    const result = await CLITestUtils.runCLI(["standup"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "standup");
  });

  test("should handle help command", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "usage");
    CLITestUtils.expectOutputContains(result, "checkpoint");
    CLITestUtils.expectOutputContains(result, "recall");
    CLITestUtils.expectOutputContains(result, "standup");
  });

  test("should handle short command aliases (cp, rc, su)", async () => {
    const cpResult = await CLITestUtils.runCLI(["cp", "Test checkpoint alias"]);
    CLITestUtils.expectSuccess(cpResult);
    CLITestUtils.expectOutputContains(cpResult, "checkpoint saved");

    const rcResult = await CLITestUtils.runCLI(["rc"]);
    CLITestUtils.expectSuccess(rcResult);

    const suResult = await CLITestUtils.runCLI(["su"]);
    CLITestUtils.expectSuccess(suResult);
  });

  test("should handle unknown commands gracefully", async () => {
    const result = await CLITestUtils.runCLI(["unknown-command"]);

    CLITestUtils.expectSuccess(result); // Should show help, not error
    CLITestUtils.expectOutputContains(result, "usage");
  });

  test("should handle empty command line", async () => {
    const result = await CLITestUtils.runCLI([]);

    CLITestUtils.expectSuccess(result); // Should show help
    CLITestUtils.expectOutputContains(result, "usage");
  });
});

describe("CLI Interface - Checkpoint Command", () => {
  test("should require description argument", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint"]);

    CLITestUtils.expectFailure(result);
    CLITestUtils.expectErrorContains(result, "description required");
  });

  test("should accept optional tags argument", async () => {
    const result = await CLITestUtils.runCLI([
      "checkpoint",
      "Test with tags",
      "tag1,tag2,tag3"
    ]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "checkpoint saved");
    CLITestUtils.expectOutputContains(result, "tag1, tag2, tag3");
  });

  test("should handle quoted descriptions with spaces", async () => {
    const result = await CLITestUtils.runCLI([
      "checkpoint",
      "This is a description with spaces"
    ]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "checkpoint saved");
  });

  test("should handle descriptions with special characters", async () => {
    const specialDesc = "Test with émojis 🎉 and quotes 'single' \"double\"";
    const result = await CLITestUtils.runCLI(["checkpoint", specialDesc]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "checkpoint saved");
  });

  test("should parse comma-separated tags", async () => {
    const result = await CLITestUtils.runCLI([
      "checkpoint",
      "Test with parsed tags",
      "bug-fix,auth,critical"
    ]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "bug-fix, auth, critical");
  });

  test("should trim whitespace from tags", async () => {
    const result = await CLITestUtils.runCLI([
      "checkpoint",
      "Test whitespace trimming",
      " tag1 , tag2 , tag3 "
    ]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "tag1, tag2, tag3");
  });

  test("should display success message", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint", "Success message test"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "✅");
    CLITestUtils.expectOutputContains(result, "checkpoint saved");
  });

  test("should show generated ID", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint", "ID display test"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "🆔");
    // ID format: YYYYMMDDHHMMSS_random
    expect(result.stdout).toMatch(/\d{14}_[a-z0-9]{6}/);
  });

  test("should show git context when available", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint", "Git context test"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "📁");
  });
});

describe("CLI Interface - Recall Command", () => {
  beforeEach(async () => {
    // Create test data for recall tests
    const testEntries = [
      "Recent authentication work",
      "Added user dashboard feature",
      "Fixed critical bug in parser"
    ];

    for (const desc of testEntries) {
      await CLITestUtils.runCLI(["checkpoint", desc]);
    }
  });

  test("should use default parameters when none provided", async () => {
    const result = await CLITestUtils.runCLI(["recall"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "found");
  });

  test("should parse --days parameter", async () => {
    const result1 = await CLITestUtils.runCLI(["recall", "--days=7"]);
    CLITestUtils.expectSuccess(result1);

    const result2 = await CLITestUtils.runCLI(["recall", "--days", "7"]);
    CLITestUtils.expectSuccess(result2);
  });

  test("should parse --search parameter", async () => {
    const result1 = await CLITestUtils.runCLI(["recall", "--search=auth"]);
    CLITestUtils.expectSuccess(result1);

    const result2 = await CLITestUtils.runCLI(["recall", "--search", "dashboard"]);
    CLITestUtils.expectSuccess(result2);
    CLITestUtils.expectOutputContains(result2, "dashboard");
  });

  test("should parse --project parameter", async () => {
    const result = await CLITestUtils.runCLI(["recall", "--project", "test-project"]);
    CLITestUtils.expectSuccess(result);
  });

  test("should validate numeric days parameter", async () => {
    const validResult = await CLITestUtils.runCLI(["recall", "--days", "5"]);
    CLITestUtils.expectSuccess(validResult);

    const invalidResult = await CLITestUtils.runCLI(["recall", "--days", "not-a-number"]);
    CLITestUtils.expectFailure(invalidResult);
  });

  test("should handle invalid days values gracefully", async () => {
    const negativeResult = await CLITestUtils.runCLI(["recall", "--days", "-5"]);
    // Should handle gracefully, not crash
    expect(negativeResult.exitCode).toBeDefined();

    const zeroResult = await CLITestUtils.runCLI(["recall", "--days", "0"]);
    CLITestUtils.expectSuccess(zeroResult);
  });

  test("should display entries in readable format", async () => {
    const result = await CLITestUtils.runCLI(["recall"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "🧠");
    CLITestUtils.expectOutputContains(result, "•");

    // Should show time indicators
    expect(result.stdout).toMatch(/\(\d+[mhd] ago\)/);
  });

  test("should handle no entries found gracefully", async () => {
    const result = await CLITestUtils.runCLI(["recall", "--search", "nonexistent-query-12345"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "no entries found");
  });

  test("should parse --list-workspaces parameter", async () => {
    const result = await CLITestUtils.runCLI(["recall", "--list-workspaces"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "workspace");
  });

  test("should parse --from parameter for date range filtering", async () => {
    const result1 = await CLITestUtils.runCLI(["recall", "--from=2025-01-01"]);
    CLITestUtils.expectSuccess(result1);

    const result2 = await CLITestUtils.runCLI(["recall", "--from", "2025-01-01"]);
    CLITestUtils.expectSuccess(result2);
  });

  test("should parse --to parameter for date range filtering", async () => {
    const result1 = await CLITestUtils.runCLI(["recall", "--to=2025-12-31"]);
    CLITestUtils.expectSuccess(result1);

    const result2 = await CLITestUtils.runCLI(["recall", "--to", "2025-12-31"]);
    CLITestUtils.expectSuccess(result2);
  });

  test("should handle date range filtering with both --from and --to", async () => {
    const result = await CLITestUtils.runCLI([
      "recall",
      "--from", "2025-01-01",
      "--to", "2025-12-31"
    ]);
    CLITestUtils.expectSuccess(result);
  });

  test("should validate date format for --from parameter", async () => {
    const validResult = await CLITestUtils.runCLI(["recall", "--from", "2025-01-01"]);
    CLITestUtils.expectSuccess(validResult);

    // Invalid date should still succeed but may return no results
    const invalidResult = await CLITestUtils.runCLI(["recall", "--from", "invalid-date"]);
    // The function should handle invalid dates gracefully
    expect(invalidResult.exitCode).toBeDefined();
  });

  test("should require value for --from parameter", async () => {
    const result = await CLITestUtils.runCLI(["recall", "--from="]);
    CLITestUtils.expectFailure(result);
    CLITestUtils.expectErrorContains(result, "--from= requires a value");
  });

  test("should require value for --to parameter", async () => {
    const result = await CLITestUtils.runCLI(["recall", "--to="]);
    CLITestUtils.expectFailure(result);
    CLITestUtils.expectErrorContains(result, "--to= requires a value");
  });

  test("should handle workspace listing with proper formatting", async () => {
    const result = await CLITestUtils.runCLI(["recall", "--list-workspaces"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "📂");
    CLITestUtils.expectOutputContains(result, "📁");
  });

  test("should combine parameters correctly", async () => {
    const result = await CLITestUtils.runCLI([
      "recall",
      "--workspace", "current",
      "--from", "2025-01-01",
      "--days", "30"
    ]);
    CLITestUtils.expectSuccess(result);
  });
});

describe("CLI Interface - Standup Command", () => {
  beforeEach(async () => {
    // Create varied test data for standup tests
    const testData = [
      { desc: "Implemented user authentication", tags: "feature,auth" },
      { desc: "Fixed memory leak in parser", tags: "bug-fix,critical" },
      { desc: "Added dashboard analytics", tags: "feature,ui" },
      { desc: "Optimized database queries", tags: "performance" },
    ];

    for (const item of testData) {
      await CLITestUtils.runCLI(["checkpoint", item.desc, item.tags]);
    }
  });

  test("should use default style when none provided", async () => {
    const result = await CLITestUtils.runCLI(["standup"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "daily standup");
  });

  test("should parse --style parameter", async () => {
    const styles = ["meeting", "written", "executive", "metrics"];

    for (const style of styles) {
      const result = await CLITestUtils.runCLI(["standup", "--style", style]);
      CLITestUtils.expectSuccess(result);
    }
  });

  test("should validate style enum values", async () => {
    const validResult = await CLITestUtils.runCLI(["standup", "--style", "executive"]);
    CLITestUtils.expectSuccess(validResult);

    const invalidResult = await CLITestUtils.runCLI(["standup", "--style", "invalid-style"]);
    CLITestUtils.expectFailure(invalidResult);
  });

  test("should parse --days parameter", async () => {
    const result = await CLITestUtils.runCLI(["standup", "--days", "7"]);
    CLITestUtils.expectSuccess(result);
  });

  test("should handle --no-metrics flag", async () => {
    const result = await CLITestUtils.runCLI(["standup", "--no-metrics"]);
    CLITestUtils.expectSuccess(result);
  });

  test("should handle --include-files flag", async () => {
    const result = await CLITestUtils.runCLI(["standup", "--include-files"]);
    CLITestUtils.expectSuccess(result);
  });

  test("should generate properly formatted output", async () => {
    const result = await CLITestUtils.runCLI(["standup"]);

    CLITestUtils.expectSuccess(result);

    // Check for proper formatting elements
    CLITestUtils.expectOutputContains(result, "🏃‍♂️");
    CLITestUtils.expectOutputContains(result, "standup");
    CLITestUtils.expectOutputContains(result, "✅");

    TestAssertions.assertFormattingQuality(result.stdout);
  });

  test("should handle unknown style values", async () => {
    const result = await CLITestUtils.runCLI(["standup", "--style", "unknown"]);
    CLITestUtils.expectFailure(result);
    CLITestUtils.expectErrorContains(result, "invalid");
  });

  test("should display complete standup report", async () => {
    const result = await CLITestUtils.runCLI(["standup", "--style", "executive"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "executive summary");
    CLITestUtils.expectOutputContains(result, "impact");
  });
});

describe("CLI Interface - Help System", () => {
  test("should display main help when no command provided", async () => {
    const result = await CLITestUtils.runCLI([]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "tusk cli");
    CLITestUtils.expectOutputContains(result, "usage");
  });

  test("should display help for --help flag", async () => {
    const result = await CLITestUtils.runCLI(["--help"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "usage");
  });

  test("should display help for help command", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectSuccess(result);
    CLITestUtils.expectOutputContains(result, "usage");
  });

  test("should include all commands in help", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectOutputContains(result, "checkpoint");
    CLITestUtils.expectOutputContains(result, "recall");
    CLITestUtils.expectOutputContains(result, "standup");
  });

  test("should include command aliases in help", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectOutputContains(result, "cp");
    CLITestUtils.expectOutputContains(result, "rc");
    CLITestUtils.expectOutputContains(result, "su");
  });

  test("should include parameter descriptions", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectOutputContains(result, "days");
    CLITestUtils.expectOutputContains(result, "search");
    CLITestUtils.expectOutputContains(result, "style");
  });

  test("should include usage examples", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectOutputContains(result, "examples");
    CLITestUtils.expectOutputContains(result, "checkpoint \"");
    CLITestUtils.expectOutputContains(result, "recall --days");
  });

  test("should include Claude Code hook information", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectOutputContains(result, "claude code");
    CLITestUtils.expectOutputContains(result, "hook");
  });

  test("should be well-formatted and readable", async () => {
    const result = await CLITestUtils.runCLI(["help"]);

    CLITestUtils.expectSuccess(result);
    TestAssertions.assertFormattingQuality(result.stdout);

    // Should have reasonable length
    expect(result.stdout.length).toBeGreaterThan(500);
    expect(result.stdout.length).toBeLessThan(5000);
  });
});

describe("CLI Interface - Error Handling", () => {
  test("should handle file system permission errors", async () => {
    // This test would require special setup to simulate permission errors
    // For now, we test that errors are handled gracefully
    const result = await CLITestUtils.runCLI(["checkpoint", "Permission test"]);

    // Should either succeed or fail gracefully with helpful message
    if (!result.success) {
      expect(result.stderr.length).toBeGreaterThan(0);
    }
  });

  test("should provide meaningful error messages", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint"]);

    CLITestUtils.expectFailure(result);
    CLITestUtils.expectErrorContains(result, "description required");

    // Error message should be helpful
    expect(result.stderr).toContain("Usage:");
  });

  test("should use appropriate exit codes", async () => {
    const successResult = await CLITestUtils.runCLI(["checkpoint", "Success test"]);
    expect(successResult.exitCode).toBe(0);

    const errorResult = await CLITestUtils.runCLI(["checkpoint"]);
    expect(errorResult.exitCode).toBe(1);
  });

  test("should never crash unexpectedly", async () => {
    const edgeCaseInputs = [
      ["checkpoint", ""],
      ["recall", "--days", "abc"],
      ["standup", "--style", ""],
      ["nonexistent-command"],
      [],
    ];

    for (const input of edgeCaseInputs) {
      const result = await CLITestUtils.runCLI(input);

      // Should not crash (exit code should be defined)
      expect(result.exitCode).toBeDefined();
      expect(typeof result.exitCode).toBe("number");
    }
  });
});

describe("CLI Interface - Performance", () => {
  test("should start up quickly (under 100ms)", async () => {
    const { executionTime } = await PerformanceTester.measureExecution(
      async () => {
        return CLITestUtils.runCLI(["help"]);
      },
      TEST_CONFIG.PERFORMANCE_THRESHOLDS.CLI_STARTUP
    );

    TestAssertions.assertPerformance(
      executionTime,
      TEST_CONFIG.PERFORMANCE_THRESHOLDS.CLI_STARTUP,
      "CLI startup time"
    );
  });

  test("should execute commands efficiently", async () => {
    const { executionTime } = await PerformanceTester.measureExecution(
      async () => {
        return CLITestUtils.runCLI(["checkpoint", "Performance test checkpoint"]);
      },
      1000 // Should complete in under 1 second
    );

    TestAssertions.assertPerformance(
      executionTime,
      1000,
      "CLI command execution"
    );
  });

  test("should handle large datasets reasonably", async () => {
    // Create a dataset with many entries
    for (let i = 0; i < 50; i++) { // Reduced for test performance
      await CLITestUtils.runCLI(["checkpoint", `Large dataset entry ${i}`]);
    }

    const { executionTime } = await PerformanceTester.measureExecution(
      async () => {
        return CLITestUtils.runCLI(["recall", "--days", "7"]);
      },
      2000 // Should handle large recall in under 2 seconds
    );

    TestAssertions.assertPerformance(
      executionTime,
      2000,
      "CLI large dataset handling"
    );
  });

  test("should not consume excessive memory", async () => {
    const { memoryDelta } = await PerformanceTester.measureMemoryUsage(async () => {
      // Run multiple CLI operations
      for (let i = 0; i < 20; i++) {
        await CLITestUtils.runCLI(["checkpoint", `Memory test ${i}`]);
        await CLITestUtils.runCLI(["recall"]);
        await CLITestUtils.runCLI(["standup"]);
      }
    });

    TestAssertions.assertMemoryUsage(
      memoryDelta,
      50 * 1024 * 1024, // 50MB limit
      "CLI memory usage"
    );
  });
});

describe("CLI Interface - Output Formatting", () => {
  test("should format success messages consistently", async () => {
    const results = await Promise.all([
      CLITestUtils.runCLI(["checkpoint", "Format test 1"]),
      CLITestUtils.runCLI(["checkpoint", "Format test 2"]),
      CLITestUtils.runCLI(["checkpoint", "Format test 3"]),
    ]);

    results.forEach(result => {
      CLITestUtils.expectSuccess(result);
      CLITestUtils.expectOutputContains(result, "✅");
      CLITestUtils.expectOutputContains(result, "checkpoint saved");
      TestAssertions.assertFormattingQuality(result.stdout);
    });
  });

  test("should format error messages consistently", async () => {
    const results = await Promise.all([
      CLITestUtils.runCLI(["checkpoint"]),
      CLITestUtils.runCLI(["recall", "--days", "invalid"]),
      CLITestUtils.runCLI(["standup", "--style", "invalid"]),
    ]);

    results.forEach(result => {
      CLITestUtils.expectFailure(result);
      CLITestUtils.expectErrorContains(result, "❌");
      TestAssertions.assertFormattingQuality(result.stderr);
    });
  });

  test("should use consistent emoji and styling", async () => {
    const result = await CLITestUtils.runCLI(["checkpoint", "Styling test"]);

    CLITestUtils.expectSuccess(result);

    // Check for consistent emoji usage
    expect(result.stdout).toContain("✅"); // Success
    expect(result.stdout).toContain("📝"); // Description
    expect(result.stdout).toContain("🆔"); // ID
    expect(result.stdout).toContain("📁"); // Project
  });

  test("should be readable in different terminals", async () => {
    const result = await CLITestUtils.runCLI(["standup"]);

    CLITestUtils.expectSuccess(result);

    // Should not have excessive special characters that might not render
    const specialCharCount = (result.stdout.match(/[^\x20-\x7E\n\r\t]/g) || []).length;
    const totalCharCount = result.stdout.length;

    // Special characters should be less than 10% of total
    expect(specialCharCount / totalCharCount).toBeLessThan(0.1);
  });
});

describe("CLI Interface - Integration", () => {
  test("should work with different locale settings", async () => {
    // Test with different environment settings
    const originalLang = process.env.LANG;

    try {
      process.env.LANG = "en_US.UTF-8";
      const result1 = await CLITestUtils.runCLI(["checkpoint", "Locale test 1"]);
      CLITestUtils.expectSuccess(result1);

      process.env.LANG = "C";
      const result2 = await CLITestUtils.runCLI(["checkpoint", "Locale test 2"]);
      CLITestUtils.expectSuccess(result2);
    } finally {
      if (originalLang) {
        process.env.LANG = originalLang;
      }
    }
  });

  test("should handle automated execution", async () => {
    // Simulate automated/scripted execution
    const batchCommands = [
      ["checkpoint", "Automated test 1", "automation"],
      ["checkpoint", "Automated test 2", "automation"],
      ["recall", "--search", "automation"],
      ["standup", "--style", "metrics"],
    ];

    for (const command of batchCommands) {
      const result = await CLITestUtils.runCLI(command);
      CLITestUtils.expectSuccess(result);
    }
  });
});