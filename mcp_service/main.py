from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from .core import mcp

# Import tools to register them with the MCP server
# The side-effect of importing is that the @mcp.tool decorators run
from .tools import events
from .tools import trends
from .tools import search
from .tools import users
from .tools import feeds
from .tools import agent_configs # Import the new agent_configs tools
from .tools import staleness # Import the new staleness tools

# Get the ASGI app
app = mcp.sse_app() if hasattr(mcp, "sse_app") else mcp.asgi_app()

# Initialize Telemetry
from api.telemetry import configure_telemetry
configure_telemetry(app, "moirai-mcp")

# --- Agent Orchestrator Setup ---
from tasks.agent_orchestrator import AgentOrchestrator
import logging
logger = logging.getLogger(__name__)

# Initialize and start the Agent Orchestrator
# Pass the mcp client so it can make tool calls
agent_orchestrator = AgentOrchestrator(interval=60) # Check agents every 60 seconds
agent_orchestrator.mcp_client = mcp # Assign mcp client
agent_orchestrator.daemon = True # Allow main program to exit even if thread is running
agent_orchestrator.start()
logger.info("Agent Orchestrator thread started.")
# --- End Agent Orchestrator Setup ---

async def health_check(request):
    return JSONResponse({"status": "ok"})

async def metrics_endpoint(request):
    # Simple metrics endpoint without PrometheusMiddleware
    return Response("# Placeholder metrics endpoint\n", media_type="text/plain")

# Add routes directly
app.routes.append(Route("/health", health_check))
app.routes.append(Route("/metrics", metrics_endpoint))
