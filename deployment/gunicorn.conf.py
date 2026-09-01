import os

bind = '0.0.0.0:8000'
worker_class = 'gthread'
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
threads = int(os.getenv('GUNICORN_THREADS', '4'))
timeout = int(os.getenv('GUNICORN_TIMEOUT', '30'))
graceful_timeout = 30
keepalive = 5
accesslog = '-'
errorlog = '-'
capture_output = True
preload_app = False
max_requests = 2000
max_requests_jitter = 200
