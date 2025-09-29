/**
 * Test for SQLite I/O Disk Error Bug
 *
 * This test reproduces the SQLITE_IOERR_VNODE error that occurs when
 * running tests in temporary directories on macOS.
 *
 * Bug: SQLite disk I/O error (errno: 6922, code: SQLITE_IOERR_VNODE)
 * Location: journal.ts:441 during stmt.run() in saveCheckpoint()
 * Trigger: Tests using TUSK_TEST_DIR temp directories
 */

import { test, expect, describe, beforeEach, afterEach } from "bun:test";
import { join } from "path";
import { existsSync, mkdirSync, rmSync } from "fs";
import { tmpdir } from "os";
import { saveEntry, getRecentEntries } from '../src/utils/journal.js';
import type { JournalEntry } from '../src/utils/journal.js';
import { TestEnvironment, TestDataFactory } from "./setup.js";

describe("SQLite I/O Bug Reproduction", () => {
  let tempTestDir: string;

  beforeEach(() => {
    // Create a unique temp directory for this test
    tempTestDir = join(tmpdir(), `tusk-sqlite-bug-test-${Date.now()}-${Math.random().toString(36).slice(2)}`);

    if (!existsSync(tempTestDir)) {
      mkdirSync(tempTestDir, { recursive: true });
    }

    // Set up test environment with explicit temp directory
    process.env.TUSK_TEST_MODE = "true";
    process.env.TUSK_TEST_DIR = tempTestDir;

    TestEnvironment.setup();
  });

  afterEach(() => {
    TestEnvironment.cleanup();

    // Clean up temp directory
    if (existsSync(tempTestDir)) {
      rmSync(tempTestDir, { recursive: true, force: true });
    }

    delete process.env.TUSK_TEST_MODE;
    delete process.env.TUSK_TEST_DIR;
  });

  test("should reproduce SQLite I/O disk error in temp directory", async () => {
    // This test should currently FAIL with SQLite I/O error
    // Once fixed, it should PASS

    const entry: JournalEntry = TestDataFactory.createJournalEntry({
      description: "Test checkpoint that triggers SQLite I/O error",
      project: "test-project",
      gitBranch: "test-branch",
      tags: ["bug-reproduction", "sqlite", "io-error"]
    });

    // This call should trigger the SQLite I/O error
    // Error: SQLiteError: disk I/O error (errno: 6922, code: SQLITE_IOERR_VNODE)
    // at stmt.run() in saveCheckpoint() function
    await expect(async () => {
      await saveEntry(entry);
    }).not.toThrow(); // This will fail until bug is fixed

    // If save succeeds, verify we can read it back
    const entries = await getRecentEntries({ days: 1 });
    expect(entries).toHaveLength(1);
    expect(entries[0].description).toBe(entry.description);
  });

  test("should handle multiple concurrent writes without I/O errors", async () => {
    // Test concurrent access that might exacerbate the I/O issue
    const entries = Array.from({ length: 5 }, (_, i) =>
      TestDataFactory.createJournalEntry({
        description: `Concurrent entry ${i + 1}`,
        project: "concurrent-test"
      })
    );

    // This should not throw SQLite I/O errors
    await expect(async () => {
      await Promise.all(entries.map(entry => saveEntry(entry)));
    }).not.toThrow();

    const savedEntries = await getRecentEntries({ days: 1 });
    expect(savedEntries).toHaveLength(5);
  });

  test("should verify temp directory permissions and structure", async () => {
    // Verify the test setup is correct
    expect(process.env.TUSK_TEST_MODE).toBe("true");
    expect(process.env.TUSK_TEST_DIR).toBe(tempTestDir);
    expect(existsSync(tempTestDir)).toBe(true);

    // Check if database file can be created
    const dbPath = join(tempTestDir, "journal.db");

    // Try to create a simple entry
    const entry = TestDataFactory.createJournalEntry({
      description: "Permission test entry"
    });

    await saveEntry(entry);

    // Database file should exist after save
    expect(existsSync(dbPath)).toBe(true);
  });
});