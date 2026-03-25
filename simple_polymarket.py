import json, requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from engine import is_safe_category

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

st.set_page_config(page_title=“Harvest Scanner”, layout=“wide”)
st.title(“🌾 Short-Term Harvest Scanner”)
st.markdown(”**Near-certainty markets (96%+) — AI category filtered**”)

with st.sidebar:
st.header(“⚙️ Settings”)
min_prob      = st.slider(“Min probability”, 0.50, 0.99, 0.96, 0.01)
max_days      = st.slider(“Max days left”,   1, 90, 7)
min_vol_m     = st.slider(“Min volume ($M)”, 0.0, 2.0, 0.05, 0.01)
show_rejected = st.checkbox(“Show rejected markets”, False)
show_debug    = st.checkbox(“Show debug info”, False)

@st.cache_data(ttl=60)
def fetch_markets():
try:
r = requests.get(GAMMA_URL, params={
“active”: “true”, “closed”: “false”,
“limit”: 200, “order”: “volume”, “ascending”: “false”,
}, timeout=20)
r.raise_for_status()
return r.json()
except Exception as e:
st.error(f”API Error: {e}”)
return []

def parse_probability(m):
“””
Correctly parse YES and NO prices from a Polymarket market.
outcomePrices = [yes_price, no_price]
YES price + NO price should always sum to ~1.0

```
The BEST side is whichever outcome has the higher probability.
A market at YES=0.02, NO=0.98 means NO is 98% likely — trade NO.
"""
prices_raw = m.get("outcomePrices", [])
if isinstance(prices_raw, str):
    try:
        prices_raw = json.loads(prices_raw)
    except Exception:
        prices_raw = []

prices = []
for p in (prices_raw or []):
    try:
        prices.append(float(p))
    except Exception:
        pass

if len(prices) < 2:
    return None, None, None, None

yes_price = prices[0]
no_price  = prices[1]

# Sanity check prices sum to ~1
total = yes_price + no_price
if total < 0.5 or total > 1.5:
    return None, None, None, None

if yes_price >= no_price:
    return yes_price, no_price, yes_price, "YES"
else:
    return yes_price, no_price, no_price, "NO"
```

raw = fetch_markets()

if show_debug and raw:
st.subheader(“🔍 Debug: First 10 Markets (with correct YES/NO prices)”)
snap = []
for m in raw[:10]:
yp, np_, bp, bs = parse_probability(m)
end_str = m.get(“endDate”) or m.get(“resolutionDate”) or “”
days_left = 999
if end_str:
try:
end_dt    = datetime.fromisoformat(end_str.replace(“Z”, “+00:00”))
days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
except Exception:
pass
snap.append({
“Question”:  str(m.get(“question”,””))[:70],
“YES price”: f”{yp:.1%}” if yp is not None else “?”,
“NO price”:  f”{np_:.1%}” if np_ is not None else “?”,
“Best side”: f”{bs} @ {bp:.1%}” if bp is not None else “?”,
“Days left”: days_left,
“Vol $M”:    round(float(m.get(“volume”,0) or 0)/1e6, 3),
})
st.dataframe(pd.DataFrame(snap), use_container_width=True, hide_index=True)
st.divider()

harvest, rejected = [], []

for m in raw:
try:
question = str(m.get(“question”) or “Unknown”)[:140]
volume   = float(m.get(“volume”, 0) or 0) / 1_000_000

```
    yes_price, no_price, best_prob, best_side = parse_probability(m)
    if best_prob is None:
        continue

    days_left = 999
    end_str   = m.get("endDate") or m.get("resolutionDate")
    if end_str:
        try:
            end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
        except Exception:
            pass

    if best_prob < min_prob:
        continue
    if days_left > max_days or days_left == 0:
        continue
    if volume < min_vol_m:
        continue

    safe, reason   = is_safe_category(question)
    implied_return = round((1 - best_prob) / best_prob * 100, 2)

    row = {
        "Question":       question,
        "Side":           f"{best_side} @ {best_prob:.1%}",
        "YES price":      f"{yes_price:.1%}",
        "NO price":       f"{no_price:.1%}",
        "Volume ($M)":    round(volume, 3),
        "Days Left":      days_left,
        "Implied Return": f"+{implied_return:.1f}%",
        "Action":         f"🟢 HARVEST {best_side}" if safe else "🚩 REJECTED",
        "Reason":         reason,
    }
    (harvest if safe else rejected).append(row)

except Exception:
    continue
```

c1, c2, c3 = st.columns(3)
c1.metric(“✅ Harvest Ready”,  len(harvest))
c2.metric(“🚩 AI Rejected”,   len(rejected))
c3.metric(“📊 Total Scanned”, len(raw))
st.divider()

if harvest:
st.subheader(“🟢 Harvest Opportunities”)
df = pd.DataFrame(harvest).sort_values(“Volume ($M)”, ascending=False)
st.dataframe(
df[[“Question”,“Side”,“YES price”,“NO price”,“Volume ($M)”,“Days Left”,“Implied Return”,“Action”]],
use_container_width=True, hide_index=True
)
else:
st.info(“No harvest opportunities right now — check back when markets are near resolution.”)

if show_rejected and rejected:
st.divider()
st.subheader(“🚩 Rejected by Safety Filter”)
st.dataframe(
pd.DataFrame(rejected)[[“Question”,“Side”,“Volume ($M)”,“Days Left”,“Action”,“Reason”]],
use_container_width=True, hide_index=True
)

st.caption(f”Last refreshed: {datetime.now().strftime(’%H:%M:%S’)} · ⚠️ Informational only. Not financial advice.”)
