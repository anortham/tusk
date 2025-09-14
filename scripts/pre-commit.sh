#!/bin/bash
# Bash pre-commit script for Linux/Mac
# Run this before committing to catch issues locally

echo "🚀 Running pre-commit checks..."

# Change to project root
cd "$(dirname "$0")/.."

# Run the automated checks
python scripts/check-code.py

exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "💡 Tip: Run 'python scripts/fix-code.py' to automatically fix common issues"
fi

exit $exit_code