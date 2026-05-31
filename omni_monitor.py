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
import base64
from pathlib import Path

# ----------------------------------------------------------------------------- CONFIG
ROME = pytz.timezone("Europe/Rome")

# NUNO logo embedded fallback (used if nuno_logo.png is not in the repo)
NUNO_LOGO_B64 = "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"

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
def _single(t, period, interval):
    """Fetch one ticker on its own; return cleaned df or None."""
    try:
        df = yf.Ticker(t).history(period=period, interval=interval, auto_adjust=False)
        df = df.dropna()
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=REFRESH_SEC)
def fetch(tickers, period="5d", interval="15m"):
    """Bulk download, then individually retry any ticker that came back empty.

    Streamlit Cloud's shared IP sometimes gets throttled by Yahoo on the bulk
    call, dropping individual tickers (e.g. NG=F). We retry those one-by-one,
    then fall back to a coarser interval, then daily bars, so a single missing
    ticker never shows as blank.
    """
    tickers = list(tickers)
    out = {}
    try:
        data = yf.download(tickers, period=period, interval=interval,
                           group_by="ticker", auto_adjust=False,
                           progress=False, threads=True)
        for t in tickers:
            try:
                df = data[t].dropna() if len(tickers) > 1 else data.dropna()
                if not df.empty:
                    out[t] = df
            except Exception:
                pass
    except Exception:
        pass

    # Retry any ticker missing from the bulk result, individually.
    for t in tickers:
        if t in out:
            continue
        for per, itv in [(period, interval), ("5d", "30m"), ("1mo", "1d")]:
            df = _single(t, per, itv)
            if df is not None:
                out[t] = df
                break
    return out


def _bars_per_day(df):
    """Infer how many bars make up ~24h, from the median bar spacing."""
    try:
        if len(df) < 3:
            return 1
        deltas = df.index.to_series().diff().dropna()
        med_min = deltas.median().total_seconds() / 60.0
        if med_min <= 0:
            return 1
        return max(1, round(24 * 60 / med_min))
    except Exception:
        return 96  # assume 15-min bars


def last(df):
    return float(df["Close"].iloc[-1])


def pct_24h(df):
    """Approx 24h change, adapting to whatever bar size the data uses."""
    bpd = _bars_per_day(df)
    n = min(bpd, len(df) - 1)
    if n <= 0:
        return 0.0
    return (df["Close"].iloc[-1] / df["Close"].iloc[-1 - n] - 1) * 100


def overnight_range(df):
    """High/low of roughly the last 24h of bars — the scalping range.

    Uses the inferred bars-per-day so it works whether the data is 15-min,
    30-min, or daily-fallback bars. For daily data it takes the last ~2 days
    so there's still a usable range.
    """
    bpd = _bars_per_day(df)
    n = min(max(bpd, 2), len(df))
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
def _page_icon():
    try:
        from PIL import Image
        p = Path(__file__).parent / "nuno_logo.png"
        if p.exists():
            return Image.open(p)
    except Exception:
        pass
    return "📊"

st.set_page_config(page_title="NUNO · OMNI TradFi Monitor", layout="wide", page_icon=_page_icon())
st.markdown("<style>div[data-testid='stMetricValue']{font-size:1.1rem}</style>", unsafe_allow_html=True)

events, now = todays_events()
# NUNO logo: load from repo file if present, else use embedded fallback.
def _logo_src():
    p = Path(__file__).parent / "nuno_logo.png"
    try:
        if p.exists():
            b = base64.b64encode(p.read_bytes()).decode()
            return f"data:image/png;base64,{b}"
    except Exception:
        pass
    return f"data:image/png;base64,{NUNO_LOGO_B64}"

st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:16px; margin-bottom:4px;">
        <img src="{_logo_src()}" style="height:64px; width:64px; border-radius:12px;" />
        <div>
            <div style="font-size:1.7rem; font-weight:700; line-height:1.1;">
                Variational OMNI — TradFi Perps Monitor
            </div>
            <div style="font-size:0.85rem; opacity:0.7;">Made by NUNO</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
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
