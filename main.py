import os
import sys  # Moved to top
from flask import Flask, send_from_directory, jsonify
from flask_wtf import CSRFProtect
from api.extensions import limiter, metrics
from api.routes import api_blueprint
from api.mcp_routes import mcp_blueprint
from api.chat_routes import chat_blueprint
from api.auth import auth_blueprint, JWT_SECRET_KEY  # Import JWT_SECRET_KEY
from api.agent_routes import agent_blueprint
from api.userspace_routes import userspace_blueprint
from api.session_routes import session_blueprint
from api.telemetry import configure_telemetry  # Moved to top

from tasks.scheduler import scheduler
from tasks import init
from tasks.enrichment_worker import worker  # Moved to top
from version import get_version_string

app = Flask(__name__, static_folder="ui/dist")
# Configure app using update mapping to decouple from literal key assignments where possible
app.config.update(
    SECRET_KEY=os.environ.get("APP_SECRET_KEY") or JWT_SECRET_KEY
)

# Initialize Telemetry
# Don't configure telemetry if running in a test environment
is_test_mode = (
    "pytest" in sys.modules
    or "unittest" in sys.modules
    or os.environ.get("FLASK_ENV") == "test"
    or os.environ.get("TESTING") == "true"
)

if not is_test_mode:
    configure_telemetry(app, "moirai-api")

# CSRF protection is enabled for web security.
# It is only disabled in test mode or if explicitly requested via environment variable.
# Note: API endpoints using JWT authentication don't need CSRF protection
# as the Authorization header isn't automatically sent by browsers like cookies are.
csrf = CSRFProtect()
csrf.init_app(app)

# Exempt API routes from CSRF — these endpoints authenticate via JWT Bearer tokens
# in the Authorization header, which browsers do not attach automatically (unlike
# cookies), so CSRF attacks cannot exploit them.  NOSONAR (python:S4502)
csrf.exempt(auth_blueprint)
csrf.exempt(api_blueprint)
csrf.exempt(chat_blueprint)
csrf.exempt(mcp_blueprint)
csrf.exempt(agent_blueprint)
csrf.exempt(session_blueprint)  # NOSONAR (python:S4502)

if (
    is_test_mode 
    or os.environ.get("DISABLE_CSRF", "false").lower() == "true"
    or os.environ.get("WTF_CSRF_ENABLED", "true").lower() == "false"
):
    app.config["WTF_CSRF_ENABLED"] = False

# Configure rate limiting
if os.environ.get("DISABLE_RATE_LIMIT", "false").lower() == "true":
    app.config["RATELIMIT_ENABLED"] = False
limiter.init_app(app)

# Configure metrics
metrics.init_app(app)
metrics.info("app_info", "Application info", version="1.0.0")

app.register_blueprint(api_blueprint, url_prefix="/api")
app.register_blueprint(mcp_blueprint, url_prefix="/mcp")
app.register_blueprint(chat_blueprint, url_prefix="/api")
app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
app.register_blueprint(agent_blueprint, url_prefix="/api")
app.register_blueprint(userspace_blueprint, url_prefix="/api")
app.register_blueprint(session_blueprint, url_prefix="/api")


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/ui/<path:path>", methods=["GET"])
def serve_ui(path):
    return send_from_directory(app.static_folder, path)


# Catch-all route for SPA client-side routing
@app.route("/<path:path>", methods=["GET"])
def catch_all(path):
    if path.startswith("api/") or path.startswith("mcp/"):
        return jsonify({"message": "Not Found"}), 404

    # If the path has a file extension, try to serve it as a static file
    if "." in path.split("/")[-1]:
        try:
            return send_from_directory(app.static_folder, path)
        except (FileNotFoundError, NotADirectoryError):
            # File doesn't exist, fall through to serve index.html
            pass
    # Otherwise serve index.html for client-side routing
    return send_from_directory(app.static_folder, "index.html")


def start_services():
    # Force unbuffered output
    import sys

    sys.stdout.reconfigure(line_buffering=True)

    app.logger.info(f"{get_version_string()} starting...")
    init.run()
    app.logger.info("Moirai initialised.")

    # Start the enrichment worker only once
    # In dev mode with reloader, only start in the reloaded process (WERKZEUG_RUN_MAIN='true')
    # In production, WERKZEUG_RUN_MAIN won't be set, so worker starts normally
    # To disable worker entirely, set ENABLE_ENRICHMENT_WORKER='false'
    should_start_worker = (
        os.environ.get("ENABLE_ENRICHMENT_WORKER", "true").lower() == "true"
    )
    is_dev_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    is_production = os.environ.get("WERKZEUG_RUN_MAIN") is None

    if should_start_worker and (is_production or is_dev_reloader_child):
        worker.start()
        app.logger.info("Enrichment worker started.")

    # Start the scheduler
    interval = os.environ.get("ITERATION_INTERVAL", 600)
    scheduler.start(interval)
    app.logger.info(f"Scheduler started with interval {interval}s")


# Conditional Flask run for local development
if __name__ == "__main__":
    start_services() # Call start_services in main process only
    # Check if this is the main process and not a reloader child in development
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        port = int(os.environ.get("HTTP_PORT", 8088))
        host = os.environ.get("HTTP_HOST", "0.0.0.0")
        app.logger.info(f"Starting Moirai on {host}:{port}")
        app.run(host=host, port=port)
# Under gunicorn, the on_starting hook in gunicorn.conf.py handles
# database initialisation (init_db + ensure_default_user).
# The scheduler and worker are started separately via run_worker.py.
