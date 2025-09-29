/**
 * Enhanced Relevance Scoring for Sophisticated Hook Data
 *
 * Intelligently prioritizes context based on:
 * - Context type (insights > commits > prompts > completions)
 * - Hook source awareness
 * - Rich metadata from enhanced hooks
 * - Query context adaptation
 * - Adaptive content length management
 */

import type { CheckpointEntry } from "../core/types.js";

// ===== CONTEXT TYPE PRIORITIZATION MATRIX =====

interface ContextType {
  type: string;
  priority: number;
  baseWeight: number;
  maxTokens: number;
  description: string;
}

const CONTEXT_TYPES: Record<string, ContextType> = {
  'claude-insight': {
    type: 'claude-insight',
    priority: 10,
    baseWeight: 1.0,
    maxTokens: 200,
    description: 'Claude discoveries and explanations'
  },
  'bug-fix': {
    type: 'bug-fix',
    priority: 9,
    baseWeight: 0.95,
    maxTokens: 150,
    description: 'Critical bug fixes and resolutions'
  },
  'git-commit': {
    type: 'git-commit',
    priority: 8,
    baseWeight: 0.9,
    maxTokens: 100,
    description: 'Development milestones and commits'
  },
  'feature-development': {
    type: 'feature-development',
    priority: 7,
    baseWeight: 0.85,
    maxTokens: 150,
    description: 'New feature implementation'
  },
  'refactoring': {
    type: 'refactoring',
    priority: 6,
    baseWeight: 0.8,
    maxTokens: 120,
    description: 'Architecture and code improvements'
  },
  'security': {
    type: 'security',
    priority: 9,
    baseWeight: 0.92,
    maxTokens: 140,
    description: 'Security-related work'
  },
  'performance': {
    type: 'performance',
    priority: 7,
    baseWeight: 0.83,
    maxTokens: 130,
    description: 'Performance optimizations'
  },
  'user-request': {
    type: 'user-request',
    priority: 5,
    baseWeight: 0.7,
    maxTokens: 100,
    description: 'User prompts and requests'
  },
  'session-start': {
    type: 'session-start',
    priority: 3,
    baseWeight: 0.5,
    maxTokens: 50,
    description: 'Session initialization context'
  },
  'work-completion': {
    type: 'work-completion',
    priority: 6,
    baseWeight: 0.75,
    maxTokens: 120,
    description: 'Completed work summaries'
  }
};

// ===== ENHANCED RELEVANCE FACTORS =====

interface EnhancedRelevanceWeights {
  contextType: number;        // Weight for context type priority
  hookSource: number;         // Weight for hook source intelligence
  richTags: number;          // Weight for sophisticated tag analysis
  recency: number;           // Time-based relevance
  workContinuity: number;    // Relevance to current work context
  uniqueness: number;        // Penalty for redundant information
}

const DEFAULT_ENHANCED_WEIGHTS: EnhancedRelevanceWeights = {
  contextType: 0.4,    // High weight - context type is crucial
  hookSource: 0.2,     // Moderate weight - source matters
  richTags: 0.15,      // Rich metadata analysis
  recency: 0.15,       // Time still matters but less dominant
  workContinuity: 0.08, // Bonus for related work
  uniqueness: 0.02     // Small penalty for duplicates
};

/**
 * Detect context type from entry tags and description
 */
function detectContextType(entry: CheckpointEntry): ContextType {
  const tags = entry.tags || [];
  const description = entry.description.toLowerCase();

  // Check explicit context type tags first
  for (const tag of tags) {
    if (CONTEXT_TYPES[tag]) {
      return CONTEXT_TYPES[tag]!;
    }
  }

  // Pattern-based detection for legacy entries
  if (description.includes('claude insight') || description.includes('claude discovery')) {
    return CONTEXT_TYPES['claude-insight']!;
  }
  if (description.includes('git commit')) {
    return CONTEXT_TYPES['git-commit']!;
  }
  if (description.includes('user request') || description.includes('user:')) {
    return CONTEXT_TYPES['user-request']!;
  }
  if (description.includes('work completed') || description.includes('completed:')) {
    return CONTEXT_TYPES['work-completion']!;
  }

  // Default to generic context
  return {
    type: 'general',
    priority: 4,
    baseWeight: 0.6,
    maxTokens: 100,
    description: 'General development context'
  };
}

/**
 * Analyze rich tags for intelligence factors
 */
function analyzeRichTags(entry: CheckpointEntry): {
  complexityScore: number;
  priorityScore: number;
  technologyRelevance: number;
} {
  const tags = entry.tags || [];
  let complexityScore = 0;
  let priorityScore = 0;
  let technologyRelevance = 0;

  for (const tag of tags) {
    // Complexity scoring
    if (tag.startsWith('complexity-')) {
      const level = parseInt(tag.split('-')[1] || '0');
      complexityScore = Math.max(complexityScore, level / 5); // Normalize to 0-1
    }

    // Priority scoring
    if (tag.startsWith('priority-')) {
      const level = parseInt(tag.split('-')[1] || '0');
      priorityScore = Math.max(priorityScore, level / 4); // Normalize to 0-1
    }

    // Technology relevance
    if (tag.startsWith('tech-')) {
      technologyRelevance += 0.2; // Bonus for each technology
    }

    // Special insight types
    if (['discovery', 'diagnosis', 'solution', 'architecture'].includes(tag)) {
      complexityScore += 0.3;
    }
  }

  return {
    complexityScore: Math.min(1, complexityScore),
    priorityScore: Math.min(1, priorityScore),
    technologyRelevance: Math.min(1, technologyRelevance)
  };
}

/**
 * Calculate work continuity score based on current context
 */
function calculateWorkContinuity(entry: CheckpointEntry, currentContext?: {
  activeProject?: string;
  recentTechnologies?: string[];
  currentWorkType?: string;
}): number {
  if (!currentContext) return 0;

  let continuityScore = 0;

  // Project continuity
  if (currentContext.activeProject && entry.project === currentContext.activeProject) {
    continuityScore += 0.4;
  }

  // Technology continuity
  if (currentContext.recentTechnologies) {
    const entryTags = entry.tags || [];
    const techMatches = currentContext.recentTechnologies.filter(tech =>
      entryTags.some(tag => tag.includes(tech))
    );
    continuityScore += Math.min(0.3, techMatches.length * 0.1);
  }

  // Work type continuity
  if (currentContext.currentWorkType) {
    const entryTags = entry.tags || [];
    if (entryTags.includes(currentContext.currentWorkType)) {
      continuityScore += 0.3;
    }
  }

  return Math.min(1, continuityScore);
}

/**
 * Enhanced relevance scoring with context-type awareness
 */
export function calculateEnhancedRelevanceScore(
  entry: CheckpointEntry,
  weights: EnhancedRelevanceWeights = DEFAULT_ENHANCED_WEIGHTS,
  currentContext?: any,
  referenceDate: Date = new Date()
): number {
  // 1. Context Type Score (most important factor)
  const contextType = detectContextType(entry);
  const contextTypeScore = contextType.baseWeight;

  // 2. Hook Source Intelligence Score
  const entryTags = entry.tags || [];
  let hookSourceScore = 0.5; // Default

  if (entryTags.includes('claude-insight')) hookSourceScore = 1.0;
  else if (entryTags.includes('git-commit')) hookSourceScore = 0.9;
  else if (entryTags.includes('user-request')) hookSourceScore = 0.7;
  else if (entryTags.includes('session-start')) hookSourceScore = 0.3;

  // 3. Rich Tags Analysis
  const tagAnalysis = analyzeRichTags(entry);
  const richTagsScore = (
    tagAnalysis.complexityScore * 0.4 +
    tagAnalysis.priorityScore * 0.4 +
    tagAnalysis.technologyRelevance * 0.2
  );

  // 4. Recency Score (exponential decay but less dominant)
  const entryDate = new Date(entry.timestamp);
  const daysDiff = (referenceDate.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24);
  const recencyScore = Math.exp(-daysDiff / 10); // Slower decay than original

  // 5. Work Continuity Score
  const continuityScore = calculateWorkContinuity(entry, currentContext);

  // 6. Uniqueness Score (penalty for consolidation)
  const uniquenessScore = entry.consolidationInfo
    ? Math.max(0.2, 1 - (entry.consolidationInfo.mergedEntries - 1) * 0.15)
    : 1.0;

  // Calculate weighted total
  const totalScore = (
    contextTypeScore * weights.contextType +
    hookSourceScore * weights.hookSource +
    richTagsScore * weights.richTags +
    recencyScore * weights.recency +
    continuityScore * weights.workContinuity +
    uniquenessScore * weights.uniqueness
  );

  return Math.min(1, totalScore);
}

/**
 * Intelligent context grouping by type and relevance
 */
export function groupContextByIntelligence(entries: CheckpointEntry[]): {
  criticalInsights: CheckpointEntry[];
  recentMilestones: CheckpointEntry[];
  currentWork: CheckpointEntry[];
  background: CheckpointEntry[];
} {
  const scoredEntries = entries.map(entry => ({
    entry,
    contextType: detectContextType(entry),
    score: calculateEnhancedRelevanceScore(entry)
  }));

  const criticalInsights = scoredEntries
    .filter(item => ['claude-insight', 'discovery', 'solution'].includes(item.contextType.type))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(item => item.entry);

  const recentMilestones = scoredEntries
    .filter(item => ['git-commit', 'feature-development', 'bug-fix'].includes(item.contextType.type))
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
    .map(item => item.entry);

  const currentWork = scoredEntries
    .filter(item => item.score > 0.7 && !criticalInsights.includes(item.entry) && !recentMilestones.includes(item.entry))
    .sort((a, b) => b.score - a.score)
    .slice(0, 10)
    .map(item => item.entry);

  const background = scoredEntries
    .filter(item => !criticalInsights.includes(item.entry) && !recentMilestones.includes(item.entry) && !currentWork.includes(item.entry))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(item => item.entry);

  return { criticalInsights, recentMilestones, currentWork, background };
}

/**
 * Adaptive context length management
 */
export function manageContextLength(entries: CheckpointEntry[], maxTokens: number = 4000): {
  entries: CheckpointEntry[];
  summary: string;
  tokensUsed: number;
} {
  const grouped = groupContextByIntelligence(entries);
  let tokensUsed = 0;
  const selectedEntries: CheckpointEntry[] = [];

  // Reserve tokens for each section
  const tokenAllocation = {
    criticalInsights: Math.floor(maxTokens * 0.4),    // 40% for insights
    recentMilestones: Math.floor(maxTokens * 0.3),    // 30% for milestones
    currentWork: Math.floor(maxTokens * 0.25),        // 25% for current work
    background: Math.floor(maxTokens * 0.05)          // 5% for background
  };

  // Add entries within token limits
  function addEntriesWithinLimit(entries: CheckpointEntry[], limit: number): number {
    let used = 0;
    for (const entry of entries) {
      const contextType = detectContextType(entry);
      const estimatedTokens = Math.min(contextType.maxTokens, entry.description.length / 4);

      if (used + estimatedTokens <= limit) {
        selectedEntries.push(entry);
        used += estimatedTokens;
      } else {
        break;
      }
    }
    return used;
  }

  tokensUsed += addEntriesWithinLimit(grouped.criticalInsights, tokenAllocation.criticalInsights);
  tokensUsed += addEntriesWithinLimit(grouped.recentMilestones, tokenAllocation.recentMilestones);
  tokensUsed += addEntriesWithinLimit(grouped.currentWork, tokenAllocation.currentWork);
  tokensUsed += addEntriesWithinLimit(grouped.background, tokenAllocation.background);

  const summary = generateIntelligentSummary(grouped, selectedEntries.length, entries.length);

  return { entries: selectedEntries, summary, tokensUsed };
}

/**
 * Generate intelligent summary of context selection
 */
function generateIntelligentSummary(grouped: ReturnType<typeof groupContextByIntelligence>, selected: number, total: number): string {
  const insights = grouped.criticalInsights.length;
  const milestones = grouped.recentMilestones.length;
  const current = grouped.currentWork.length;

  return `Selected ${selected}/${total} entries: ${insights} insights, ${milestones} milestones, ${current} current work items`;
}