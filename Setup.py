#!/usr/bin/env python3
“””
setup.py — Polymarket Harvest Bot — One-Click Project Builder

Run this ONE file and it creates the entire project structure.

Usage:

1. Save this file as setup.py anywhere on your PC
1. Open terminal and run: python setup.py
1. A folder called ‘polymarket-bot’ will appear with everything inside

Then:
cd polymarket-bot
pip install -r requirements.txt
python retrain.py
streamlit run polymarket_dashboard.py
“””

import os
import sys

PROJECT = “polymarket-bot”
FILES   = {}

# NOTE: All f-string / dunder markers inside triple-quoted strings use

# backslash escapes or concatenation to avoid being interpreted by

# Python at setup.py parse time.

# ════════════════════════════════════════════════════════════════════════════

# engine.py

# ════════════════════════════════════════════════════════════════════════════

FILES[“engine.py”] = ‘’’  
“””
engine.py — Verdict Engine
Decides HARVEST / VALUE / MONITOR / TRAP / STALE / REJECT for each market.
“””

import re
import math

_REJECT_PATTERNS = []

_RAW_REJECT = [
(r”\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|doge)\b”,          “crypto asset”),
(r”\bhit\s+\$\d”,                                               “price target”),
(r”\b(reach|above|below|exceed|break)\s+\$\d”,                  “price level”),
(r”\bdip\s+to\b”,                                                “price dip”),
(r”\b(crypto|cryptocurrency|blockchain)\s+(price|market|crash)\b”,“crypto market”),
(r”\b(invade|invasion|ceasefire|troops|airstrike|missile)\b”,     “military event”),
(r”\bnuclear\s+(weapon|strike|test|launch)\b”,                   “nuclear event”),
(r”\b(declare|declared)\s+war\b”,                                “war declaration”),
(r”\b(convicted|acquitted|guilty|not\s+guilty)\b”,              “criminal verdict”),
(r”\b(sentenced|sentencing)\b”,                                   “sentencing”),
(r”\bsupreme\s+court\s+rule”,                                    “supreme court”),
(r”\b(win|wins|beat|beats|defeat|defeats)\s+the\b.*\b(match|game|series|final)\b”,
“sports result”),
(r”\b(championship|super bowl|world cup|nba finals|stanley cup)\s+winner\b”,
“championship”),
(r”\b(tweet|tweets|post)\s+on\s+(twitter|x\.com|instagram)\b”,“social post”),
(r”\bnet\s+worth\b”,                                             “net worth”),
(r”\bnumber\s+of\s+(followers|subscribers)\b”,                 “follower count”),
]

for _pat, _label in _RAW_REJECT:
_REJECT_PATTERNS.append((re.compile(_pat, re.IGNORECASE), _label))

def is_safe_category(question: str) -> tuple:
for pattern, label in _REJECT_PATTERNS:
if pattern.search(question):
return False, f”Auto-rejected: {label} category”
return True, “Category OK”

def confidence_score(market_prob, spread, volume, liquidity, days_left):
spread_score = max(0.0, 1.0 - spread / 0.10)
liq_score    = min(1.0, math.log1p(liquidity) / math.log1p(1_000_000))
time_score   = max(0.0, 1.0 - (days_left - 1) / 30)
vol_score    = min(1.0, math.log1p(volume) / math.log1p(500_000))
score = 0.35*spread_score + 0.25*liq_score + 0.25*time_score + 0.15*vol_score
return round(score, 3)

def get_verdict(ai_prob, market_prob, question=””, market_stats=None):
safe, cat_reason = is_safe_category(question)
if not safe:
return {“verdict”:“REJECT”,“signal”:”\U0001f6a9 REJECTED”,
“reason”:cat_reason,“edge”:0.0,“safe_category”:False,“confidence”:0.0}

```
stats     = market_stats or {}
spread    = float(stats.get("spread",    0.0))
volume    = float(stats.get("volume",    0.0))
liquidity = float(stats.get("liquidity", 0.0))
days_left = int(stats.get("days_left",   999))
conf      = confidence_score(market_prob, spread, volume, liquidity, days_left)

if market_prob >= 0.96 and spread > 0.08:
    return {"verdict":"STALE","signal":"\\U0001f570\\ufe0f STALE",
            "reason":f"Wide spread ({spread:.1%}) at high prob — stale order book",
            "edge":round(ai_prob-market_prob,4),"safe_category":True,"confidence":conf}

edge = ai_prob - market_prob

if abs(edge) > 0.30:
    return {"verdict":"TRAP","signal":"\\u26a0\\ufe0f TRAP",
            "reason":f"AI ({ai_prob:.1%}) vs market ({market_prob:.1%}) diverge by {abs(edge):.1%}",
            "edge":round(edge,4),"safe_category":True,"confidence":conf}

if ai_prob >= 0.96 and market_prob >= 0.96 and edge >= -0.02:
    return {"verdict":"HARVEST","signal":"\\U0001f7e2 HARVEST",
            "reason":f"AI {ai_prob:.1%} confirms market {market_prob:.1%}, conf {conf:.0%}",
            "edge":round(edge,4),"safe_category":True,"confidence":conf}

if edge > 0.05:
    return {"verdict":"VALUE","signal":"\\U0001f48e VALUE",
            "reason":f"AI {ai_prob:.1%} vs market {market_prob:.1%}, edge {edge:+.1%}",
            "edge":round(edge,4),"safe_category":True,"confidence":conf}

return {"verdict":"MONITOR","signal":"\\U0001f535 MONITOR",
        "reason":f"Insufficient edge ({edge:+.1%})",
        "edge":round(edge,4),"safe_category":True,"confidence":conf}
```

‘’’

# ════════════════════════════════════════════════════════════════════════════

# fetcher.py

# ════════════════════════════════════════════════════════════════════════════

FILES[“fetcher.py”] = ‘’’  
“””
fetcher.py — Polymarket Data Fetcher
“””

import json, math, requests
from datetime import datetime, timezone

GAMMA_URL = “https://gamma-api.polymarket.com/markets”

def fetch_markets(limit=200, order=“volume”):
try:
r = requests.get(GAMMA_URL, params={
“active”:“true”,“closed”:“false”,
“limit”:limit,“order”:order,“ascending”:“false”,
}, timeout=20)
r.raise_for_status()
return r.json()
except requests.RequestException as e:
print(f”[fetcher] API error: {e}”)
return []

def fetch_resolved_markets(limit=500):
try:
r = requests.get(GAMMA_URL, params={
“active”:“false”,“closed”:“true”,
“limit”:limit,“order”:“volume”,“ascending”:“false”,
}, timeout=30)
r.raise_for_status()
return r.json()
except requests.RequestException as e:
print(f”[fetcher] Resolved API error: {e}”)
return []

def _parse_prices(m):
prices_raw = m.get(“outcomePrices”, [])
if isinstance(prices_raw, str):
try:    prices_raw = json.loads(prices_raw)
except: return None, None
prices = []
for p in (prices_raw or []):
try:    prices.append(float(p))
except: pass
if len(prices) < 2:
return None, None
y, n = prices[0], prices[1]
if not (0.85 <= y+n <= 1.15):
return None, None
return y, n

def parse_market(m):
try:
question = str(m.get(“question”) or “”).strip()
if not question: return None

```
    y, n = _parse_prices(m)
    if y is None: return None

    best_prob = max(y, n)
    best_side = "YES" if y >= n else "NO"
    spread    = abs(y - n)
    volume    = float(m.get("volume",    0) or 0)
    liquidity = float(m.get("liquidity", 0) or 0)

    days_left = 999
    end_str = m.get("endDate") or m.get("resolutionDate")
    if end_str:
        try:
            end_dt    = datetime.fromisoformat(end_str.replace("Z","+00:00"))
            days_left = max(0,(end_dt - datetime.now(timezone.utc)).days)
        except: pass

    age_days = 0
    start_str = m.get("createdAt") or m.get("startDate")
    if start_str:
        try:
            sd       = datetime.fromisoformat(start_str.replace("Z","+00:00"))
            age_days = max(0,(datetime.now(timezone.utc) - sd).days)
        except: pass

    liq_ratio   = liquidity / (volume + 1)
    vol_per_day = volume / max(age_days, 1)
    slug        = m.get("slug") or str(m.get("id",""))
    tokens      = m.get("tokens") or []

    return {
        "question":     question, "slug": slug,
        "url":          f"https://polymarket.com/event/{slug}",
        "yes_price":    round(y,4),  "no_price":   round(n,4),
        "best_prob":    round(best_prob,4), "best_side": best_side,
        "spread":       round(spread,4),
        "volume":       round(volume,2),    "liquidity":  round(liquidity,2),
        "days_left":    days_left,           "age_days":   age_days,
        "vol_per_day":  round(vol_per_day,2),"liq_ratio":  round(liq_ratio,4),
        "log_volume":   round(math.log1p(volume),4),
        "yes_token_id": tokens[0].get("token_id") if len(tokens)>0 else None,
        "no_token_id":  tokens[1].get("token_id") if len(tokens)>1 else None,
    }
except Exception as e:
    print(f"[fetcher] parse_market error: {e}")
    return None
```

def fetch_and_parse(min_prob=0.95, max_days=7, min_volume=50_000,
min_liquidity=1_000, limit=200):
seen, markets = set(), []
for order in (“volume”,“liquidity”):
for raw_m in fetch_markets(limit=limit, order=order):
mid = raw_m.get(“id”) or raw_m.get(“slug”)
if mid in seen: continue
seen.add(mid)
m = parse_market(raw_m)
if not m: continue
if (m[“best_prob”] >= min_prob and 0 < m[“days_left”] <= max_days
and m[“volume”] >= min_volume and m[“liquidity”] >= min_liquidity):
markets.append(m)
return markets
‘’’

# ════════════════════════════════════════════════════════════════════════════

# bridge.py

# ════════════════════════════════════════════════════════════════════════════

# Note: **file** inside the template is escaped as **file** (no change needed

# because it’s not being f-string-interpolated — it’s just a string literal).

FILES[“bridge.py”] = ‘’’  
“””
bridge.py — AI Model Bridge
“””

import os, math
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(**file**), “models”, “champion.pkl”)
_bundle = None

FEATURE_NAMES = [
“prob”,“log_volume”,“spread”,“spread_pct”,
“days_to_resolve”,“liquidity”,“liq_ratio”,“vol_per_day”,“log_liquidity”,
]

def _load_model():
global _bundle
if _bundle is not None: return _bundle
try:
import joblib
_bundle = joblib.load(MODEL_PATH)
return _bundle
except FileNotFoundError:
print(f”[bridge] No model at {MODEL_PATH} — run: python retrain.py”)
return None
except Exception as e:
print(f”[bridge] Could not load: {e}”)
return None

def _engineer_features(stats):
prob      = float(stats.get(“prob”,           0.95))
volume    = float(stats.get(“volume”,         1000))
spread    = float(stats.get(“spread”,         0.01))
days      = float(stats.get(“days_to_resolve”,1))
liquidity = float(stats.get(“liquidity”,      0))
liq_ratio = float(stats.get(“liq_ratio”,      0))
vol_per_day = float(stats.get(“vol_per_day”,  0))
log_volume    = math.log1p(volume)
log_liquidity = math.log1p(liquidity)
spread_pct    = spread / (prob + 1e-6)
return np.array([[prob,log_volume,spread,spread_pct,
days,liquidity,liq_ratio,vol_per_day,log_liquidity]])

def get_ai_prediction(stats):
bundle = _load_model()
if bundle is None: return None
try:
X     = _engineer_features(stats)
raw_p = bundle[“model”].predict_proba(X)[:,1][0]
cal_p = float(bundle[“calibrator”].predict([raw_p])[0])
return round(float(np.clip(cal_p, 0.0, 1.0)), 4)
except Exception as e:
print(f”[bridge] Prediction error: {e}”)
return None

def get_model_info():
import time
bundle = _load_model()
if bundle is None: return {“loaded”:False,“path”:MODEL_PATH}
age_hours = round((time.time() - bundle.get(“timestamp”,0))/3600, 1)
return {
“loaded”:      True,      “path”:        MODEL_PATH,
“features”:    bundle.get(“features”,[]),
“age_hours”:   age_hours, “age_warning”: age_hours > 168,
“trained_on”:  bundle.get(“trained_on”,”?”),
“data_source”: bundle.get(“data_source”,”?”),
“cv_accuracy”: bundle.get(“cv_accuracy”),
}

def invalidate_cache():
global _bundle
_bundle = None
‘’’

# ════════════════════════════════════════════════════════════════════════════

# retrain.py

# ════════════════════════════════════════════════════════════════════════════

FILES[“retrain.py”] = ‘’’  
“””
retrain.py — AI Model Training
Run: python retrain.py
“””

import os, time, json, math, joblib, requests
import numpy as np, pandas as pd, xgboost as xgb
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from datetime import datetime, timezone

GAMMA_URL     = “https://gamma-api.polymarket.com/markets”
MODEL_PATH    = os.path.join(os.path.dirname(**file**), “models”, “champion.pkl”)
MIN_REAL_ROWS = 100

FEATURE_NAMES = [
“prob”,“log_volume”,“spread”,“spread_pct”,
“days_to_resolve”,“liquidity”,“liq_ratio”,“vol_per_day”,“log_liquidity”,
]

def _parse_outcome(m):
result = (m.get(“result”) or m.get(“winner”) or “”).strip().upper()
if result == “YES”: return 1
if result == “NO”:  return 0
tokens = m.get(“tokens”) or []
for i, tok in enumerate(tokens[:2]):
if str(tok.get(“winner”,””)).lower() == “true”:
return 1 if i==0 else 0
prices_raw = m.get(“outcomePrices”,[])
if isinstance(prices_raw, str):
try:    prices_raw = json.loads(prices_raw)
except: return None
try:   prices = [float(p) for p in prices_raw if p is not None]
except:return None
if len(prices) < 2: return None
y, n = prices[0], prices[1]
if not (0.85 <= y+n <= 1.15): return None
if y >= 0.90: return 1
if n >= 0.90: return 0
return None

def fetch_resolved_markets(limit=500):
print(“Fetching resolved markets…”)
rows = []
for order in (“volume”,“liquidity”):
try:
r = requests.get(GAMMA_URL, params={
“active”:“false”,“closed”:“true”,
“limit”:limit,“order”:order,“ascending”:“false”,
}, timeout=30)
r.raise_for_status()
raw = r.json()
except Exception as e:
print(f”  API error ({order}): {e}”)
continue
for m in raw:
try:
outcome = _parse_outcome(m)
if outcome is None: continue
prices_raw = m.get(“outcomePrices”,[])
if isinstance(prices_raw,str): prices_raw = json.loads(prices_raw)
prices = [float(p) for p in (prices_raw or []) if p is not None]
if len(prices) < 2: continue
y,n       = prices[0],prices[1]
best_prob = max(y,n)
spread    = abs(y-n)
volume    = float(m.get(“volume”,0) or 0)
liquidity = float(m.get(“liquidity”,0) or 0)
if volume < 1000: continue
days = 1
s_str = m.get(“startDate”) or m.get(“createdAt”)
e_str = m.get(“endDate”) or m.get(“resolutionDate”)
if s_str and e_str:
try:
s = datetime.fromisoformat(s_str.replace(“Z”,”+00:00”))
e = datetime.fromisoformat(e_str.replace(“Z”,”+00:00”))
days = max(1,(e-s).days)
except: pass
liq_ratio   = liquidity/(volume+1)
vol_per_day = volume/days
spread_pct  = spread/(best_prob+1e-6)
rows.append({
“prob”:best_prob,“log_volume”:math.log1p(volume),
“spread”:spread,“spread_pct”:spread_pct,
“days_to_resolve”:days,“liquidity”:liquidity,
“liq_ratio”:liq_ratio,“vol_per_day”:vol_per_day,
“log_liquidity”:math.log1p(liquidity),“outcome”:outcome,
})
except: continue
df = pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
print(f”  Parsed {len(df)} resolved markets”)
return df

def fetch_from_database():
if not all(os.getenv(k) for k in [“DB_NAME”,“DB_USER”,“DB_PASS”,“DB_HOST”]):
return pd.DataFrame()
try:
import psycopg2
conn = psycopg2.connect(
dbname=os.getenv(“DB_NAME”),user=os.getenv(“DB_USER”),
password=os.getenv(“DB_PASS”),host=os.getenv(“DB_HOST”),
connect_timeout=10)
df = pd.read_sql(
“SELECT prob,log_volume,spread,spread_pct,days_to_resolve,”
“liquidity,liq_ratio,vol_per_day,log_liquidity,outcome “
“FROM markets WHERE outcome IS NOT NULL AND volume>1000”, conn)
conn.close()
print(f”  {len(df)} rows from DB”)
return df
except Exception as e:
print(f”  DB failed: {e}”)
return pd.DataFrame()

def get_synthetic_fallback(n=300):
print(“WARNING: Using SYNTHETIC fallback data. Predictions will be approximate.”)
rng    = np.random.default_rng(42)
probs  = np.clip(rng.beta(8,0.5,n),0.50,0.999)
vols   = rng.lognormal(11,1.5,n)
spread = rng.beta(1,30,n)
days   = rng.integers(0,30,n).astype(float)+1
liq    = vols*rng.uniform(0.05,0.40,n)
liq_ratio   = liq/(vols+1)
vol_per_day = vols/days
spread_pct  = spread/(probs+1e-6)
noise       = rng.normal(0,0.06,n)
resolve_prob = np.clip(probs - spread*0.5 + noise, 0, 1)
outcome = (rng.uniform(0,1,n) < resolve_prob).astype(int)
return pd.DataFrame({
“prob”:probs,“log_volume”:np.log1p(vols),
“spread”:spread,“spread_pct”:spread_pct,
“days_to_resolve”:days,“liquidity”:liq,
“liq_ratio”:liq_ratio,“vol_per_day”:vol_per_day,
“log_liquidity”:np.log1p(liq),“outcome”:outcome,
})

def main():
print(”\n AI Training”)
print(”=”*50)
df = fetch_from_database()
if len(df) < MIN_REAL_ROWS:
api_df = fetch_resolved_markets(500)
df = api_df if df.empty else pd.concat([df,api_df],ignore_index=True)
data_source   = “real”
used_synthetic = False
if len(df) < MIN_REAL_ROWS:
synth = get_synthetic_fallback(n=max(MIN_REAL_ROWS-len(df),200))
df = pd.concat([df,synth],ignore_index=True) if not df.empty else synth
data_source   = “mixed” if len(df)>len(synth) else “synthetic”
used_synthetic = True
df = df.dropna().reset_index(drop=True)
print(f”Training on {len(df)} rows | source: {data_source}”)
X = df[FEATURE_NAMES]
y = df[“outcome”]
model = xgb.XGBClassifier(
n_estimators=300,max_depth=4,learning_rate=0.04,
subsample=0.8,colsample_bytree=0.8,min_child_weight=3,
gamma=0.1,reg_alpha=0.1,reg_lambda=1.0,
eval_metric=“logloss”,random_state=42,verbosity=0)
model.fit(X,y)
cv_acc = None
n_splits = min(5,max(2,len(df)//20))
if len(df) >= n_splits*5:
skf    = StratifiedKFold(n_splits=n_splits,shuffle=True,random_state=42)
cv_acc = cross_val_score(model,X,y,cv=skf,scoring=“accuracy”)
print(f”CV Accuracy: {cv_acc.mean():.3f} +/- {cv_acc.std():.3f}”)
calibrator = IsotonicRegression(out_of_bounds=“clip”)
calibrator.fit(model.predict_proba(X)[:,1],y)
os.makedirs(os.path.dirname(MODEL_PATH),exist_ok=True)
joblib.dump({
“model”:model,“calibrator”:calibrator,“features”:list(FEATURE_NAMES),
“timestamp”:time.time(),“trained_on”:len(df),“data_source”:data_source,
“cv_accuracy”:round(float(cv_acc.mean()),3) if cv_acc is not None else None,
}, MODEL_PATH)
print(f”Saved to {MODEL_PATH}”)
print(”=”*50)

if **name** == “**main**”:
main()
‘’’

# ════════════════════════════════════════════════════════════════════════════

# simple_polymarket.py

# ════════════════════════════════════════════════════════════════════════════

FILES[“simple_polymarket.py”] = ‘’’  
“””
simple_polymarket.py — Basic Harvest Scanner (no model required)
Run: streamlit run simple_polymarket.py
“””

import json, math, requests
import streamlit as st, pandas as pd
from datetime import datetime, timezone
from engine import is_safe_category, confidence_score

GAMMA_URL = “https://gamma-api.polymarket.com/markets”
st.set_page_config(page_title=“Harvest Scanner”, layout=“wide”)
st.title(”\U0001f33e Short-Term Harvest Scanner”)
st.markdown(”**Near-certainty markets (96%+) — category-filtered, confidence-scored**”)

with st.sidebar:
st.header(“Settings”)
min_prob      = st.slider(“Min probability”,  0.90, 0.99, 0.96, 0.01)
max_days      = st.slider(“Max days left”,    1, 14, 7)
min_vol_m     = st.slider(“Min volume ($M)”,  0.01, 2.0, 0.05, 0.01)
min_conf      = st.slider(“Min confidence”,   0.0, 1.0, 0.40, 0.05)
show_rejected = st.checkbox(“Show rejected markets”, False)
show_stale    = st.checkbox(“Show stale markets”, False)

@st.cache_data(ttl=60)
def fetch_markets():
try:
r = requests.get(GAMMA_URL, params={
“active”:“true”,“closed”:“false”,“limit”:200,
“order”:“volume”,“ascending”:“false”,
}, timeout=20)
r.raise_for_status()
return r.json()
except Exception as e:
st.error(f”API Error: {e}”)
return []

raw = fetch_markets()
harvest, rejected, stale = [], [], []

for m in raw:
try:
question  = str(m.get(“question”) or “Unknown”)[:140]
volume    = float(m.get(“volume”,    0) or 0)
liquidity = float(m.get(“liquidity”, 0) or 0)
prices_raw = m.get(“outcomePrices”,[])
if isinstance(prices_raw,str): prices_raw = json.loads(prices_raw)
prices = [float(p) for p in (prices_raw or []) if p is not None]
if len(prices) < 2: continue
y,n = prices[0],prices[1]
if not (0.85 <= y+n <= 1.15): continue
best_prob = max(y,n)
best_side = “YES” if y>=n else “NO”
spread    = abs(y-n)
days_left = 999
end_str = m.get(“endDate”) or m.get(“resolutionDate”)
if end_str:
try:
end_dt    = datetime.fromisoformat(end_str.replace(“Z”,”+00:00”))
days_left = max(0,(end_dt - datetime.now(timezone.utc)).days)
except: pass
if best_prob < min_prob or days_left==0 or days_left>max_days: continue
if volume/1e6 < min_vol_m: continue
conf = confidence_score(best_prob,spread,volume,liquidity,days_left)
safe,reason = is_safe_category(question)
ret = round((1-best_prob)/best_prob*100,2) if best_prob<1 else 0.0
row = {
“Question”:question,“Side”:f”{best_side} @ {best_prob:.1%}”,
“Spread”:f”{spread:.1%}”,“Volume ($M)”:round(volume/1e6,3),
“Days Left”:days_left,“Implied Return”:f”+{ret:.1f}%”,
“Confidence”:f”{conf:.0%}”,“Reason”:reason,
}
if best_prob>=0.96 and spread>0.08:
row[“Action”]=”\U0001f570\ufe0f STALE”; stale.append(row)
elif not safe:
row[“Action”]=”\U0001f6a9 REJECTED”; rejected.append(row)
elif conf>=min_conf:
row[“Action”]=”\U0001f7e2 HARVEST”; harvest.append(row)
else:
row[“Action”]=”\u26a1 LOW CONF”; rejected.append(row)
except: continue

c1,c2,c3,c4 = st.columns(4)
c1.metric(“Harvest Ready”,len(harvest))
c2.metric(“Filtered Out”, len(rejected))
c3.metric(“Stale Books”,  len(stale))
c4.metric(“Total Scanned”,len(raw))
st.divider()

if harvest:
st.subheader(“Harvest Opportunities”)
df = pd.DataFrame(harvest).sort_values(“Volume ($M)”,ascending=False)
st.dataframe(df[[“Question”,“Side”,“Spread”,“Volume ($M)”,“Days Left”,
“Implied Return”,“Confidence”,“Action”]],
use_container_width=True,hide_index=True)
else:
st.info(“No harvest opportunities — adjust filters or check back later.”)

if show_stale and stale:
st.divider()
st.subheader(“Stale Order Books”)
st.dataframe(pd.DataFrame(stale)[[“Question”,“Side”,“Spread”,“Volume ($M)”,“Days Left”,“Action”]],
use_container_width=True,hide_index=True)

if show_rejected and rejected:
st.divider()
st.subheader(“Rejected”)
st.dataframe(pd.DataFrame(rejected)[[“Question”,“Side”,“Volume ($M)”,“Days Left”,“Action”,“Reason”]],
use_container_width=True,hide_index=True)

st.caption(f”Refreshed: {datetime.now().strftime(\'%H:%M:%S\')} · Not financial advice.”)
‘’’

# ════════════════════════════════════════════════════════════════════════════

# polymarket_dashboard.py

# ════════════════════════════════════════════════════════════════════════════

FILES[“polymarket_dashboard.py”] = ‘’’  
“””
polymarket_dashboard.py — Full AI-Powered Dashboard
Run: streamlit run polymarket_dashboard.py
Requires: python retrain.py first
“””

import json, math, subprocess, requests
import streamlit as st, pandas as pd
from datetime import datetime, timezone
from bridge import get_ai_prediction, get_model_info, invalidate_cache
from engine import get_verdict, is_safe_category

GAMMA_URL = “https://gamma-api.polymarket.com/markets”
st.set_page_config(page_title=“AI Harvest Scanner”,layout=“wide”,page_icon=”\U0001f33e”)
st.title(”\U0001f33e AI-Powered Harvest Scanner”)
st.markdown(”*XGBoost + calibration · category safety · confidence scoring · live data*”)

with st.sidebar:
st.header(“Filters”)
min_prob   = st.slider(“Min probability”,0.90,0.99,0.96,0.01)
max_days   = st.slider(“Max days left”,  1,14,7)
min_vol_k  = st.slider(“Min volume ($K)”,10,500,50)*1_000
min_conf   = st.slider(“Min confidence”, 0.0,1.0,0.35,0.05)
show_rej   = st.checkbox(“Show rejected”,  False)
show_mon   = st.checkbox(“Show monitor”,   False)
show_stale = st.checkbox(“Show stale”,     False)
st.divider()
st.subheader(“AI Model”)
info = get_model_info()
if info[“loaded”]:
if info.get(“age_warning”): st.warning(f”Model is {info['age_hours']:.0f}h old”)
else: st.success(“Model loaded”)
st.caption(f”Rows: {info.get('trained_on','?')} | Age: {info['age_hours']:.0f}h”)
if info.get(“cv_accuracy”): st.caption(f”CV accuracy: {info['cv_accuracy']:.1%}”)
else:
st.error(“No model — run retrain.py”)
if st.button(“Retrain Model”):
with st.spinner(“Training…”):
res = subprocess.run([“python”,“retrain.py”],capture_output=True,text=True)
if res.returncode==0:
invalidate_cache(); st.cache_data.clear(); st.success(“Done!”)
st.text(res.stdout[-600:])
else:
st.error(“Failed”); st.text(res.stderr[:400])

@st.cache_data(ttl=60)
def fetch_markets():
try:
r = requests.get(GAMMA_URL,params={
“active”:“true”,“closed”:“false”,“limit”:200,
“order”:“volume”,“ascending”:“false”,
},timeout=20)
r.raise_for_status(); return r.json()
except Exception as e:
st.error(f”API Error: {e}”); return []

def process_markets(raw,min_prob,max_days,min_vol):
results=[]
for m in raw:
try:
question=str(m.get(“question”) or “”).strip()[:140]
if not question: continue
prices_raw=m.get(“outcomePrices”,[])
if isinstance(prices_raw,str): prices_raw=json.loads(prices_raw)
prices=[float(p) for p in (prices_raw or []) if p is not None]
if len(prices)<2: continue
y,n=prices[0],prices[1]
if not (0.85<=y+n<=1.15): continue
best_prob=max(y,n); best_side=“YES” if y>=n else “NO”; spread=abs(y-n)
volume=float(m.get(“volume”,0) or 0); liquidity=float(m.get(“liquidity”,0) or 0)
days_left=999
end_str=m.get(“endDate”) or m.get(“resolutionDate”)
if end_str:
try:
end_dt=datetime.fromisoformat(end_str.replace(“Z”,”+00:00”))
days_left=max(0,(end_dt-datetime.now(timezone.utc)).days)
except: pass
age_days=0
start_str=m.get(“createdAt”) or m.get(“startDate”)
if start_str:
try:
sd=datetime.fromisoformat(start_str.replace(“Z”,”+00:00”))
age_days=max(0,(datetime.now(timezone.utc)-sd).days)
except: pass
liq_ratio=liquidity/(volume+1); vol_per_day=volume/max(age_days,1)
ai_prob=get_ai_prediction({
“prob”:best_prob,“volume”:volume,“spread”:spread,
“spread_pct”:spread/(best_prob+1e-6),“days_to_resolve”:days_left,
“liquidity”:liquidity,“liq_ratio”:liq_ratio,“vol_per_day”:vol_per_day,
})
market_stats={“spread”:spread,“volume”:volume,“liquidity”:liquidity,“days_left”:days_left}
safe,cat_reason=is_safe_category(question)
if not safe:
v={“verdict”:“REJECT”,“signal”:”\U0001f6a9 REJECTED”,“reason”:cat_reason,
“edge”:0.0,“safe_category”:False,“confidence”:0.0}
elif ai_prob is None:
v={“verdict”:“NOMODEL”,“signal”:”\U0001f504 No Model”,“reason”:“Run retrain.py”,
“edge”:0.0,“safe_category”:True,“confidence”:0.0}
else:
v=get_verdict(ai_prob,best_prob,question,market_stats)
ret=round((1-best_prob)/best_prob*100,2) if best_prob<1 else 0.0
ann=round(ret*365/days_left,1) if days_left>0 else 0.0
results.append({
“question”:question,“best_prob”:best_prob,“best_side”:best_side,
“spread”:spread,“ai_prob”:ai_prob,“volume”:volume,“liquidity”:liquidity,
“days_left”:days_left,“implied_return”:ret,“annual_yield”:ann,
“verdict”:v[“verdict”],“signal”:v[“signal”],“reason”:v[“reason”],
“edge”:v.get(“edge”,0.0),“confidence”:v.get(“confidence”,0.0),
“url”:f”https://polymarket.com/event/{m.get('slug','')}”,
})
except: continue
return results

with st.spinner(“Fetching live markets…”):
raw      = fetch_markets()
all_mkts = process_markets(raw,min_prob,max_days,min_vol_k)

harvest  = [m for m in all_mkts if m[“verdict”]==“HARVEST”  and m[“confidence”]>=min_conf]
value    = [m for m in all_mkts if m[“verdict”]==“VALUE”    and m[“confidence”]>=min_conf]
monitor  = [m for m in all_mkts if m[“verdict”]==“MONITOR”]
stale_l  = [m for m in all_mkts if m[“verdict”]==“STALE”]
rejected = [m for m in all_mkts if m[“verdict”] in (“REJECT”,“TRAP”,“NOMODEL”)]

c1,c2,c3,c4,c5,c6=st.columns(6)
c1.metric(”\U0001f7e2 Harvest”,len(harvest)); c2.metric(”\U0001f48e Value”,len(value))
c3.metric(”\U0001f570\ufe0f Stale”,len(stale_l)); c4.metric(”\U0001f535 Monitor”,len(monitor))
c5.metric(”\U0001f6a9 Rejected”,len(rejected)); c6.metric(”\U0001f4ca Scanned”,len(raw))
st.divider()

def render_table(mkts,title):
if not mkts: return
st.subheader(title)
rows=[{
“Market”:m[“question”],“Market Prob”:f”{m['best_side']} @ {m['best_prob']:.1%}”,
“AI Prob”:f”{m['ai_prob']:.1%}” if m[“ai_prob”] else “—”,
“Edge”:f”{m['edge']:+.1%}”,“Spread”:f”{m['spread']:.1%}”,
“Volume”:f”${m['volume']/1e6:.2f}M”,“Days”:m[“days_left”],
“Return”:f”+{m['implied_return']:.1f}%”,“Ann.Yield”:f”+{m['annual_yield']:.0f}%/yr”,
“Conf”:f”{m['confidence']:.0%}”,“Signal”:m[“signal”],
“Trade”:m[“url”],
} for m in sorted(mkts,key=lambda x:x[“volume”],reverse=True)]
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True,
column_config={“Trade”:st.column_config.LinkColumn(“Trade”)})

render_table(harvest,”\U0001f7e2 Harvest Opportunities”)
if not harvest: st.info(“No harvest opportunities — adjust filters or check back later.”)
render_table(value, “\U0001f48e Value Plays”)
if show_stale: render_table(stale_l,”\U0001f570\ufe0f Stale Order Books”)
if show_mon:   render_table(monitor,”\U0001f535 Monitor List”)
if show_rej:   render_table(rejected,”\U0001f6a9 Rejected / Trap”)

st.divider()
st.caption(f”Not financial advice. Refreshed: {datetime.now().strftime('%H:%M:%S')} | Polymarket Gamma API”)
‘’’

# ════════════════════════════════════════════════════════════════════════════

# requirements.txt

# ════════════════════════════════════════════════════════════════════════════

FILES[“requirements.txt”] = “””  
streamlit>=1.32.0
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
“””

# ════════════════════════════════════════════════════════════════════════════

# .gitignore

# ════════════════════════════════════════════════════════════════════════════

FILES[”.gitignore”] = “””  
.env
bankroll.json
traded.json
rejected.json
harvest_bot.log
**pycache**/
*.pyc
.DS_Store
models/champion.pkl
“””

# ════════════════════════════════════════════════════════════════════════════

# .github/workflows/retrain.yml

# ════════════════════════════════════════════════════════════════════════════

FILES[”.github/workflows/retrain.yml”] = “””  
name: Auto-Retrain AI Model

on:
workflow_dispatch:
schedule:
- cron: ‘0 2 * * 0’   # every Sunday 02:00 UTC

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
    run: |
      pip install pandas numpy xgboost scikit-learn joblib scipy \\
                  psycopg2-binary requests

  - name: Run retraining
    env:
      DB_NAME: ${{ secrets.DB_NAME }}
      DB_USER: ${{ secrets.DB_USER }}
      DB_PASS: ${{ secrets.DB_PASS }}
      DB_HOST: ${{ secrets.DB_HOST }}
    run: python retrain.py

  - name: Verify model created
    run: |
      [ -f models/champion.pkl ] && echo "Model OK" || (echo "Missing" && exit 1)

  - name: Commit model
    run: |
      git config --local user.email "github-actions[bot]@users.noreply.github.com"
      git config --local user.name  "github-actions[bot]"
      git add models/champion.pkl
      git diff --staged --quiet || \\
        git commit -m "chore: retrain AI model [$(date -u '+%Y-%m-%d')]"
      git push
```

“””

# ════════════════════════════════════════════════════════════════════════════

# README.md

# ════════════════════════════════════════════════════════════════════════════

FILES[“README.md”] = “””\

# Polymarket Harvest Bot

Scans Polymarket for near-certainty markets (≥96% probability) within
a short time window, filters unreliable categories, and scores confidence
using spread tightness, liquidity depth, and time horizon.

## Quick Start

```bash
python setup.py          # or: files are already generated
cd polymarket-bot
pip install -r requirements.txt
python retrain.py        # train AI model (needs internet)
streamlit run simple_polymarket.py          # no-model scanner
streamlit run polymarket_dashboard.py       # full AI dashboard
```

## Files

|File                     |Purpose                                                          |
|-------------------------|-----------------------------------------------------------------|
|`engine.py`              |Verdict logic — HARVEST / VALUE / MONITOR / STALE / TRAP / REJECT|
|`fetcher.py`             |Polymarket Gamma API wrapper with richer feature extraction      |
|`bridge.py`              |XGBoost model loader and feature engineer                        |
|`retrain.py`             |Model training script (run manually or via GitHub Actions)       |
|`simple_polymarket.py`   |Lightweight Streamlit scanner (no model required)                |
|`polymarket_dashboard.py`|Full AI dashboard (requires retrain first)                       |

## Confidence Score

Combines four signals (weighted):

- **Spread tightness** (35%) — tight YES+NO spread = confident market
- **Liquidity depth** (25%) — deep order book = hard to manipulate
- **Time horizon** (25%) — fewer days = less time for shock events
- **Volume** (15%) — more traded = stronger price discovery

## Safety Filter

Rejects markets matching high-variance categories using regex word boundaries:
crypto price targets, military events, criminal verdicts, sports results,
social media counts, net worth markets.

## ⚠️ Disclaimer

Informational only. Not financial advice.
“””

# ════════════════════════════════════════════════════════════════════════════

# Build

# ════════════════════════════════════════════════════════════════════════════

def build():
print(f”\n🔨 Building {PROJECT}/…”)

```
if os.path.exists(PROJECT):
    print(f"⚠️  Folder '{PROJECT}' already exists — delete it first to rebuild")
    sys.exit(1)

for filepath, content in FILES.items():
    full_path = os.path.join(PROJECT, filepath)
    os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ {filepath}")

os.makedirs(os.path.join(PROJECT, "models"), exist_ok=True)
open(os.path.join(PROJECT, "models", ".gitkeep"), "w").close()
print(f"  ✅ models/.gitkeep")

print(f"""
```

✅ Done! Project created in ‘{PROJECT}/’

Next steps:
cd {PROJECT}
pip install -r requirements.txt
python retrain.py
streamlit run simple_polymarket.py
“””)

if **name** == “**main**”:
build()
