"""A shared, pooled HTTP session for CouchDB requests.

``requests.request()`` opens a new TCP connection for every call. Each new
connection resolves the CouchDB service name and connects to whichever
address comes first, so one slow or dead address behind that name costs a
connect timeout on a share of all requests. Reusing connections pays that
price once per connection instead of once per request, and saves the
handshake on every call.
"""

import os
import threading

import requests
from requests.adapters import HTTPAdapter

# Connections kept per host. gunicorn workers and the worker threads each make
# only a handful of concurrent CouchDB calls.
POOL_SIZE = 20

_lock = threading.Lock()
_session: requests.Session | None = None
_session_pid: int | None = None


def couchdb_session() -> requests.Session:
    """Return this process's session, creating it on first use.

    The session is rebuilt after a fork so that a child process (a gunicorn
    worker) never shares sockets with its parent.
    """
    global _session, _session_pid
    pid = os.getpid()
    if _session is None or _session_pid != pid:
        with _lock:
            if _session is None or _session_pid != pid:
                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=4, pool_maxsize=POOL_SIZE)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                _session, _session_pid = session, pid
    return _session
