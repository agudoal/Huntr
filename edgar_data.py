#!/usr/bin/env python3
"""
edgar_data.py — Huntr Workstream A  (02. Data)
Free-data module: SEC EDGAR APIs (no key, no auth required).

Public API
----------
get_sector_sc_scores()            -> (dict[subsector -> score 0-100], audit_dict)
get_company_si_scores(universe)   -> dict[ticker -> {'score': float, 'flags': list}]
improve_float(yahoo_info)         -> float (0-1) or None

EDGAR rate-limit guidance: <= 10 req/s.  We sleep 0.25 s between calls.
User-Agent is required per SEC policy.
"""

import re
import time
import requests
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_EFTS   = "https://efts.sec.gov/LATEST/search-index"
_SUBM   = "https://data.sec.gov/submissions/CIK{:010d}.json"
_HDR    = {"User-Agent": "Huntr/1.0 research-signal contact:alex.agudo.moliner@gmail.com"}

# SIC code -> Huntr subsector label (many SICs map to the same subsector)
SIC_SUBSECTOR: dict[str, str] = {
    "7372": "appsw",    # Prepackaged Software
    "7371": "itserv",   # Computer Programming & Data Processing
    "7374": "pay",      # Computer Processing & Data Preparation
    "7375": "internet", # Information Retrieval Services
    "7376": "infrasw",  # Computer Facilities Management
    "7377": "infrasw",  # Computer Rental & Leasing
    "7379": "itserv",   # Computer Related Services (misc)
    "7389": "itserv",   # Services-Misc Business Services
    "3674": "semis",    # Semiconductors & Related Devices
    "3672": "semieq",   # Printed Circuit Boards
    "3677": "semieq",   # Electronic Coils, Transformers
    "3679": "semieq",   # Electronic Components (NEC)
    "3559": "semieq",   # Special Industry Machinery
    "3669": "hw",       # Communications Equipment (Other)
    "3576": "hw",       # Computer Communications Equipment
    "3577": "hw",       # Computer Peripheral Equipment
    "3812": "hw",       # Defense Electronics / Instruments
    "3825": "semieq",   # Instruments for Measuring
    "7993": "gaming",   # Video Games / Coin-Op Amusement (excl. slots)
    "7812": "gaming",   # Motion Picture Production (some gaming studios)
    "7380": "cyber",    # Security Services
    "7382": "cyber",    # Home Security Services (incl. software)
    "3669": "hw",       # Electronic Components & Accessories
    "4813": "hw",       # Telephone Communications
    "4899": "infrasw",  # Communications Services (NEC)
    "7372": "appsw",    # (duplicate key, last wins — both are appsw, fine)
}

ALL_SUBS = [
    "appsw", "infrasw", "itserv", "pay",
    "cyber", "internet", "hw", "semis", "semieq", "gaming",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _get(url: str, params: dict | None = None, sleep: float = 0.25, tries: int = 3):
    """GET with retries; returns parsed JSON or None on failure."""
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=_HDR, timeout=20)
            r.raise_for_status()
            time.sleep(sleep)
            return r.json()
        except Exception as exc:
            wait = 1.5 * (attempt + 1)
            if attempt < tries - 1:
                time.sleep(wait)
            else:
                print(f"    [EDGAR] ✗ {url[:70]}… → {exc}")
    return None


def _efts(params: dict, sleep: float = 0.30) -> tuple[list, int]:
    """Call EDGAR EFTS; return (hits_list, total_count)."""
    data = _get(_EFTS, params=params, sleep=sleep)
    if data is None:
        return [], 0
    hits  = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", len(hits))
    return hits, int(total)


_sic_cache: dict[str, str] = {}

def _sic_for_cik(cik_raw: str) -> str:
    """Fetch SIC code string for a CIK; cached to avoid duplicate calls."""
    key = re.sub(r"[^0-9]", "", cik_raw)
    if key in _sic_cache:
        return _sic_cache[key]
    try:
        data = _get(_SUBM.format(int(key)), sleep=0.20)
        sic  = str(data.get("sic") or "") if data else ""
    except Exception:
        sic = ""
    _sic_cache[key] = sic
    return sic


def _cik_from_hit(hit: dict) -> str:
    src = hit.get("_source", {})
    cik = src.get("entity_id", "")
    if not cik:
        for dn in src.get("display_names", []):
            cik = dn.get("id", "")
            if cik:
                break
    return cik


def _date_window(months_back: int) -> tuple[str, str]:
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=int(months_back * 30.44))
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# f_sc — Sector Consolidation
# ---------------------------------------------------------------------------
def get_sector_sc_scores() -> tuple[dict, dict]:
    """
    Pull SC TO-T + DEFM14A filings from EDGAR EFTS for the last 24 months.
    Map each target's SIC code -> subsector; count unique-company deals per subsector.
    Returns:
        scores  = dict[subsector -> score 0-100]   (max subsector = 100; floor = 20)
        audit   = dict[subsector -> {'count': N, 'score': S}]
    """
    startdt, enddt = _date_window(24)
    seen_ciks:  set[str] = set()
    sub_counts: dict[str, int] = defaultdict(int)

    for form_type in ("SC TO-T", "DEFM14A"):
        hits, total = _efts({
            "forms":     form_type,
            "dateRange": "custom",
            "startdt":   startdt,
            "enddt":     enddt,
            "size":      "50",      # sample; enough to calibrate subsector heat
        })
        print(f"  [EDGAR f_sc] {form_type} last 24m: {total} total, {len(hits)} sampled")

        for h in hits:
            cik = _cik_from_hit(h)
            if not cik or cik in seen_ciks:
                continue
            seen_ciks.add(cik)
            sic = _sic_for_cik(cik)
            sub = SIC_SUBSECTOR.get(sic)
            if sub:
                sub_counts[sub] += 1

    counts  = {s: sub_counts.get(s, 0) for s in ALL_SUBS}
    max_c   = max(counts.values(), default=1) or 1
    scores  = {s: max(20, round(c / max_c * 100)) for s, c in counts.items()}
    audit   = {s: {"count": counts[s], "score": scores[s]} for s in ALL_SUBS}
    print(f"  [EDGAR f_sc] Subsector deal counts: { {s: counts[s] for s in ALL_SUBS if counts[s]>0} }")
    return scores, audit


# ---------------------------------------------------------------------------
# f_si — Strategic Interest (per company)
# ---------------------------------------------------------------------------
def get_company_si_scores(universe: list[dict]) -> dict:
    """
    Per-company strategic-interest score derived from EDGAR EFTS searches.

    Scoring (additive; capped at 100):
      +50  SC TO-T filing names this company as target
      +40  SC 14D-9 (board recommendation/rejection = active offer)
      +30  SC 13D  (activist / large-stake >5% filing)
      +20  DEFM14A or SC 13E-3 (merger proxy / going-private)
      +10  recency bonus (filing within last 6 months)
      Base = 50 (neutral — no EDGAR evidence)

    Returns: dict[ticker -> {'score': float, 'flags': list[str]}]
    Most EMEA names will score 50 (neutral); flagged names 60–100.
    """
    startdt_12m, enddt = _date_window(12)
    startdt_6m,  _     = _date_window(6)

    results: dict[str, dict] = {}

    for i, u in enumerate(universe, 1):
        name   = u["name"]
        ticker = u["ticker"].strip()

        # Build search terms — quoted full name + first meaningful word as fallback
        clean  = re.sub(r"[,.()/&]", " ", name).strip()
        words  = clean.split()
        short  = words[0] if words else clean      # e.g. "Allfunds" from "Allfunds Group"
        # Avoid overly generic short names (len<=3) to prevent false positives
        use_short = len(short) > 3

        raw_pts = 0
        flags:  list[str] = []

        # 1. Tender offer — company named as target in SC TO-T
        h1, _ = _efts({
            "q":         f'"{name}"',
            "forms":     "SC TO-T",
            "dateRange": "custom",
            "startdt":   startdt_12m,
            "enddt":     enddt,
            "size":      "3",
        })
        if h1:
            raw_pts += 50
            fd = h1[0].get("_source", {}).get("file_date", "")
            if fd >= startdt_6m:
                raw_pts += 10          # recency bonus
            flags.append(f"SC TO-T tender offer ({fd})")

        # 2. Board response = active offer underway (SC 14D-9)
        h2, _ = _efts({
            "q":         f'"{name}"',
            "forms":     "SC 14D9",
            "dateRange": "custom",
            "startdt":   startdt_12m,
            "enddt":     enddt,
            "size":      "3",
        })
        if h2:
            raw_pts += 40
            flags.append("SC 14D-9 board response (active offer)")

        # 3. Activist / large-stake disclosure (SC 13D)
        h3, _ = _efts({
            "q":         f'"{name}"',
            "forms":     "SC 13D",
            "dateRange": "custom",
            "startdt":   startdt_12m,
            "enddt":     enddt,
            "size":      "5",
        })
        if h3:
            raw_pts += 30
            flags.append(f"SC 13D activist/large-holder ({len(h3)} filing(s))")

        # 4. Merger proxy or going-private transaction (DEFM14A / SC 13E-3)
        q4   = f'"{name}"' if len(name) > 6 else (f'"{short}"' if use_short else None)
        if q4:
            h4, _ = _efts({
                "q":         q4,
                "forms":     "DEFM14A,SC 13E-3",
                "dateRange": "custom",
                "startdt":   startdt_12m,
                "enddt":     enddt,
                "size":      "3",
            })
            if h4:
                raw_pts += 20
                flags.append("Merger proxy / going-private filing")

        # Final score: 50 (neutral) + signal evidence, capped at 100
        final = min(50 + raw_pts, 100) if raw_pts > 0 else 50
        results[ticker] = {"score": float(final), "flags": flags}

        status = f"  [{flags[0]}]" if flags else ""
        print(f"  [EDGAR f_si] {i:>3}/{len(universe)}  {name}: raw_pts={raw_pts} → {final}{status}")
        time.sleep(0.05)   # light between-company pacing; each EFTS call already sleeps

    return results


# ---------------------------------------------------------------------------
# Improved float (f_own)
# ---------------------------------------------------------------------------
def improve_float(info: dict) -> float | None:
    """
    Return a corrected free-float fraction (0.0–1.0) from a Yahoo `info` dict.

    Method
    ------
    1. Yahoo floatShares / sharesOutstanding  (existing pipeline method)
    2. Cross-check: 1 – heldPercentInsiders   (more reliable for EU names)
       - `heldPercentInsiders` captures executive/board holdings only;
         `1 – insiders` is a lower-bound on the tradeable float.
    3. Accept the *higher* of the two estimates — artificially low float values
       are the dominant data-quality failure (e.g. Worldline 9.6%), so we
       prefer the more open (higher-float) reading when both are available.
    4. Reject values below 5% — almost certainly a data gap; return None.
    5. Cap at 100%.
    """
    candidates: list[float] = []

    # Method 1 — floatShares ratio
    fl = info.get("floatShares")
    sh = info.get("sharesOutstanding")
    if fl and sh and sh > 0:
        r = fl / sh
        if 0.0 < r <= 1.0:
            candidates.append(r)

    # Method 2 — 1 minus insiders
    ins = info.get("heldPercentInsiders")
    if ins is not None:
        try:
            ins_f = float(ins)
            if 0.0 <= ins_f < 1.0:
                approx = 1.0 - ins_f
                if approx > 0.05:
                    candidates.append(approx)
        except (TypeError, ValueError):
            pass

    if not candidates:
        return None

    best = min(max(candidates), 1.0)   # highest estimate, capped at 100%
    if best < 0.05:
        return None   # reject — almost certainly a data gap
    return best
