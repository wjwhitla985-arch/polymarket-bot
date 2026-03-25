# #!/usr/bin/env python3
“””
setup.py — Polymarket Harvest Bot — One-Click Project Builder

Run this ONE file and it creates the entire project structure.

Usage:
1. Save this file as setup.py anywhere on your PC
2. Open Command Prompt / Terminal
3. Run: python setup.py
4. A folder called ‘Polymarket-bot’ will appear with everything inside

Then:
cd Polymarket-bot
pip install -r requirements.txt
python retrain.py
streamlit run polymarket_dashboard.py
“””

import os
import sys

PROJECT = “Polymarket-bot”

FILES = {}

# ════════════════════════════════════════════════════════════════

# engine.py

# ════════════════════════════════════════════════════════════════

FILES[“engine.py”] = ‘’’”””
engine.py — Verdict Engine
Decides HARVEST / VALUE / MONITOR / TRAP / REJECT for each market.
Category safety filter blocks crypto prices, wars, legal, sports.
“””

REJECT_KEYWORDS = [
“bitcoin”, “btc”, “ethereum”, “eth”, “crypto”, “price”, “hit $”,
“reach $”, “above $”, “below $”, “dip to”,
“strike”, “invade”, “ceasefire”, “war”, “military”, “troops”,
“nuclear”, “missiles”, “attack”,
“convicted”, “sentenced”, “guilty”, “verdict”, “ruling”, “lawsuit”,
“win the match”, “beat “, “championship winner”, “super bowl winner”,
“world cup winner”, “tweet”, “post on”, “elon musk net worth”,
]

def is_safe_category(question: str) -> tuple:
q = question.lower()
for kw in REJECT_KEYWORDS:
if kw in q:
return False, f”Auto-rejected: contains '{kw}' — unreliable category”
return True, “Category OK”

def get_verdict(ai_prob: float, market_prob: float, question: str = “”) -> dict:
safe, cat_reason = is_safe_category(question)
if not safe:
return {“verdict”: “REJECT”, “signal”: “🚩 REJECTED”, “reason”: cat_reason, “edge”: 0.0, “safe_category”: False}

```
edge = ai_prob - market_prob

if abs(edge) > 0.30:
    return {"verdict": "TRAP", "signal": "⚠️ TRAP",
            "reason": f"AI ({ai_prob:.1%}) vs market ({market_prob:.1%}) diverge by {abs(edge):.1%} — likely mispriced",
            "edge": round(edge, 4), "safe_category": True}

if ai_prob >= 0.96 and market_prob >= 0.96 and edge >= -0.02:
    return {"verdict": "HARVEST", "signal": "🟢 HARVEST",
            "reason": f"AI {ai_prob:.1%} confirms market {market_prob:.1%} — near-certainty, edge {edge:+.1%}",
            "edge": round(edge, 4), "safe_category": True}

if edge > 0.05:
    return {"verdict": "VALUE", "signal": "💎 VALUE",
            "reason": f"AI {ai_prob:.1%} vs market {market_prob:.1%} — positive edge {edge:+.1%}",
            "edge": round(edge, 4), "safe_category": True}

return {"verdict": "MONITOR", "signal": "🔵 MONITOR",
        "reason": f"Insufficient edge ({edge:+.1%}) or probability below threshold",
        "edge": round(edge, 4), "safe_category": True}
```

‘’’

# ════════════════════════════════════════════════════════════════

# fetcher.py

# ════════════════════════════════════════════════════════════════

FILES[“fetcher.py”] = ‘’’”””
fetcher.py — Polymarket Data Fetcher
Fetches and parses live market data from the Polymarket Gamma API.
“””

import json
import requests
from datetime import datetime, timezone

GAMMA_URL = “https://gamma-api.polymarket.com/markets”

def fetch_markets(limit: int = 200) -> list:
try:
r = requests.get(GAMMA_URL, params={
“active”: “true”, “closed”: “false”,
“limit”: limit, “order”: “volume”, “ascending”: “false”,
}, timeout=20)
r.raise_for_status()
return r.json()
except requests.RequestException as e:
print(f”[fetcher] API error: {e}”)
return []

def parse_market(m: dict) -> dict:
try:
question = str(m.get(“question”) or “”).strip()
if not question:
return None

```
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
        return None

    yes_price = prices[0]
    no_price  = prices[1]
    best_prob = max(yes_price, no_price)
    best_side = "YES" if yes_price >= no_price else "NO"
    spread    = abs(yes_price - no_price)
    volume    = float(m.get("volume",    0) or 0)
    liquidity = float(m.get("liquidity", 0) or 0)

    days_left = 999
    end_str = m.get("endDate") or m.get("resolutionDate")
    if end_str:
        try:
            end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
        except Exception:
            pass

    tokens   = m.get("tokens") or []
    best_idx = 0 if best_side == "YES" else 1
    token_id = tokens[best_idx].get("token_id") if len(tokens) > best_idx else None

    return {
        "question": question, "slug": m.get("slug", "") or str(m.get("id", "")),
        "yes_price": yes_price, "no_price": no_price,
        "best_prob": best_prob, "best_side": best_side, "spread": spread,
        "volume": volume, "liquidity": liquidity, "days_left": days_left,
        "end_date": end_str or "unknown", "best_token_id": token_id,
        "url": f"https://polymarket.com/event/{m.get(\'slug\', \'\')}",
    }
except Exception:
    return None
```

def fetch_and_parse(min_prob=0.95, max_days=7, min_volume=50_000, limit=200) -> list:
raw = fetch_markets(limit=limit)
markets = []
for raw_m in raw:
m = parse_market(raw_m)
if not m:
continue
if (m[“best_prob”] >= min_prob and 0 < m[“days_left”] <= max_days
and m[“volume”] >= min_volume and m[“liquidity”] > 1_000
and m[“best_token_id”]):
markets.append(m)
return markets
‘’’

# ════════════════════════════════════════════════════════════════

# bridge.py

# ════════════════════════════════════════════════════════════════

FILES[“bridge.py”] = ‘’’”””
bridge.py — AI Model Bridge
Loads the trained XGBoost model and provides get_ai_prediction().
“””

import os
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(**file**), “models”, “champion.pkl”)
_bundle = None

def _load_model():
global _bundle
if _bundle is not None:
return _bundle
try:
import joblib
_bundle = joblib.load(MODEL_PATH)
print(f”[bridge] Model loaded from {MODEL_PATH}”)
return _bundle
except FileNotFoundError:
print(f”[bridge] No model at {MODEL_PATH} — run: python retrain.py”)
return None
except Exception as e:
print(f”[bridge] Could not load model: {e}”)
return None

def _engineer_features(stats: dict) -> np.ndarray:
prob            = float(stats.get(“prob”,            0.95))
volume          = float(stats.get(“volume”,          1000))
spread          = float(stats.get(“spread”,          0.01))
days_to_resolve = float(stats.get(“days_to_resolve”, 1))
log_volume = np.log1p(volume)
liquidity  = volume / (spread + 0.0001)
return np.array([[prob, log_volume, spread, days_to_resolve, liquidity]])

def get_ai_prediction(stats: dict):
bundle = _load_model()
if bundle is None:
return None
try:
X     = _engineer_features(stats)
raw_p = bundle[“model”].predict_proba(X)[:, 1][0]
cal_p = float(bundle[“calibrator”].predict([raw_p])[0])
return round(cal_p, 4)
except Exception as e:
print(f”[bridge] Prediction error: {e}”)
return None

def get_model_info() -> dict:
bundle = _load_model()
if bundle is None:
return {“loaded”: False, “path”: MODEL_PATH}
import time
return {
“loaded”:     True,
“path”:       MODEL_PATH,
“features”:   bundle.get(“features”, []),
“age_hours”:  round((time.time() - bundle.get(“timestamp”, 0)) / 3600, 1),
“trained_on”: bundle.get(“trained_on”, “unknown”),
}
‘’’

# ════════════════════════════════════════════════════════════════

# retrain.py

# ════════════════════════════════════════════════════════════════

FILES[“retrain.py”] = ‘’’”””
retrain.py — AI Model Training
Trains XGBoost on real resolved Polymarket markets.
Run manually: python retrain.py
Runs automatically: every Sunday via GitHub Actions
“””

import os, time, json, joblib, requests
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import cross_val_score
from datetime import datetime, timezone

GAMMA_URL  = “https://gamma-api.polymarket.com/markets”
MODEL_PATH = “models/champion.pkl”
MIN_ROWS   = 30

def fetch_resolved_markets(limit=500) -> pd.DataFrame:
print(“📡 Fetching resolved markets from Polymarket API…”)
try:
r = requests.get(GAMMA_URL, params={
“active”: “false”, “closed”: “true”,
“limit”: limit, “order”: “volume”, “ascending”: “false”,
}, timeout=30)
r.raise_for_status()
raw = r.json()
except Exception as e:
print(f”  ⚠️ API fetch failed: {e}”)
return pd.DataFrame()

```
rows = []
for m in raw:
    try:
        prices_raw = m.get("outcomePrices", [])
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)
        prices = [float(p) for p in (prices_raw or []) if p is not None]
        if len(prices) < 2:
            continue

        best_prob = max(prices)
        spread    = abs(prices[0] - prices[1])
        volume    = float(m.get("volume",    0) or 0)
        liquidity = float(m.get("liquidity", 0) or 0)
        if volume < 1000:
            continue

        days_to_resolve = 1
        start_str = m.get("startDate")
        end_str   = m.get("endDate") or m.get("resolutionDate")
        if start_str and end_str:
            try:
                s = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                e = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                days_to_resolve = max(0, (e - s).days)
            except Exception:
                pass

        outcome = 1 if prices[0] > 0.5 else 0
        rows.append({
            "prob": best_prob, "volume": volume, "spread": spread,
            "days_to_resolve": days_to_resolve, "liquidity": liquidity,
            "outcome": outcome,
        })
    except Exception:
        continue

df = pd.DataFrame(rows)
print(f"  ✅ Parsed {len(df)} resolved markets")
return df
```

def fetch_from_database() -> pd.DataFrame:
if not all(os.getenv(k) for k in [“DB_NAME”, “DB_USER”, “DB_PASS”, “DB_HOST”]):
return pd.DataFrame()
print(“📥 Connecting to database…”)
try:
import psycopg2
conn = psycopg2.connect(
dbname=os.getenv(“DB_NAME”), user=os.getenv(“DB_USER”),
password=os.getenv(“DB_PASS”), host=os.getenv(“DB_HOST”),
connect_timeout=10,
)
df = pd.read_sql(
“SELECT prob, volume, spread, days_to_resolve, liquidity, outcome “
“FROM markets WHERE outcome IS NOT NULL AND volume > 1000”, conn)
conn.close()
print(f”  ✅ {len(df)} rows from database”)
return df
except Exception as e:
print(f”  ⚠️ DB failed: {e}”)
return pd.DataFrame()

def get_synthetic_fallback() -> pd.DataFrame:
print(“⚠️  Using synthetic fallback data”)
rng    = np.random.default_rng(42)
n      = 200
probs  = np.clip(rng.beta(8, 0.4, n), 0.50, 0.999)
vols   = rng.lognormal(11, 1.5, n)
spread = rng.beta(1, 20, n)
days   = rng.integers(0, 14, n).astype(float)
liq    = vols * rng.uniform(0.1, 0.5, n)
outcome = (rng.uniform(0, 1, n) < probs).astype(int)
return pd.DataFrame({
“prob”: np.round(probs, 4), “volume”: np.round(vols, 2),
“spread”: np.round(spread, 4), “days_to_resolve”: days,
“liquidity”: np.round(liq, 2), “outcome”: outcome,
})

def engineer_features(df: pd.DataFrame):
df = df.copy()
df[“log_volume”] = np.log1p(df[“volume”])
df[“liquidity”]  = df[“volume”] / (df[“spread”] + 0.0001)
features = [“prob”, “log_volume”, “spread”, “days_to_resolve”, “liquidity”]
return df[features], df[“outcome”]

def main():
print(”\n🤖 AI Training Session Starting…”)
print(”=” * 50)

```
df = fetch_from_database()
if len(df) < MIN_ROWS:
    api_df = fetch_resolved_markets(500)
    df = api_df if df.empty else pd.concat([df, api_df], ignore_index=True)
if len(df) < MIN_ROWS:
    synth  = get_synthetic_fallback()
    df = pd.concat([df, synth], ignore_index=True) if not df.empty else synth

df          = df.dropna().reset_index(drop=True)
data_source = "real" if len(df) > MIN_ROWS else "synthetic"
print(f"\\n📊 Training on {len(df)} rows ({data_source})")

X, y = engineer_features(df)

model = xgb.XGBClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    eval_metric="logloss", random_state=42, verbosity=0,
)
model.fit(X, y)

if len(df) >= MIN_ROWS:
    cv = cross_val_score(model, X, y, cv=min(5, len(df)//10), scoring="accuracy")
    print(f"  CV Accuracy: {cv.mean():.3f} ± {cv.std():.3f}")

calibrator = IsotonicRegression(out_of_bounds="clip")
calibrator.fit(model.predict_proba(X)[:, 1], y)

os.makedirs("models", exist_ok=True)
joblib.dump({
    "model": model, "calibrator": calibrator,
    "features": list(X.columns), "timestamp": time.time(),
    "trained_on": len(df), "data_source": data_source,
}, MODEL_PATH)

print(f"\\n✅ Saved → {MODEL_PATH} | Rows: {len(df)} | Source: {data_source}")
print("=" * 50)
```

if **name** == “**main**”:
main()
‘’’

# ════════════════════════════════════════════════════════════════

# simple_polymarket.py

# ════════════════════════════════════════════════════════════════

FILES[“simple_polymarket.py”] = ‘’’”””
simple_polymarket.py — Basic Harvest Scanner (Streamlit)
Run: streamlit run simple_polymarket.py
“””

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
min_prob      = st.slider(“Min probability”, 0.90, 0.99, 0.96, 0.01)
max_days      = st.slider(“Max days left”,   1, 14, 7)
min_vol_m     = st.slider(“Min volume ($M)”, 0.01, 2.0, 0.05, 0.01)
show_rejected = st.checkbox(“Show rejected markets”, False)

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
harvest, rejected = [], []

for m in raw:
try:
question  = str(m.get(“question”) or “Unknown”)[:140]
volume    = float(m.get(“volume”, 0) or 0) / 1_000_000
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
```

c1, c2, c3 = st.columns(3)
c1.metric(“✅ Harvest Ready”,  len(harvest))
c2.metric(“🚩 AI Rejected”,   len(rejected))
c3.metric(“📊 Total Scanned”, len(raw))
st.divider()

if harvest:
st.subheader(“🟢 Harvest Opportunities”)
df = pd.DataFrame(harvest).sort_values(“Volume ($M)”, ascending=False)
st.dataframe(df.drop(columns=[“Reason”]), use_container_width=True, hide_index=True)
else:
st.info(“No opportunities found. Try adjusting the sidebar filters.”)

if show_rejected and rejected:
st.divider()
st.subheader(“🚩 Rejected by Safety Filter”)
st.dataframe(pd.DataFrame(rejected), use_container_width=True, hide_index=True)

st.caption(“⚠️ Informational only. Not financial advice.”)
‘’’

# ════════════════════════════════════════════════════════════════

# polymarket_dashboard.py

# ════════════════════════════════════════════════════════════════

FILES[“polymarket_dashboard.py”] = ‘’’”””
polymarket_dashboard.py — Full AI-Powered Dashboard (Streamlit)
Run: streamlit run polymarket_dashboard.py
Requires: python retrain.py first (to build models/champion.pkl)
“””

import json, requests
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from bridge import get_ai_prediction, get_model_info
from engine import get_verdict, is_safe_category

GAMMA_URL = “https://gamma-api.polymarket.com/markets”

st.set_page_config(page_title=“AI Harvest Scanner”, layout=“wide”, page_icon=“🌾”)
st.title(“🌾 AI-Powered Harvest Scanner”)
st.markdown(”*XGBoost model + category safety filters + live Polymarket data*”)

with st.sidebar:
st.header(“⚙️ Settings”)
min_prob = st.slider(“Min probability”, 0.90, 0.99, 0.96, 0.01)
max_days = st.slider(“Max days left”,   1, 14, 7)
min_vol  = st.slider(“Min volume ($K)”, 10, 500, 50) * 1000
show_rej = st.checkbox(“Show rejected”, False)
show_mon = st.checkbox(“Show monitor”,  False)
st.divider()
st.subheader(“🤖 AI Model”)
info = get_model_info()
if info[“loaded”]:
st.success(“Model loaded ✅”)
st.caption(f”Trained on {info.get('trained_on','?')} rows · {info['age_hours']}h ago”)
else:
st.error(“No model — run retrain.py”)
if st.button(“🔄 Retrain Now”):
import subprocess
with st.spinner(“Training…”):
r = subprocess.run([“python”, “retrain.py”], capture_output=True, text=True)
if r.returncode == 0:
st.success(“Done!”)
st.cache_data.clear()
else:
st.error(r.stderr[:300])

@st.cache_data(ttl=60)
def fetch_markets(limit=200):
try:
r = requests.get(GAMMA_URL, params={
“active”: “true”, “closed”: “false”,
“limit”: limit, “order”: “volume”, “ascending”: “false”,
}, timeout=20)
r.raise_for_status()
return r.json()
except Exception as e:
st.error(f”API Error: {e}”)
return []

def process_markets(raw, min_prob, max_days, min_vol):
results = []
for m in raw:
try:
question = str(m.get(“question”) or “”).strip()[:140]
if not question:
continue
prices_raw = m.get(“outcomePrices”, [])
if isinstance(prices_raw, str):
prices_raw = json.loads(prices_raw)
prices = [float(p) for p in (prices_raw or []) if p is not None]
if len(prices) < 2:
continue

```
        yes_price = prices[0]
        no_price  = prices[1]
        best_prob = max(yes_price, no_price)
        best_side = "YES" if yes_price >= no_price else "NO"
        spread    = abs(yes_price - no_price)
        volume    = float(m.get("volume",    0) or 0)
        liquidity = float(m.get("liquidity", 0) or 0)

        days_left = 999
        end_str   = m.get("endDate") or m.get("resolutionDate")
        if end_str:
            try:
                end_dt    = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                days_left = max(0, (end_dt - datetime.now(timezone.utc)).days)
            except Exception:
                pass

        safe, cat_reason = is_safe_category(question)
        ai_prob = get_ai_prediction({
            "prob": best_prob, "volume": volume,
            "spread": spread, "days_to_resolve": days_left,
        })

        if not safe:
            v = {"verdict": "REJECT", "signal": "🚩 REJECTED", "reason": cat_reason, "edge": 0.0}
        elif ai_prob is None:
            v = {"verdict": "MONITOR", "signal": "🔄 No Model", "reason": "Run retrain.py", "edge": 0.0}
        else:
            v = get_verdict(ai_prob, best_prob, question)

        results.append({
            "question":       question,
            "best_prob":      best_prob,
            "best_side":      best_side,
            "ai_prob":        ai_prob,
            "volume":         volume,
            "days_left":      days_left,
            "implied_return": round((1 - best_prob) / best_prob * 100, 2) if best_prob < 1 else 0,
            "verdict":        v["verdict"],
            "signal":         v["signal"],
            "reason":         v["reason"],
            "edge":           v.get("edge", 0.0),
            "url":            f"https://polymarket.com/event/{m.get(\'slug\',\'\')}",
        })
    except Exception:
        continue
return results
```

with st.spinner(“Fetching markets…”):
raw      = fetch_markets()
all_mkts = process_markets(raw, min_prob, max_days, min_vol)

harvest  = [m for m in all_mkts if m[“verdict”] == “HARVEST”]
value    = [m for m in all_mkts if m[“verdict”] == “VALUE”]
monitor  = [m for m in all_mkts if m[“verdict”] == “MONITOR”]
rejected = [m for m in all_mkts if m[“verdict”] in (“REJECT”, “TRAP”)]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(“🟢 Harvest”,  len(harvest))
c2.metric(“💎 Value”,    len(value))
c3.metric(“🔵 Monitor”,  len(monitor))
c4.metric(“🚩 Rejected”, len(rejected))
c5.metric(“📊 Scanned”,  len(raw))
st.divider()

def render_table(mkts, title):
if not mkts:
return
st.subheader(title)
rows = [{
“Market”:         m[“question”],
“Market Prob”:    f”{m['best_side']} @ {m['best_prob']:.1%}”,
“AI Prob”:        f”{m['ai_prob']:.1%}” if m[“ai_prob”] else “—”,
“Edge”:           f”{m['edge']:+.1%}”,
“Volume”:         f”${m['volume']/1e6:.2f}M”,
“Days”:           m[“days_left”],
“Return”:         f”+{m['implied_return']:.1f}%”,
“Signal”:         m[“signal”],
“Link”:           m[“url”],
} for m in sorted(mkts, key=lambda x: x[“volume”], reverse=True)]
st.dataframe(
pd.DataFrame(rows), use_container_width=True, hide_index=True,
column_config={“Link”: st.column_config.LinkColumn(“Trade”)},
)

render_table(harvest,  “🟢 Harvest Opportunities”)
render_table(value,    “💎 Value Plays”)
if show_mon: render_table(monitor,  “🔵 Monitor”)
if show_rej: render_table(rejected, “🚩 Rejected”)

st.divider()
st.caption(f”⚠️ Informational only. Not financial advice. Last refresh: {datetime.now().strftime('%H:%M:%S')}”)
‘’’

# ════════════════════════════════════════════════════════════════

# requirements.txt

# ════════════════════════════════════════════════════════════════

FILES[“requirements.txt”] = “”“streamlit>=1.32.0
requests>=2.31.0
pandas>=2.0.0
numpy>=1.26.0
xgboost>=2.0.0
scikit-learn>=1.4.0
joblib>=1.3.0
scipy>=1.12.0
psycopg2-binary>=2.9.0
py-clob-client>=0.17.0
python-dotenv>=1.0.0
anthropic>=0.25.0
“””

# ════════════════════════════════════════════════════════════════

# .gitignore

# ════════════════════════════════════════════════════════════════

FILES[”.gitignore”] = “””.env
bankroll.json
traded.json
rejected.json
harvest_bot.log
**pycache**/
*.pyc
.DS_Store
“””

# ════════════════════════════════════════════════════════════════

# .github/workflows/retrain.yml

# ════════════════════════════════════════════════════════════════

FILES[”.github/workflows/retrain.yml”] = “”“name: Auto-Retrain AI Model

on:
workflow_dispatch:
schedule:
- cron: ‘0 2 * * 0’

permissions:
contents: write

jobs:
retrain:
runs-on: ubuntu-latest
steps:
- uses: actions/checkout@v4

```
  - uses: actions/setup-python@v5
    with:
      python-version: '3.11'
      cache: 'pip'

  - name: Install dependencies
    run: pip install pandas numpy xgboost scikit-learn joblib scipy psycopg2-binary requests

  - name: Run retraining
    env:
      DB_NAME: ${{ secrets.DB_NAME }}
      DB_USER: ${{ secrets.DB_USER }}
      DB_PASS: ${{ secrets.DB_PASS }}
      DB_HOST: ${{ secrets.DB_HOST }}
    run: python retrain.py

  - name: Verify model created
    run: |
      [ -f models/champion.pkl ] && echo "✅ Model exists" || (echo "❌ Missing" && exit 1)

  - name: Commit model
    run: |
      git config --local user.email "github-actions[bot]@users.noreply.github.com"
      git config --local user.name  "github-actions[bot]"
      git add models/champion.pkl
      git diff --staged --quiet || git commit -m "chore: retrain AI model [$(date -u '+%Y-%m-%d')]"
      git push
```

“””

# ════════════════════════════════════════════════════════════════

# BUILD THE PROJECT

# ════════════════════════════════════════════════════════════════

def build():
print(f”\n🔨 Building {PROJECT}/…”)

```
if os.path.exists(PROJECT):
    print(f"⚠️  Folder '{PROJECT}' already exists — skipping (delete it first to rebuild)")
    sys.exit(1)

for filepath, content in FILES.items():
    full_path = os.path.join(PROJECT, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ {filepath}")

# Create empty models directory placeholder
models_dir = os.path.join(PROJECT, "models")
os.makedirs(models_dir, exist_ok=True)
open(os.path.join(models_dir, ".gitkeep"), "w").close()
print(f"  ✅ models/.gitkeep")

print(f"""
```

✅ Done! Project created in ‘{PROJECT}/’

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Install dependencies:
   cd {PROJECT}
   pip install -r requirements.txt
1. Train the AI model:
   python retrain.py
1. Run the basic scanner:
   streamlit run simple_polymarket.py
1. Run the full AI dashboard:
   streamlit run polymarket_dashboard.py
1. Push to GitHub:
   git init
   git add .
   git commit -m “Initial commit”
   git remote add origin https://github.com/YOUR_USERNAME/polymarket-bot.git
   git push -u origin main

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
“””)

if **name** == “**main**”:
build()
