import os
import sys

# Ensure backend directory is in sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Memory optimizations for cloud containers (Render 512MB RAM)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import uvicorn

if __name__ == "__main__":
    port_str = os.environ.get("PORT", "10000")
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 10000

    print(f"🚀 Starting Lemma AI FastAPI server on 0.0.0.0:{port}...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, app_dir="backend", workers=1)
