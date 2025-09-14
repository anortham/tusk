# Tusk Development Scripts

Automated scripts for maintaining code quality and preventing pipeline failures.

## Quick Start

**Before committing changes:**

```bash
# Windows PowerShell
.\scripts\pre-commit.ps1

# Linux/Mac/Git Bash
./scripts/pre-commit.sh
```

## Individual Scripts

### `fix-code.py`
Automatically fixes common code quality issues:
- Black formatting
- Ruff linting (auto-fixable issues)

```bash
python scripts/fix-code.py
```

### `check-code.py`
Runs all quality checks (same as Azure Pipeline):
- Black formatting check
- Ruff linting
- MyPy type checking
- Pytest with coverage

```bash
python scripts/check-code.py
```

## Why Use These Scripts?

**Problem:** Azure DevOps pipeline fails with formatting/linting errors after pushing code.

**Solution:** Run these scripts locally before committing to catch and fix issues early.

**Workflow:**
1. Make code changes
2. Run `python scripts/fix-code.py` (optional - auto-fixes what it can)
3. Run `python scripts/check-code.py` (required - must pass)
4. Commit and push (pipeline should succeed)

## Integration with Git Hooks

To automatically run checks before every commit:

```bash
# Create git pre-commit hook
cp scripts/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Now checks run automatically whenever you `git commit`.