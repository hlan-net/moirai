from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from .core import mcp

# Import tools to register them with the MCP server
# The side-effect of importing is that the @mcp.tool decorators run
from .tools import events
from .tools import trends
from .tools import search

# Get the ASGI app
app = mcp.sse_app() if hasattr(mcp, "sse_app") else mcp.asgi_app()

# Initialize Telemetry
from api.telemetry import configure_telemetry
configure_telemetry(app, "moirai-mcp")

async def health_check(request):
    return JSONResponse({"status": "ok"})

async def metrics_endpoint(request):
    # Simple metrics endpoint without PrometheusMiddleware
    return Response("# Placeholder metrics endpoint\n", media_type="text/plain")

# Add routes directly
app.routes.append(Route("/health", health_check))
app.routes.append(Route("/metrics", metrics_endpoint))
