# 1m archive → 1H vs verified history-candles (exact decimal comparison)

| pair | minutes | missing min | dup | zero-vol min (flat at prev close) | hours compared | only archive / only verified |
|---|---|---|---|---|---|---|
| BTC-USDT | 43200 (2026-05-31 16:00 → 2026-06-30 15:59 UTC) | 0 | 0 | 0 (0) | 720 | 0 / 0 |
| DOGE-USDT | 43200 (2026-05-31 16:00 → 2026-06-30 15:59 UTC) | 0 | 0 | 85 (85) | 720 | 0 / 0 |
| ETH-USDT | 43200 (2026-05-31 16:00 → 2026-06-30 15:59 UTC) | 0 | 0 | 1 (1) | 720 | 0 / 0 |
| LSK-USDT | 43200 (2026-05-31 16:00 → 2026-06-30 15:59 UTC) | 0 | 0 | 31552 (31552) | 720 | 0 / 0 |
| SAND-USDT | 43200 (2026-05-31 16:00 → 2026-06-30 15:59 UTC) | 0 | 0 | 19689 (19689) | 720 | 0 / 0 |
| SOL-USDT | 43200 (2026-05-31 16:00 → 2026-06-30 15:59 UTC) | 0 | 0 | 0 (0) | 720 | 0 / 0 |

Zero-volume minutes are written by OKX as flat candles at the previous close (no trade). Rule A aggregates every minute; rule B aggregates only minutes with volume > 0 (an hour with no traded minute would keep its flat minutes; count shown in JSON).

## Rule A: all minutes

| pair | column | mismatches | max abs diff | max rel diff | worst hour UTC |
|---|---|---|---|---|---|
| BTC-USDT | open | 0 | 0 | 0 |  |
| BTC-USDT | high | 0 | 0 | 0 |  |
| BTC-USDT | low | 0 | 0 | 0 |  |
| BTC-USDT | close | 0 | 0 | 0 |  |
| BTC-USDT | volume_base | 0 | 0 | 0 |  |
| BTC-USDT | volume_quote | 0 | 0 | 0 |  |
| DOGE-USDT | open | 0 | 0 | 0 |  |
| DOGE-USDT | high | 0 | 0 | 0 |  |
| DOGE-USDT | low | 0 | 0 | 0 |  |
| DOGE-USDT | close | 0 | 0 | 0 |  |
| DOGE-USDT | volume_base | 0 | 0 | 0 |  |
| DOGE-USDT | volume_quote | 0 | 0 | 0 |  |
| ETH-USDT | open | 0 | 0 | 0 |  |
| ETH-USDT | high | 0 | 0 | 0 |  |
| ETH-USDT | low | 0 | 0 | 0 |  |
| ETH-USDT | close | 0 | 0 | 0 |  |
| ETH-USDT | volume_base | 0 | 0 | 0 |  |
| ETH-USDT | volume_quote | 0 | 0 | 0 |  |
| LSK-USDT | open | 398 | 0.0022 | 2.517e-02 | 2026-06-27 13:00 |
| LSK-USDT | high | 76 | 0.0019 | 2.132e-02 | 2026-06-28 19:00 |
| LSK-USDT | low | 58 | 0.0012 | 1.356e-02 | 2026-06-18 20:00 |
| LSK-USDT | close | 0 | 0 | 0 |  |
| LSK-USDT | volume_base | 0 | 0 | 0 |  |
| LSK-USDT | volume_quote | 0 | 0 | 0 |  |
| SAND-USDT | open | 213 | 0.00045 | 8.687e-03 | 2026-06-06 03:00 |
| SAND-USDT | high | 33 | 0.00037 | 7.132e-03 | 2026-06-06 03:00 |
| SAND-USDT | low | 15 | 0.00021 | 4.161e-03 | 2026-06-19 08:00 |
| SAND-USDT | close | 0 | 0 | 0 |  |
| SAND-USDT | volume_base | 0 | 0 | 0 |  |
| SAND-USDT | volume_quote | 0 | 0 | 0 |  |
| SOL-USDT | open | 0 | 0 | 0 |  |
| SOL-USDT | high | 0 | 0 | 0 |  |
| SOL-USDT | low | 0 | 0 | 0 |  |
| SOL-USDT | close | 0 | 0 | 0 |  |
| SOL-USDT | volume_base | 0 | 0 | 0 |  |
| SOL-USDT | volume_quote | 0 | 0 | 0 |  |

## Rule B: traded minutes only

| pair | column | mismatches | max abs diff | max rel diff | worst hour UTC (archive vs verified) |
|---|---|---|---|---|---|
| BTC-USDT | open | 0 | 0 | 0 |   |
| BTC-USDT | high | 0 | 0 | 0 |   |
| BTC-USDT | low | 0 | 0 | 0 |   |
| BTC-USDT | close | 0 | 0 | 0 |   |
| BTC-USDT | volume_base | 0 | 0 | 0 |   |
| BTC-USDT | volume_quote | 0 | 0 | 0 |   |
| DOGE-USDT | open | 0 | 0 | 0 |   |
| DOGE-USDT | high | 0 | 0 | 0 |   |
| DOGE-USDT | low | 0 | 0 | 0 |   |
| DOGE-USDT | close | 0 | 0 | 0 |   |
| DOGE-USDT | volume_base | 0 | 0 | 0 |   |
| DOGE-USDT | volume_quote | 0 | 0 | 0 |   |
| ETH-USDT | open | 0 | 0 | 0 |   |
| ETH-USDT | high | 0 | 0 | 0 |   |
| ETH-USDT | low | 0 | 0 | 0 |   |
| ETH-USDT | close | 0 | 0 | 0 |   |
| ETH-USDT | volume_base | 0 | 0 | 0 |   |
| ETH-USDT | volume_quote | 0 | 0 | 0 |   |
| LSK-USDT | open | 0 | 0 | 0 |   |
| LSK-USDT | high | 0 | 0 | 0 |   |
| LSK-USDT | low | 0 | 0 | 0 |   |
| LSK-USDT | close | 0 | 0 | 0 |   |
| LSK-USDT | volume_base | 0 | 0 | 0 |   |
| LSK-USDT | volume_quote | 0 | 0 | 0 |   |
| SAND-USDT | open | 0 | 0 | 0 |   |
| SAND-USDT | high | 0 | 0 | 0 |   |
| SAND-USDT | low | 0 | 0 | 0 |   |
| SAND-USDT | close | 0 | 0 | 0 |   |
| SAND-USDT | volume_base | 0 | 0 | 0 |   |
| SAND-USDT | volume_quote | 0 | 0 | 0 |   |
| SOL-USDT | open | 0 | 0 | 0 |   |
| SOL-USDT | high | 0 | 0 | 0 |   |
| SOL-USDT | low | 0 | 0 | 0 |   |
| SOL-USDT | close | 0 | 0 | 0 |   |
| SOL-USDT | volume_base | 0 | 0 | 0 |   |
| SOL-USDT | volume_quote | 0 | 0 | 0 |   |
