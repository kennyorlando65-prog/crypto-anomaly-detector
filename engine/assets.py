"""Tracked asset list.

Kept deliberately small. See the README section "How many assets can this
track?" for the arithmetic behind the default of 8.
"""

from __future__ import annotations

import os

# CoinGecko ids, with the ticker used for display.
DEFAULT_ASSETS: list[dict[str, str]] = [
    {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin"},
    {"id": "ethereum", "symbol": "ETH", "name": "Ethereum"},
    {"id": "solana", "symbol": "SOL", "name": "Solana"},
    {"id": "cardano", "symbol": "ADA", "name": "Cardano"},
    {"id": "ripple", "symbol": "XRP", "name": "XRP"},
    {"id": "dogecoin", "symbol": "DOGE", "name": "Dogecoin"},
    {"id": "chainlink", "symbol": "LINK", "name": "Chainlink"},
    {"id": "polkadot", "symbol": "DOT", "name": "Polkadot"},
]

# Hard ceiling. Above this the free tier cannot refresh inside a useful
# window, so the API refuses rather than silently timing out.
MAX_ASSETS = 25


def tracked_assets() -> list[dict[str, str]]:
    """Return the tracked assets, honouring a comma-separated env override.

    ``TRACKED_ASSETS=bitcoin,ethereum`` narrows or reorders the list without
    a code change. Unknown ids are passed through, because CoinGecko is the
    authority on what exists and it will simply return nothing for a bad id.
    """
    raw = os.environ.get("TRACKED_ASSETS", "").strip()
    if not raw:
        return DEFAULT_ASSETS

    known = {a["id"]: a for a in DEFAULT_ASSETS}
    selected: list[dict[str, str]] = []
    for token in raw.split(","):
        coin_id = token.strip().lower()
        if not coin_id:
            continue
        selected.append(
            known.get(coin_id, {"id": coin_id, "symbol": coin_id.upper()[:6], "name": coin_id.title()})
        )

    return selected[:MAX_ASSETS] if selected else DEFAULT_ASSETS
