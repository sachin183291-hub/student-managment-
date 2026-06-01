import os
import sys

# Add parent directory to path first so 'app' module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Create the WSGI Flask application instance
app = create_app()
