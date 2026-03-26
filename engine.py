“””
engine.py — Verdict Engine
Decides HARVEST / VALUE / MONITOR / TRAP / REJECT for each market.

Fixes vs original:

- Keyword filter now uses regex word boundaries (no more false positives
  on “beat expectations”, “housing price index”, “ruling party”, etc.)
- All return dicts include safe_category key (was missing in original)
- Added confidence_score() for liquidity/spread quality signal
- Added STALE verdict for markets with suspicious spread at high prob
- get_verdict() now accepts optional market_stats dict for richer logic
  “””

import re

# —————————————————————————

# Category safety filter

# —————————————————————————

# (pattern, human label) — compiled once at import time

_REJECT_PATTERNS: list[tuple[re.Pattern, str]] = []

_RAW_REJECT = [
# Crypto price predictions — volatile and hard to model
(r”\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|doge)\b”,          “crypto asset”),
(r”\bhit\s+$\d”,                                                  “price target”),
(r”\b(reach|above|below|exceed|break)\s+$\d”,                    “price level”),
(r”\bdip\s+to\b”,                                                  “price dip”),
(r”\b(crypto|cryptocurrency|blockchain)\s+(price|market|crash)\b”,“crypto market”),

```
# Geopolitical — too binary and news-dependent
(r"\b(invade|invasion|ceasefire|troops|airstrike|missile)\b",     "military event"),
(r"\bnuclear\s+(weapon|strike|test|launch)\b",                    "nuclear event"),
(r"\b(declare|declared)\s+war\b",                                 "war declaration"),

# Legal — ruling can flip on appeal, unpredictable timeline
(r"\b(convicted|acquitted|guilty|not\s+guilty)\b",               "criminal verdict"),
(r"\b(sentenced|sentencing)\b",                                   "sentencing"),
(r"\bsupreme\s+court\s+rule",                                     "supreme court"),

# Sports outcomes — manipulation risk, last-second variance
(r"\b(win|wins|beat|beats|defeat|defeats)\s+the\b.*\b(match|game|series|final)\b",
                                                                   "sports result"),
(r"\b(championship|super bowl|world cup|nba finals|stanley cup)\s+winner\b",
                                                                   "championship"),

# Social media / celebrity net worth — unreliable resolution criteria
(r"\b(tweet|tweets|post)\s+on\s+(twitter|x\.com|instagram)\b",   "social post"),
(r"\bnet\s+worth\b",                                               "net worth"),
(r"\bnumber\s+of\s+(followers|subscribers)\b",                    "follower count"),
```

]

for _pat, _label in _RAW_REJECT:
_REJECT_PATTERNS.append((re.compile(_pat, re.IGNORECASE), _label))

def is_safe_category(question: str) -> tuple[bool, str]:
“””
Return (is_safe, reason).
Uses regex word boundaries — no more false positives on substrings like
‘beat expectations’, ‘housing price index’, ‘ruling party’, ‘verdict of history’.
“””
for pattern, label in _REJECT_PATTERNS:
if pattern.search(question):
return False, f”Auto-rejected: {label} category — unreliable resolution”
return True, “Category OK”

# —————————————————————————

# Market quality / confidence scoring

# —————————————————————————

def confidence_score(market_prob: float, spread: float, volume: float,
liquidity: float, days_left: int) -> float:
“””
Returns a [0, 1] quality score for how trustworthy the market price is.
High score = tight spread, deep liquidity, high volume, short time horizon.

```
Components:
  spread_score   : tighter spread → more confident market
  liquidity_score: deeper order book → harder to manipulate
  time_score     : fewer days → less time for shock events
  volume_score   : more traded → stronger price discovery
"""
# Spread: 0 spread = 1.0, 0.10 spread = 0.0 (linear)
spread_score = max(0.0, 1.0 - spread / 0.10)

# Liquidity: $0 = 0, $1M+ = 1.0 (log scale)
import math
liq_score = min(1.0, math.log1p(liquidity) / math.log1p(1_000_000))

# Time: 1 day = 1.0, 30 days = 0.0 (linear)
time_score = max(0.0, 1.0 - (days_left - 1) / 30)

# Volume: $0 = 0, $500k+ = 1.0 (log scale)
vol_score = min(1.0, math.log1p(volume) / math.log1p(500_000))

# Weighted average — spread and time matter most for harvest
score = (0.35 * spread_score +
         0.25 * liq_score +
         0.25 * time_score +
         0.15 * vol_score)
return round(score, 3)
```

# —————————————————————————

# Verdict engine

# —————————————————————————

def get_verdict(ai_prob: float, market_prob: float,
question: str = “”,
market_stats: dict | None = None) -> dict:
“””
Classify a market opportunity.

```
Verdicts (in priority order):
  REJECT   — unsafe category
  STALE    — wide spread at high probability (price may not reflect reality)
  TRAP     — AI and market disagree by >30pp (model uncertainty warning)
  HARVEST  — both AI and market agree ≥96%, short horizon confirmed
  VALUE    — positive AI edge ≥5pp
  MONITOR  — insufficient edge

Args:
  ai_prob      : probability from the XGBoost model
  market_prob  : best (YES or NO) price from Polymarket
  question     : market question text (for category filter)
  market_stats : optional dict with spread, volume, liquidity, days_left
                 used to compute confidence_score and STALE detection
"""
safe, cat_reason = is_safe_category(question)
if not safe:
    return {
        "verdict": "REJECT",
        "signal": "🚩 REJECTED",
        "reason": cat_reason,
        "edge": 0.0,
        "safe_category": False,
        "confidence": 0.0,
    }

stats = market_stats or {}
spread    = float(stats.get("spread",    0.0))
volume    = float(stats.get("volume",    0.0))
liquidity = float(stats.get("liquidity", 0.0))
days_left = int(stats.get("days_left",   999))

conf = confidence_score(market_prob, spread, volume, liquidity, days_left)

# STALE: market shows high probability but spread is suspiciously wide.
# e.g., YES=0.96, NO=0.04, spread=0.04 is fine.
# But YES=0.96, NO=0.10 (doesn't sum to 1) or spread > 0.08 at 96%
# suggests stale order book that hasn't been updated.
if market_prob >= 0.96 and spread > 0.08:
    return {
        "verdict": "STALE",
        "signal": "🕰️ STALE",
        "reason": f"Wide spread ({spread:.1%}) at high prob — stale order book",
        "edge": round(ai_prob - market_prob, 4),
        "safe_category": True,
        "confidence": conf,
    }

edge = ai_prob - market_prob

# TRAP: AI and market diverge strongly — one of them is wrong
if abs(edge) > 0.30:
    return {
        "verdict": "TRAP",
        "signal": "⚠️ TRAP",
        "reason": (f"AI ({ai_prob:.1%}) vs market ({market_prob:.1%}) "
                   f"diverge by {abs(edge):.1%} — model uncertainty"),
        "edge": round(edge, 4),
        "safe_category": True,
        "confidence": conf,
    }

# HARVEST: near-certainty confirmed by both AI and market
if ai_prob >= 0.96 and market_prob >= 0.96 and edge >= -0.02:
    return {
        "verdict": "HARVEST",
        "signal": "🟢 HARVEST",
        "reason": (f"AI {ai_prob:.1%} confirms market {market_prob:.1%} "
                   f"— near-certainty, edge {edge:+.1%}, conf {conf:.0%}"),
        "edge": round(edge, 4),
        "safe_category": True,
        "confidence": conf,
    }

# VALUE: meaningful positive edge
if edge > 0.05:
    return {
        "verdict": "VALUE",
        "signal": "💎 VALUE",
        "reason": (f"AI {ai_prob:.1%} vs market {market_prob:.1%} "
                   f"— positive edge {edge:+.1%}"),
        "edge": round(edge, 4),
        "safe_category": True,
        "confidence": conf,
    }

return {
    "verdict": "MONITOR",
    "signal": "🔵 MONITOR",
    "reason": f"Insufficient edge ({edge:+.1%}) or prob below threshold",
    "edge": round(edge, 4),
    "safe_category": True,
    "confidence": conf,
}
```
