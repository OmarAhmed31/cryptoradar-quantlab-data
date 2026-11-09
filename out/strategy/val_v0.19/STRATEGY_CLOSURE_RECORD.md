# Strategy A_N10: closure record (reviewer decision 2026-11-09)

**Reviewer verification:** the v0.19-mini package (25/25 hashes, commit `9e5034f`). Per the one-shot rule, nothing was re-run.

**Official wording (adopted as given):**
> Strategy Plan v0.1.3: PASS against B1, but NOT PROFITABLE in absolute terms. The observed relative performance is primarily defensive and is not evidence of a profitable low-volatility crypto premium.

**Key reviewer finding:**
- The gate compared the strategy with B1 only, not with B3.
- **Cash also beat B1**, by +4.07%/week (p = 0.0017), so passing the gate does not show value above cash.

**Decision (option 1):**
- A_N10 is closed, with its results unchanged.
- It is **not** run as a profit strategy and **not** moved to Forward Shadow.
- The Final Holdout stays sealed.
- **Neither option 2 nor option 3 starts without its own approved plan.**

**Reviewer guidance for future plans (recorded, not yet a plan):**
- **Option 2: an edge inside crypto.** Stablecoins, gold tokens and staking or wrapped tokens are excluded from the universe **before** any computation, selection or analysis. The final test must use data not used for hypotheses or selection: Forward Shadow, or the Holdout through its own opening procedure (never opened automatically).
- **Option 3: risk management.** This is a different project. It needs a new hypothesis that answers:
  - when to exit to stablecoins;
  - when to come back;
  - whether that beats holding cash;
  - what switching costs;
  - what depeg and issuer risk it carries.
- Searching for alpha and searching for loss reduction are **not to be mixed**.
