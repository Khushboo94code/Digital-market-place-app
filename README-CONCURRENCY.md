# Concurrency setup (WSGI + Gunicorn)

This document explains how `mysite` went from serving one request at a time to
serving many, what was changed, and why each change was needed.

---

## 1. The short answer

Yes — the app can run multiple worker processes and multiple threads. It now
does, via **Gunicorn** with the `gthread` worker:

```
2 worker processes x 8 threads each = 16 concurrent requests
```

Measured on this machine: 16 requests fired at once, **all 16 in flight
simultaneously**, all returning 200, total 89 ms.

---

## 2. Why `runserver` was not the answer

A common misconception is that the dev server is single-request. It is not —
`manage.py runserver` is already threaded (one thread per request). The real
problems with it are different:

- It is **single-process**, so it can never use more than one CPU core.
- It is explicitly **not built for production** — no request limits, no worker
  recycling, no graceful restarts, and it reloads code on every file change.
- It auto-reloads and serves static files in ways that are unsafe under load.

So the goal was not "add threads" (they existed) but "run a real WSGI server
with a proper process + thread model".

---

## 3. How WSGI fits in

`mysite/wsgi.py` was already present and unchanged. It exposes:

```python
application = get_wsgi_application()
```

WSGI is just a calling convention: the server (Gunicorn) hands Django a request
and gets a response. Django itself is thread-safe at the request level, so one
process can run many request threads. What decides your concurrency is entirely
the **server** in front of that `application` object — which is what was added.

---

## 4. What was changed

### 4.1 New file: `gunicorn.conf.py`

The server config. Key choices and the reasoning:

| Setting | Value | Why |
|---|---|---|
| `worker_class` | `gthread` | The default `sync` worker handles **one** request per process. `gthread` gives each worker a thread pool, so a worker blocked on a Stripe HTTP call can still serve other requests. |
| `workers` | `2` | Deliberately low. Every extra *process* contends for the same single-writer SQLite file. |
| `threads` | `8` | This app is I/O-bound, so concurrency comes mostly from threads. |
| `timeout` | `60` | Stripe calls can be slow; don't let the arbiter kill a worker mid-checkout. |
| `preload_app` | `True` | Loads Django once before forking — less memory, faster boot. |
| `max_requests` | `1000` (+jitter) | Recycles workers so a slow leak can't accumulate. |
| `post_fork` hook | `connections.close_all()` | **Important.** With `preload_app`, Django is set up *before* the fork. A SQLite connection must not be shared across forked processes, so each worker drops the inherited one and opens its own. |

Note on sizing: the usual `(2 * CPU) + 1` formula is for **sync** workers. This
machine has 10 cores, so that formula would put 21 processes on one SQLite file.
That is the wrong shape for this app — hence 2 processes and 8 threads.

### 4.2 `mysite/settings.py` — SQLite made concurrency-safe

This was the single most necessary change. SQLite allows **many readers but only
one writer**. Without this, the second concurrent write fails outright with
`OperationalError: database is locked`.

```python
'OPTIONS': {
    'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
    'transaction_mode': 'IMMEDIATE',
    'timeout': 20,
},
```

- **WAL (write-ahead logging)** — lets readers keep working while a write is in
  progress. In the default rollback-journal mode, a writer blocks all readers.
- **`transaction_mode: 'IMMEDIATE'`** — takes the write lock at `BEGIN` instead
  of upgrading from a read lock mid-transaction. That upgrade case is the one
  SQLite cannot retry safely, and it is the usual source of stubborn lock errors.
- **`timeout: 20`** — wait up to 20s for a busy writer rather than erroring
  instantly.

Verified live: `journal_mode = wal`, `timeout = 20`.

### 4.3 `myapp/views.py` — two genuine thread-safety bugs

Turning on concurrency **exposes latent races that were harmless single-threaded**.
Two existed in this code and were fixed.

#### Bug A — shared mutable global (`stripe.api_key`)

`stripe.api_key` is a module-level global in the Stripe library. It was being
assigned *inside* two views, on every request:

```python
def create_checkout_session(request, id):
    stripe.api_key = settings.STRIPE_SECRET_KEY   # ran per request
```

With threads, every request mutates the same global while other threads are
mid-call. It is benign here only because the value is always identical — but it
is the exact pattern that breaks the moment a second key is introduced. Now set
**once at import**:

```python
stripe.api_key = settings.STRIPE_SECRET_KEY   # module level, set once
```

#### Bug B — double-counted sales (a real money bug)

This was read-then-write, which is safe with one request at a time and **wrong**
the instant two arrive together:

```python
# BEFORE
if not order.has_paid:          # thread A and thread B both read False
    order.has_paid = True
    order.save()
    Product.objects.filter(...).update(total_sales=F('total_sales')+1)  # counted TWICE
```

A buyer double-clicking or refreshing the success page could inflate
`total_sales` and `total_sales_amount`. The fix claims the order with a **single
conditional UPDATE** and lets the database pick the winner:

```python
# AFTER
with transaction.atomic():
    claimed = orderDetail.objects.filter(pk=order.pk, has_paid=False).update(
        stripe_payment_intent=session.payment_intent or '',
        has_paid=True,
        updated_on=timezone.now(),      # .update() skips auto_now
    )
    if claimed:                         # row count — exactly one caller gets 1
        Product.objects.filter(id=order.product_id).update(
            total_sales=F('total_sales') + 1,
            total_sales_amount=F('total_sales_amount') + order.amount,
        )
```

`.update()` is one atomic SQL statement, so the `has_paid=False` filter and the
write cannot be split by another thread. Note `updated_on` is set explicitly
because `QuerySet.update()` does not trigger `auto_now`.

**Verified:** 12 simultaneous success-page refreshes on one order → exactly
**1** thread won the claim, `total_sales = 1`, `total_sales_amount = 10.0`.

### 4.4 New file: `requirements.txt`

The project had none. Pins Django, stripe, pillow, dotenv, requests, and the
newly added gunicorn.

---

## 5. How to run it

Development (unchanged — auto-reload is genuinely useful here):

```bash
../env/bin/python manage.py runserver
```

Production-style, with workers and threads:

```bash
../env/bin/gunicorn -c gunicorn.conf.py mysite.wsgi:application
```

Override the port if 8000 is busy:

```bash
../env/bin/gunicorn -c gunicorn.conf.py -b 127.0.0.1:8001 mysite.wsgi:application
```

---

## 6. Verification performed

| Check | Result |
|---|---|
| `manage.py check` | 0 issues |
| WAL / timeout actually applied | `journal_mode = wal`, `timeout = 20` |
| Gunicorn boots 2 gthread workers | Yes |
| 16 simultaneous requests | 16/16 → HTTP 200, peak in-flight **16**, 89 ms total |
| 24 simultaneous SQLite writes | 24/24 committed, **zero** "database is locked" |
| 12-way race on one order | Exactly 1 claim, no double-count — **PASS** |

---

## 7. Limits you should know about

These are honest constraints of the current setup, not things that were broken.

1. **SQLite is still the ceiling.** WAL raises the write ceiling considerably but
   does not remove it — writes remain serialized to one at a time. For real
   production traffic, move to PostgreSQL. At that point you can raise workers to
   `(2 * CPU) + 1` and the `post_fork` hook stops mattering as much.
2. **`DEBUG = True` and `ALLOWED_HOSTS = []`** in `settings.py`. Both must change
   before any real deployment; `DEBUG=True` also leaks stack traces and slowly
   accumulates queries in memory.
3. **Static and media files** are not served by Gunicorn. You need WhiteNoise or
   a real file server / object storage in front.
4. **No background job queue.** Stripe calls happen inline in the request. Threads
   hide this well, but heavy work belongs in Celery or similar.
5. **Payment confirmation depends on the buyer's browser** reaching the success
   page. A Stripe **webhook** is the reliable way to mark orders paid — the
   conditional-update fix above makes adding one safe, since the webhook and the
   redirect can now race without double-counting.
