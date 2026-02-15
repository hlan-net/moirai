from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from .core import mcp
from api.telemetry import configure_telemetry
from tasks.agent_orchestrator import AgentOrchestrator
import logging
import os # Added for env vars
import redis # Added for Redis client

logger = logging.getLogger(__name__)

# Get the ASGI app
app = mcp.sse_app() if hasattr(mcp, "sse_app") else mcp.asgi_app()

# Initialize Telemetry
configure_telemetry(app, "moirai-mcp")

# --- Redis Client Setup ---
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)
    redis_client.ping() # Test connection
    logger.info("Connected to Redis successfully.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}")
    redis_client = None # Ensure it's None if connection fails
# --- End Redis Client Setup ---

# Initialize and start the Agent Orchestrator
# Pass the mcp client so it can make tool calls
agent_orchestrator = AgentOrchestrator(interval=60, redis_client=redis_client) # Pass redis_client
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
