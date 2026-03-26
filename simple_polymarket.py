import json
import math
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from engine import is_safe_category, confidence_score

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

st.set_page_config(page_title="Harvest Scanner", layout="wide")
st.title("🌾 Short-Term Harvest Scanner")
st.markdown("**Near-certainty markets (96%+) — category-filtered, confidence-scored**")

# —————————————————————————

# Sidebar

# —————————————————————————

with st.sidebar:
st.header("⚙️ Settings")
min_prob      = st.slider("Min probability",  0.90, 0.99, 0.96, 0.01)
max_days      = st.slider("Max days left",    1, 14, 7)
min_vol_m     = st.slider("Min volume ($M)",  0.01, 2.0, 0.05, 0.01)
min_conf      = st.slider("Min confidence",   0.0, 1.0, 0.40, 0.05,
help="Combines spread tightness, liquidity, time horizon")
show_rejected = st.checkbox("Show rejected markets", False)
show_stale    = st.checkbox("Show stale markets", False)
st.divider()
st.caption("Confidence = spread tightness + liquidity depth + time horizon + volume")

# —————————————————————————

# Data fetch

# —————————————————————————

@st.cache_data(ttl=60)
def fetch_markets() -> list:
try:
r = requests.get(
GAMMA_URL,
params={
"active":    "true",
"closed":    "false",
"limit":     200,
"order":     "volume",
"ascending": "false",
},
timeout=20,
)
r.raise_for_status()
return r.json()
except Exception as e:
st.error(f"API Error: {e}")
return []

def parse_probability(m: dict):
"""Return (yes_price, no_price, best_prob, best_side) or all-None."""
prices_raw = m.get("outcomePrices", [])
if isinstance(prices_raw, str):
try:
prices_raw = json.loads(prices_raw)
except Exception:
return None, None, None, None

```
prices = []
for p in (prices_raw or []):
    try:
        prices.append(float(p))
    except Exception:
        pass

if len(prices) < 2:
    return None, None, None, None

yes_price, no_price = prices[0], prices[1]
total = yes_price + no_price
if not (0.85 <= total <= 1.15):   # prices must sum to ~1
    return None, None, None, None

best_prob = max(yes_price, no_price)
best_side = "YES" if yes_price >= no_price else "NO"
return yes_price, no_price, best_prob, best_side
```

# —————————————————————————

# Main scan

# —————————————————————————

raw = fetch_markets()
harvest, rejected, stale = [], [], []

for m in raw:
try:
question = str(m.get("question") or “Unknown”)[:140]
volume   = float(m.get("volume",    0) or 0) / 1_000_000
liquidity = float(m.get("liquidity", 0) or 0)

```
    yes_price, no_price, best_prob, best_side = parse_probability(m)
    if best_prob is None:
        continue

    spread = abs(yes_price - no_price)

    days_left = 999
    end_str = m.get("endDate") or m.get("resolutionDate")
    if end_str:
        try:
            end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
        except Exception:
            pass

    # Apply filters
    if best_prob < min_prob or days_left == 0 or days_left > max_days:
        continue
    if volume < min_vol_m:
        continue

    conf = confidence_score(best_prob, spread, volume * 1e6, liquidity, days_left)
    safe, reason = is_safe_category(question)

    implied_return = round((1 - best_prob) / best_prob * 100, 2) if best_prob < 1 else 0.0

    row = {
        "Question":       question,
        "Side":           f"{best_side} @ {best_prob:.1%}",
        "YES price":      f"{yes_price:.1%}",
        "NO price":       f"{no_price:.1%}",
        "Spread":         f"{spread:.1%}",
        "Volume ($M)":    round(volume, 3),
        "Days Left":      days_left,
        "Implied Return": f"+{implied_return:.1f}%",
        "Confidence":     f"{conf:.0%}",
        "Reason":         reason,
    }

    # Wide spread at high prob = stale book
    if best_prob >= 0.96 and spread > 0.08:
        row["Action"] = "🕰️ STALE"
        stale.append(row)
    elif not safe:
        row["Action"] = "🚩 REJECTED"
        rejected.append(row)
    elif conf >= min_conf:
        row["Action"] = "🟢 HARVEST"
        harvest.append(row)
    else:
        row["Action"] = "⚡ LOW CONF"
        rejected.append(row)

except Exception:
    continue
```

# —————————————————————————

# Display

# —————————————————————————

c1, c2, c3, c4 = st.columns(4)
c1.metric("✅ Harvest Ready", len(harvest))
c2.metric("🚩 Filtered Out",  len(rejected))
c3.metric("🕰️ Stale Books",   len(stale))
c4.metric("📊 Total Scanned", len(raw))
st.divider()

if harvest:
st.subheader("🟢 Harvest Opportunities")
df = pd.DataFrame(harvest).sort_values("Volume ($M)", ascending=False)
st.dataframe(
df[["Question", "Side", "YES price", "NO price", "Spread",
"Volume ($M)", "Days Left", "Implied Return", "Confidence", "Action"]],
use_container_width=True, hide_index=True,
)
else:
st.info("No harvest opportunities right now — try adjusting the sidebar filters.")

if show_stale and stale:
st.divider()
st.subheader("🕰️ Stale Order Books (wide spread at high prob)")
st.caption("These show high probability but the spread suggests the book hasn’t been updated.")
st.dataframe(
pd.DataFrame(stale)[[“Question”, “Side”, “Spread”, “Volume ($M)”, “Days Left”, “Action”]],
use_container_width=True, hide_index=True,
)

if show_rejected and rejected:
st.divider()
st.subheader(“🚩 Filtered Out”)
st.dataframe(
pd.DataFrame(rejected)[[“Question”, “Side”, “Volume ($M)”, “Days Left”, “Action”, “Reason”]],
use_container_width=True, hide_index=True,
)

st.caption(
f”Last refreshed: {datetime.now().strftime(’%H:%M:%S’)} · “
“⚠️ Informational only. Not financial advice.")
