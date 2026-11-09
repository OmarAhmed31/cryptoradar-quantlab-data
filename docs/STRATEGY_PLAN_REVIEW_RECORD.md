# Strategy Plan Review Record (reviewer decisions 2026-11-09)

**Plan:** `docs/STRATEGY_PLAN_v0.1.3.md`, sha256 `58e63af0…a245`, commit `d8df8cb`. The plan text is unchanged by this record.

## Fee (S5): reviewer decision, binding wording

**Approved for the simulation:**
- **0.10% per side.** It must be described as **a conservative taker assumption based on the observed fee**. The screenshots are **not** said to have proven the taker fee on both sides.
- **The 0.20% per side sensitivity** is kept.
- Nothing else in the plan changes.

**The reviewer's reasoning:**
- The order-details screen proves that the stop-loss **executed as Market**.
- In the trading history, the fee appears on the **"Buy … USDT"** row, and the **"Sell … MET"** row shows a fee of 0.
- So the observed fee row alone does not prove a taker fee on both sides.

**Factual note (author, for the record; it does not change the decision):** in the OKX trading history, one spot sell fill is shown as **two ledger rows** with the same timestamp:
- the base-asset row, "Sell … MET", with fee 0;
- the quote-asset row, "Buy … USDT", where the fee is charged in the received currency.

The arithmetic ties them together: filled 4,574.646 MET × fill price 0.2899 = **1,326.1898754 USDT**, which is exactly the "Buy … USDT" amount. The rows are kept private, and only the identity is recorded here.

## Open point raised by the author BEFORE any simulation (needs the reviewer)

**S7/S6, the gating capital level:**
- The plan reports capacity at $1k, $10k and $100k, but it does not say at which capital level the S3 selection and the S6 gate are evaluated. The 1% cap of DV30_med binds more as capital grows.
- **Proposal:** S3 selection and the S6 gate are evaluated at **$10k**. The gate must **also** hold at **$1k**. $100k is reported only.
- The code is parametrised and computes all three, so whatever the reviewer decides, nothing has to be recomputed. **No result exists yet.**
