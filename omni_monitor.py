"""
Variational OMNI — TradFi Perps Trading Monitor
================================================
Daily dashboard for a zero-fee volume competition.

Tracks: macro drivers (DXY, US10Y, equities), the commodity perp universe,
and computes LIVE entry/exit levels for the hedged volume-farm pairs
(CL/BZ oil spread, XAU/XAG gold-silver ratio).

Data source: Yahoo Finance (free, no API key).
Timezone: Europe/Rome.

Run:
    pip install streamlit yfinance pandas numpy pytz
    streamlit run omni_monitor.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

# ----------------------------------------------------------------------------- CONFIG
ROME = pytz.timezone("Europe/Rome")

# Map OMNI assets -> Yahoo Finance continuous-futures tickers
ASSETS = {
    "XAU":    {"name": "Gold",      "yf": "GC=F", "lev": "50x", "tier": "A"},
    "CL":     {"name": "WTI Crude", "yf": "CL=F", "lev": "50x", "tier": "A"},
    "XAG":    {"name": "Silver",    "yf": "SI=F", "lev": "50x", "tier": "B"},
    "SPCX":   {"name": "S&P proxy", "yf": "ES=F", "lev": "5x",  "tier": "B"},
    "BZ":     {"name": "Brent",     "yf": "BZ=F", "lev": "50x", "tier": "B"},
    "COPPER": {"name": "Copper",    "yf": "HG=F", "lev": "50x", "tier": "C"},
    "XPT":    {"name": "Platinum",  "yf": "PL=F", "lev": "50x", "tier": "C"},
    "XPD":    {"name": "Palladium", "yf": "PA=F", "lev": "50x", "tier": "C"},
    "NATGAS": {"name": "Nat Gas",   "yf": "NG=F", "lev": "50x", "tier": "C"},
}

MACRO = {
    "DXY":   "DX-Y.NYB",   # Dollar index (inverse to metals)
    "US10Y": "^TNX",       # 10Y yield (inverse to metals)
    "VIX":   "^VIX",       # Risk sentiment
}

# Normal spread/ratio reference bands for the hedged pairs
CL_BZ_BAND = (2.5, 5.0)    # Brent premium over WTI, USD
GS_BAND    = (80.0, 92.0)  # Gold/Silver ratio
PT_PD_BAND = (1.2, 1.6)    # Platinum/Palladium ratio

REFRESH_SEC = 60

# ----------------------------------------------------------------------------- DATA
@st.cache_data(ttl=REFRESH_SEC)
def fetch(tickers, period="5d", interval="15m"):
    """Bulk download; returns dict of DataFrames keyed by ticker."""
    out = {}
    data = yf.download(list(tickers), period=period, interval=interval,
                       group_by="ticker", auto_adjust=False, progress=False, threads=True)
    for t in tickers:
        try:
            df = data[t].dropna() if len(tickers) > 1 else data.dropna()
            if not df.empty:
                out[t] = df
        except Exception:
            pass
    return out


def last(df):
    return float(df["Close"].iloc[-1])


def pct_24h(df):
    """Approx 24h change using ~96 fifteen-min bars."""
    n = min(96, len(df) - 1)
    if n <= 0:
        return 0.0
    return (df["Close"].iloc[-1] / df["Close"].iloc[-1 - n] - 1) * 100


def overnight_range(df):
    """High/low of the last ~24h of bars — the scalping range."""
    n = min(96, len(df))
    window = df.tail(n)
    return float(window["High"].max()), float(window["Low"].min())


def session_pos(price, hi, lo):
    """Where price sits in the range, 0=low 1=high."""
    if hi == lo:
        return 0.5
    return (price - lo) / (hi - lo)

# ----------------------------------------------------------------------------- LEVELS
def reversion_levels(price, hi, lo):
    """
    Mean-reversion scalp levels inside the overnight range.
    Buy near the bottom 20%, sell near the top 20%, stop just outside.
    """
    rng = hi - lo
    buy_zone  = lo + rng * 0.20
    sell_zone = hi - rng * 0.20
    mid       = (hi + lo) / 2
    return {
        "buy_below":   buy_zone,
        "buy_stop":    lo - rng * 0.10,
        "buy_target":  mid,
        "sell_above":  sell_zone,
        "sell_stop":   hi + rng * 0.10,
        "sell_target": mid,
    }


def pair_signal(ratio, band, mode="ratio"):
    """Direction + strength for a hedged-pair trade vs its normal band."""
    lo, hi = band
    if ratio > hi:
        z = (ratio - hi) / (hi - lo)
        return "stretched HIGH", min(z, 2.0)
    if ratio < lo:
        z = (lo - ratio) / (hi - lo)
        return "stretched LOW", min(z, 2.0)
    return "in range", 0.0

# ----------------------------------------------------------------------------- CALENDAR
def todays_events():
    now = datetime.now(ROME)
    wd = now.weekday()  # 0=Mon
    ev = [
        ("08:00", "Check DXY / 10Y / Asian ranges", "All"),
        ("14:30", "US data window (CPI/NFP/PCE/claims)", "All — peak vol"),
        ("15:30", "US equity open", "SPCX, COPPER"),
        ("20:00", "FOMC (Fed days only)", "All"),
    ]
    if wd == 2:  # Wed
        ev.append(("16:30", "EIA crude inventories", "CL, BZ"))
    if wd == 3:  # Thu
        ev.append(("16:30", "EIA nat-gas storage", "NATGAS"))
    return sorted(ev), now

# ----------------------------------------------------------------------------- UI
st.set_page_config(page_title="OMNI TradFi Monitor", layout="wide", page_icon="📊")
st.markdown("<style>div[data-testid='stMetricValue']{font-size:1.1rem}</style>", unsafe_allow_html=True)

events, now = todays_events()
st.title("📊 Variational OMNI — TradFi Perps Monitor")
st.caption(f"Zero-fee volume comp · {now:%A %d %b %Y · %H:%M} Rome · auto-refresh {REFRESH_SEC}s")

with st.expander("❓ How to read this dashboard (start here)", expanded=False):
    st.markdown(
        "**Read the screen top to bottom — it's four sections:**\n\n"
        "**1. Macro Drivers** — the 'weather' for your trades. DXY (dollar) and US10Y "
        "(yield) move *opposite* to gold/silver: when they drop, metals are favored to rise. "
        "VIX is the fear gauge — high = scared market (gold up, stocks down). Just glance to "
        "get today's bias.\n\n"
        "**2. Hedged Volume Pairs** — your *main* tool and the safest way to farm comp volume. "
        "You trade two related things at once (e.g. sell gold + buy silver), so you're not "
        "betting on up/down — you're betting they snap back to normal. When a box turns green "
        "with an instruction, that's your highest-confidence trade: open **both** legs at "
        "**equal size**, wait for the relationship to normalise, close both.\n\n"
        "**3. Asset Scalping Table** — quick in-and-out trades. **Pos** shows where price sits "
        "in today's range (10% = cheap/near bottom, 90% = expensive/near top). Only act on "
        "🟢 BUY / 🔴 SELL signals, and only on **Tier A** assets (XAU, CL) while learning. "
        "Enter at Buy</Sell>, **always set the Stop**, exit at Target.\n\n"
        "**4. Calendar + Iron Rules** — times (Rome) when big news hits. Around **14:30**, "
        "**EIA (Wed)**, and **FOMC** → *stand aside*, prices jump and stops get blown through. "
        "The #1 rule: **ignore the 50x, use small size.**\n\n"
        "---\n"
        "**Daily routine:** ① check the dollar bias → ② any green pair instruction? (best trade) "
        "→ ③ scan table for 🟢/🔴 on Tier A → ④ news within 30 min? wait → ⑤ small size, always a stop, "
        "take profit at Target.\n\n"
        "*The one-liner: green pair instructions are bread-and-butter, Tier-A signals are quick "
        "trades, never trade into news, always small size with a stop.*"
    )

with st.spinner("Fetching live data…"):
    asset_tickers = [v["yf"] for v in ASSETS.values()]
    macro_tickers = list(MACRO.values())
    adata = fetch(asset_tickers)
    mdata = fetch(macro_tickers)

# ---- Macro strip
st.subheader("Macro Drivers", help="The market 'weather'. These set today's bias — "
             "you mostly just glance at them before trading.")
mc = st.columns(3)
macro_now = {}
MACRO_HELP = {
    "DXY":   "US Dollar index. Moves OPPOSITE to gold/silver. Dollar UP = metals headwind; "
             "Dollar DOWN = metals tailwind. The blue note below tells you which way today.",
    "US10Y": "US 10-year bond yield. Also OPPOSITE to metals — rising yields pressure gold. "
             "Watch around the 14:30 data window.",
    "VIX":   "The 'fear gauge'. HIGH/rising = scared market (risk-off → gold up, stocks down). "
             "LOW = calm (risk-on).",
}
for i, (label, tk) in enumerate(MACRO.items()):
    df = mdata.get(tk)
    if df is not None:
        val, chg = last(df), pct_24h(df)
        macro_now[label] = val
        hint = {"DXY": "metals inverse", "US10Y": "metals inverse", "VIX": "risk gauge"}[label]
        mc[i].metric(f"{label} · {hint}", f"{val:,.2f}", f"{chg:+.2f}%",
                     help=MACRO_HELP[label])
    else:
        mc[i].metric(label, "n/a", help=MACRO_HELP[label])

# Quick metals bias read
bias = []
if "DXY" in macro_now:
    dxy_chg = pct_24h(mdata[MACRO["DXY"]])
    bias.append("DXY up → metals headwind" if dxy_chg > 0.1 else
                "DXY down → metals tailwind" if dxy_chg < -0.1 else "DXY flat")
if bias:
    st.info("  ·  ".join(bias))

# ---- Hedged pairs (the volume engine)
st.subheader("🎯 Hedged Volume Pairs — live levels",
             help="Your MAIN tool. Trade two related assets at once so you're market-neutral — "
                  "betting they snap back to their normal relationship, not on up/down. "
                  "When a box shows a green instruction, open BOTH legs at EQUAL size, wait for "
                  "it to normalise, close both. 'In range' = no edge (can still farm volume).")

def get(asset):
    df = adata.get(ASSETS[asset]["yf"])
    return last(df) if df is not None else None

p = {a: get(a) for a in ASSETS}
pc = st.columns(3)

# CL / BZ oil spread
with pc[0]:
    st.markdown("**Oil spread · BZ − CL**")
    if p["CL"] and p["BZ"]:
        spread = p["BZ"] - p["CL"]
        state, strength = pair_signal(spread, CL_BZ_BAND)
        st.metric("Brent premium", f"${spread:.2f}", f"{state}",
                  help="How much pricier Brent (BZ) is than WTI (CL). Normally ~$2.5–5. "
                       "If it's stretched too high, short BZ + long CL (and vice versa) — "
                       "you profit as the gap returns to normal. z≈ how far from normal "
                       "(0 = normal, 1+ = very stretched).")
        st.caption(f"Normal ${CL_BZ_BAND[0]}–${CL_BZ_BAND[1]} · z≈{strength:.1f}")
        if state == "stretched HIGH":
            st.success("→ SHORT BZ / LONG CL (spread reverts down)")
        elif state == "stretched LOW":
            st.success("→ LONG BZ / SHORT CL (spread reverts up)")
        else:
            st.write("→ farm both legs neutral, no edge")
    else:
        st.write("data n/a")

# XAU / XAG ratio
with pc[1]:
    st.markdown("**Gold/Silver ratio**")
    if p["XAU"] and p["XAG"]:
        gs = p["XAU"] / p["XAG"]
        state, strength = pair_signal(gs, GS_BAND)
        st.metric("XAU/XAG", f"{gs:.1f}", f"{state}",
                  help="How many ounces of silver = 1 ounce of gold. Normally ~80–92. "
                       "If stretched HIGH, gold is expensive vs silver → short XAU + long XAG. "
                       "If LOW, the reverse. Both legs count for volume and you stay neutral. "
                       "z≈ how far from normal.")
        st.caption(f"Normal {GS_BAND[0]}–{GS_BAND[1]} · z≈{strength:.1f}")
        if state == "stretched HIGH":
            st.success("→ SHORT XAU / LONG XAG (ratio reverts down)")
        elif state == "stretched LOW":
            st.success("→ LONG XAU / SHORT XAG (ratio reverts up)")
        else:
            st.write("→ farm both legs neutral, no edge")
    else:
        st.write("data n/a")

# XPT / XPD ratio
with pc[2]:
    st.markdown("**Platinum/Palladium ratio**")
    if p["XPT"] and p["XPD"]:
        pp = p["XPT"] / p["XPD"]
        state, strength = pair_signal(pp, PT_PD_BAND)
        st.metric("XPT/XPD", f"{pp:.2f}", f"{state}",
                  help="Platinum price ÷ palladium price. Normally ~1.2–1.6. Same idea as the "
                       "other pairs, BUT both metals are thin/illiquid here — use TINY size or "
                       "skip. Not a beginner trade.")
        st.caption(f"Normal {PT_PD_BAND[0]}–{PT_PD_BAND[1]} · thin, small size")
    else:
        st.write("data n/a")

# ---- Per-asset scalping table
st.subheader("Asset Scalping Levels (overnight range mean-reversion)",
             help="Quick in-and-out trades. The idea: when price hits the bottom of its recent "
                  "range it tends to bounce (BUY), when it hits the top it tends to pull back "
                  "(SELL). Only act on 🟢/🔴 signals, only on Tier A assets while learning, and "
                  "ALWAYS set the stop.")
with st.expander("📖 What each column means"):
    st.markdown(
        "- **Tier** — A = trade freely (deep, liquid: XAU, CL). B = careful / pair-hedge only. "
        "C = thin, tiny size or skip.\n"
        "- **Price / 24h%** — current price and how much it moved in the last day.\n"
        "- **Range Lo / Range Hi** — the low and high of roughly the last 24 hours.\n"
        "- **Pos** — where price sits in that range. **10% = near the bottom (cheap, may bounce)**, "
        "**90% = near the top (expensive, may drop)**.\n"
        "- **Buy<** — the price to buy *below* (you want it cheap, near the bottom).\n"
        "- **B-Stop** — if you bought, exit here to cap the loss if it keeps falling.\n"
        "- **Sell>** — the price to short *above* (near the top).\n"
        "- **S-Stop** — if you shorted, exit here if it keeps rising.\n"
        "- **Target** — where to take profit (the middle of the range — the 'snap back' point).\n"
        "- **Signal** — 🟢 BUY zone (near bottom) · 🔴 SELL zone (near top) · ⚪ wait (middle, no edge)."
    )
rows = []
for a, meta in ASSETS.items():
    df = adata.get(meta["yf"])
    if df is None:
        rows.append({"Asset": a, "Name": meta["name"], "Tier": meta["tier"], "Price": None})
        continue
    price = last(df)
    chg = pct_24h(df)
    hi, lo = overnight_range(df)
    pos = session_pos(price, hi, lo)
    lv = reversion_levels(price, hi, lo)
    # signal: near bottom -> buy, near top -> sell
    sig = "🟢 BUY zone" if pos <= 0.22 else "🔴 SELL zone" if pos >= 0.78 else "⚪ wait"
    rows.append({
        "Asset": a, "Name": meta["name"], "Tier": meta["tier"], "Lev": meta["lev"],
        "Price": round(price, 4), "24h%": round(chg, 2),
        "Range Lo": round(lo, 4), "Range Hi": round(hi, 4),
        "Pos": f"{pos*100:.0f}%",
        "Buy<": round(lv["buy_below"], 4), "B-Stop": round(lv["buy_stop"], 4),
        "Sell>": round(lv["sell_above"], 4), "S-Stop": round(lv["sell_stop"], 4),
        "Target": round(lv["buy_target"], 4),
        "Signal": sig,
    })
table = pd.DataFrame(rows)
st.dataframe(table, use_container_width=True, hide_index=True)
st.caption("Tier A = farm freely (deep book) · B = pair-hedge / careful · C = thin, tiny size or skip")

# ---- Calendar + rules
cal, rules = st.columns([1.3, 1])
with cal:
    st.subheader("📅 Today (Rome time)",
                 help="When big news hits. Around 14:30, EIA (Wed 16:30), and FOMC, prices jump "
                      "hard and stops can get skipped — STAND ASIDE during these unless you "
                      "really know what you're doing.")
    cdf = pd.DataFrame(events, columns=["Time", "Event", "Affects"])
    st.dataframe(cdf, use_container_width=True, hide_index=True)
with rules:
    st.subheader("⚠️ Iron Rules (50x)",
                 help="The platform offers 50x leverage — that's a trap. A 2% move against a "
                      "full-50x position wipes you out. Use small size so your REAL leverage is "
                      "low, and never risk more than 1–2% of the account on one trade.")
    st.markdown(
        "- Real leverage **single-digit**, ignore the 50x\n"
        "- Risk **≤1–2%** per trade (notional × stop)\n"
        "- **Size for the gap**, not the spread\n"
        "- Stick to **Tier A** for volume farming\n"
        "- Stand aside through **14:30 / EIA / FOMC**"
    )

st.divider()
if st.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()
st.caption("Data: Yahoo Finance (15-min delayed). Levels are mechanical guides, not advice. "
           "Bands are editable at the top of the file.")
