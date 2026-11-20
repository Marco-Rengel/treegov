"""Entry point for the TreeGov MCP server.

Runs the server over stdio, keeping all data local.
"""

from __future__ import annotations

from backend_v3.import_guard import install_import_guard

install_import_guard()


def main() -> None:
    """Install the white-box import guard and run the FastMCP server."""
    install_import_guard()
    try:
        from mcp_v3.server import app
    except ImportError:
        import sys
        print(
            "Error: El SDK de MCP no está instalado. "
            "Ejecuta: pip install treegov[mcp]",
            file=sys.stderr,
        )
        sys.exit(1)
    app.run()


if __name__ == "__main__":
    main()
