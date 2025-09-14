#!/usr/bin/env python3
"""
Automated code quality checks script for Tusk.

Runs all the same checks that Azure DevOps pipeline runs:
- Black formatting
- Ruff linting
- MyPy type checking
- Pytest with coverage

Run this before committing to catch issues locally.
"""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\nCHECKING: {description}")
    print(f"   Running: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,  # Run from project root
        )

        if result.returncode == 0:
            print(f"   PASS: {description}")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"   FAIL: {description} (exit code {result.returncode})")
            if result.stdout.strip():
                print(f"   STDOUT: {result.stdout.strip()}")
            if result.stderr.strip():
                print(f"   STDERR: {result.stderr.strip()}")
            return False

    except FileNotFoundError as e:
        print(f"   ERROR: {description} failed - command not found: {e}")
        return False
    except Exception as e:
        print(f"   ERROR: {description} failed with error: {e}")
        return False


def main():
    """Run all code quality checks."""
    print("Running Tusk code quality checks...")
    print("This runs the same checks as Azure DevOps pipeline")

    checks = [
        # Black formatting check
        (
            ["python", "-m", "black", "--check", "src", "tests"],
            "Black formatting check"
        ),

        # Ruff linting
        (
            ["python", "-m", "ruff", "check", "src", "tests"],
            "Ruff linting"
        ),

        # MyPy type checking
        (
            ["python", "-m", "mypy", "src"],
            "MyPy type checking"
        ),

        # Pytest with coverage
        (
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "--cov=src", "--cov-report=term-missing"],
            "Pytest with coverage"
        ),
    ]

    failed_checks = []

    for command, description in checks:
        if not run_command(command, description):
            failed_checks.append(description)

    print(f"\n{'='*60}")

    if failed_checks:
        print("FAILED: Some checks failed:")
        for check in failed_checks:
            print(f"   - {check}")
        print("\nFix the issues above before committing to avoid pipeline failures.")
        sys.exit(1)
    else:
        print("SUCCESS: All checks passed! Safe to commit.")
        sys.exit(0)


if __name__ == "__main__":
    main()