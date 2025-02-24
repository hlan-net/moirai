import os
from flask import Flask, send_from_directory
from flask_wtf import CSRFProtect
from api.routes import api_blueprint
from tasks.scheduler import scheduler

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

if __name__ == "__main__":
    # Start scheduling URL fetches
    scheduler.start(os.environ.get("ITERATION_INTERVAL", 600))
    port = int(os.environ.get("HTTP_PORT", 8088))
    app.run(host="0.0.0.0", port=port)
