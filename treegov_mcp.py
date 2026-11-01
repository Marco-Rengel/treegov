"""Entry point for the TreeGov MCP server.

Runs the server over stdio, keeping all data local.
"""
import sys

# TODO(zona_gris): el import es eager y requiere el SDK oficial (extra
# "mcp"); el diseño de la apertura (audit_log 01/11/2026) pedía
# "manejo del ImportError del SDK" (import lazy). Si el usuario corre
# `treegov-mcp` sin instalar treegov[mcp], verá un traceback crudo de
# ModuleNotFoundError. El asistente estratégico decide en el siguiente
# turno: (a) mantener eager, (b) try/except ImportError con mensaje que
# sugiera `pip install treegov[mcp]`.
from mcp_v3.server import app


def main() -> None:
    """Run the FastMCP server."""
    # Nota: FastMCP se encarga de redirigir los logs al stderr por defecto
    # para no contaminar el stdout (canal del protocolo JSON-RPC).
    app.run()


if __name__ == "__main__":
    main()
