#!/usr/bin/env python3
"""
Migration script to move Tusk data from old structure to new .coa/tusk structure.

This script moves:
- data/default/* → .coa/tusk/data/*
- logs/* → .coa/tusk/logs/*

Run this script from the project root directory.
"""

import shutil
import sys
from pathlib import Path


def migrate_tusk_data():
    """Migrate Tusk data to the new .coa/tusk structure."""
    
    print("🚀 Starting Tusk data migration to .coa/tusk structure...")
    
    # Define paths
    project_root = Path.cwd()
    old_data_dir = project_root / "data" / "default"
    old_logs_dir = project_root / "logs"
    
    new_base_dir = project_root / ".coa" / "tusk"
    new_data_dir = new_base_dir / "data"
    new_logs_dir = new_base_dir / "logs"
    
    # Check if old structure exists
    has_old_data = old_data_dir.exists()
    has_old_logs = old_logs_dir.exists()
    
    if not has_old_data and not has_old_logs:
        print("✅ No old data structure found - nothing to migrate.")
        return True
    
    print(f"📁 Found data to migrate:")
    if has_old_data:
        print(f"   - Data: {old_data_dir}")
    if has_old_logs:
        print(f"   - Logs: {old_logs_dir}")
    
    # Create new directory structure
    print(f"📂 Creating new directory structure at {new_base_dir}")
    new_base_dir.mkdir(parents=True, exist_ok=True)
    new_data_dir.mkdir(parents=True, exist_ok=True)
    new_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Migrate data
    if has_old_data:
        print(f"📦 Migrating data from {old_data_dir} to {new_data_dir}")
        
        # Copy all subdirectories and files from data/default/ to .coa/tusk/data/
        for item in old_data_dir.iterdir():
            if item.is_dir():
                dest_dir = new_data_dir / item.name
                if dest_dir.exists():
                    print(f"   ⚠️  Directory {dest_dir} already exists, merging contents...")
                    # Merge directories
                    _merge_directories(item, dest_dir)
                else:
                    print(f"   📁 Copying {item.name}/")
                    shutil.copytree(item, dest_dir)
            else:
                dest_file = new_data_dir / item.name
                if dest_file.exists():
                    print(f"   ⚠️  File {dest_file} already exists, skipping...")
                else:
                    print(f"   📄 Copying {item.name}")
                    shutil.copy2(item, dest_file)
    
    # Migrate logs
    if has_old_logs:
        print(f"📋 Migrating logs from {old_logs_dir} to {new_logs_dir}")
        
        # Copy all log files
        for item in old_logs_dir.iterdir():
            if item.is_file():
                dest_file = new_logs_dir / item.name
                if dest_file.exists():
                    print(f"   ⚠️  Log file {dest_file} already exists, skipping...")
                else:
                    print(f"   📄 Copying {item.name}")
                    shutil.copy2(item, dest_file)
    
    print("✅ Migration completed successfully!")
    print(f"📍 New data location: {new_data_dir}")
    print(f"📍 New logs location: {new_logs_dir}")
    
    # Ask about cleanup (only if running interactively)
    if sys.stdin.isatty():
        print("\n🧹 Clean up old directories?")
        print("   This will remove the old data/ and logs/ directories.")
        print("   Make sure to backup important data first!")
        
        try:
            cleanup = input("   Remove old directories? (y/N): ").lower().strip()
            if cleanup in ('y', 'yes'):
                _cleanup_old_directories(old_data_dir.parent, old_logs_dir)
            else:
                print("   Old directories kept. You can remove them manually later.")
        except EOFError:
            print("   Old directories kept (non-interactive mode).")
    else:
        print("\n   Old directories kept. Run interactively to clean up automatically,")
        print("   or remove them manually: data/ and logs/")
    
    return True


def _merge_directories(src_dir: Path, dest_dir: Path):
    """Merge contents of src_dir into dest_dir."""
    for item in src_dir.iterdir():
        if item.is_dir():
            dest_subdir = dest_dir / item.name
            if dest_subdir.exists():
                _merge_directories(item, dest_subdir)
            else:
                shutil.copytree(item, dest_subdir)
        else:
            dest_file = dest_dir / item.name
            if not dest_file.exists():
                shutil.copy2(item, dest_file)


def _cleanup_old_directories(data_parent_dir: Path, logs_dir: Path):
    """Remove old data and logs directories."""
    try:
        if data_parent_dir.exists() and data_parent_dir.name == "data":
            print(f"   🗑️  Removing {data_parent_dir}")
            shutil.rmtree(data_parent_dir)
        
        if logs_dir.exists() and logs_dir.name == "logs":
            print(f"   🗑️  Removing {logs_dir}")
            shutil.rmtree(logs_dir)
        
        print("   ✅ Old directories removed successfully!")
        
    except Exception as e:
        print(f"   ❌ Error removing old directories: {e}")
        print("   You may need to remove them manually.")


def main():
    """Main entry point."""
    try:
        # Check if we're in a project directory
        if not Path.cwd().name:
            print("❌ Could not determine current directory")
            sys.exit(1)
        
        print(f"📍 Working in: {Path.cwd()}")
        
        success = migrate_tusk_data()
        
        if success:
            print("\n🎉 Migration completed! Tusk is now using the new .coa/tusk structure.")
            print("   You can now run Tusk and it will use the migrated data.")
        else:
            print("\n❌ Migration failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Migration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()