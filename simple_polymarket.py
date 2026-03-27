import json
import math
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from engine import is_safe_category, confidence_score_full, get_verdict, harvest_tier, expected_value

GAMMA_URL = “https://gamma-api.polymarket.com/markets”

st.set_page_config(page_title=“Harvest Scanner”, layout=“wide”)
st.title(“Polymarket Harvest Scanner”)
st.markdown(“Scans for high-confidence near-certainty markets. Tier A = tightest spread + shortest horizon.”)

# —————————————————————————

# Sidebar

# —————————————————————————

with st.sidebar:
st.header(“Filters”)
min_prob    = st.slider(“Min probability”,    0.90, 0.99, 0.96, 0.01)
max_days    = st.slider(“Max days left”,      1, 14, 7)
min_vol_k   = st.slider(“Min volume ($K)”,    10, 500, 100) * 1_000
min_liq_k   = st.slider(“Min liquidity ($K)”, 5, 200, 10) * 1_000
max_spread  = st.slider(“Max spread %”,       1, 10, 5) / 100
min_conf    = st.slider(“Min confidence”,     0.0, 1.0, 0.45, 0.05)
tier_filter = st.multiselect(“Tiers to show”, [“A”, “B”, “C”], default=[“A”, “B”])
st.divider()
show_rejected = st.checkbox(“Show rejected”, False)
show_stale    = st.checkbox(“Show stale”,    False)
show_monitor  = st.checkbox(“Show monitor”,  False)
st.divider()
st.caption(
“Confidence = spread tightness + liquidity + time horizon + volume\n\n”
“Tier A: spread <1.5%, <=3 days, deep liquidity\n”
“Tier B: spread <3%, good volume\n”
“Tier C: passes minimum thresholds”
)

# —————————————————————————

# Fetch

# —————————————————————————

@st.cache_data(ttl=60)
def fetch_markets():
try:
r = requests.get(
GAMMA_URL,
params={
“active”:    “true”,
“closed”:    “false”,
“limit”:     300,
“order”:     “volume”,
“ascending”: “false”,
},
timeout=20,
)
r.raise_for_status()
return r.json()
except Exception as e:
st.error(f”API error: {e}”)
return []

# —————————————————————————

# Process

# —————————————————————————

def process(raw):
results = []

```
for m in raw:
    try:
        question  = str(m.get("question") or "").strip()[:160]
        if not question:
            continue

        volume    = float(m.get("volume",    0) or 0)
        liquidity = float(m.get("liquidity", 0) or 0)

        # Parse prices
        prices_raw = m.get("outcomePrices", [])
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)
        prices = [float(p) for p in (prices_raw or []) if p is not None]
        if len(prices) < 2:
            continue

        y, n = prices[0], prices[1]
        if not (0.85 <= y + n <= 1.15):   # must sum to ~1
            continue

        best_prob = max(y, n)
        best_side = "YES" if y >= n else "NO"
        spread    = abs(y - n)

        # Days left
        days_left = 999
        end_str = m.get("endDate") or m.get("resolutionDate")
        if end_str:
            try:
                end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
            except Exception:
                pass

        # Hard filters — cut early to save processing
        if best_prob < min_prob:
            continue
        if days_left == 0 or days_left > max_days:
            continue
        if volume < min_vol_k:
            continue
        if liquidity < min_liq_k:
            continue
        if spread > max_spread:
            continue

        conf  = confidence_score_full(best_prob, spread, volume, liquidity, days_left, question)
        tier  = harvest_tier(best_prob, spread, days_left, volume, liquidity)
        ev    = expected_value(best_prob, conf)
        v     = get_verdict(best_prob, question, {
            "spread":    spread,
            "volume":    volume,
            "liquidity": liquidity,
            "days_left": days_left,
        })

        implied_return = round((1 - best_prob) / best_prob * 100, 2) if best_prob < 1 else 0.0
        ann_yield      = round(implied_return * 365 / days_left, 1) if days_left > 0 else 0.0

        results.append({
            "question":       question,
            "best_prob":      best_prob,
            "best_side":      best_side,
            "spread":         spread,
            "volume":         volume,
            "liquidity":      liquidity,
            "days_left":      days_left,
            "implied_return": implied_return,
            "ann_yield":      ann_yield,
            "confidence":     conf,
            "tier":           tier,
            "ev":             ev,
            "verdict":        v["verdict"],
            "reason":         v["reason"],
            "url":            f"https://polymarket.com/event/{m.get('slug', '')}",
        })

    except Exception:
        continue

return results
```

# —————————————————————————

# Run

# —————————————————————————

with st.spinner(“Fetching markets…”):
raw     = fetch_markets()
all_mkts = process(raw)

harvest  = [m for m in all_mkts if m[“verdict”] == “HARVEST” and m[“tier”] in tier_filter]
value    = [m for m in all_mkts if m[“verdict”] == “VALUE”]
monitor  = [m for m in all_mkts if m[“verdict”] == “MONITOR”]
stale    = [m for m in all_mkts if m[“verdict”] == “STALE”]
rejected = [m for m in all_mkts if m[“verdict”] == “REJECT”]

# Sort harvest: Tier A first, then by EV descending

tier_order = {“A”: 0, “B”: 1, “C”: 2}
harvest_sorted = sorted(harvest, key=lambda x: (tier_order.get(x[“tier”], 9), -x[“ev”]))

# —————————————————————————

# Metrics

# —————————————————————————

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(“Harvest”,       len(harvest))
c2.metric(“Value”,         len(value))
c3.metric(“Stale”,         len(stale))
c4.metric(“Total Scanned”, len(raw))

tier_a = sum(1 for m in harvest if m[“tier”] == “A”)
tier_b = sum(1 for m in harvest if m[“tier”] == “B”)
c5.metric(“Tier A / B”, f”{tier_a} / {tier_b}”)

st.divider()

# —————————————————————————

# Tables

# —————————————————————————

def render(mkts, title):
if not mkts:
return
st.subheader(title)
rows = [{
“Tier”:           m[“tier”],
“Market”:         m[“question”],
“Side”:           f”{m[‘best_side’]} @ {m[‘best_prob’]:.1%}”,
“Spread”:         f”{m[‘spread’]:.1%}”,
“Volume”:         f”${m[‘volume’]/1_000:.0f}K”,
“Liquidity”:      f”${m[‘liquidity’]/1_000:.0f}K”,
“Days”:           m[“days_left”],
“Return”:         f”+{m[‘implied_return’]:.1f}%”,
“Ann. Yield”:     f”+{m[‘ann_yield’]:.0f}%/yr”,
“Confidence”:     f”{m[‘confidence’]:.0%}”,
“EV”:             f”{m[‘ev’]:+.1f}%”,
“Trade”:          m[“url”],
} for m in mkts]
st.dataframe(
pd.DataFrame(rows),
use_container_width=True,
hide_index=True,
column_config={“Trade”: st.column_config.LinkColumn(“Trade”)},
)

render(harvest_sorted, “Harvest Opportunities”)

if not harvest_sorted:
st.info(“No harvest opportunities right now. Try loosening the sidebar filters.”)

render(value, “Value Plays”)

if show_monitor:
st.divider()
render(monitor, “Monitor”)

if show_stale:
st.divider()
render(stale, “Stale Order Books”)

if show_rejected:
st.divider()
render(rejected, “Rejected”)

st.divider()

# —————————————————————————

# Guide

# —————————————————————————

with st.expander(“How to read this”):
st.markdown(”””
**Tier A** — Best quality. Spread under 1.5%, resolves within 3 days, deep liquidity.
Trade these first.

**Tier B** — Good quality. Spread under 3%, solid volume. Still worth trading.

**Tier C** — Passes minimum filters but lower conviction. Trade cautiously or skip.

**Spread** — The gap between YES and NO prices. Tighter = more confident market.
Above 5% at 96% probability means the book is stale or uncertain.

**Confidence** — Combined score: spread tightness + liquidity + time horizon + volume.
Aim for 60%+ for real conviction.

**EV** — Expected value adjusted for confidence. Positive = edge exists.

**Ann. Yield** — Annualises the implied return. Useful for comparing a 1-day 2% vs a 7-day 2%.

**Not financial advice.**
“””)

st.caption(f”Last refreshed: {datetime.now().strftime(’%H:%M:%S’)} | Polymarket Gamma API”)