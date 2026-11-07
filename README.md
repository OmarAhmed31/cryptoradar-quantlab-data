# cryptoradar-quantlab-data

Research data collector for the CryptoRadar Quant Lab: **read-only public OKX market data** and OKX's official delisting announcements.

- No API keys, no secrets, no trading. Nothing here can reach or change CryptoRadar.
- Network is limited in code to `www.okx.com` (see `lab/guard.py`, tested by `tests/test_proxy.py`).
- `.github/workflows/okx-probe.yml`: probe run on BTC, ETH and SAND, plus raw delisting pages. Results are committed into `out/`.
- Wider downloads only after the probe is reviewed and approved.
