from flask import Flask
from api import api_blueprint
from dashboard import create_dashboard

# Initialize Flask server
server = Flask(__name__)

# Register API blueprint
server.register_blueprint(api_blueprint)

# Attach Dash application
dash_app = create_dashboard(server)

if __name__ == "__main__":
    server.run(host='0.0.0.0', debug=True)
