"""Crypto-only universe exclusions (Spec v0.1.3 §3; economic nature, fixed before any P1 computation)."""
EXCLUDED = {
    "USDC": "USD stablecoin", "PYUSD": "USD stablecoin", "USDG": "USD stablecoin", "USD1": "USD stablecoin",
    "USAT": "USD stablecoin (verified)", "EURT": "EUR stablecoin", "BRL1": "BRL stablecoin",
    "USTC": "stablecoin by design, de-pegged", "XAUT": "gold-backed", "PAXG": "gold-backed",
    "STETH": "staked/wrapped", "BETH": "staked/wrapped", "JITOSOL": "staked/wrapped", "OKSOL": "staked/wrapped",
    "CGL": "unverified -> excluded until a primary source (U6)",
}


def is_excluded(series):
    return series.split("#")[0].split("-")[0] in EXCLUDED
