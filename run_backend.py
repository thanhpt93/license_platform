"""
Root launcher for NOVA License Management Backend.
Allows running from either C:\\project\\license_platform or C:\\project\\license_platform\\backend.
Runs on port 8080 by default so it does not conflict with NOVA Machine Vision Platform on port 8000.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402, F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        app_dir=str(BACKEND_DIR),
        host="127.0.0.1",
        port=8080,
        reload=True,
        reload_dirs=[str(BACKEND_DIR)],
    )
