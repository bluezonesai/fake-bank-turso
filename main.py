import os
import sys

# Ensure the current directory is in the Python path
# This line is still important for finding modules in the same directory
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, send_from_directory

# --- CORRECTED IMPORTS FOR FLAT STRUCTURE ---
# Import bank.py and user.py directly as modules
import bank # This will import bank.py
import user # This will import user.py

# Now access db and bank_bp from the imported modules
from bank import db
from bank import bank_bp # Assuming bank_bp is defined in bank.py

# If user-related routes are in user.py, you might need:
# from user import user_bp # Assuming user_bp is defined in user.py
# app.register_blueprint(user_bp, url_prefix=\"/user\")
# --- END CORRECTED IMPORTS ---

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static') # Corrected static folder path
app.config["SECRET_KEY"] = 'asdf#FGSgvasgf$5$WGT'

app.register_blueprint(bank_bp, url_prefix=\"/api\")

# ... rest of your database configuration and app context

# Configure database - Turso or fallback to SQLite
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
    # Use Turso database
    database_url = f"sqlite+{TURSO_DATABASE_URL}?secure=true"
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {
            'auth_token': TURSO_AUTH_TOKEN,
            'check_same_thread': False
        }
    }
else:
    # Fallback to local SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
