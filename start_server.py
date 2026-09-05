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
os.environ["MALLOC_TRIM_THRESHOLD_"] = "100000"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"

import uvicorn
import gc

if __name__ == "__main__":
    port_str = os.environ.get("PORT", "10000")
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 10000

    # Only spawn a separate Celery worker process if explicitly requested via env.
    # On 512MB cloud instances (Render), running in single-process eager mode saves 250MB+ RAM!
    celery_proc = None
    should_spawn_worker = os.environ.get("SPAWN_CELERY_WORKER", "false").lower() == "true"
    if should_spawn_worker:
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
    else:
        print("⚡ Cloud Memory Optimized: Single process eager execution active (512MB RAM Safe).")

    gc.collect()
    print(f"🚀 Starting Lemma AI FastAPI server on 0.0.0.0:{port}...")
    try:
        uvicorn.run("app.main:app", host="0.0.0.0", port=port, app_dir="backend", workers=1)
    finally:
        if celery_proc:
            try:
                celery_proc.terminate()
            except Exception:
                pass
