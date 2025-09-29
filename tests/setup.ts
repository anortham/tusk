/**
 * Test Setup and Utilities
 * Provides common test utilities and setup functions
 */

import { existsSync, rmSync, mkdirSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { beforeEach, afterEach } from "bun:test";
import type { JournalEntry } from '../src/utils/journal.js';
import { __resetDefaultJournal } from '../src/utils/journal.js';

// Test environment configuration
export const TEST_CONFIG = {
  // Use a temporary directory for test data
  TEST_TUSK_DIR: join(tmpdir(), "tusk-test-" + Date.now()),
  TIMEOUT_MS: 5000,
  PERFORMANCE_THRESHOLDS: {
    JOURNAL_OPERATION: 100, // ms
    GIT_OPERATION: 500, // ms
    MCP_RESPONSE: 1000, // ms
    CLI_STARTUP: 100, // ms
    STANDUP_GENERATION: 200, // ms
  },
};

// Test data factory
export class TestDataFactory {
  static createJournalEntry(overrides: Partial<JournalEntry> = {}): JournalEntry {
    return {
      id: `test_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      description: "Test checkpoint entry",
      project: "test-project",
      gitBranch: "test-branch",
      gitCommit: "abc123",
      files: ["test-file.ts"],
      tags: ["test", "example"],
      ...overrides,
    };
  }

  static createMultipleEntries(count: number, baseOverrides: Partial<JournalEntry> = {}): JournalEntry[] {
    return Array.from({ length: count }, (_, i) =>
      this.createJournalEntry({
        ...baseOverrides,
        description: `Test entry ${i + 1}`,
        timestamp: new Date(Date.now() - i * 60000).toISOString(), // Spread entries over time
      })
    );
  }

  static createEntriesWithDifferentProjects(projects: string[]): JournalEntry[] {
    return projects.flatMap((project, projectIndex) =>
      Array.from({ length: Math.floor(Math.random() * 5) + 1 }, (_, entryIndex) =>
        this.createJournalEntry({
          project,
          description: `${project} work item ${entryIndex + 1}`,
          timestamp: new Date(Date.now() - (projectIndex * 1000 + entryIndex * 100) * 60000).toISOString(),
        })
      )
    );
  }

  static createEntriesWithTimeDistribution(daysBack: number): JournalEntry[] {
    const entries: JournalEntry[] = [];
    const now = new Date();

    for (let day = 0; day < daysBack; day++) {
      const entriesPerDay = Math.floor(Math.random() * 8) + 1; // 1-8 entries per day
      for (let entry = 0; entry < entriesPerDay; entry++) {
        const timestamp = new Date(now.getTime() - day * 24 * 60 * 60 * 1000 - entry * 60 * 60 * 1000);
        entries.push(
          this.createJournalEntry({
            description: `Day ${day + 1} activity ${entry + 1}`,
            timestamp: timestamp.toISOString(),
            project: day % 3 === 0 ? "project-a" : day % 3 === 1 ? "project-b" : "project-c",
          })
        );
      }
    }

    return entries;
  }
}

// Test environment setup
export class TestEnvironment {
  static setup(): void {
    // Create test directory
    if (!existsSync(TEST_CONFIG.TEST_TUSK_DIR)) {
      mkdirSync(TEST_CONFIG.TEST_TUSK_DIR, { recursive: true });
    }

    // Override environment variables for testing
    process.env.TUSK_TEST_MODE = "true";
    process.env.TUSK_TEST_DIR = TEST_CONFIG.TEST_TUSK_DIR;
  }

  static cleanup(): void {
    // Reset the default journal singleton for test isolation
    __resetDefaultJournal();

    // Clean up test directory
    if (existsSync(TEST_CONFIG.TEST_TUSK_DIR)) {
      rmSync(TEST_CONFIG.TEST_TUSK_DIR, { recursive: true, force: true });
    }

    // Clean up environment
    delete process.env.TUSK_TEST_MODE;
    delete process.env.TUSK_TEST_DIR;
  }

  static resetJournal(): void {
    // Remove SQLite database files
    const dbPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.db");
    const walPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.db-wal");
    const shmPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.db-shm");

    [dbPath, walPath, shmPath].forEach(path => {
      if (existsSync(path)) {
        rmSync(path);
      }
    });

    // Legacy JSONL cleanup (for backward compatibility)
    const jsonlPath = join(TEST_CONFIG.TEST_TUSK_DIR, "journal.jsonl");
    if (existsSync(jsonlPath)) {
      rmSync(jsonlPath);
    }
  }
}

// Performance testing utilities
export class PerformanceTester {
  static async measureExecution<T>(
    operation: () => Promise<T>,
    expectedThreshold: number
  ): Promise<{ result: T; executionTime: number; withinThreshold: boolean }> {
    const startTime = performance.now();
    const result = await operation();
    const executionTime = performance.now() - startTime;

    return {
      result,
      executionTime,
      withinThreshold: executionTime <= expectedThreshold,
    };
  }

  static async measureMemoryUsage<T>(operation: () => Promise<T>): Promise<{ result: T; memoryDelta: number }> {
    // Force garbage collection if available
    if (global.gc) {
      global.gc();
    }

    const initialMemory = process.memoryUsage().heapUsed;
    const result = await operation();

    if (global.gc) {
      global.gc();
    }

    const finalMemory = process.memoryUsage().heapUsed;
    const memoryDelta = finalMemory - initialMemory;

    return { result, memoryDelta };
  }
}

// Error testing utilities
export class ErrorTester {
  static createCorruptedJSONL(validEntries: JournalEntry[]): string {
    const lines = validEntries.map(entry => JSON.stringify(entry));
    // Insert some corrupted lines
    lines.splice(2, 0, "{ invalid json");
    lines.splice(5, 0, "not json at all");
    lines.splice(8, 0, '{"incomplete": "json"');
    return lines.join("\n");
  }

  static simulatePermissionError(): Error {
    const error = new Error("EACCES: permission denied");
    (error as any).code = "EACCES";
    return error;
  }

  static simulateDiskSpaceError(): Error {
    const error = new Error("ENOSPC: no space left on device");
    (error as any).code = "ENOSPC";
    return error;
  }
}

// Assertion helpers
export class TestAssertions {
  static assertJournalEntry(entry: any, expected: Partial<JournalEntry>): void {
    if (expected.id && entry.id !== expected.id) {
      throw new Error(`Expected id ${expected.id}, got ${entry.id}`);
    }
    if (expected.description && entry.description !== expected.description) {
      throw new Error(`Expected description ${expected.description}, got ${entry.description}`);
    }
    if (expected.project && entry.project !== expected.project) {
      throw new Error(`Expected project ${expected.project}, got ${entry.project}`);
    }
    if (expected.tags && JSON.stringify(entry.tags) !== JSON.stringify(expected.tags)) {
      throw new Error(`Expected tags ${JSON.stringify(expected.tags)}, got ${JSON.stringify(entry.tags)}`);
    }
  }

  static assertPerformance(executionTime: number, threshold: number, operation: string): void {
    if (executionTime > threshold) {
      throw new Error(`${operation} took ${executionTime}ms, expected under ${threshold}ms`);
    }
  }

  static assertMemoryUsage(memoryDelta: number, maxIncrease: number, operation: string): void {
    if (memoryDelta > maxIncrease) {
      throw new Error(`${operation} increased memory by ${memoryDelta} bytes, expected under ${maxIncrease} bytes`);
    }
  }

  static assertArrayContainsSubset<T>(actual: T[], expected: T[], message?: string): void {
    const missing = expected.filter(item => !actual.includes(item));
    if (missing.length > 0) {
      throw new Error(`${message || "Array missing items"}: ${JSON.stringify(missing)}`);
    }
  }

  static assertStringContains(text: string, expectedSubstring: string, message?: string): void {
    if (!text.includes(expectedSubstring)) {
      throw new Error(`${message || "String does not contain expected substring"}: "${expectedSubstring}"`);
    }
  }

  static assertFormattingQuality(text: string): void {
    // Check for consistent line endings
    if (text.includes("\r\n") && text.includes("\n") && !text.includes("\r\n")) {
      throw new Error("Inconsistent line endings detected");
    }

    // Check for reasonable line lengths (most lines under 120 chars)
    const lines = text.split("\n");
    const longLines = lines.filter(line => line.length > 120);
    if (longLines.length > lines.length * 0.1) {
      throw new Error(`Too many long lines: ${longLines.length}/${lines.length}`);
    }

    // Check for proper spacing (no multiple consecutive spaces except in code blocks)
    const multipleSpaces = text.match(/  +/g);
    if (multipleSpaces && multipleSpaces.length > 5) {
      console.warn("Potentially inconsistent spacing detected");
    }
  }
}

// Global test hooks
export function setupTestHooks(): void {
  // Setup before each test
  beforeEach(() => {
    TestEnvironment.setup();
  });

  // Cleanup after each test
  afterEach(() => {
    TestEnvironment.cleanup();
  });
}

// All utilities are exported inline above