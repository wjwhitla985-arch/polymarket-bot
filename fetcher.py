“””
fetcher.py — Polymarket Data Fetcher
Fetches and parses live market data from the Polymarket Gamma API.

Enhancements vs original:

- Extracts spread and liquidity alongside volume
- Computes vol_per_day (activity intensity signal)
- Validates YES + NO prices sum to ~1.0 (rejects stale books)
- Returns token IDs for both sides (needed for CLOB execution)
- Market age tracking (days since creation)
- Distinguishes endDate vs resolutionDate priority
  “””

import json
import math
import requests
from datetime import datetime, timezone

GAMMA_URL = “https://gamma-api.polymarket.com/markets”

def fetch_markets(limit: int = 200, order: str = “volume”) -> list:
“””
Fetch active, open markets from the Gamma API.
order: ‘volume’ | ‘liquidity’ | ‘endDate’
“””
try:
r = requests.get(
GAMMA_URL,
params={
“active”:     “true”,
“closed”:     “false”,
“limit”:      limit,
“order”:      order,
“ascending”:  “false”,
},
timeout=20,
)
r.raise_for_status()
return r.json()
except requests.RequestException as e:
print(f”[fetcher] API error: {e}”)
return []

def fetch_resolved_markets(limit: int = 500) -> list:
“”“Fetch resolved (closed) markets for model training.”””
try:
r = requests.get(
GAMMA_URL,
params={
“active”:    “false”,
“closed”:    “true”,
“limit”:     limit,
“order”:     “volume”,
“ascending”: “false”,
},
timeout=30,
)
r.raise_for_status()
return r.json()
except requests.RequestException as e:
print(f”[fetcher] Resolved API error: {e}”)
return []

def _parse_prices(m: dict) -> tuple[float | None, float | None]:
“””
Return (yes_price, no_price) or (None, None) on failure.
Validates that prices sum to approximately 1.0.
“””
prices_raw = m.get(“outcomePrices”, [])
if isinstance(prices_raw, str):
try:
prices_raw = json.loads(prices_raw)
except Exception:
return None, None

```
prices = []
for p in (prices_raw or []):
    try:
        prices.append(float(p))
    except Exception:
        pass

if len(prices) < 2:
    return None, None

yes_price, no_price = prices[0], prices[1]

# Reject books where prices don't sum to ~1 (stale / misconfigured)
total = yes_price + no_price
if not (0.85 <= total <= 1.15):
    return None, None

return yes_price, no_price
```

def _parse_days(m: dict) -> int:
“”“Days until market resolution from now. Returns 999 if unknown.”””
end_str = m.get(“endDate”) or m.get(“resolutionDate”)
if not end_str:
return 999
try:
end_dt = datetime.fromisoformat(end_str.replace(“Z”, “+00:00”))
return max(0, (end_dt - datetime.now(timezone.utc)).days)
except Exception:
return 999

def _parse_age_days(m: dict) -> int:
“”“Days since market was created. Returns 0 if unknown.”””
start_str = m.get(“createdAt”) or m.get(“startDate”)
if not start_str:
return 0
try:
start_dt = datetime.fromisoformat(start_str.replace(“Z”, “+00:00”))
return max(0, (datetime.now(timezone.utc) - start_dt).days)
except Exception:
return 0

def parse_market(m: dict) -> dict | None:
“””
Parse a raw Gamma API market dict into a clean feature dict.
Returns None if the market is malformed or prices are invalid.
“””
try:
question = str(m.get(“question”) or “”).strip()
if not question:
return None

```
    yes_price, no_price = _parse_prices(m)
    if yes_price is None:
        return None

    best_prob = max(yes_price, no_price)
    best_side = "YES" if yes_price >= no_price else "NO"
    spread    = abs(yes_price - no_price)

    volume    = float(m.get("volume",    0) or 0)
    liquidity = float(m.get("liquidity", 0) or 0)

    days_left = _parse_days(m)
    age_days  = _parse_age_days(m)

    # Activity intensity: how much is trading per day of the market's life
    vol_per_day = volume / max(age_days, 1)

    # Liquidity depth ratio: how much cushion exists relative to volume
    liq_ratio = liquidity / (volume + 1)

    # Log-volume for model features
    log_volume = math.log1p(volume)

    # Token IDs for CLOB execution
    tokens   = m.get("tokens") or []
    yes_tok  = tokens[0].get("token_id") if len(tokens) > 0 else None
    no_tok   = tokens[1].get("token_id") if len(tokens) > 1 else None
    best_tok = yes_tok if best_side == "YES" else no_tok

    slug = m.get("slug") or str(m.get("id", ""))

    return {
        "question":    question,
        "slug":        slug,
        "url":         f"https://polymarket.com/event/{slug}",
        "yes_price":   round(yes_price,  4),
        "no_price":    round(no_price,   4),
        "best_prob":   round(best_prob,  4),
        "best_side":   best_side,
        "spread":      round(spread,     4),
        "volume":      round(volume,     2),
        "liquidity":   round(liquidity,  2),
        "days_left":   days_left,
        "age_days":    age_days,
        "vol_per_day": round(vol_per_day, 2),
        "liq_ratio":   round(liq_ratio,   4),
        "log_volume":  round(log_volume,  4),
        "yes_token_id": yes_tok,
        "no_token_id":  no_tok,
        "best_token_id": best_tok,
    }
except Exception as e:
    print(f"[fetcher] parse_market error: {e}")
    return None
```

def fetch_and_parse(
min_prob: float   = 0.95,
max_days: int     = 7,
min_volume: float = 50_000,
min_liquidity: float = 1_000,
limit: int        = 200,
) -> list[dict]:
“””
High-level convenience: fetch live markets and apply quality filters.
Fetches by volume AND liquidity order to get a fuller picture.
“””
seen = set()
markets = []

```
for order in ("volume", "liquidity"):
    raw = fetch_markets(limit=limit, order=order)
    for raw_m in raw:
        mid = raw_m.get("id") or raw_m.get("slug")
        if mid in seen:
            continue
        seen.add(mid)

        m = parse_market(raw_m)
        if not m:
            continue
        if (
            m["best_prob"]  >= min_prob
            and 0 < m["days_left"] <= max_days
            and m["volume"]    >= min_volume
            and m["liquidity"] >= min_liquidity
            and m["best_token_id"]
        ):
            markets.append(m)

return markets
```
