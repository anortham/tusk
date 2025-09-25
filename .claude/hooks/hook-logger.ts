/**
 * Tusk Hook Logger - Minimal logging with daily rotation
 *
 * Provides concise logging for hook activities with automatic daily log rotation
 * to prevent log files from growing indefinitely.
 */

import { appendFileSync, existsSync, writeFileSync, statSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const HOOKS_LOG_PATH = join(homedir(), ".tusk", "hooks.log");
const MAX_LOG_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours

function shouldRotateLog(): boolean {
  if (!existsSync(HOOKS_LOG_PATH)) {
    return false;
  }

  try {
    const stats = statSync(HOOKS_LOG_PATH);
    const ageMs = Date.now() - stats.mtime.getTime();
    return ageMs > MAX_LOG_AGE_MS;
  } catch {
    return false;
  }
}

function rotateLog(): void {
  try {
    if (shouldRotateLog()) {
      const today = new Date().toISOString().split('T')[0];
      writeFileSync(HOOKS_LOG_PATH, `=== Tusk Hooks Log - ${today} ===\n`);
    }
  } catch (error) {
    // Silently fail rotation - don't block hook execution
  }
}

export function logHookActivity(hookName: string, action: string, details?: string): void {
  try {
    rotateLog();

    const timestamp = new Date().toLocaleTimeString();
    const message = details ? `${action}: ${details}` : action;
    const logEntry = `[${timestamp}] ${hookName}: ${message}\n`;

    appendFileSync(HOOKS_LOG_PATH, logEntry);
  } catch {
    // Silently fail logging - don't block hook execution
  }
}

export function logSuccess(hookName: string, description: string): void {
  logHookActivity(hookName, "✅ Saved", description);
}

export function logError(hookName: string, error: string): void {
  logHookActivity(hookName, "❌ Failed", error);
}

export function logSkip(hookName: string, reason: string): void {
  logHookActivity(hookName, "⏭️ Skipped", reason);
}