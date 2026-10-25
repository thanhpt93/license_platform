"""
Root `app` package bridge so `app.*` imports work seamlessly whether commands are executed
from `C:\\project\\license_platform` or `C:\\project\\license_platform\\backend`.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
BACKEND_APP_DIR = BACKEND_DIR / "app"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

__path__.append(str(BACKEND_APP_DIR))
