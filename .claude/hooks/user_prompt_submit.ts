#!/usr/bin/env bun
/**
 * Tusk User Prompt Submit Hook
 *
 * Captures important user prompts and technical decisions to prevent loss during compaction.
 * Automatically detects and saves checkpoints for significant discussions and decisions.
 */

import { spawnSync } from "bun";
import { appendFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const HOOKS_LOG_PATH = join(homedir(), ".tusk", "hooks.log");

function logHookActivity(message: string) {
  try {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [user_prompt_submit] ${message}\n`;
    appendFileSync(HOOKS_LOG_PATH, logEntry);
  } catch (error) {
    console.error(`⚠️ Failed to write to hooks log: ${error}`);
  }
}

function detectImportantPrompt(text: string): boolean {
  const importantPatterns = [
    /\b(implement|build|create|develop|design|architecture)\b/i,
    /\b(bug|fix|issue|problem|error|debug)\b/i,
    /\b(plan|strategy|approach|solution|algorithm)\b/i,
    /\b(refactor|optimize|improve|enhance|update)\b/i,
    /\b(review|analyze|investigate|research)\b/i,
    /\b(deploy|release|production|staging)\b/i,
    /\b(test|testing|tests|spec|specification)\b/i,
    /\b(api|database|security|performance)\b/i,
  ];

  return importantPatterns.some(pattern => pattern.test(text));
}

function extractKeyContent(text: string): string {
  // Remove common prefixes
  let cleaned = text.replace(/^(please|can you|could you|help me|i need to|let's)\s*/i, '');

  // Get first sentence or meaningful chunk
  const sentences = cleaned.split(/[.!?]\s+/);
  if (sentences.length > 0) {
    const firstSentence = sentences[0].trim();
    if (firstSentence.length > 10) {
      if (firstSentence.length > 80) {
        return firstSentence.substring(0, 77) + "...";
      }
      return firstSentence;
    }
  }

  // Fallback to first 80 chars
  if (cleaned.length > 80) {
    return cleaned.substring(0, 77) + "...";
  }
  return cleaned;
}

async function main() {
  logHookActivity("Hook triggered");

  try {
    // Read JSON input from stdin
    const stdinBuffer = [];
    for await (const chunk of process.stdin) {
      stdinBuffer.push(chunk);
    }
    const inputData = JSON.parse(Buffer.concat(stdinBuffer).toString());

    logHookActivity(`Input data keys: ${JSON.stringify(Object.keys(inputData))}`);

    // Extract session_id and prompt from input data
    const sessionId = inputData.session_id || 'unknown';
    const content = inputData.prompt || '';

    logHookActivity(`Session ID: ${sessionId}`);
    logHookActivity(`Prompt content length: ${content.length}`);
    logHookActivity(`Content preview: ${content.substring(0, 100)}...`);

    // Skip if the prompt is too short or not important
    if (content.trim().length < 20) {
      logHookActivity("Content too short, skipping");
      process.exit(0);
    }

    if (!detectImportantPrompt(content)) {
      logHookActivity("Content not detected as important, skipping");
      process.exit(0);
    }

    const keyContent = extractKeyContent(content);
    const description = `User request: ${keyContent}`;

    logHookActivity(`Creating checkpoint with description: ${description}`);

    // Save checkpoint using tusk CLI with absolute path
    const result = spawnSync(["bun", "/Users/murphy/Source/tusk/cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      logHookActivity(`✅ Checkpoint saved successfully: ${description}`);
      console.error(`✅ User prompt checkpoint saved: ${description}`);
    } else {
      const errorOutput = new TextDecoder().decode(result.stderr);
      logHookActivity(`❌ Checkpoint failed: ${errorOutput}`);
      console.error(`⚠️ User prompt checkpoint failed: ${errorOutput}`);
    }
  } catch (error) {
    logHookActivity(`❌ Hook error: ${error}`);
    console.error(`⚠️ User prompt hook error: ${error}`);
    // Exit successfully to not interfere with Claude
    process.exit(0);
  }

  logHookActivity("Hook completed");
  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();