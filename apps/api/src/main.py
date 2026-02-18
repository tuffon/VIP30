import os
import sys
from pathlib import Path

# Add the project root to Python path to ensure imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"Starting application...")
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

try:
    from src.api.main import app
    print("Successfully imported FastAPI app")
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    raise

# Re-export the app for gunicorn
__all__ = ["app"]
