#!/usr/bin/env bun
/**
 * Migration script to update plans table schema
 * Removes the foreign key constraint that was causing issues
 */

import { Database } from "bun:sqlite";
import { join } from "path";
import { homedir } from "os";

const dbPath = join(homedir(), '.tusk', 'journal.db');

console.log(`Migrating database at: ${dbPath}`);

const db = new Database(dbPath);

try {
  // Check if plans table exists
  const tableExists = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='plans'").get();

  if (tableExists) {
    console.log("Plans table exists, migrating with data preservation...");

    // CRITICAL: Back up existing plans BEFORE dropping table
    const existingPlans = db.prepare("SELECT * FROM plans").all();
    console.log(`📦 Backing up ${existingPlans.length} existing plans...`);

    // Drop the old plans table
    db.run("DROP TABLE IF EXISTS plans");

    // Create new plans table without foreign key
    db.run(`
      CREATE TABLE plans (
        id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        progress_notes TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        completed_at INTEGER,
        is_active BOOLEAN DEFAULT 0
      )
    `);

    // Create indexes
    db.run("CREATE INDEX IF NOT EXISTS idx_plans_workspace ON plans(workspace_id)");
    db.run("CREATE INDEX IF NOT EXISTS idx_plans_active ON plans(workspace_id, is_active) WHERE is_active = 1");
    db.run("CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(workspace_id, status)");

    // Restore backed up plans
    if (existingPlans.length > 0) {
      const insertStmt = db.prepare(`
        INSERT INTO plans (id, workspace_id, title, content, status, progress_notes, created_at, updated_at, completed_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);

      for (const plan of existingPlans) {
        insertStmt.run(
          plan.id,
          plan.workspace_id,
          plan.title,
          plan.content,
          plan.status || 'active',
          plan.progress_notes || null,
          plan.created_at,
          plan.updated_at,
          plan.completed_at || null,
          plan.is_active || 0
        );
      }

      console.log(`✅ Restored ${existingPlans.length} plans successfully`);
    }

    console.log("✅ Plans table migrated successfully");
  } else {
    console.log("Plans table doesn't exist yet, will be created on first use");
  }

} catch (error) {
  console.error("❌ Migration failed:", error);
  process.exit(1);
} finally {
  db.close();
}

console.log("Migration complete!");
