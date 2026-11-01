"""Entry point for the TreeGov MCP server.

Runs the server over stdio, keeping all data local.
"""


def main() -> None:
    """Run the FastMCP server."""
    try:
        from mcp_v3.server import app
    except ImportError:
        import sys
        print("Error: El SDK de MCP no está instalado. Ejecuta: pip install treegov[mcp]", file=sys.stderr)
        sys.exit(1)
    app.run()


if __name__ == "__main__":
    main()
