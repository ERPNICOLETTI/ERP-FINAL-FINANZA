import sys
import os

# Ensure the root project directory is in the python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from erp_api.main import app

if __name__ == "__main__":
    import uvicorn
    # Iniciar en localhost (127.0.0.1)
    uvicorn.run("erp_api.main:app", host="127.0.0.1", port=5005, reload=True)
