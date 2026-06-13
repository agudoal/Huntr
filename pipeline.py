#!/usr/bin/env python3
"""
Huntr pipeline  --  Stage-1 + Workstream A  (02. Data)
Reads universe.csv, scores every name via Yahoo Finance (yfinance),
then enriches f_sc (sector consolidation) and f_si (strategic interest)
from SEC EDGAR free APIs via edgar_data.py.
Writes huntr_scored.json.

Factor  Weight  Source
------  ------  -----------------------------------------------
f_val    20%    Yahoo: EV/EBITDA & EV/Sales (winsorised + blended)
f_own    20%    Yahoo: free float (improved by heldPercentInsiders)
f_bs     15%    Yahoo: net debt / EBITDA
f_sz     15%    Yahoo: market cap (EUR-converted)
f_sc     15%    EDGAR EFTS: trailing-24m deal count per subsector
f_si     15%    EDGAR EFTS: per-company tender / activist / merger filings
"""

import csv
import json
import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

import edgar_data  # Workstream A -- EDGAR enrichment
import insights     # Buyer-ranking & structured-thesis engine

# ---------------------------------------------------------------------------
# Currency / FX helpers  (unchanged from Stage-1 v2)
# ---------------------------------------------------------------------------
SUFFIX_CCY = {
    ".PA": "EUR", ".AS": "EUR", ".MI": "EUR", ".DE": "EUR",
    ".HE": "EUR", ".MC": "EUR", ".VI": "EUR", ".BR": "EUR",
    ".LS": "EUR", ".L":  "GBP", ".SW": "CHF", ".ST": "SEK",
    ".OL": "NOK", ".CO": "DKK", ".WA": "PLN", ".JO": "ZAR",
}

def ccy_of(tk):
    for suf, c in SUFFIX_CCY.items():
        if tk.endswith(suf):
            return c
    return "USD"


def fetch_fx():
    fallback = {
        "EUR": 1.0, "USD": 0.92, "GBP": 1.17, "CHF": 1.05,
        "SEK": 0.088, "NOK": 0.086, "DKK": 0.134, "PLN": 0.23, "ZAR": 0.050,
    }
    fx = {"EUR": 1.0}
    for c in ["USD", "GBP", "CHF", "SEK", "NOK", "DKK", "PLN", "ZAR"]:
        val = None
        try:
            val = yf.Ticker("EUR" + c + "=X").fast_info.get("last_price")
            if val:
                val = 1.0 / val
        except Exception:
            pass
        fx[c] = val if val else fallback[c]
        time.sleep(0.2)
    return fx


# ---------------------------------------------------------------------------
# Yahoo fetch with retry
# ---------------------------------------------------------------------------
def get_info(tk, tries=3):
    for _ in range(tries):
        try:
            d = yf.Ticker(tk).info or {}
            if d.get("marketCap"):
                return d
        except Exception:
            pass
        time.sleep(1.0)
    return {}


# ---------------------------------------------------------------------------
# Universe loader
# ---------------------------------------------------------------------------
def load_universe(path="universe.csv"):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("status") or "active").strip().lower() == "delisted":
                continue
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------
def pct(series, invert=False):
    r = series.rank(pct=True) * 100
    return (100 - r) if invert else r


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    universe = load_universe()
    fx = fetch_fx()
    print("FX (EUR per unit):", {k: round(v, 4) for k, v in fx.items()})

    # -----------------------------------------------------------------------
    # Pass 1 -- Yahoo fundamentals
    # -----------------------------------------------------------------------
    def fetch_one(u):
        tk = u["ticker"].strip()
        rec = {
            "name": u["name"], "ticker": tk,
            "region": u["region"], "subsector": u["subsector"],
            "country": u.get("country", ""),
            "ccy": ccy_of(tk),
            "mktcap_eur": None, "ev_ebitda": None, "ev_rev": None,
            "nd_ebitda": None, "float_pct": None,
        }
        try:
            info = get_info(tk)
            td, tc = info.get("totalDebt"), info.get("totalCash")
            net_debt = (td - tc) if (td is not None and tc is not None) else None
            mc = info.get("marketCap")
            ebitda = info.get("ebitda")
            # *** Workstream A: improved float ***
            flp = edgar_data.improve_float(info)
            rec.update({
                "mktcap_eur": mc * fx.get(rec["ccy"], 1.0) if mc else None,
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "ev_rev": info.get("enterpriseToRevenue"),
                "nd_ebitda": (net_debt / ebitda)
                             if (net_debt is not None and ebitda) else None,
                "float_pct": flp,
            })
        except Exception as e:
            print("      ! " + tk + " skipped (" + type(e).__name__ + ": " + str(e) + ")")
        return rec

    recs = []
    for i, u in enumerate(universe, 1):
        recs.append(fetch_one(u))
        print(str(i).rjust(3) + "/" + str(len(universe)) + "  " + u["name"])
        time.sleep(0.8)

    # Second pass: retry blanks after rate-limit cooldown
    missing = [j for j, r in enumerate(recs) if r["mktcap_eur"] is None]
    if missing:
        print("Retrying " + str(len(missing)) + " names after 45 s cooldown...")
        time.sleep(45)
        for j in missing:
            r2 = fetch_one(universe[j])
            if r2["mktcap_eur"] is not None:
                recs[j] = r2
            time.sleep(1.2)
        still = sum(1 for j in missing if recs[j]["mktcap_eur"] is None)
        print("After retry: " + str(len(missing) - still) + " recovered, " + str(still) + " still blank.")

    # -----------------------------------------------------------------------
    # Pass 2 -- EDGAR enrichment (Workstream A)
    # -----------------------------------------------------------------------
    print("\n-- EDGAR enrichment --")

    # Defaults — used if EDGAR is unreachable (graceful fallback to neutral 50)
    _floor = {s: 50 for s in edgar_data.ALL_SUBS}
    _floor_audit = {s: {"count": 0, "score": 50} for s in edgar_data.ALL_SUBS}
    sc_scores, sc_audit = _floor, _floor_audit
    si_results: dict = {}

    try:
        print("Fetching sector consolidation scores (EDGAR)...")
        sc_scores, sc_audit = edgar_data.get_sector_sc_scores()
    except Exception as exc:
        print(f"  [EDGAR f_sc] ERROR (using floor=50): {exc}")

    try:
        print("Fetching per-company strategic-interest signals (EDGAR)...")
        si_results = edgar_data.get_company_si_scores(universe)
    except Exception as exc:
        print(f"  [EDGAR f_si] ERROR (using neutral=50): {exc}")

    # -----------------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------------
    df = pd.DataFrame(recs)
    for col in ["mktcap_eur", "ev_ebitda", "ev_rev", "nd_ebitda", "float_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    CAP = 40.0
    ev_ebitda_clean = df["ev_ebitda"].where(
        (df["ev_ebitda"] > 0) & (df["ev_ebitda"] <= CAP)
    )
    ev_rev_clean = df["ev_rev"].where(df["ev_rev"] > 0)
    df["f_val"] = pd.concat(
        [pct(ev_ebitda_clean, True), pct(ev_rev_clean, True)], axis=1
    ).mean(axis=1)

    df["f_own"] = pct(df["float_pct"])
    df["f_bs"] = pct(df["nd_ebitda"], True)
    df["f_sz"] = pct(df["mktcap_eur"], True)

    # *** Workstream A: sector consolidation -- subsector lookup ***
    df["f_sc"] = df["subsector"].map(sc_scores).fillna(50.0)

    # *** Workstream A: strategic interest -- per-company EDGAR signal ***
    df["f_si"] = df["ticker"].map(
        {tk: v["score"] for tk, v in si_results.items()}
    ).fillna(50.0)

    W = {"f_val": 20, "f_own": 20, "f_bs": 15, "f_sz": 15, "f_sc": 15, "f_si": 15}
    for k in W:
        df[k] = df[k].fillna(50.0)

    df["score"] = (
        sum(df[k] * w for k, w in W.items()) / sum(W.values())
    ).round(0).astype(int)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["decile"] = pd.qcut(
        df["score"].rank(method="first"), 10, labels=range(1, 11)
    ).astype(int)

    live_cols = ["ev_ebitda", "float_pct", "nd_ebitda", "mktcap_eur"]
    df["coverage"] = df[live_cols].notna().sum(axis=1).astype(str) + "/4"

    # -----------------------------------------------------------------------
    # Serialise to JSON
    # -----------------------------------------------------------------------
    out = []
    for _, r in df.iterrows():
        tk = r["ticker"]
        si_info = si_results.get(tk, {"score": 50.0, "flags": []})
        sub = r["subsector"]
        sc_info = sc_audit.get(sub, {"count": 0, "score": 50})

        company = {
            "name": r["name"],
            "ticker": tk,
            "region": r["region"],
            "country": r.get("country", ""),
            "subsector": sub,
            "score": int(r["score"]),
            "decile": int(r["decile"]),
            "rank": int(r["rank"]),
            "coverage": r["coverage"],
            "currency": r["ccy"],
            "factors": {
                k: (None if pd.isna(r[k]) else round(float(r[k]), 1))
                for k in W
            },
            "raw": {
                "mktcap_eur": None if pd.isna(r["mktcap_eur"]) else float(r["mktcap_eur"]),
                "ev_ebitda":  None if pd.isna(r["ev_ebitda"])  else float(r["ev_ebitda"]),
                "ev_rev":     None if pd.isna(r["ev_rev"])      else float(r["ev_rev"]),
                "nd_ebitda":  None if pd.isna(r["nd_ebitda"])   else float(r["nd_ebitda"]),
                "float_pct":  None if pd.isna(r["float_pct"])   else float(r["float_pct"]),
            },
            "edgar": {
                "sc_deals":    sc_info["count"],
                "sc_score":    sc_info["score"],
                "si_score":    si_info["score"],
                "si_flags":    si_info["flags"],
                "si_flag_str": " | ".join(si_info["flags"]) if si_info["flags"] else "",
            },
        }

        # --- Buyer ranking + structured thesis (insights.py) ---
        # Re-ranks named acquirers from tonight's factors and injects live
        # figures into the thesis, so both refresh every night.
        try:
            _ins = insights.enrich({
                "name": company["name"], "ticker": tk,
                "subsector": company["subsector"],
                "factors": company["factors"],
                "raw": company["raw"],
                "edgar": {"sc_deals": sc_info["count"], "si_flags": si_info["flags"]},
            })
            company["buyers"] = _ins["buyers"]
            company["thesis"] = _ins["thesis"]
        except Exception as _e:
            print("      ! insights failed for " + tk + " (" + type(_e).__name__ + ": " + str(_e) + ")")
            company["buyers"], company["thesis"] = [], {}

        out.append(company)

    payload = {
        "meta": {
            "source":    "Yahoo Finance (yfinance) + SEC EDGAR EFTS",
            "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "version":   "workstream-a",
            "weights":   W,
            "note": (
                "f_val/f_own/f_bs/f_sz from Yahoo; "
                "f_sc from EDGAR SC TO-T + DEFM14A deal counts (24m); "
                "f_si from EDGAR per-company SC TO-T / 14D-9 / 13D search. "
                "f_own improved: max(floatShares ratio, 1-heldPercentInsiders)."
            ),
        },
        "companies": out,
    }

    with open("huntr_scored.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\nWrote huntr_scored.json with " + str(len(out)) + " companies.")


if __name__ == "__main__":
    main()
