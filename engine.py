REJECT_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "price", "hit $",
    "reach $", "above $", "below $", "dip to",
    "strike", "invade", "ceasefire", "war", "military", "troops",
    "nuclear", "missiles", "attack",
    "convicted", "sentenced", "guilty", "verdict", "ruling", "lawsuit",
    "win the match", "beat ", "championship winner", "super bowl winner",
    "world cup winner", "tweet", "post on", "elon musk net worth",
]

def is_safe_category(question: str) -> tuple:
    q = question.lower()
    for kw in REJECT_KEYWORDS:
        if kw in q:
            return False, f"Auto-rejected: contains '{kw}' — unreliable category"
    return True, "Category OK"

def get_verdict(ai_prob: float, market_prob: float, question: str = "") -> dict:
    safe, cat_reason = is_safe_category(question)
    if not safe:
        return {"verdict": "REJECT", "signal": "🚩 REJECTED", "reason": cat_reason, "edge": 0.0}
    edge = ai_prob - market_prob
    if abs(edge) > 0.30:
        return {"verdict": "TRAP", "signal": "⚠️ TRAP", "reason": f"AI vs market diverge by {abs(edge):.1%}", "edge": round(edge, 4)}
    if ai_prob >= 0.96 and market_prob >= 0.96 and edge >= -0.02:
        return {"verdict": "HARVEST", "signal": "🟢 HARVEST", "reason": f"AI {ai_prob:.1%} confirms market {market_prob:.1%}", "edge": round(edge, 4)}
    if edge > 0.05:
        return {"verdict": "VALUE", "signal": "💎 VALUE", "reason": f"Positive edge {edge:+.1%}", "edge": round(edge, 4)}
    return {"verdict": "MONITOR", "signal": "🔵 MONITOR", "reason": f"Insufficient edge ({edge:+.1%})", "edge": round(edge, 4)}
