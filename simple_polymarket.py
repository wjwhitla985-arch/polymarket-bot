import json, requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from engine import is_safe_category

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

st.set_page_config(page_title="Harvest Scanner", layout="wide")
st.title("🌾 Short-Term Harvest Scanner")
st.markdown("**Near-certainty markets (96%+) — AI category filtered**")

with st.sidebar:
    st.header("⚙️ Settings")
    min_prob      = st.slider("Min probability", 0.90, 0.99, 0.96, 0.01)
    max_days      = st.slider("Max days left",   1, 14, 7)
    min_vol_m     = st.slider("Min volume ($M)", 0.01, 2.0, 0.05, 0.01)
    show_rejected = st.checkbox("Show rejected markets", False)

@st.cache_data(ttl=60)
def fetch_markets():
    try:
        r = requests.get(GAMMA_URL, params={
            "active": "true", "closed": "false",
            "limit": 200, "order": "volume", "ascending": "false",
        }, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

raw = fetch_markets()
harvest, rejected = [], []

for m in raw:
    try:
        question   = str(m.get("question") or "Unknown")[:140]
        volume     = float(m.get("volume", 0) or 0) / 1_000_000
        prices_raw = m.get("outcomePrices", [])
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)
        prices    = [float(p) for p in (prices_raw or []) if p is not None]
        if not prices:
            continue
        best_prob = max(prices)
        best_side = "YES" if prices[0] >= prices[1] else "NO"

        days_left = 999
        end_str   = m.get("endDate") or m.get("resolutionDate")
        if end_str:
            try:
                end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
            except Exception:
                pass

        if not (best_prob >= min_prob and 0 < days_left <= max_days and volume >= min_vol_m):
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
    except Exception:
        continue

c1, c2, c3 = st.columns(3)
c1.metric("✅ Harvest Ready",  len(harvest))
c2.metric("🚩 AI Rejected",   len(rejected))
c3.metric("📊 Total Scanned", len(raw))
st.divider()

if harvest:
    st.subheader("🟢 Harvest Opportunities")
    df = pd.DataFrame(harvest).sort_values("Volume ($M)", ascending=False)
    st.dataframe(df.drop(columns=["Reason"]), use_container_width=True, hide_index=True)
else:
    st.info("No opportunities found. Try adjusting the sidebar filters.")

if show_rejected and rejected:
    st.divider()
    st.subheader("🚩 Rejected by Safety Filter")
    st.dataframe(pd.DataFrame(rejected), use_container_width=True, hide_index=True)

st.caption("⚠️ Informational only. Not financial advice.")
