from starlette.responses import JSONResponse, Response
from starlette.requests import Request
from starlette.routing import Route
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from .core import mcp
from api.telemetry import configure_telemetry
from api.auth_utils import verify_auth_header
from tasks.agent_orchestrator import AgentOrchestrator
from .tools import feeds, issues, search, staleness, users, agent_configs, annotations  # noqa: F401
from version import get_version_string
import logging
import os  # Added for env vars
import redis  # Added for Redis client
import threading
import uvicorn
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

logger = logging.getLogger(__name__)

_metrics_started = False

# --- Auth Middleware ---
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Exempt health
        if request.url.path in ["/health"]:
            return await call_next(request)
        
        auth_header = request.headers.get("Authorization")
        success, error_msg, _ = verify_auth_header(auth_header)
        
        if not success:
            return JSONResponse({"error": error_msg}, status_code=401)
            
        return await call_next(request)

# Print version info
logger.info(f"{get_version_string()} starting...")

# Get the ASGI app
app = mcp.sse_app() if hasattr(mcp, "sse_app") else mcp.asgi_app()

# Add Auth Middleware
app.add_middleware(AuthMiddleware)

# Initialize Telemetry
configure_telemetry(app, "moirai-mcp")


def _build_metrics_app() -> Starlette:
    async def metrics_endpoint(request: Request) -> Response:
        data = generate_latest(REGISTRY)
        return Response(data, media_type=CONTENT_TYPE_LATEST)

    return Starlette(routes=[Route("/metrics", metrics_endpoint)])


def _run_metrics_server(metrics_host: str, metrics_port: int) -> None:
    metrics_app = _build_metrics_app()
    config = uvicorn.Config(metrics_app, host=metrics_host, port=metrics_port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def start_metrics_server() -> None:
    global _metrics_started
    if _metrics_started:
        return

    metrics_enabled = os.environ.get("METRICS_ENABLED", "true").lower() in ("1", "true", "yes")
    if not metrics_enabled:
        logger.info("Metrics server disabled by METRICS_ENABLED.")
        return

    metrics_host = os.environ.get("METRICS_HOST", "0.0.0.0")
    try:
        metrics_port = int(os.environ.get("METRICS_PORT", "9000"))
    except ValueError:
        logger.error("Invalid METRICS_PORT value; expected integer.")
        return

    thread = threading.Thread(
        target=_run_metrics_server,
        args=(metrics_host, metrics_port),
        daemon=True,
        name="metrics-server",
    )
    thread.start()
    _metrics_started = True
    logger.info("Metrics server started on %s:%s", metrics_host, metrics_port)


if hasattr(app, "add_event_handler"):
    app.add_event_handler("startup", start_metrics_server)
else:
    start_metrics_server()

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
try:
    agent_orchestrator = AgentOrchestrator(interval=60, redis_client=redis_client) # Pass redis_client
    agent_orchestrator.mcp_client = mcp  # Assign mcp client
    agent_orchestrator.daemon = True  # Allow main program to exit even if thread is running
    agent_orchestrator.start()
    logger.info("Agent Orchestrator thread started.")
except Exception as orchestrator_err:
    logger.error(f"Failed to start Agent Orchestrator: {orchestrator_err}")


async def health_check(request: Request) -> JSONResponse:  # Moved definition here
    return JSONResponse({"status": "ok", "version": get_version_string()})


# Add routes directly
app.routes.append(Route("/health", health_check))
