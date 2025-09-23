#!/usr/bin/env bun
/**
 * Tusk-Bun User Prompt Submit Hook
 *
 * Captures important user prompts and technical decisions to prevent loss during compaction.
 * Automatically detects and saves checkpoints for significant discussions and decisions.
 */

import { spawnSync } from "bun";

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
  try {
    const args = process.argv.slice(2);
    const dataIndex = args.indexOf('--data');

    if (dataIndex === -1 || !args[dataIndex + 1]) {
      process.exit(0);
    }

    const data = JSON.parse(args[dataIndex + 1]);
    const userMessage = data.user_message || {};
    const content = userMessage.content || '';

    // Skip if the prompt is too short or not important
    if (content.trim().length < 20 || !detectImportantPrompt(content)) {
      process.exit(0);
    }

    const keyContent = extractKeyContent(content);
    const description = `User request: ${keyContent}`;

    // Save checkpoint using local tusk CLI
    const result = spawnSync(["bun", "./cli.ts", "checkpoint", description], {
      stdout: "pipe",
      stderr: "pipe",
    });

    if (result.success) {
      console.error(`✅ User prompt checkpoint saved: ${description}`);
    }
  } catch (error) {
    console.error(`⚠️ User prompt hook error: ${error}`);
  }

  // Always exit successfully to not interfere with Claude
  process.exit(0);
}

main();