import os
from flask import Flask, send_from_directory
from flask_wtf import CSRFProtect
from api.extensions import limiter, metrics
from api.routes import api_blueprint
from api.mcp_routes import mcp_blueprint
from api.chat_routes import chat_blueprint
from tasks.scheduler import scheduler
from tasks import init
from version import get_version_string

app = Flask(__name__, static_folder='ui/dist')

# Initialize Telemetry
from api.telemetry import configure_telemetry
configure_telemetry(app, "moirai-api")

# CSRF protection is disabled to support the current API authentication design.
# The API uses HTTP Basic Auth which is stateless and doesn't require CSRF tokens.
# Note: If adding session-based authentication in the future, re-enable CSRF protection.
csrf = CSRFProtect()
csrf.init_app(app)
app.config['WTF_CSRF_ENABLED'] = False

# Configure rate limiting
limiter.init_app(app)

# Configure metrics
metrics.init_app(app)
metrics.info('app_info', 'Application info', version='1.0.0')

app.register_blueprint(api_blueprint, url_prefix='/api')
app.register_blueprint(mcp_blueprint, url_prefix='/mcp')
app.register_blueprint(chat_blueprint, url_prefix='/api')

@app.route("/")
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/ui/<path:path>')
def serve_ui(path):
    return send_from_directory(app.static_folder, path)

# Catch-all route for SPA client-side routing
@app.route('/<path:path>')
def catch_all(path):
    # If the path has a file extension, try to serve it as a static file
    if '.' in path.split('/')[-1]:
        try:
            return send_from_directory(app.static_folder, path)
        except (FileNotFoundError, NotADirectoryError):
            # File doesn't exist, fall through to serve index.html
            pass
    # Otherwise serve index.html for client-side routing
    return send_from_directory(app.static_folder, 'index.html')

def start_services():
    # Force unbuffered output
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    
    print(f"{get_version_string()} starting...", flush=True)
    init.run()
    print("Moirai initialised.")
    
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

