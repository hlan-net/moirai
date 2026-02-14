from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from .core import mcp
from api.telemetry import configure_telemetry  # Moved to top
from tasks.agent_orchestrator import AgentOrchestrator  # Moved to top
import logging  # Moved to top

logger = logging.getLogger(__name__)  # Moved this here

# Get the ASGI app
app = mcp.sse_app() if hasattr(mcp, "sse_app") else mcp.asgi_app()

# Initialize Telemetry
configure_telemetry(app, "moirai-mcp")

# Initialize and start the Agent Orchestrator
# Pass the mcp client so it can make tool calls
agent_orchestrator = AgentOrchestrator(interval=60)  # Check agents every 60 seconds
agent_orchestrator.mcp_client = mcp  # Assign mcp client
agent_orchestrator.daemon = True  # Allow main program to exit even if thread is running
agent_orchestrator.start()
logger.info("Agent Orchestrator thread started.")


async def health_check(request):  # Moved definition here
    return JSONResponse({"status": "ok"})


async def metrics_endpoint(request):  # Moved definition here
    # Simple metrics endpoint without PrometheusMiddleware
    return Response("# Placeholder metrics endpoint\n", media_type="text/plain")


# Add routes directly
app.routes.append(Route("/health", health_check))
app.routes.append(Route("/metrics", metrics_endpoint))
