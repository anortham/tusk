"""Enhanced base tool with automatic docstring parameter enhancement."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import inspect
import docstring_parser
from fastmcp.utilities.logging import get_logger

if TYPE_CHECKING:
    from ..server import TuskServer

logger = get_logger(__name__)


class EnhancedBaseTool(ABC):
    """Base class for enhanced Tusk memory tools with rich parameter descriptions."""

    def __init__(self, server: "TuskServer"):
        self.server = server
        self.config = server.config
        self.checkpoint_storage = server.checkpoint_storage
        self.todo_storage = server.todo_storage
        self.plan_storage = server.plan_storage
        self.search_engine = server.search_engine

    @abstractmethod
    def register(self, mcp_server) -> None:
        """Register this tool's functions with the MCP server."""
        pass

    def get_current_workspace(self) -> str:
        """Get the current workspace ID (deprecated - returns empty string)."""
        return ""

    def enhance_registered_tools(self, mcp_server, tool_names: list[str]) -> None:
        """
        Enhance registered tools with rich parameter descriptions from docstrings.

        Call this after registering tools to add docstring-based parameter descriptions.
        """
        if not hasattr(mcp_server, '_tool_manager') or not hasattr(mcp_server._tool_manager, '_tools'):
            logger.warning("Cannot enhance tools: FastMCP server structure not as expected")
            return

        enhanced_count = 0
        for tool_name in tool_names:
            if tool_name in mcp_server._tool_manager._tools:
                tool = mcp_server._tool_manager._tools[tool_name]

                try:
                    # Get the original function that was registered
                    original_func = tool.fn if hasattr(tool, 'fn') else None
                    if not original_func:
                        continue

                    # Enhance parameter schema
                    if hasattr(tool, 'parameters'):
                        enhanced_params = self._enhance_parameter_schema(original_func, tool.parameters)
                        if enhanced_params != tool.parameters:
                            tool.parameters = enhanced_params
                            enhanced_count += 1
                            logger.debug(f"Enhanced parameters for tool: {tool_name}")

                    # Enhance description
                    if hasattr(tool, 'description'):
                        enhanced_desc = self._enhance_description(original_func, tool.description or "")
                        if enhanced_desc != tool.description:
                            tool.description = enhanced_desc
                            logger.debug(f"Enhanced description for tool: {tool_name}")

                except Exception as e:
                    logger.warning(f"Failed to enhance tool {tool_name}: {e}")
                    continue

        if enhanced_count > 0:
            logger.info(f"Enhanced {enhanced_count} tools with rich parameter descriptions")

    def _enhance_parameter_schema(self, func, existing_schema: dict) -> dict:
        """Enhance parameter schema with docstring descriptions."""
        try:
            # Get the function's docstring
            docstring = inspect.getdoc(func)
            if not docstring:
                return existing_schema

            # Parse the docstring
            parsed_doc = docstring_parser.parse(docstring)
            if not parsed_doc.params:
                return existing_schema

            # Create parameter description mapping
            param_descriptions = {param.arg_name: param for param in parsed_doc.params}

            # Create enhanced schema
            enhanced_schema = existing_schema.copy()
            if "properties" in enhanced_schema:
                for param_name, param_props in enhanced_schema["properties"].items():
                    if param_name in param_descriptions:
                        doc_param = param_descriptions[param_name]
                        if doc_param.description:
                            # Clean and format description
                            description = doc_param.description.strip().strip('.')
                            if description:
                                description = description[0].upper() + description[1:] + '.'
                                # Create new dict to avoid modifying original
                                new_props = param_props.copy()
                                new_props["description"] = description
                                enhanced_schema["properties"] = enhanced_schema["properties"].copy()
                                enhanced_schema["properties"][param_name] = new_props

            return enhanced_schema

        except Exception as e:
            logger.warning(f"Failed to enhance parameters for {func.__name__}: {e}")
            return existing_schema

    def _enhance_description(self, func, existing_description: str) -> str:
        """Enhance tool description with return information from docstring."""
        try:
            # Get the function's docstring
            docstring = inspect.getdoc(func)
            if not docstring:
                return existing_description

            # Parse the docstring
            parsed_doc = docstring_parser.parse(docstring)

            # Start with existing description
            enhanced_description = existing_description.strip().strip('.')
            if enhanced_description:
                enhanced_description += '.'

            # Add return description if available
            if parsed_doc.returns and parsed_doc.returns.description:
                return_desc = parsed_doc.returns.description.strip().strip('.')
                if return_desc:
                    prefix = " " if enhanced_description else ""
                    enhanced_description = f"{enhanced_description}{prefix}Returns {return_desc}."

            return enhanced_description

        except Exception as e:
            logger.warning(f"Failed to enhance description for {func.__name__}: {e}")
            return existing_description