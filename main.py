"""
Main entry point for the Nova backend application.
"""
import os
from api.server import app
from config.sql import init_db


if __name__ == "__main__":
    # Initialize database
    init_db()
    
    # Run the Flask app
    debug = os.getenv("DEBUG", "False").lower() == "true"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5100))
    
    print(f"Starting Nova backend on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
