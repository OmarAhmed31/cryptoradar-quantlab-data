"""Quant Lab isolation guard (Phase 0).

Installed at the start of every lab process. Cannot be removed once installed
(Python audit hooks are permanent for the process lifetime).

Enforces:
  * writes only inside the lab's own output dirs (never source data, never CryptoRadar files)
  * network only to an explicit allowlist (default: none; OKX public market data when fetching)
  * no subprocess / exec / shell
  * no ctypes / native loading (closes the easiest audit-hook bypass)
  * CPU / RAM / file-size limits
  * single job at a time (lock) + kill switch (state/STOP)

Defense in depth, not the only wall: the lab also holds no CryptoRadar credentials,
runs outside Cloudflare, and verifies snapshot hashes before every use.
"""
import os, sys, socket, resource, fcntl, json, time, pathlib

LAB = pathlib.Path(__file__).resolve().parents[1]
STATE = LAB / "state"
STOP_FILE = STATE / "STOP"
_installed = {"on": False}
_cfg = {}

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


class IsolationError(PermissionError):
    pass


def _inside(p, roots):
    try:
        rp = os.path.realpath(os.fsdecode(p))
    except Exception:
        return False
    return any(rp == r or rp.startswith(r + os.sep) for r in roots)


_orig_getaddrinfo = None


def _hook(event, args):
    roots = _cfg["write_roots"]
    if event == "open":
        path, mode, flags = args
        if isinstance(path, int) or path is None:
            return
        wr = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & _WRITE_FLAGS)
        if wr and not _inside(path, roots):
            raise IsolationError(f"write blocked outside lab: {path}")
    elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate", "os.utime", "shutil.rmtree", "os.link", "os.symlink"):
        p = args[0]
        if not isinstance(p, int) and not _inside(p, roots):
            raise IsolationError(f"{event} blocked outside lab: {p}")
    elif event in ("os.rename", "os.replace", "shutil.move", "shutil.copyfile"):
        for p in args[:2]:
            if event == "shutil.copyfile" and p is args[0]:
                continue  # reading source is fine
            if not isinstance(p, int) and not _inside(p, roots):
                raise IsolationError(f"{event} blocked outside lab: {p}")
    elif event == "socket.getaddrinfo" or event == "socket.gethostbyname":
        host = args[0]
        if isinstance(host, bytes):
            host = host.decode()
        if host not in _cfg["net_hosts"]:
            raise IsolationError(f"network blocked: {host}")
    elif event == "socket.connect":
        addr = args[1]
        host = addr[0] if isinstance(addr, tuple) else addr
        if host not in _cfg["net_ips"] and host not in _cfg["net_hosts"] and not _cfg.get("proxy_ok", False):
            raise IsolationError(f"connect blocked: {host}")
    elif event == "http.client.connect":
        # through a proxy the socket goes to the proxy; the real target is the tunnel host
        conn = args[0]
        target = getattr(conn, "_tunnel_host", None) or args[1]
        if target not in _cfg["allow_targets"]:
            raise IsolationError(f"network blocked (target): {target}")
    elif event == "http.client.send":
        data = args[1]
        if isinstance(data, (bytes, bytearray)) and data[:8] == b"CONNECT ":
            target = data[8:].split(b" ", 1)[0].rsplit(b":", 1)[0].decode(errors="replace")
            if target not in _cfg["allow_targets"]:
                raise IsolationError(f"network blocked (tunnel): {target}")
    elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "pty.spawn"):
        raise IsolationError(f"{event} blocked")
    elif event in ("ctypes.dlopen", "ctypes.dlsym", "ctypes.cdata"):
        raise IsolationError(f"{event} blocked")


def install(write_dirs=("out", "state", "registry", "reports"), net_hosts=(), mem_mb=3072, cpu_s=3600, fsize_mb=600, job="job"):
    """Call once at process start. write_dirs are relative to the lab root."""
    if _installed["on"]:
        return
    roots = []
    for d in write_dirs:
        p = (LAB / d)
        p.mkdir(parents=True, exist_ok=True)
        roots.append(os.path.realpath(p))
    _cfg["write_roots"] = roots
    _cfg["net_hosts"] = set(net_hosts)
    _cfg["allow_targets"] = set(net_hosts)   # final destinations (never the proxy itself)
    # an outbound HTTPS proxy (if the environment forces one) must be allowed explicitly
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    _cfg["net_ips"] = set()
    _cfg["proxy_ok"] = False
    if net_hosts and proxy:
        from urllib.parse import urlparse
        ph = urlparse(proxy).hostname
        if ph:
            _cfg["net_hosts"].add(ph)
            _cfg["net_ips"].add(ph)
    # socket.connect sees IP addresses after DNS. Resolve every permitted name ONCE here (before the
    # hook is active) so a proxy or target given as a DNS name is not wrongly refused. Only these IPs
    # are connectable; a name that fails to resolve simply stays unreachable (fails closed).
    if net_hosts:
        for h in list(_cfg["net_hosts"]):
            try:
                for ai in socket.getaddrinfo(h, None):
                    _cfg["net_ips"].add(ai[4][0])
            except OSError:
                pass
        # v0.4: CDN names (static.okx.com) rotate IPs during a long job. Every later lookup of a PERMITTED name
        # also adds the addresses it returns. The audit hook still refuses the lookup of any other name, so only
        # addresses of permitted names can ever become connectable (same policy as before, applied at use time).
        global _orig_getaddrinfo
        if _orig_getaddrinfo is None:
            _orig_getaddrinfo = socket.getaddrinfo

            def _getaddrinfo(host, *a, **k):
                res = _orig_getaddrinfo(host, *a, **k)
                h = host.decode() if isinstance(host, bytes) else host
                if h in _cfg["net_hosts"]:
                    for ai in res:
                        _cfg["net_ips"].add(ai[4][0])
                return res
            socket.getaddrinfo = _getaddrinfo
    for k, v in ((resource.RLIMIT_AS, mem_mb), (resource.RLIMIT_FSIZE, fsize_mb)):
        b = v * 1024 * 1024
        resource.setrlimit(k, (b, b))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
    # single job lock (opened before the hook so the lock file lives in state/)
    STATE.mkdir(exist_ok=True)
    lf = open(STATE / "lab.lock", "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another Quant Lab job is running")
    _cfg["lock"] = lf
    _cfg["job"] = job
    _cfg["t0"] = time.time()
    sys.addaudithook(_hook)
    _installed["on"] = True
    check_stop()
    health("running")


def check_stop():
    """Kill switch: create state/STOP to make every job exit at its next checkpoint."""
    if STOP_FILE.exists():
        health("stopped_by_kill_switch")
        raise SystemExit("Quant Lab kill switch is ON (state/STOP)")


def health(status, **extra):
    ru = resource.getrusage(resource.RUSAGE_SELF)
    h = {"status": status, "job": _cfg.get("job"), "pid": os.getpid(), "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "elapsed_s": round(time.time() - _cfg.get("t0", time.time()), 2), "cpu_s": round(ru.ru_utime + ru.ru_stime, 2),
         "max_rss_mb": round(ru.ru_maxrss / 1024, 1)}
    h.update(extra)
    atomic_write(STATE / "health.json", json.dumps(h, indent=1))
    return h


def atomic_write(path, text, mode="w"):
    """Write to temp then rename: a killed job never leaves a half-written output."""
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    with open(tmp, mode, encoding=None if "b" in mode else "utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
