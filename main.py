import os
from flask import Flask, send_from_directory
from flask_wtf import CSRFProtect
from api.routes import api_blueprint
from api.mcp_routes import mcp_blueprint
from api.chat_routes import chat_blueprint
from tasks.scheduler import scheduler
from tasks import init

app = Flask(__name__, static_folder='ui/dist')

# Disable CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)
app.config['WTF_CSRF_ENABLED'] = False

@app.route("/")
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/ui/<path:path>')
def serve_ui(path):
    return send_from_directory(app.static_folder, path)

app.register_blueprint(api_blueprint, url_prefix='/api')
app.register_blueprint(mcp_blueprint, url_prefix='/mcp')
app.register_blueprint(chat_blueprint, url_prefix='/api')

if __name__ == "__main__":
    # Initialise
    print("Moirai starting...")
    init.run()
    print("Moirai initialised.")
    
    # Start the scheduler
    interval = os.environ.get("ITERATION_INTERVAL", 600)
    scheduler.start(interval)
    print(f"Scheduler started with interval {interval}s")

    # Start the application
    port = int(os.environ.get("HTTP_PORT", 8088))
    print(f"Starting Moirai on port {port}")
    app.run(host="0.0.0.0", port=port)

