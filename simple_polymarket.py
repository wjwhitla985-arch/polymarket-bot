import json, requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from engine import is_safe_category

GAMMA_URL = “https://gamma-api.polymarket.com/markets”

st.set_page_config(page_title=“Harvest Scanner”, layout=“wide”)
st.title(“🌾 Short-Term Harvest Scanner”)
st.markdown(”**Near-certainty markets (96%+) — AI category filtered**”)

with st.sidebar:
st.header(“⚙️ Settings”)
min_prob      = st.slider(“Min probability”, 0.50, 0.99, 0.60, 0.01)
max_days      = st.slider(“Max days left”,   1, 90, 30)
min_vol_m     = st.slider(“Min volume ($M)”, 0.0, 2.0, 0.0, 0.01)
show_rejected = st.checkbox(“Show rejected markets”, True)
show_debug    = st.checkbox(“Show debug info”, True)

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

raw = fetch_markets()

# ── DEBUG: Show raw API response ──────────────────────────────────────────

if show_debug:
st.subheader(“🔍 Debug: Raw API Response”)
st.write(f”Total markets returned by API: **{len(raw)}**”)

```
if raw:
    # Show first market raw structure
    st.write("**First market raw data:**")
    st.json(raw[0])

    # Show sample of probabilities across first 20 markets
    st.write("**Probability snapshot (first 20 markets):**")
    snap = []
    for m in raw[:20]:
        try:
            q = str(m.get("question",""))[:80]
            prices_raw = m.get("outcomePrices", [])
            if isinstance(prices_raw, str):
                prices_raw = json.loads(prices_raw)
            prices = [float(p) for p in (prices_raw or []) if p is not None]
            best   = max(prices) if prices else 0
            vol    = float(m.get("volume", 0) or 0) / 1_000_000
            end    = m.get("endDate") or m.get("resolutionDate") or "unknown"

            days_left = 999
            if end and end != "unknown":
                try:
                    end_dt    = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
                except Exception:
                    pass

            snap.append({
                "Question":  q,
                "Best Prob": f"{best:.1%}",
                "Volume $M": round(vol, 3),
                "Days Left": days_left,
                "End Date":  end[:10] if end else "?",
            })
        except Exception as ex:
            snap.append({"Question": str(m.get("question","?"))[:60], "Error": str(ex)})

    st.dataframe(pd.DataFrame(snap), use_container_width=True, hide_index=True)
else:
    st.error("API returned 0 markets — possible connection issue")
st.divider()
```

# ── Main processing ───────────────────────────────────────────────────────

harvest, rejected, filtered_out = [], [], []

for m in raw:
try:
question   = str(m.get(“question”) or “Unknown”)[:140]
volume     = float(m.get(“volume”, 0) or 0) / 1_000_000
prices_raw = m.get(“outcomePrices”, [])
if isinstance(prices_raw, str):
prices_raw = json.loads(prices_raw)
prices    = [float(p) for p in (prices_raw or []) if p is not None]
if not prices:
continue
best_prob = max(prices)
best_side = “YES” if prices[0] >= prices[1] else “NO”

```
    days_left = 999
    end_str   = m.get("endDate") or m.get("resolutionDate")
    if end_str:
        try:
            end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
        except Exception:
            pass

    # Track why markets are filtered out
    filter_reason = None
    if best_prob < min_prob:
        filter_reason = f"Prob {best_prob:.1%} below {min_prob:.1%}"
    elif days_left > max_days:
        filter_reason = f"Days left {days_left} > {max_days}"
    elif days_left == 0:
        filter_reason = "Already expired"
    elif volume < min_vol_m:
        filter_reason = f"Volume ${volume:.3f}M below ${min_vol_m:.2f}M"

    if filter_reason:
        filtered_out.append({
            "Question":     question[:80],
            "Best Prob":    f"{best_prob:.1%}",
            "Volume ($M)":  round(volume, 3),
            "Days Left":    days_left,
            "Filter Reason": filter_reason,
        })
        continue

    safe, reason   = is_safe_category(question)
    implied_return = round((1 - best_prob) / best_prob * 100, 2) if best_prob < 1 else 0

    row = {
        "Question":       question,
        "Side":           f"{best_side} @ {best_prob:.1%}",
        "Volume ($M)":    round(volume, 3),
        "Days Left":      days_left,
        "Implied Return": f"+{implied_return:.1f}%",
        "Action":         f"🟢 HARVEST {best_side}" if safe else "🚩 REJECTED",
        "Reason":         reason,
    }
    (harvest if safe else rejected).append(row)

except Exception as ex:
    continue
```

# ── Metrics ───────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric(“✅ Harvest Ready”,   len(harvest))
c2.metric(“🚩 AI Rejected”,    len(rejected))
c3.metric(“⏭️ Pre-filtered”,   len(filtered_out))
c4.metric(“📊 Total Scanned”,  len(raw))
st.divider()

# ── Results ───────────────────────────────────────────────────────────────

if harvest:
st.subheader(“🟢 Harvest Opportunities”)
df = pd.DataFrame(harvest).sort_values(“Volume ($M)”, ascending=False)
st.dataframe(df.drop(columns=[“Reason”]), use_container_width=True, hide_index=True)
else:
st.info(“No harvest opportunities passed all filters right now.”)

if show_rejected and rejected:
st.divider()
st.subheader(“🚩 Rejected by Safety Filter”)
st.dataframe(pd.DataFrame(rejected), use_container_width=True, hide_index=True)

if show_debug and filtered_out:
st.divider()
st.subheader(f”⏭️ Pre-filtered out ({len(filtered_out)} markets)”)
st.caption(“These didn’t pass probability/days/volume thresholds”)
st.dataframe(
pd.DataFrame(filtered_out).sort_values(“Best Prob”, ascending=False),
use_container_width=True, hide_index=True
)

st.caption(“⚠️ Informational only. Not financial advice.”)
