import os
import sys  # Moved to top
from flask import Flask, send_from_directory, jsonify
from flask_wtf import CSRFProtect
from api.extensions import limiter, metrics
from api.routes import api_blueprint
from api.mcp_routes import mcp_blueprint
from api.chat_routes import chat_blueprint
from api.auth import auth_blueprint  # Moved to top
from api.telemetry import configure_telemetry  # Moved to top

from tasks.scheduler import scheduler
from tasks import init
from tasks.enrichment_worker import worker  # Moved to top
from version import get_version_string

app = Flask(__name__, static_folder="ui/dist")

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

# CSRF protection is disabled to support the current API authentication design.
# The API uses HTTP Basic Auth which is stateless and doesn't require CSRF tokens.
# Note: If adding session-based authentication in the future, re-enable CSRF protection.
csrf = CSRFProtect()
csrf.init_app(app)
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


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/ui/<path:path>")
def serve_ui(path):
    return send_from_directory(app.static_folder, path)


# Catch-all route for SPA client-side routing
@app.route("/<path:path>")
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

    print(f"{get_version_string()} starting...", flush=True)
    init.run()
    print("Moirai initialised.")

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
        print("Enrichment worker started.")

    # Start the scheduler
    interval = os.environ.get("ITERATION_INTERVAL", 600)
    scheduler.start(interval)
    print(f"Scheduler started with interval {interval}s")


if __name__ == "__main__":
    start_services()

    # Start the application
    port = int(os.environ.get("HTTP_PORT", 8088))
    print(f"Starting Moirai on port {port}")
    app.run(host="0.0.0.0", port=port)
else:
    # Production mode startup (e.g. Uvicorn/Gunicorn)
    if os.environ.get("ENABLE_PROD_STARTUP", "").lower() == "true":
        start_services()
