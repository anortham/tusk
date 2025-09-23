# Makefile for tusk-bun project
# Provides convenient shortcuts for common development tasks

.PHONY: help install test test-unit test-integration test-quick test-coverage test-watch clean setup benchmark validate lint type-check ci-test dev start

# Default target
help: ## Show this help message
	@echo "tusk-bun development commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make install     # Install dependencies"
	@echo "  make test        # Run all tests"
	@echo "  make test-quick  # Run quick subset of tests"
	@echo "  make benchmark   # Run performance benchmarks"
	@echo "  make dev         # Start development server"

# Installation and setup
install: ## Install dependencies
	bun install

setup: ## Setup development environment
	bun run test:setup --verbose

clean: ## Clean build artifacts and test results
	bun run test:clean
	rm -rf node_modules/.cache
	rm -rf .bun-cache

# Development
dev: ## Start development server with hot reload
	bun run dev

start: ## Start the MCP server
	bun run start

# Testing
test: ## Run all tests
	bun test

test-unit: ## Run unit tests only
	bun run test:unit

test-integration: ## Run integration tests only
	bun run test:integration

test-quick: ## Run quick subset of tests
	bun run test:quick

test-coverage: ## Run tests with coverage report
	bun run test:coverage

test-watch: ## Run tests in watch mode
	bun run test:watch

test-performance: ## Run performance tests with extended timeout
	bun run test:performance

test-debug: ## Run tests with verbose output and bail on first failure
	bun run test:debug

# Advanced test runners
test-runner: ## Run advanced test runner (specify suite with SUITE=name)
	bun run tests/scripts/test-runner.ts --suite $(or $(SUITE),unit) --verbose

benchmark: ## Run performance benchmarks
	bun run test:benchmark

# Code quality
validate: ## Run full validation (tests + lint + type-check)
	bun run validate

lint: ## Run linter
	bun run lint

type-check: ## Run TypeScript type checking
	bun run type-check

# CI/CD
ci-test: ## Run tests in CI mode
	bun run test:ci

ci-full: ## Run full CI validation
	make install
	make setup
	make validate
	make benchmark

# Project commands
checkpoint: ## Create a checkpoint (usage: make checkpoint MSG="your message")
	bun run checkpoint "$(MSG)"

recall: ## Recall recent entries (usage: make recall DAYS=7)
	bun run recall --days $(or $(DAYS),7)

standup: ## Generate standup report (usage: make standup STYLE=meeting)
	bun run standup --style $(or $(STYLE),meeting)

# Maintenance
update: ## Update dependencies
	bun update

audit: ## Run security audit
	bun audit

# Docker (if needed)
docker-build: ## Build Docker image
	docker build -t tusk-bun .

docker-test: ## Run tests in Docker
	docker run --rm tusk-bun make test

# Documentation
docs: ## Generate documentation (placeholder)
	@echo "📚 Documentation generation not yet implemented"
	@echo "Available documentation:"
	@echo "  - README.md"
	@echo "  - CLAUDE.md (development guide)"
	@echo "  - tests/contracts/ (test specifications)"

# Environment info
info: ## Show environment information
	@echo "Environment Information:"
	@echo "  Bun version: $(shell bun --version 2>/dev/null || echo 'not installed')"
	@echo "  Node version: $(shell node --version 2>/dev/null || echo 'not installed')"
	@echo "  Platform: $(shell uname -s) $(shell uname -m)"
	@echo "  Working directory: $(shell pwd)"
	@echo "  Git branch: $(shell git branch --show-current 2>/dev/null || echo 'not a git repo')"
	@echo "  Git status: $(shell git status --porcelain 2>/dev/null | wc -l | xargs echo) modified files"

# Quick actions for common workflows
quick-test: setup test-quick ## Setup environment and run quick tests

full-test: setup test-coverage benchmark ## Setup environment and run comprehensive tests

dev-setup: install setup ## Complete development setup for new contributors

ci-check: clean install setup validate ## Simulate CI environment locally