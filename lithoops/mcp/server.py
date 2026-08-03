"""MCP server exposing LithoOps read-only data tools.

Uses the official MCP Python SDK (MCPServer, the high-level API) over stdio.
Any MCP-compatible client (Claude Desktop, IDEs, custom agents) can connect
and call the same five read-only tools the local agents use. Exposing data
this way -- rather than raw file/database access -- makes access explicit,
auditable and safe.

Run:  python -m lithoops.mcp.server
"""
from __future__ import annotations

from mcp.server import MCPServer

from lithoops.mcp import registry

app = MCPServer("lithoops-ai")


def _register_tools() -> None:
    """Register every read-only registry tool with the MCP server."""
    for spec in registry.list_tools():
        name = spec["name"]
        fn = registry.TOOLS[name]["fn"]
        app.add_tool(fn, name=name, description=spec["description"])


_register_tools()


def main() -> None:
    app.run()  # defaults to stdio transport


if __name__ == "__main__":
    main()
