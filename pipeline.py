#!/usr/bin/env python3
"""
Huntr Stage-1 pipeline (automation version).
Reads universe.csv, scores every name via Yahoo Finance (yfinance), writes huntr_scored.json.
Same logic as the validated Colab notebook v2: EUR-converted size, winsorised valuation
(EV/EBITDA cap 40x blended with EV/Sales), free float capped at 100%.
Runs unattended on GitHub Actions. The EODHD key (env EODHD_API_KEY) is reserved for a future
universe-refresh step (the free tier is 20 calls/day, fine for the screener, not per-name fundamentals).
"""
import csv, json, time
from datetime import datetime, timezone
import yfinance as yf
import pandas as pd

SUFFIX_CCY = {".PA":"EUR",".AS":"EUR",".MI":"EUR",".DE":"EUR",".HE":"EUR",".MC":"EUR",
              ".VI":"EUR",".BR":"EUR",".LS":"EUR",".L":"GBP",".SW":"CHF",".ST":"SEK",
              ".OL":"NOK",".CO":"DKK",".WA":"PLN",".JO":"ZAR"}

def ccy_of(tk):
    for suf, c in SUFFIX_CCY.items():
        if tk.endswith(suf):
            return c
    return "USD"   # US-listed ADRs

def fetch_fx():
    fb = {"EUR":1.0,"USD":0.92,"GBP":1.17,"CHF":1.05,"SEK":0.088,"NOK":0.086,"DKK":0.134,"PLN":0.23,"ZAR":0.050}
    fx = {"EUR":1.0}
    for c in ["USD","GBP","CHF","SEK","NOK","DKK","PLN","ZAR"]:
        val = None
        try:
            r = yf.Ticker(f"EUR{c}=X").fast_info.get("last_price")
            if r:
                val = 1.0 / r
        except Exception:
            pass
        fx[c] = val if val else fb[c]
        time.sleep(0.2)
    return fx

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

def load_universe(path="universe.csv"):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("status") or "active").strip().lower() == "delisted":
                continue
            rows.append(r)
    return rows

def pct(series, invert=False):
    r = series.rank(pct=True) * 100
    return (100 - r) if invert else r

def main():
    universe = load_universe()
    fx = fetch_fx()
    print("FX (EUR per unit):", {k: round(v, 4) for k, v in fx.items()})
    recs = []
    for i, u in enumerate(universe, 1):
        tk = u["ticker"].strip()
        # start with an all-blank record so a single bad name can never kill the whole run
        rec = {"name": u["name"], "ticker": tk, "region": u["region"], "subsector": u["subsector"],
               "ccy": ccy_of(tk), "mktcap_eur": None, "ev_ebitda": None, "ev_rev": None,
               "nd_ebitda": None, "float_pct": None}
        try:
            info = get_info(tk)
            td, tc = info.get("totalDebt"), info.get("totalCash")
            net_debt = (td - tc) if (td is not None and tc is not None) else None
            mc = info.get("marketCap")
            ebitda = info.get("ebitda")
            fl, sh = info.get("floatShares"), info.get("sharesOutstanding")
            flp = (fl / sh) if (fl and sh) else None
            if flp is not None:
                flp = min(flp, 1.0)
            rec.update({
                "mktcap_eur": mc * fx.get(rec["ccy"], 1.0) if mc else None,
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "ev_rev": info.get("enterpriseToRevenue"),
                # guard: only divide when BOTH net debt and EBITDA are real numbers
                "nd_ebitda": (net_debt / ebitda) if (net_debt is not None and ebitda) else None,
                "float_pct": flp,
            })
        except Exception as e:
            print(f'      ! {tk} skipped ({type(e).__name__})')
        recs.append(rec)
        print(f'{i:>3}/{len(universe)}  {u["name"]}')
        time.sleep(0.3)

    df = pd.DataFrame(recs)
    for col in ["mktcap_eur", "ev_ebitda", "ev_rev", "nd_ebitda", "float_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    CAP = 40.0
    ev_ebitda_clean = df["ev_ebitda"].where((df["ev_ebitda"] > 0) & (df["ev_ebitda"] <= CAP))
    ev_rev_clean = df["ev_rev"].where(df["ev_rev"] > 0)
    df["f_val"] = pd.concat([pct(ev_ebitda_clean, True), pct(ev_rev_clean, True)], axis=1).mean(axis=1)
    df["f_own"] = pct(df["float_pct"])
    df["f_bs"]  = pct(df["nd_ebitda"], True)
    df["f_sz"]  = pct(df["mktcap_eur"], True)
    df["f_sc"]  = 50.0
    df["f_si"]  = 50.0

    W = {"f_val":20, "f_own":20, "f_bs":15, "f_sz":15, "f_sc":15, "f_si":15}
    for k in W:
        df[k] = df[k].fillna(50.0)
    df["score"] = (sum(df[k]*w for k, w in W.items()) / sum(W.values())).round(0).astype(int)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["decile"] = pd.qcut(df["score"].rank(method="first"), 10, labels=range(1, 11)).astype(int)
    live = ["ev_ebitda", "float_pct", "nd_ebitda", "mktcap_eur"]
    df["coverage"] = df[live].notna().sum(axis=1).astype(str) + "/4"

    out = []
    for _, r in df.iterrows():
        out.append({
            "name": r["name"], "ticker": r["ticker"], "region": r["region"], "subsector": r["subsector"],
            "score": int(r["score"]), "decile": int(r["decile"]), "rank": int(r["rank"]),
            "coverage": r["coverage"], "currency": r["ccy"],
            "factors": {k: (None if pd.isna(r[k]) else round(float(r[k]), 1)) for k in W},
            "raw": {
                "mktcap_eur": None if pd.isna(r["mktcap_eur"]) else float(r["mktcap_eur"]),
                "ev_ebitda":  None if pd.isna(r["ev_ebitda"])  else float(r["ev_ebitda"]),
                "ev_rev":     None if pd.isna(r["ev_rev"])     else float(r["ev_rev"]),
                "nd_ebitda":  None if pd.isna(r["nd_ebitda"])  else float(r["nd_ebitda"]),
                "float_pct":  None if pd.isna(r["float_pct"])  else float(r["float_pct"]),
            },
        })
    payload = {"meta": {"source": "Yahoo Finance via yfinance",
                        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                        "version": "stage1-auto", "weights": W,
                        "note": "Nightly automated run. f_sc & f_si neutral placeholders; ownership = Yahoo free float."},
               "companies": out}
    with open("huntr_scored.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Wrote huntr_scored.json with", len(out), "companies.")

if __name__ == "__main__":
    main()
