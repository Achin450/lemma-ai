import os
import sys
import subprocess

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

    # Start Celery worker in background process to process research generation tasks
    celery_proc = None
    try:
        celery_cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.tasks.celery_app.celery_app",
            "worker",
            "--loglevel=info",
            "-P", "solo"
        ]
        celery_proc = subprocess.Popen(celery_cmd, cwd=backend_dir)
        print("🚀 Celery background worker daemon started successfully!")
    except Exception as e:
        print(f"⚠️ Could not start Celery worker daemon: {e}")

    print(f"🚀 Starting Lemma AI FastAPI server on 0.0.0.0:{port}...")
    try:
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, app_dir="backend", workers=1)
    finally:
        if celery_proc:
            try:
                celery_proc.terminate()
            except Exception:
                pass
