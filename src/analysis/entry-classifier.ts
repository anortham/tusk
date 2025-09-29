/**
 * Entry Classification System for Tusk Journal System
 * Automatically categorizes checkpoint entries and assigns confidence scores
 */

import type { CheckpointEntry } from "../core/types.js";

export type EntryType = 'user-request' | 'session-marker' | 'auto-save' | 'progress' | 'completion';

export interface ClassificationResult {
  entryType: EntryType;
  confidenceScore: number; // 0.0-1.0
  reasoningPoints: string[];
  suggestedTags?: string[];
}

export interface ClassificationPattern {
  patterns: RegExp[];
  type: EntryType;
  baseConfidence: number;
  tags?: string[];
  negativePatterns?: RegExp[]; // Patterns that decrease confidence
}

/**
 * Entry classifier that analyzes checkpoint descriptions and context
 */
export class EntryClassifier {
  private patterns: ClassificationPattern[] = [
    // Session markers (high confidence)
    {
      patterns: [
        /^session started/i,
        /^conversation started/i,
        /^resuming work/i,
        /^beginning session/i,
        /\bsession[-\s]?start\b/i,
      ],
      type: 'session-marker',
      baseConfidence: 0.95,
      tags: ['session-boundary'],
    },

    // Completion patterns (high confidence)
    {
      patterns: [
        /\b(completed|finished|done|resolved|fixed|implemented|deployed)\b/i,
        /\b(successfully|achievement|milestone|breakthrough)\b/i,
        /\b(shipped|released|merged|closed)\b/i,
        /✅|✓|☑️/,
      ],
      type: 'completion',
      baseConfidence: 0.85,
      tags: ['achievement', 'completion'],
      negativePatterns: [
        /\b(started|beginning|working on|in progress)\b/i,
        /\b(need to|should|will|planning)\b/i,
      ],
    },

    // Progress patterns (medium-high confidence)
    {
      patterns: [
        /\b(working on|implementing|debugging|investigating)\b/i,
        /\b(making progress|moving forward|continuing)\b/i,
        /\b(updated|modified|enhanced|improved)\b/i,
        /\b(in progress|wip|work[-\s]?in[-\s]?progress)\b/i,
      ],
      type: 'progress',
      baseConfidence: 0.75,
      tags: ['work-in-progress'],
    },

    // Auto-save patterns (lower confidence)
    {
      patterns: [
        /^auto[-\s]?saved?/i,
        /^checkpoint/i,
        /^saving progress/i,
        /^backup/i,
        /pre[-\s]?compact/i,
      ],
      type: 'auto-save',
      baseConfidence: 0.5,
      tags: ['automated'],
    },

    // User request patterns (detect explicit user requests)
    {
      patterns: [
        /^(please|can you|could you|help me|i need)/i,
        /^(let's|we should|i want to)/i,
        /\b(request|task|todo|action item)\b/i,
      ],
      type: 'user-request',
      baseConfidence: 0.9,
      tags: ['user-initiated'],
    },
  ];

  /**
   * Classify a checkpoint entry
   */
  classify(entry: CheckpointEntry): ClassificationResult {
    const description = entry.description.trim();
    const reasoningPoints: string[] = [];
    let bestMatch: { pattern: ClassificationPattern; score: number } | null = null;

    // Analyze against all patterns
    for (const pattern of this.patterns) {
      const score = this.calculatePatternScore(description, pattern, reasoningPoints);
      if (!bestMatch || score > bestMatch.score) {
        bestMatch = { pattern, score };
      }
    }

    // Apply contextual adjustments
    const contextualScore = bestMatch ? this.applyContextualAdjustments(
      entry,
      bestMatch.pattern,
      bestMatch.score,
      reasoningPoints
    ) : 0.6; // Default confidence for unmatched patterns

    const finalType = bestMatch?.pattern.type || 'user-request';
    const finalScore = Math.max(0.1, Math.min(1.0, contextualScore));

    // Generate suggested tags
    const suggestedTags = this.generateSuggestedTags(entry, finalType);

    return {
      entryType: finalType,
      confidenceScore: finalScore,
      reasoningPoints,
      suggestedTags,
    };
  }

  /**
   * Calculate pattern matching score
   */
  private calculatePatternScore(
    description: string,
    pattern: ClassificationPattern,
    reasoningPoints: string[]
  ): number {
    let score = 0;
    let matchCount = 0;

    // Check positive patterns
    for (const regex of pattern.patterns) {
      if (regex.test(description)) {
        score += pattern.baseConfidence;
        matchCount++;
        reasoningPoints.push(`Matched ${pattern.type} pattern: ${regex.source}`);
      }
    }

    // Apply negative patterns (reduce confidence)
    if (pattern.negativePatterns) {
      for (const negRegex of pattern.negativePatterns) {
        if (negRegex.test(description)) {
          score -= 0.2;
          reasoningPoints.push(`Negative pattern matched: ${negRegex.source}`);
        }
      }
    }

    // Normalize by pattern count (but reward multiple matches)
    return matchCount > 0 ? score / Math.sqrt(pattern.patterns.length) : 0;
  }

  /**
   * Apply contextual adjustments based on entry metadata
   */
  private applyContextualAdjustments(
    entry: CheckpointEntry,
    pattern: ClassificationPattern,
    baseScore: number,
    reasoningPoints: string[]
  ): number {
    let adjustedScore = baseScore;

    // Length-based adjustments
    const descLength = entry.description.length;
    if (descLength < 10) {
      adjustedScore -= 0.2;
      reasoningPoints.push("Short description reduces confidence");
    } else if (descLength > 100) {
      adjustedScore += 0.1;
      reasoningPoints.push("Detailed description increases confidence");
    }

    // Git context boosts confidence
    if (entry.gitCommit) {
      adjustedScore += 0.15;
      reasoningPoints.push("Git commit context increases confidence");
    } else if (entry.gitBranch) {
      adjustedScore += 0.1;
      reasoningPoints.push("Git branch context increases confidence");
    }

    // File context adds value
    if (entry.files && entry.files.length > 0) {
      adjustedScore += 0.1;
      reasoningPoints.push(`File context (${entry.files.length} files) increases confidence`);
    }

    // Tag context
    if (entry.tags && entry.tags.length > 0) {
      adjustedScore += 0.05;
      reasoningPoints.push("Existing tags increase confidence");

      // Specific tag boosts
      const criticalTags = ['critical', 'important', 'breakthrough', 'milestone'];
      if (entry.tags.some(tag => criticalTags.includes(tag.toLowerCase()))) {
        adjustedScore += 0.1;
        reasoningPoints.push("Critical tags boost confidence");
      }
    }

    // Time-based adjustments (recent entries more likely to be relevant)
    const entryTime = new Date(entry.timestamp).getTime();
    const hoursSinceEntry = (Date.now() - entryTime) / (1000 * 60 * 60);

    if (hoursSinceEntry < 1) {
      adjustedScore += 0.1;
      reasoningPoints.push("Recent entry increases confidence");
    } else if (hoursSinceEntry > 24) {
      adjustedScore -= 0.05;
      reasoningPoints.push("Older entry slightly reduces confidence");
    }

    return adjustedScore;
  }

  /**
   * Generate suggested tags based on entry analysis
   */
  private generateSuggestedTags(entry: CheckpointEntry, entryType: EntryType): string[] {
    const tags: string[] = [];
    const description = entry.description.toLowerCase();

    // Add type-based tags
    const pattern = this.patterns.find(p => p.type === entryType);
    if (pattern?.tags) {
      tags.push(...pattern.tags);
    }

    // Technology detection
    const technologies = [
      { names: ['typescript', 'ts'], tag: 'typescript' },
      { names: ['javascript', 'js'], tag: 'javascript' },
      { names: ['python', 'py'], tag: 'python' },
      { names: ['rust', 'cargo'], tag: 'rust' },
      { names: ['react', 'jsx', 'tsx'], tag: 'react' },
      { names: ['node', 'npm', 'bun'], tag: 'nodejs' },
      { names: ['git', 'commit', 'merge'], tag: 'git' },
      { names: ['database', 'sql', 'sqlite'], tag: 'database' },
      { names: ['api', 'endpoint', 'rest'], tag: 'api' },
      { names: ['test', 'testing', 'spec'], tag: 'testing' },
    ];

    for (const tech of technologies) {
      if (tech.names.some(name => description.includes(name))) {
        tags.push(tech.tag);
      }
    }

    // Activity detection
    const activities = [
      { patterns: ['bug', 'fix', 'error', 'issue'], tag: 'bug-fix' },
      { patterns: ['feature', 'new', 'add'], tag: 'feature' },
      { patterns: ['refactor', 'cleanup', 'improve'], tag: 'refactoring' },
      { patterns: ['performance', 'optimize', 'speed'], tag: 'performance' },
      { patterns: ['security', 'auth', 'secure'], tag: 'security' },
      { patterns: ['deploy', 'release', 'publish'], tag: 'deployment' },
    ];

    for (const activity of activities) {
      if (activity.patterns.some(pattern => description.includes(pattern))) {
        tags.push(activity.tag);
      }
    }

    // Priority detection
    if (/\b(urgent|critical|important|priority|asap)\b/i.test(description)) {
      tags.push('high-priority');
    }

    return [...new Set(tags)]; // Remove duplicates
  }

  /**
   * Batch classify multiple entries
   */
  classifyBatch(entries: CheckpointEntry[]): Map<string, ClassificationResult> {
    const results = new Map<string, ClassificationResult>();

    for (const entry of entries) {
      if (entry.id) {
        results.set(entry.id, this.classify(entry));
      }
    }

    return results;
  }

  /**
   * Get quality score for an entry (combination of confidence and content richness)
   */
  getQualityScore(entry: CheckpointEntry): number {
    const classification = this.classify(entry);
    let qualityScore = classification.confidenceScore;

    // Boost quality for high-value entry types
    if (classification.entryType === 'completion') {
      qualityScore += 0.1;
    } else if (classification.entryType === 'session-marker') {
      qualityScore -= 0.1; // Session markers are less valuable for recall
    }

    // Content richness bonus
    const wordCount = entry.description.split(/\s+/).length;
    if (wordCount > 10) {
      qualityScore += Math.min(0.1, wordCount / 100);
    }

    return Math.max(0.0, Math.min(1.0, qualityScore));
  }
}

// Export singleton instance
export const entryClassifier = new EntryClassifier();