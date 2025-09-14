#!/usr/bin/env python3
"""
Automated code fixing script for Tusk.

Runs automatic fixes for common code quality issues:
- Black formatting (auto-fix)
- Ruff linting (auto-fix what it can)

Run this before running check-code.py to automatically fix common issues.
"""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\nRUNNING: {description}")
    print(f"   Command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,  # Run from project root
        )

        print(f"   Exit code: {result.returncode}")
        if result.stdout.strip():
            print(f"   Output: {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"   Warnings: {result.stderr.strip()}")

        return result.returncode == 0

    except FileNotFoundError as e:
        print(f"   ERROR: {description} failed - command not found: {e}")
        return False
    except Exception as e:
        print(f"   ERROR: {description} failed with error: {e}")
        return False


def main():
    """Run all automatic code fixes."""
    print("Running Tusk automatic code fixes...")
    print("This will automatically fix formatting and linting issues")

    fixes = [
        # Black auto-formatting
        (
            ["python", "-m", "black", "src", "tests"],
            "Black auto-formatting"
        ),

        # Ruff auto-fix
        (
            ["python", "-m", "ruff", "check", "src", "tests", "--fix"],
            "Ruff auto-fix"
        ),

        # Ruff auto-fix with unsafe fixes
        (
            ["python", "-m", "ruff", "check", "src", "tests", "--fix", "--unsafe-fixes"],
            "Ruff auto-fix (unsafe)"
        ),
    ]

    for command, description in fixes:
        run_command(command, description)

    print(f"\n{'='*60}")
    print("SUCCESS: Automatic fixes completed!")
    print("Run 'python scripts/check-code.py' to verify all checks pass")


if __name__ == "__main__":
    main()