"""Gunicorn config for mysite.

Run with:  ../env/bin/gunicorn -c gunicorn.conf.py mysite.wsgi:application

Sizing note: this app is I/O-bound (Stripe API calls, SQLite, template
rendering), not CPU-bound, so concurrency comes mostly from threads. Processes
are kept low on purpose because every worker process contends for the same
single-writer SQLite file.
"""

import multiprocessing
import os

# macOS only, and required for outbound HTTPS to work at all here.
#
# Gunicorn always forks its workers. When a forked worker resolves a hostname
# (api.stripe.com), macOS's resolver initialises Objective-C runtime state, and
# ObjC refuses to do that in a process that was forked from a multi-threaded
# parent. It kills the worker mid-request:
#
#   objc[...]: +[NSNumber initialize] may have been in progress in another
#              thread when fork() was called. Crashing instead.
#   [ERROR] Worker (pid:...) was sent SIGKILL!
#
# The browser just sees the connection close with no response, so a Buy click
# looked like it did nothing. Setting this before the fork tells ObjC to allow
# it. Harmless on Linux, where the variable is simply ignored.
os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')

# Railway assigns the port at runtime via $PORT and routes traffic to the
# container's external interface. Binding to loopback there makes the service
# unreachable and the deploy healthcheck fails.
_port = os.environ.get('PORT')
bind = f'0.0.0.0:{_port}' if _port else '127.0.0.1:8000'

# gthread gives each worker a thread pool, so a worker blocked on a Stripe HTTP
# call can still serve other requests. The default 'sync' worker cannot.
worker_class = 'gthread'

# 2 processes x 8 threads = 16 concurrent requests. The usual (2*CPU)+1 formula
# is for sync workers; it would put 21 processes on the SQLite file here.
# WEB_CONCURRENCY is gunicorn's standard override. Once on Postgres the
# single-writer limit is gone, so raising this is safe.
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '8'))

# Stripe calls can be slow; don't let the arbiter kill a worker mid-checkout.
timeout = 60
graceful_timeout = 30

# Off, so each worker imports the app itself after forking. Keeping it off also
# means no DB connection is inherited across the fork, which is why there is no
# post_fork hook below. (The ObjC fork crash that broke checkout is handled by
# OBJC_DISABLE_INITIALIZE_FORK_SAFETY above, not by this setting — turning
# preload back on is safe if you want the lower memory use.)
preload_app = False

# Recycle workers periodically so a slow leak can't accumulate.
max_requests = 1000
max_requests_jitter = 100

accesslog = '-'
errorlog = '-'
loglevel = 'info'


# No post_fork hook: it was there to drop DB connections inherited across the
# fork, which only happens with preload_app. With preload_app off, each worker
# imports Django itself after forking and opens its own connections. Running the
# hook now would also crash, since it fires before Django settings are loaded.


# Kept for reference when moving off SQLite: with Postgres you can raise this to
# (2 * multiprocessing.cpu_count()) + 1 workers.
_cpu_count = multiprocessing.cpu_count()
