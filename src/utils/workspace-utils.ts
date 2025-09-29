/**
 * Workspace Detection and Management Utilities for Tusk Journal System
 * Functions for detecting workspace context and managing workspace information
 */

import { existsSync, readFileSync, realpathSync } from "fs";
import { join, normalize, resolve, dirname, basename } from "path";
import { createHash } from "crypto";
import type { WorkspaceInfo } from "../core/types.js";

/**
 * Detect workspace context using git root, package.json, or cwd
 */
export function detectWorkspace(cwd: string): WorkspaceInfo {
  const normalizedCwd = normalizePath(cwd);

  // Try to find git repository root
  const gitRoot = findGitRoot(normalizedCwd);
  if (gitRoot) {
    return {
      workspaceId: hashPath(gitRoot),
      workspacePath: gitRoot,
      workspaceName: basename(gitRoot),
      detectionMethod: 'git',
    };
  }

  // Try to find package.json directory
  const packageRoot = findPackageRoot(normalizedCwd);
  if (packageRoot) {
    const packageName = getPackageName(packageRoot);
    return {
      workspaceId: hashPath(packageRoot),
      workspacePath: packageRoot,
      workspaceName: packageName || basename(packageRoot),
      detectionMethod: 'package',
    };
  }

  // Fall back to current working directory
  return {
    workspaceId: hashPath(normalizedCwd),
    workspacePath: normalizedCwd,
    workspaceName: basename(normalizedCwd),
    detectionMethod: 'cwd',
  };
}

/**
 * Find git repository root by walking up the directory tree
 */
export function findGitRoot(startPath: string): string | null {
  let currentPath = startPath;

  while (currentPath !== dirname(currentPath)) {
    const gitPath = join(currentPath, '.git');
    if (existsSync(gitPath)) {
      return normalizePath(currentPath);
    }
    currentPath = dirname(currentPath);
  }

  return null;
}

/**
 * Find package.json directory by walking up the directory tree
 */
export function findPackageRoot(startPath: string): string | null {
  let currentPath = startPath;

  while (currentPath !== dirname(currentPath)) {
    const packagePath = join(currentPath, 'package.json');
    if (existsSync(packagePath)) {
      return normalizePath(currentPath);
    }
    currentPath = dirname(currentPath);
  }

  return null;
}

/**
 * Get package name from package.json
 */
export function getPackageName(packageRoot: string): string | null {
  try {
    const packagePath = join(packageRoot, 'package.json');
    const packageContent = readFileSync(packagePath, 'utf-8');
    const packageJson = JSON.parse(packageContent);
    return packageJson.name || null;
  } catch {
    return null;
  }
}

/**
 * Normalize path for cross-platform consistency
 */
export function normalizePath(path: string): string {
  // Check if it's already an absolute path (Windows or Unix)
  const isWindowsAbsolute = /^[A-Za-z]:[\\\/]/.test(path);
  const isUnixAbsolute = path.startsWith('/');
  const isUncPath = path.startsWith('\\\\') || path.startsWith('//');

  let resolved: string;

  if (isWindowsAbsolute || isUnixAbsolute || isUncPath) {
    // Already absolute, just normalize
    resolved = normalize(path);
  } else {
    // Relative path, resolve against cwd
    resolved = resolve(path);
  }

  // Resolve symlinks for consistent workspace detection
  try {
    if (existsSync(resolved)) {
      // Use realpathSync to properly resolve all symlinks in the path
      resolved = realpathSync(resolved);
    }
    // On macOS, normalize /private/var to /var for consistency
    if (process.platform === 'darwin' && resolved.startsWith('/private/var/')) {
      resolved = resolved.replace('/private/var/', '/var/');
    }
  } catch {
    // If we can't resolve the path, just use the resolved version
  }

  // Always use forward slashes for consistency
  return resolved.replace(/\\/g, '/');
}

/**
 * Create consistent hash for a path (case-insensitive on Windows)
 */
export function hashPath(path: string): string {
  const normalized = normalizePath(path);
  // Make case-insensitive on Windows
  const forHashing = process.platform === 'win32' ? normalized.toLowerCase() : normalized;
  return createHash('sha256')
    .update(forHashing)
    .digest('hex')
    .slice(0, 12);
}

/**
 * Normalize file paths in arrays for cross-platform storage
 */
export function normalizePaths(paths: string[], workspacePath: string): string[] {
  return paths.map(path => {
    const normalizedPath = normalizePath(path);
    // Convert absolute paths to relative paths from workspace root
    if (normalizedPath.startsWith(workspacePath)) {
      return normalizedPath.substring(workspacePath.length + 1); // +1 to remove leading slash
    }
    return normalizedPath;
  });
}