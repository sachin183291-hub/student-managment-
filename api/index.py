from app import create_app
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = create_app()

# For Vercel WSGI handler
def handler(event, context):
    return app(event, context)
