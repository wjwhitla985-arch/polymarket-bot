import re
import math

# —————————————————————————

# Category safety filter — regex word boundaries to avoid false positives

# —————————————————————————

_REJECT_PATTERNS = []

_RAW_REJECT = [
(r”\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|doge|crypto)\b”,     “crypto price”),
(r”\bhit\s+$\d”,                                                   “price target”),
(r”\b(reach|above|below|exceed|break)\s+$\d”,                     “price level”),
(r”\bdip\s+to\b”,                                                   “price dip”),
(r”\b(invade|invasion|ceasefire|troops|airstrike|missile)\b”,      “military event”),
(r”\bnuclear\s+(weapon|strike|test|launch)\b”,                     “nuclear event”),
(r”\b(declare|declared)\s+war\b”,                                  “war declaration”),
(r”\b(convicted|acquitted|guilty|not\s+guilty)\b”,                “criminal verdict”),
(r”\b(sentenced|sentencing)\b”,                                    “sentencing”),
(r”\bsupreme\s+court\s+rule”,                                      “supreme court”),
(r”\b(championship|super bowl|world cup|nba finals|stanley cup)\s+winner\b”, “championship”),
(r”\b(tweet|tweets|post)\s+on\s+(twitter|x.com|instagram)\b”,    “social post”),
(r”\bnet\s+worth\b”,                                               “net worth”),
(r”\bnumber\s+of\s+(followers|subscribers)\b”,                    “follower count”),
# Sports match results — high variance, last-second swings
(r”\b(win|beat|defeat)\s+.{0,30}\b(match|game|series|final)\b”,   “sports result”),
]

for _pat, _label in _RAW_REJECT:
_REJECT_PATTERNS.append((re.compile(_pat, re.IGNORECASE), _label))

# —————————————————————————

# Resolution reliability — some question types resolve far more consistently

# —————————————————————————

_HIGH_RELIABILITY = [
re.compile(r, re.IGNORECASE) for r in [
r”\bwill .+ (be|remain) (above|below|at|over|under) .+ (on|by|before|at) \w+ \d{1,2}”,
r”\bwill .+ (gdp|cpi|inflation|unemployment|rate|index) .+ (above|below|exceed)”,
r”\bwill .+ (win|lose) .+ (election|primary|vote|referendum)”,
r”\bwill .+ (pass|fail|approve|reject) .+ (bill|act|legislation|measure)”,
r”\bwill .+ (report|release|publish) .+ (earnings|results|data)”,
r”\bwill .+ (ipo|list|merge|acquire)”,
r”\bwill .+ remain (president|prime minister|ceo|chair)”,
]
]

_LOW_RELIABILITY = [
re.compile(r, re.IGNORECASE) for r in [
r”\btweet\b”,
r”\bsay\b.{0,20}\b(statement|interview|speech)\b”,
r”\bby (end of|close of) (day|week|month)\b”,
r”\bbefore (midnight|noon|eod)\b”,
]
]

def resolution_reliability(question: str) -> float:
“””
Returns a [0.7, 1.0] multiplier based on how reliably this type
of question resolves. High-reliability categories (economic data,
elections, earnings) score near 1.0. Vague or social questions lower.
“””
for pattern in _HIGH_RELIABILITY:
if pattern.search(question):
return 1.0
for pattern in _LOW_RELIABILITY:
if pattern.search(question):
return 0.72
return 0.88   # default

# —————————————————————————

# Category safety check

# —————————————————————————

def is_safe_category(question: str) -> tuple:
for pattern, label in _REJECT_PATTERNS:
if pattern.search(question):
return False, f”Rejected: {label} category”
return True, “OK”

# —————————————————————————

# Confidence scoring

# —————————————————————————

def confidence_score(market_prob: float, spread: float, volume: float,
liquidity: float, days_left: int) -> float:
“””
[0, 1] quality score. Higher = more trustworthy market price.
Weights: spread tightness (35%), liquidity (25%), time (25%), volume (15%)
“””
spread_score = max(0.0, 1.0 - spread / 0.08)   # 0% spread=1.0, 8%=0.0
liq_score    = min(1.0, math.log1p(liquidity)  / math.log1p(500_000))
time_score   = max(0.0, 1.0 - (days_left - 1) / 14)
vol_score    = min(1.0, math.log1p(volume)     / math.log1p(500_000))

```
raw = (0.35 * spread_score +
       0.25 * liq_score +
       0.25 * time_score +
       0.15 * vol_score)

# Multiply by resolution reliability
reliability = resolution_reliability("")   # overridden externally
return round(raw, 3)
```

def confidence_score_full(market_prob: float, spread: float, volume: float,
liquidity: float, days_left: int,
question: str = “”) -> float:
spread_score = max(0.0, 1.0 - spread / 0.08)
liq_score    = min(1.0, math.log1p(liquidity)  / math.log1p(500_000))
time_score   = max(0.0, 1.0 - (days_left - 1) / 14)
vol_score    = min(1.0, math.log1p(volume)     / math.log1p(500_000))

```
raw = (0.35 * spread_score +
       0.25 * liq_score +
       0.25 * time_score +
       0.15 * vol_score)

reliability = resolution_reliability(question)
return round(raw * reliability, 3)
```

# —————————————————————————

# Expected value — the number that actually matters

# —————————————————————————

def expected_value(market_prob: float, confidence: float) -> float:
“””
EV of buying the winning side at market_prob price.
Payout = 1.0, cost = market_prob.
Adjusted by our confidence in the market price being accurate.

```
EV = (confidence * 1.0) + ((1 - confidence) * 0) - market_prob
   = confidence - market_prob

Expressed as % of stake.
"""
ev = (confidence * 1.0 - market_prob) / market_prob * 100
return round(ev, 2)
```

# —————————————————————————

# Harvest quality tier

# —————————————————————————

def harvest_tier(market_prob: float, spread: float, days_left: int,
volume: float, liquidity: float) -> str:
“””
A  — very tight spread (<1.5%), short horizon (<=3 days), deep liquidity
B  — tight spread (<3%), medium horizon, good volume
C  — passes minimum thresholds but lower conviction
“””
tight   = spread < 0.015
medium  = spread < 0.030
short   = days_left <= 3
liquid  = liquidity >= 50_000
big_vol = volume    >= 200_000

```
if tight and short and liquid:
    return "A"
if medium and (short or liquid) and big_vol:
    return "B"
return "C"
```

# —————————————————————————

# Verdict

# —————————————————————————

def get_verdict(market_prob: float, question: str = “”,
market_stats: dict = None) -> dict:
safe, cat_reason = is_safe_category(question)
if not safe:
return {
“verdict”: “REJECT”, “signal”: “REJECTED”,
“reason”: cat_reason, “confidence”: 0.0, “ev”: 0.0, “tier”: “-”,
}

```
stats     = market_stats or {}
spread    = float(stats.get("spread",    0.0))
volume    = float(stats.get("volume",    0.0))
liquidity = float(stats.get("liquidity", 0.0))
days_left = int(stats.get("days_left",   999))

conf = confidence_score_full(market_prob, spread, volume, liquidity,
                             days_left, question)
ev   = expected_value(market_prob, conf)
tier = harvest_tier(market_prob, spread, days_left, volume, liquidity)

# Stale book: high prob but spread too wide
if market_prob >= 0.96 and spread > 0.08:
    return {
        "verdict": "STALE", "signal": "STALE",
        "reason": f"Wide spread ({spread:.1%}) at high prob — stale book",
        "confidence": conf, "ev": ev, "tier": tier,
    }

if market_prob >= 0.96 and conf >= 0.45:
    return {
        "verdict": "HARVEST", "signal": "HARVEST",
        "reason": f"Near-certainty | conf {conf:.0%} | tier {tier}",
        "confidence": conf, "ev": ev, "tier": tier,
    }

if market_prob >= 0.90 and conf >= 0.55 and ev > 2.0:
    return {
        "verdict": "VALUE", "signal": "VALUE",
        "reason": f"Good edge | conf {conf:.0%} | EV {ev:+.1f}%",
        "confidence": conf, "ev": ev, "tier": tier,
    }

return {
    "verdict": "MONITOR", "signal": "MONITOR",
    "reason": f"Insufficient confidence ({conf:.0%}) or EV ({ev:+.1f}%)",
    "confidence": conf, "ev": ev, "tier": tier,
}
```