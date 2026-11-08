"""Deterministic proxy-path tests (Phase 0 closure). Run: python3 -I tests/test_proxy.py

A local mock proxy (127.0.0.1, random port) runs in the test harness and LOGS every byte it receives.
Guarded children are pointed at it with HTTPS_PROXY. Each test asserts BOTH:
  (a) the exact exception class in the child (guard.IsolationError vs a network error), and
  (b) what the proxy actually received (CONNECT line present / absent).
So no test can pass just because "the network failed".
"""
import unittest, subprocess, sys, os, json, pathlib, socket, threading, time

LAB = pathlib.Path(__file__).resolve().parents[1]
PRE = f"import sys; sys.path.insert(0, {str(LAB)!r}); from lab import guard; "
WRAP = ("\nimport urllib.error\ntry:\n{body}\n    print('RESULT:OK')\n"
        "except guard.IsolationError as e:\n    print('RESULT:ISOLATION', e)\n"
        "except urllib.error.URLError as e:\n"
        "    if isinstance(e.reason, guard.IsolationError): print('RESULT:ISOLATION', e.reason)  # urllib wraps OSError subclasses\n"
        "    else: print('RESULT:OTHER', type(e).__name__, str(e)[:120])\n"
        "except Exception as e:\n    print('RESULT:OTHER', type(e).__name__, str(e)[:120])\n")


class MockProxy:
    """Accepts connections, records request bytes, answers CONNECT with a fixed status, keeps reading."""
    def __init__(self, status=b"200 Connection established"):
        self.status = status
        self.log = []          # list of (conn_no, bytes)
        self.conns = 0
        self.srv = socket.socket(); self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0)); self.srv.listen(8); self.srv.settimeout(0.2)
        self.port = self.srv.getsockname()[1]
        self.stop = False
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def _run(self):
        while not self.stop:
            try:
                c, _ = self.srv.accept()
            except socket.timeout:
                continue
            self.conns += 1
            threading.Thread(target=self._handle, args=(c, self.conns), daemon=True).start()

    def _handle(self, c, n):
        c.settimeout(2.0)
        buf, answered = b"", False
        try:
            while True:
                d = c.recv(4096)
                if not d:
                    break
                buf += d
                self.log.append((n, d))
                if not answered and b"\r\n\r\n" in buf:
                    c.sendall(b"HTTP/1.1 " + self.status + b"\r\n\r\n"); answered = True
        except (socket.timeout, OSError):
            pass
        finally:
            c.close()

    def received(self):
        return b"".join(d for _, d in self.log)

    def close(self):
        self.stop = True; self.t.join(1); self.srv.close()


def child(code, port, timeout=30, proxy_host="127.0.0.1", use_proxy=True):
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy", "no_proxy")}
    if use_proxy:
        env["HTTPS_PROXY"] = env["https_proxy"] = f"http://{proxy_host}:{port}"
    r = subprocess.run([sys.executable, "-I", "-c", PRE + code], capture_output=True, text=True, timeout=timeout, cwd=str(LAB), env=env)
    out = r.stdout + r.stderr
    res = [ln for ln in out.splitlines() if ln.startswith("RESULT:")]
    return (res[-1] if res else "RESULT:NONE " + out[-300:]), out


def body(lines):
    return WRAP.format(body="\n".join("    " + ln for ln in lines))


class P(unittest.TestCase):
    def setUp(self):
        self.px = MockProxy()

    def tearDown(self):
        time.sleep(0.3); self.px.close()

    # P1: http.client.connect checks the TUNNEL target, not the proxy host
    def test_P1_connect_forbidden_tunnel_target_blocked_by_guard_before_any_socket(self):
        res, out = child("guard.install(job='p1', net_hosts=('www.okx.com',)); import http.client" + body([
            f"c = http.client.HTTPConnection('127.0.0.1', {self.px.port}, timeout=5)",
            "c.set_tunnel('cryptoradar2.pages.dev', 443)",
            "c.connect()"]), self.px.port)
        time.sleep(0.3)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertIn("network blocked (target): cryptoradar2.pages.dev", res)
        self.assertEqual(self.px.conns, 0, "proxy must receive NO connection at all")

    # P2: allowed tunnel target passes the guard and the proxy really gets CONNECT www.okx.com
    def test_P2_connect_allowed_target_passes_guard_and_reaches_proxy(self):
        res, out = child("guard.install(job='p2', net_hosts=('www.okx.com',)); import http.client" + body([
            f"c = http.client.HTTPConnection('127.0.0.1', {self.px.port}, timeout=5)",
            "c.set_tunnel('www.okx.com', 443)",
            "c.connect()"]), self.px.port)
        time.sleep(0.3)
        self.assertEqual(res, "RESULT:OK", res + out[-300:])
        self.assertIn(b"CONNECT www.okx.com:443 HTTP/1.", self.px.received())

    # P3: a raw CONNECT message sent inside an allowed connection is blocked by the guard (send check)
    def test_P3_raw_connect_message_to_forbidden_host_blocked_by_send_check(self):
        res, out = child("guard.install(job='p3', net_hosts=('www.okx.com',)); import http.client" + body([
            f"c = http.client.HTTPConnection('127.0.0.1', {self.px.port}, timeout=5)",
            "c.set_tunnel('www.okx.com', 443)",
            "c.connect()",
            "c.send(b'CONNECT api.telegram.org:443 HTTP/1.1\\r\\nHost: api.telegram.org:443\\r\\n\\r\\n')"]), self.px.port)
        time.sleep(0.5)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertIn("network blocked (tunnel): api.telegram.org", res)
        got = self.px.received()
        self.assertIn(b"CONNECT www.okx.com:443", got)            # the allowed tunnel happened
        self.assertNotIn(b"api.telegram.org", got)                # the forbidden one never left the process

    # P4: raw CONNECT to the allowed host passes the send check (control for P3)
    def test_P4_raw_connect_message_to_okx_passes_send_check(self):
        res, out = child("guard.install(job='p4', net_hosts=('www.okx.com',)); import http.client" + body([
            f"c = http.client.HTTPConnection('127.0.0.1', {self.px.port}, timeout=5)",
            "c.set_tunnel('www.okx.com', 443)",
            "c.connect()",
            "c.send(b'CONNECT www.okx.com:443 HTTP/1.1\\r\\nHost: www.okx.com:443\\r\\n\\r\\n')"]), self.px.port)
        time.sleep(0.5)
        self.assertEqual(res, "RESULT:OK", res)
        self.assertEqual(self.px.received().count(b"CONNECT www.okx.com:443"), 2)

    # P5: integration through urllib (the code path okx_fetch uses), forbidden host
    def test_P5_urllib_forbidden_host_never_reaches_proxy(self):
        for host in ("cryptoradar2.pages.dev", "cryptoradar.workers.dev", "api.telegram.org", "api.coingecko.com", "example.com"):
            self.px.log.clear(); self.px.conns = 0
            res, out = child("guard.install(job='p5', net_hosts=('www.okx.com',)); import urllib.request" + body([
                f"urllib.request.urlopen('https://{host}/x', timeout=5)"]), self.px.port)
            time.sleep(0.3)
            self.assertTrue(res.startswith("RESULT:ISOLATION"), host + " " + res)
            self.assertIn(f"network blocked (target): {host}", res)
            self.assertEqual(self.px.conns, 0, host)

    # P6: integration through urllib, allowed host: proxy receives the CONNECT; the later failure is a network error, NOT the guard
    def test_P6_urllib_okx_reaches_proxy_failure_is_network_not_guard(self):
        res, out = child("guard.install(job='p6', net_hosts=('www.okx.com',)); import urllib.request" + body([
            "urllib.request.urlopen('https://www.okx.com/api/v5/public/time', timeout=5)"]), self.px.port)
        time.sleep(0.3)
        self.assertTrue(res.startswith("RESULT:OTHER"), res)      # TLS cannot complete against the mock
        self.assertNotIn("ISOLATION", res)
        self.assertIn(b"CONNECT www.okx.com:443 HTTP/1.", self.px.received())

    # P7: proxy answers 403 (like the real environment) -> error is a network error AFTER the CONNECT was sent
    def test_P7_proxy_403_is_network_error_after_connect(self):
        self.px.status = b"403 Forbidden"
        res, out = child("guard.install(job='p7', net_hosts=('www.okx.com',)); import urllib.request" + body([
            "urllib.request.urlopen('https://www.okx.com/api/v5/public/time', timeout=5)"]), self.px.port)
        time.sleep(0.3)
        self.assertTrue(res.startswith("RESULT:OTHER URLError"), res)
        self.assertIn("403", res)
        self.assertIn(b"CONNECT www.okx.com:443", self.px.received())

    # P8: a job WITHOUT net permission cannot even reach the proxy
    def test_P8_no_network_job_cannot_use_proxy_even_for_okx(self):
        res, out = child("guard.install(job='p8'); import urllib.request" + body([
            "urllib.request.urlopen('https://www.okx.com/api/v5/public/time', timeout=5)"]), self.px.port)
        time.sleep(0.3)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertEqual(self.px.conns, 0)

    # P9: the proxy host itself is not a permitted final destination (no plain request to the proxy)
    def test_P9_direct_request_to_proxy_host_blocked(self):
        res, out = child("guard.install(job='p9', net_hosts=('www.okx.com',)); import http.client" + body([
            f"c = http.client.HTTPConnection('127.0.0.1', {self.px.port}, timeout=5)",
            "c.request('GET', 'http://cryptoradar2.pages.dev/')"]), self.px.port)
        time.sleep(0.3)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertIn("network blocked (target): 127.0.0.1", res)
        self.assertEqual(self.px.conns, 0)

    # P10: proxy given as a DNS NAME (localhost -> 127.0.0.1): allowed target still reaches it, forbidden still blocked
    def test_P10_dns_named_proxy_works_and_still_blocks(self):
        res, out = child("guard.install(job='p10', net_hosts=('www.okx.com',)); import urllib.request" + body([
            "urllib.request.urlopen('https://www.okx.com/api/v5/public/time', timeout=5)"]), self.px.port, proxy_host="localhost")
        time.sleep(0.3)
        self.assertNotIn("ISOLATION", res, res)
        self.assertIn(b"CONNECT www.okx.com:443", self.px.received())
        self.px.log.clear(); self.px.conns = 0
        res, out = child("guard.install(job='p10b', net_hosts=('www.okx.com',)); import urllib.request" + body([
            "urllib.request.urlopen('https://cryptoradar2.pages.dev/', timeout=5)"]), self.px.port, proxy_host="localhost")
        time.sleep(0.3)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertEqual(self.px.conns, 0)

    # P11: no proxy, permitted target given as a DNS name: its resolved IP is connectable, any other IP is not
    def test_P11_direct_dns_target_allowed_other_ip_blocked(self):
        res, out = child("guard.install(job='p11', net_hosts=('localhost',)); import socket" + body([
            f"s = socket.create_connection(('localhost', {self.px.port}), timeout=5); s.sendall(b'PING\\r\\n\\r\\n'); s.close()"]), self.px.port, use_proxy=False)
        time.sleep(0.3)
        self.assertEqual(res, "RESULT:OK", res + out[-300:])
        self.assertIn(b"PING", self.px.received())
        self.px.log.clear(); self.px.conns = 0
        res, out = child("guard.install(job='p11b', net_hosts=('localhost',)); import socket" + body([
            f"s = socket.socket(); s.settimeout(3); s.connect(('127.0.0.2', {self.px.port}))"]), self.px.port, use_proxy=False)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertIn("connect blocked: 127.0.0.2", res)

    # P12 (guard v0.4): a permitted name whose IP was NOT known at install time (CDN rotation) becomes connectable
    # on its next lookup; a forbidden name cannot add anything; an IP no permitted name resolved to stays blocked
    def test_P12_permitted_name_rotated_ip_added_at_lookup_forbidden_name_cannot(self):
        res, out = child("guard.install(job='p12', net_hosts=('localhost',)); import socket" + body([
            "guard._cfg['net_ips'].clear()                       # simulate: install-time IPs are stale",
            "s = socket.socket(); s.settimeout(3)",
            "try:\n        s.connect(('127.0.0.1', %d)); print('RESULT:UNEXPECTED_OK')\n    except guard.IsolationError: pass" % self.px.port,
            f"s2 = socket.create_connection(('localhost', {self.px.port}), timeout=5); s2.sendall(b'ROT\\r\\n\\r\\n'); s2.close()"]), self.px.port, use_proxy=False)
        time.sleep(0.3)
        self.assertEqual(res, "RESULT:OK", res + out[-300:])
        self.assertIn(b"ROT", self.px.received())
        res, out = child("guard.install(job='p12b', net_hosts=('localhost',)); import socket" + body([
            "socket.getaddrinfo('cryptoradar2.pages.dev', 443)"]), self.px.port, use_proxy=False)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertIn("network blocked: cryptoradar2.pages.dev", res)
        res, out = child("guard.install(job='p12c', net_hosts=('localhost',)); import socket" + body([
            "socket.getaddrinfo('localhost', 80)",
            f"s = socket.socket(); s.settimeout(3); s.connect(('127.0.0.2', {self.px.port}))"]), self.px.port, use_proxy=False)
        self.assertTrue(res.startswith("RESULT:ISOLATION"), res)
        self.assertIn("connect blocked: 127.0.0.2", res)


if __name__ == "__main__":
    r = unittest.main(verbosity=2, exit=False)
    res = {"suite": "proxy", "ran": r.result.testsRun, "failures": len(r.result.failures), "errors": len(r.result.errors),
           "skipped": len(r.result.skipped), "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / "reports" / "proxy_tests_result.json").write_text(json.dumps(res, indent=1))
    sys.exit(0 if r.result.wasSuccessful() else 1)
