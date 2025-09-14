"""Test all enhanced tools to verify parameter descriptions."""

import json
from src.tusk.tools.enhanced_simple import EnhancedUnifiedTaskTool
from src.tusk.tools.enhanced_all import (
    EnhancedUnifiedCheckpointTool,
    EnhancedUnifiedRecallTool,
    EnhancedUnifiedPlanTool,
    EnhancedUnifiedStandupTool
)
from src.tusk.config import TuskConfig
from src.tusk.storage import CheckpointStorage, PlanStorage, SearchEngine, TaskStorage
from fastmcp import FastMCP

class MockServer:
    """Mock server to test all enhanced tools."""

    def __init__(self):
        config = TuskConfig.from_env()
        config.ensure_directories()

        self.config = config
        self.checkpoint_storage = CheckpointStorage(config)
        self.task_storage = TaskStorage(config)
        self.plan_storage = PlanStorage(config)
        self.search_engine = SearchEngine(config)

        # Create FastMCP instance
        self.mcp = FastMCP(name="TestAllEnhanced")

def test_tool_parameters(tool_name, tool_instance, server):
    """Test parameter enhancement for a specific tool."""
    print(f"\n=== Testing {tool_name} Tool ===")

    # Register the tool
    tool_instance.register(server.mcp)

    # Check if tool was registered
    if hasattr(server.mcp, '_tool_manager') and hasattr(server.mcp._tool_manager, '_tools'):
        tools = server.mcp._tool_manager._tools
        if tool_name in tools:
            tool = tools[tool_name]
            print(f"[OK] {tool_name} tool found")

            # Check parameters schema
            if hasattr(tool, 'parameters') and 'properties' in tool.parameters:
                params = tool.parameters['properties']
                print(f"[PARAMS] Found {len(params)} parameters:")

                enhanced_count = 0
                for param_name, param_info in params.items():
                    if 'description' in param_info:
                        enhanced_count += 1
                        # Show first 100 chars of description
                        desc_preview = param_info['description'][:100]
                        if len(param_info['description']) > 100:
                            desc_preview += "..."
                        print(f"  - {param_name}: {desc_preview}")
                    else:
                        print(f"  - {param_name}: [NO DESCRIPTION]")

                print(f"[RESULT] {enhanced_count}/{len(params)} parameters have descriptions")

                # Check tool description
                if hasattr(tool, 'description'):
                    desc_lines = tool.description.count('\n') + 1
                    print(f"[DESC] Tool has {desc_lines}-line description")
                else:
                    print("[ERROR] Tool has no description")

                return enhanced_count == len(params)
            else:
                print("[ERROR] Tool has no parameters schema")
                return False
        else:
            print(f"[ERROR] {tool_name} tool not found in registry")
            return False
    else:
        print("[ERROR] FastMCP tool manager not accessible")
        return False

def main():
    """Test all enhanced tools."""
    print("Testing all enhanced tools for parameter descriptions...")

    server = MockServer()

    # Test all enhanced tools
    tools_to_test = [
        ("task", EnhancedUnifiedTaskTool(server)),
        ("checkpoint", EnhancedUnifiedCheckpointTool(server)),
        ("recall", EnhancedUnifiedRecallTool(server)),
        ("plan", EnhancedUnifiedPlanTool(server)),
        ("standup", EnhancedUnifiedStandupTool(server))
    ]

    results = {}
    for tool_name, tool_instance in tools_to_test:
        try:
            results[tool_name] = test_tool_parameters(tool_name, tool_instance, server)
        except Exception as e:
            print(f"[ERROR] Testing {tool_name} failed: {e}")
            results[tool_name] = False

    # Summary
    print(f"\n=== SUMMARY ===")
    successful_tools = sum(1 for success in results.values() if success)
    total_tools = len(results)

    for tool_name, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {tool_name}")

    print(f"\n[OVERALL] {successful_tools}/{total_tools} tools successfully enhanced")

    if successful_tools == total_tools:
        print("[SUCCESS] All tools have rich parameter descriptions!")
    else:
        print("[PARTIAL] Some tools need attention")

if __name__ == "__main__":
    main()