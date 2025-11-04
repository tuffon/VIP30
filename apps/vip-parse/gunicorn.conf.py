# Gunicorn configuration file
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = 1  # Start with 1 worker for debugging
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120  # Increase timeout to 2 minutes
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
# Disable access logs to reduce noise from platform health checks
accesslog = None
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "costbook-api"

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (not needed for Render)
keyfile = None
certfile = None

# Preload app for better performance
preload_app = True

def when_ready(server):
    """Called just after the server is started."""
    print("Gunicorn server is ready!")

def worker_int(worker):
    """Called just after a worker has been initialized."""
    print(f"Worker {worker.pid} initialized")

def worker_abort(worker):
    """Called when a worker received SIGABRT."""
    print(f"Worker {worker.pid} received SIGABRT")

def pre_fork(server, worker):
    """Called just before a worker has been forked."""
    print(f"About to fork worker {worker.pid}")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker {worker.pid} forked")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    print(f"Worker {worker.pid} initialized application")
