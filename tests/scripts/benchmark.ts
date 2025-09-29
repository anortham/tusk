#!/usr/bin/env bun
/**
 * Benchmark Script for tusk-bun Performance Testing
 * Measures performance across different scenarios and operations
 */

import { performance } from "perf_hooks";
import { join } from "path";
import { existsSync, mkdirSync, writeFileSync } from "fs";
import { tmpdir } from "os";

import { saveEntry, getRecentEntries, getJournalStats } from "../../src/utils/journal.js";
import { generateStandup } from "../../src/reports/standup.js";
import { TestDataFactory, TestEnvironment, TEST_CONFIG } from "../setup.js";

interface BenchmarkResult {
  name: string;
  description: string;
  duration: number;
  memoryUsed: number;
  operationsPerSecond: number;
  success: boolean;
  error?: string;
  metadata?: Record<string, any>;
}

interface BenchmarkSuite {
  name: string;
  results: BenchmarkResult[];
  totalDuration: number;
  averageMemoryUsage: number;
  successRate: number;
}

class PerformanceBenchmark {
  private results: BenchmarkResult[] = [];
  private suites: BenchmarkSuite[] = [];

  async runAllBenchmarks(): Promise<void> {
    console.log("🏃‍♂️ Starting tusk-bun performance benchmarks...\n");

    await this.runJournalBenchmarks();
    await this.runStandupBenchmarks();
    await this.runScalabilityBenchmarks();
    await this.runConcurrencyBenchmarks();
    await this.runMemoryBenchmarks();

    this.generateReport();
  }

  private async runJournalBenchmarks(): Promise<void> {
    console.log("📝 Running journal operation benchmarks...");
    const suiteResults: BenchmarkResult[] = [];

    // Benchmark: Single entry append
    suiteResults.push(await this.benchmark(
      "journal-single-append",
      "Single journal entry append operation",
      async () => {
        const entry = TestDataFactory.createJournalEntry({
          description: "Benchmark test entry",
        });
        await saveEntry(entry);
      }
    ));

    // Benchmark: Batch entry append
    suiteResults.push(await this.benchmark(
      "journal-batch-append",
      "Batch append 100 journal entries",
      async () => {
        const entries = TestDataFactory.createMultipleEntries(100);
        for (const entry of entries) {
          await saveEntry(entry);
        }
      }
    ));

    // Benchmark: Recent entries retrieval
    suiteResults.push(await this.benchmark(
      "journal-recent-retrieval",
      "Retrieve recent entries from populated journal",
      async () => {
        await getRecentEntries({ days: 7 });
      }
    ));

    // Benchmark: Journal statistics
    suiteResults.push(await this.benchmark(
      "journal-stats",
      "Calculate journal statistics",
      async () => {
        await getJournalStats();
      }
    ));

    this.addSuite("Journal Operations", suiteResults);
    console.log(`   Completed ${suiteResults.length} journal benchmarks\n`);
  }

  private async runStandupBenchmarks(): Promise<void> {
    console.log("📊 Running standup generation benchmarks...");
    const suiteResults: BenchmarkResult[] = [];

    // Setup test data for standup benchmarks
    const standupEntries = TestDataFactory.createMultipleEntries(50, {
      project: "benchmark-project",
    });
    for (const entry of standupEntries) {
      await saveEntry(entry);
    }

    // Benchmark each standup style
    const styles = ["meeting", "written", "executive", "metrics"] as const;
    for (const style of styles) {
      suiteResults.push(await this.benchmark(
        `standup-${style}`,
        `Generate ${style} style standup report`,
        async () => {
          await generateStandup({
            style,
            days: 7,
            includeMetrics: true,
            includeFiles: true,
          });
        }
      ));
    }

    // Benchmark standup with large dataset
    const largeDataset = TestDataFactory.createMultipleEntries(500);
    for (const entry of largeDataset) {
      await saveEntry(entry);
    }

    suiteResults.push(await this.benchmark(
      "standup-large-dataset",
      "Generate standup with 550+ entries",
      async () => {
        await generateStandup({
          style: "metrics",
          days: 30,
          includeMetrics: true,
        });
      }
    ));

    this.addSuite("Standup Generation", suiteResults);
    console.log(`   Completed ${suiteResults.length} standup benchmarks\n`);
  }

  private async runScalabilityBenchmarks(): Promise<void> {
    console.log("📈 Running scalability benchmarks...");
    const suiteResults: BenchmarkResult[] = [];

    // Test different data sizes
    const dataSizes = [10, 100, 500, 1000];

    for (const size of dataSizes) {
      // Clean environment for each test
      TestEnvironment.cleanup();
      TestEnvironment.setup();

      suiteResults.push(await this.benchmark(
        `scalability-${size}`,
        `End-to-end workflow with ${size} entries`,
        async () => {
          // Create and store entries
          const entries = TestDataFactory.createMultipleEntries(size);
          for (const entry of entries) {
            await saveEntry(entry);
          }

          // Retrieve and process
          await getRecentEntries({ days: 30 });
          await getJournalStats();
          await generateStandup({ style: "executive", days: 30 });
        }
      ));
    }

    this.addSuite("Scalability", suiteResults);
    console.log(`   Completed ${suiteResults.length} scalability benchmarks\n`);
  }

  private async runConcurrencyBenchmarks(): Promise<void> {
    console.log("🔀 Running concurrency benchmarks...");
    const suiteResults: BenchmarkResult[] = [];

    // Benchmark concurrent writes
    suiteResults.push(await this.benchmark(
      "concurrent-writes",
      "10 concurrent journal write operations",
      async () => {
        const writePromises = Array.from({ length: 10 }, (_, i) => {
          const entry = TestDataFactory.createJournalEntry({
            description: `Concurrent entry ${i}`,
          });
          return saveEntry(entry);
        });
        await Promise.all(writePromises);
      }
    ));

    // Benchmark concurrent reads
    suiteResults.push(await this.benchmark(
      "concurrent-reads",
      "10 concurrent journal read operations",
      async () => {
        const readPromises = Array.from({ length: 10 }, () => getRecentEntries({ days: 1 }));
        await Promise.all(readPromises);
      }
    ));

    // Benchmark mixed concurrent operations
    suiteResults.push(await this.benchmark(
      "concurrent-mixed",
      "Mixed concurrent read/write/standup operations",
      async () => {
        const operations = [
          () => saveEntry(TestDataFactory.createJournalEntry()),
          () => getRecentEntries({ days: 1 }),
          () => generateStandup({ style: "meeting", days: 1 }),
          () => getJournalStats(),
        ];

        const promises = Array.from({ length: 8 }, (_, i) => operations[i % operations.length]?.());
        await Promise.all(promises);
      }
    ));

    this.addSuite("Concurrency", suiteResults);
    console.log(`   Completed ${suiteResults.length} concurrency benchmarks\n`);
  }

  private async runMemoryBenchmarks(): Promise<void> {
    console.log("🧠 Running memory usage benchmarks...");
    const suiteResults: BenchmarkResult[] = [];

    // Benchmark memory usage with large datasets
    suiteResults.push(await this.benchmark(
      "memory-large-dataset",
      "Memory usage with 1000 entries",
      async () => {
        const entries = TestDataFactory.createMultipleEntries(1000);
        for (const entry of entries) {
          await saveEntry(entry);
        }
        await generateStandup({ style: "metrics", days: 30, includeMetrics: true });
      }
    ));

    // Benchmark memory cleanup
    suiteResults.push(await this.benchmark(
      "memory-cleanup",
      "Memory cleanup after operations",
      async () => {
        // Create large dataset
        const entries = TestDataFactory.createMultipleEntries(500);
        for (const entry of entries) {
          await saveEntry(entry);
        }

        // Perform multiple operations
        await getRecentEntries({ days: 30 });
        await generateStandup({ style: "executive", days: 30 });
        await getJournalStats();

        // Force cleanup if available
        if (global.gc) {
          global.gc();
        }
      }
    ));

    this.addSuite("Memory Usage", suiteResults);
    console.log(`   Completed ${suiteResults.length} memory benchmarks\n`);
  }

  private async benchmark(
    name: string,
    description: string,
    operation: () => Promise<void>
  ): Promise<BenchmarkResult> {
    // Prepare environment
    TestEnvironment.setup();

    let success = true;
    let error: string | undefined;
    let memoryBefore = 0;
    let memoryAfter = 0;

    try {
      // Force garbage collection if available
      if (global.gc) {
        global.gc();
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      memoryBefore = process.memoryUsage().heapUsed;
      const startTime = performance.now();

      await operation();

      const endTime = performance.now();
      memoryAfter = process.memoryUsage().heapUsed;

      const duration = endTime - startTime;
      const memoryUsed = Math.max(0, memoryAfter - memoryBefore);
      const operationsPerSecond = 1000 / duration;

      return {
        name,
        description,
        duration,
        memoryUsed,
        operationsPerSecond,
        success,
        metadata: {
          memoryBefore,
          memoryAfter,
          timestamp: new Date().toISOString(),
        },
      };
    } catch (err) {
      success = false;
      error = err instanceof Error ? err.message : String(err);

      return {
        name,
        description,
        duration: 0,
        memoryUsed: 0,
        operationsPerSecond: 0,
        success,
        error,
      };
    } finally {
      TestEnvironment.cleanup();
    }
  }

  private addSuite(name: string, results: BenchmarkResult[]): void {
    const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);
    const averageMemoryUsage = results.reduce((sum, r) => sum + r.memoryUsed, 0) / results.length;
    const successRate = results.filter(r => r.success).length / results.length;

    this.suites.push({
      name,
      results,
      totalDuration,
      averageMemoryUsage,
      successRate,
    });

    this.results.push(...results);
  }

  private generateReport(): void {
    console.log("📊 Performance Benchmark Report");
    console.log("================================\n");

    // Overall summary
    const totalDuration = this.results.reduce((sum, r) => sum + r.duration, 0);
    const averageMemoryUsage = this.results.reduce((sum, r) => sum + r.memoryUsed, 0) / this.results.length;
    const overallSuccessRate = this.results.filter(r => r.success).length / this.results.length;

    console.log("📈 Overall Performance Summary:");
    console.log(`   Total Benchmarks: ${this.results.length}`);
    console.log(`   Total Duration: ${totalDuration.toFixed(2)}ms`);
    console.log(`   Average Memory Usage: ${this.formatBytes(averageMemoryUsage)}`);
    console.log(`   Success Rate: ${(overallSuccessRate * 100).toFixed(1)}%`);
    console.log(`   Bun Version: ${Bun.version}`);
    console.log(`   Platform: ${process.platform} ${process.arch}\n`);

    // Suite summaries
    for (const suite of this.suites) {
      console.log(`🏷️  ${suite.name} Suite:`);
      console.log(`   Duration: ${suite.totalDuration.toFixed(2)}ms`);
      console.log(`   Avg Memory: ${this.formatBytes(suite.averageMemoryUsage)}`);
      console.log(`   Success Rate: ${(suite.successRate * 100).toFixed(1)}%`);

      for (const result of suite.results) {
        const status = result.success ? "✅" : "❌";
        const duration = result.duration.toFixed(2);
        const memory = this.formatBytes(result.memoryUsed);
        const ops = result.operationsPerSecond.toFixed(2);

        console.log(`   ${status} ${result.name}: ${duration}ms, ${memory}, ${ops} ops/sec`);
        if (result.error) {
          console.log(`      Error: ${result.error}`);
        }
      }
      console.log();
    }

    // Performance analysis
    this.analyzePerformance();

    // Save detailed results
    this.saveResults();
  }

  private analyzePerformance(): void {
    console.log("🔍 Performance Analysis:");

    // Find slowest operations
    const slowest = [...this.results]
      .filter(r => r.success)
      .sort((a, b) => b.duration - a.duration)
      .slice(0, 3);

    console.log("   Slowest Operations:");
    for (const op of slowest) {
      console.log(`   - ${op.name}: ${op.duration.toFixed(2)}ms`);
    }

    // Find memory-intensive operations
    const memoryIntensive = [...this.results]
      .filter(r => r.success)
      .sort((a, b) => b.memoryUsed - a.memoryUsed)
      .slice(0, 3);

    console.log("   Most Memory-Intensive:");
    for (const op of memoryIntensive) {
      console.log(`   - ${op.name}: ${this.formatBytes(op.memoryUsed)}`);
    }

    // Check for performance regressions
    const performanceThresholds = {
      "journal-single-append": 50, // 50ms
      "standup-meeting": 200, // 200ms
      "journal-stats": 100, // 100ms
    };

    console.log("   Performance Threshold Analysis:");
    for (const [benchmarkName, threshold] of Object.entries(performanceThresholds)) {
      const result = this.results.find(r => r.name === benchmarkName);
      if (result && result.success) {
        const status = result.duration <= threshold ? "✅" : "⚠️";
        console.log(`   ${status} ${benchmarkName}: ${result.duration.toFixed(2)}ms (threshold: ${threshold}ms)`);
      }
    }

    console.log();
  }

  private saveResults(): void {
    const reportDir = "test-results";
    if (!existsSync(reportDir)) {
      mkdirSync(reportDir, { recursive: true });
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `benchmark-${timestamp}.json`;
    const filepath = join(reportDir, filename);

    const report = {
      timestamp: new Date().toISOString(),
      bunVersion: Bun.version,
      platform: `${process.platform} ${process.arch}`,
      nodeVersion: process.version,
      suites: this.suites,
      summary: {
        totalBenchmarks: this.results.length,
        totalDuration: this.results.reduce((sum, r) => sum + r.duration, 0),
        averageMemoryUsage: this.results.reduce((sum, r) => sum + r.memoryUsed, 0) / this.results.length,
        successRate: this.results.filter(r => r.success).length / this.results.length,
      },
    };

    writeFileSync(filepath, JSON.stringify(report, null, 2));
    console.log(`💾 Detailed results saved to: ${filepath}`);
  }

  private formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2);

  if (args.includes("--help") || args.includes("-h")) {
    console.log(`
Performance Benchmark Script

Usage: bun run tests/scripts/benchmark.ts [options]

Options:
  --help, -h      Show this help message

Examples:
  bun run test:benchmark
  bun run tests/scripts/benchmark.ts
`);
    process.exit(0);
  }

  try {
    const benchmark = new PerformanceBenchmark();
    await benchmark.runAllBenchmarks();
  } catch (error) {
    console.error("❌ Benchmark failed:", error);
    process.exit(1);
  }
}

// Run if this script is executed directly
if (import.meta.main) {
  main();
}

export { PerformanceBenchmark };