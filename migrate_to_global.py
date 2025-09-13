#!/usr/bin/env python3
"""Migration utility to move from local project storage to global storage.

This script helps migrate existing Tusk data from project-specific .coa/tusk/data
directories to the new global storage at ~/.coa/tusk/data.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tusk.config import TuskConfig
from tusk.models import Checkpoint, Todo, Plan


class TuskMigration:
    """Handles migration from local to global storage."""
    
    def __init__(self):
        self.global_config = TuskConfig(storage_mode="global")
        self.global_data_dir = self.global_config.get_data_dir()
        self.projects_found: List[Dict] = []
        self.migration_log: List[str] = []
    
    def log(self, message: str) -> None:
        """Add message to migration log."""
        self.migration_log.append(message)
        print(f"[MIGRATE] {message}")
    
    def find_local_installations(self, search_paths: Optional[List[str]] = None) -> List[Dict]:
        """Find existing local Tusk installations."""
        if search_paths is None:
            # Common places to look for projects
            search_paths = [
                str(Path.home() / "Projects"),
                str(Path.home() / "Code"), 
                str(Path.home() / "Documents"),
                str(Path.cwd().parent),  # Parent of current directory
                str(Path.cwd()),  # Current directory
            ]
        
        installations = []
        
        for search_path in search_paths:
            search_dir = Path(search_path)
            if not search_dir.exists():
                continue
                
            self.log(f"Searching for Tusk data in: {search_dir}")
            
            # Look for .coa/tusk/data directories
            for project_dir in search_dir.rglob("*"):
                if not project_dir.is_dir():
                    continue
                    
                tusk_data = project_dir / ".coa" / "tusk" / "data"
                if tusk_data.exists():
                    # Check if it has actual data
                    has_data = any([
                        (tusk_data / "checkpoints").exists() and list((tusk_data / "checkpoints").rglob("*.json")),
                        (tusk_data / "todos").exists() and list((tusk_data / "todos").rglob("*.json")),
                        (tusk_data / "plans").exists() and list((tusk_data / "plans").rglob("*.json")),
                    ])
                    
                    if has_data:
                        installations.append({
                            "project_path": str(project_dir),
                            "project_name": project_dir.name,
                            "data_path": str(tusk_data),
                            "estimated_items": self._count_items(tusk_data)
                        })
                        self.log(f"Found Tusk data in: {project_dir}")
        
        return installations
    
    def _count_items(self, data_dir: Path) -> Dict[str, int]:
        """Count items in a data directory."""
        counts = {"checkpoints": 0, "todos": 0, "plans": 0}
        
        for item_type in counts.keys():
            type_dir = data_dir / item_type
            if type_dir.exists():
                counts[item_type] = len(list(type_dir.rglob("*.json")))
        
        return counts
    
    def migrate_project(self, installation: Dict, dry_run: bool = False) -> bool:
        """Migrate a single project's data to global storage."""
        project_path = installation["project_path"]
        project_name = installation["project_name"]
        data_path = Path(installation["data_path"])
        
        self.log(f"Migrating project: {project_name} ({project_path})")
        
        if dry_run:
            self.log("DRY RUN: Would migrate the following:")
            for item_type, count in installation["estimated_items"].items():
                if count > 0:
                    self.log(f"  - {count} {item_type}")
            return True
        
        try:
            # Ensure global directories exist
            self.global_config.ensure_directories()
            
            # Migrate each type of data
            success = True
            for item_type in ["checkpoints", "todos", "plans"]:
                type_success = self._migrate_items(
                    data_path / item_type,
                    item_type,
                    project_name,
                    project_path
                )
                success = success and type_success
            
            # Update project registry
            if success:
                self._register_project(project_path, project_name)
                self.log(f"✅ Successfully migrated {project_name}")
            else:
                self.log(f"❌ Failed to migrate {project_name}")
            
            return success
            
        except Exception as e:
            self.log(f"❌ Error migrating {project_name}: {e}")
            return False
    
    def _migrate_items(self, source_dir: Path, item_type: str, project_name: str, project_path: str) -> bool:
        """Migrate items of a specific type."""
        if not source_dir.exists():
            return True  # No items to migrate
        
        target_dir = self.global_data_dir / item_type
        migrated_count = 0
        
        for json_file in source_dir.rglob("*.json"):
            try:
                # Load the item and update project fields
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Add project tracking fields if missing
                if "project_id" not in data:
                    data["project_id"] = project_name
                if "project_path" not in data:
                    data["project_path"] = project_path
                
                # Determine target file path
                if item_type == "checkpoints":
                    # Preserve date-based directory structure
                    relative_path = json_file.relative_to(source_dir)
                    target_file = target_dir / relative_path
                else:
                    # todos and plans use flat structure
                    target_file = target_dir / json_file.name
                
                # Ensure target directory exists
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Write updated data
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
                migrated_count += 1
                
            except Exception as e:
                self.log(f"Warning: Failed to migrate {json_file}: {e}")
                continue
        
        if migrated_count > 0:
            self.log(f"  Migrated {migrated_count} {item_type}")
        
        return True
    
    def _register_project(self, project_path: str, project_name: str) -> None:
        """Register the project in the global registry."""
        registry = self.global_config.load_projects_registry()
        registry[project_path] = project_name
        self.global_config.save_projects_registry(registry)
        self.log(f"  Registered project in global registry")
    
    def backup_local_data(self, installation: Dict) -> bool:
        """Create a backup of local data before migration."""
        data_path = Path(installation["data_path"])
        backup_path = data_path.parent / f"tusk_backup_{installation['project_name']}"
        
        try:
            if backup_path.exists():
                shutil.rmtree(backup_path)
            
            shutil.copytree(data_path, backup_path)
            self.log(f"  Created backup at: {backup_path}")
            return True
            
        except Exception as e:
            self.log(f"Warning: Failed to create backup: {e}")
            return False
    
    def cleanup_local_data(self, installation: Dict, confirm: bool = False) -> bool:
        """Remove local data after successful migration."""
        if not confirm:
            self.log("Skipping cleanup (not confirmed)")
            return False
        
        data_path = Path(installation["data_path"])
        
        try:
            shutil.rmtree(data_path)
            self.log(f"  Cleaned up local data: {data_path}")
            
            # Also remove empty parent directories if they're empty
            coa_dir = data_path.parent.parent  # .coa directory
            if coa_dir.exists() and not any(coa_dir.iterdir()):
                coa_dir.rmdir()
                self.log(f"  Removed empty .coa directory: {coa_dir}")
            
            return True
            
        except Exception as e:
            self.log(f"Warning: Failed to cleanup local data: {e}")
            return False
    
    def run_interactive_migration(self) -> None:
        """Run an interactive migration process."""
        print("🔄 Tusk Migration Utility")
        print("=" * 50)
        print("This utility will help you migrate from local project storage")
        print("to global storage at ~/.coa/tusk/")
        print()
        
        # Find installations
        print("🔍 Searching for existing Tusk installations...")
        installations = self.find_local_installations()
        
        if not installations:
            print("❌ No local Tusk installations found.")
            print("Your data may already be in global storage, or you haven't used Tusk yet.")
            return
        
        print(f"✅ Found {len(installations)} installation(s):")
        print()
        
        for i, installation in enumerate(installations, 1):
            print(f"{i}. Project: {installation['project_name']}")
            print(f"   Path: {installation['project_path']}")
            items = installation['estimated_items']
            print(f"   Data: {items['checkpoints']} checkpoints, {items['todos']} todos, {items['plans']} plans")
            print()
        
        # Ask what to do
        print("Options:")
        print("1. Migrate all projects")
        print("2. Select specific projects")
        print("3. Dry run (preview migration)")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            self._migrate_all(installations)
        elif choice == "2":
            self._migrate_selected(installations)
        elif choice == "3":
            self._dry_run(installations)
        elif choice == "4":
            print("Migration cancelled.")
        else:
            print("Invalid choice.")
    
    def _migrate_all(self, installations: List[Dict]) -> None:
        """Migrate all found installations."""
        print(f"\n🚀 Migrating {len(installations)} project(s)...")
        
        backup = input("Create backups before migration? (y/N): ").strip().lower() == 'y'
        cleanup = input("Remove local data after migration? (y/N): ").strip().lower() == 'y'
        
        for installation in installations:
            if backup:
                self.backup_local_data(installation)
            
            success = self.migrate_project(installation)
            
            if success and cleanup:
                confirm = input(f"Remove local data for {installation['project_name']}? (y/N): ").strip().lower() == 'y'
                self.cleanup_local_data(installation, confirm)
        
        print("\n✅ Migration complete!")
        print(f"Global storage location: {self.global_data_dir}")
    
    def _migrate_selected(self, installations: List[Dict]) -> None:
        """Migrate selected installations."""
        print("\nSelect projects to migrate (comma-separated numbers):")
        selection = input("Projects: ").strip()
        
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected = [installations[i] for i in indices if 0 <= i < len(installations)]
            
            if selected:
                self._migrate_all(selected)
            else:
                print("No valid projects selected.")
                
        except ValueError:
            print("Invalid selection format.")
    
    def _dry_run(self, installations: List[Dict]) -> None:
        """Preview what would be migrated."""
        print("\n🔍 DRY RUN - Preview of migration:")
        print("=" * 40)
        
        for installation in installations:
            self.migrate_project(installation, dry_run=True)
            print()
        
        print("✅ Dry run complete. No changes were made.")


def main():
    """Main entry point."""
    migration = TuskMigration()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Automatic migration for CI/scripts
        installations = migration.find_local_installations()
        if installations:
            print(f"Found {len(installations)} installations to migrate")
            for installation in installations:
                migration.migrate_project(installation)
        else:
            print("No installations found to migrate")
    else:
        # Interactive migration
        migration.run_interactive_migration()


if __name__ == "__main__":
    main()