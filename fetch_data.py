#!/usr/bin/env python3
"""
Axle Flex Intel - Structured data fetcher
Sources: Elexon BMRS (BOALF, WINDFOR, FUELHH, TSDF, MID, MELNGC)
Output: JSON to stdout for consumption by the daily briefing agent.
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
SESSION = requests.Session()
SESSION.headers["Accept"] = "application/json"


def fetch(dataset, params):
    try:
        r = SESSION.get(f"{BASE}/{dataset}", params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        return {"_error": str(e)}


def date_window(days_ago=1):
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    start = d.strftime("%Y-%m-%dT00:00:00Z")
    end = d.strftime("%Y-%m-%dT23:59:59Z")
    date = d.strftime("%Y-%m-%d")
    return date, start, end


def curtailment_analysis():
    date, start, end = date_window(1)
    items = fetch("BOALF", {"from": start, "to": end})
    if isinstance(items, dict):
        return {"error": items["_error"], "date": date}

    # SO-instructed turn-downs: system operator reduced a unit's output
    turn_downs = [
        i for i in items
        if i.get("soFlag") and i.get("levelTo", 0) < i.get("levelFrom", 0)
    ]

    # Wind BMU heuristic: names containing common offshore/onshore wind patterns
    WIND_PATTERNS = ("WEO", "WIN", "WND", "WIND", "MOWEO", "HOWAO", "DUDGE",
                     "WOWEO", "LNWD", "GLNKL", "VNTS", "BEINND", "ORMND",
                     "STRM", "WHILW", "FARR", "CLAC", "BRWND")
    wind_downs = [
        i for i in turn_downs
        if any(p in i.get("nationalGridBmUnit", "").upper() for p in WIND_PATTERNS)
    ]

    def mw_hours(instructions):
        total = 0.0
        for i in instructions:
            mw_reduction = i["levelFrom"] - i["levelTo"]
            # Estimate duration: each settlement period = 30 min
            sp_span = abs(i.get("settlementPeriodTo", i.get("settlementPeriodFrom", 1))
                          - i.get("settlementPeriodFrom", 1)) or 1
            hours = sp_span * 0.5
            total += mw_reduction * hours
        return round(total, 1)

    by_bmu = {}
    for i in wind_downs:
        bmu = i.get("nationalGridBmUnit", i.get("bmUnit", "unknown"))
        by_bmu.setdefault(bmu, 0)
        by_bmu[bmu] += i["levelFrom"] - i["levelTo"]

    top_wind = sorted(by_bmu.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "date": date,
        "total_boalf_records": len(items),
        "so_instructed_turn_downs": len(turn_downs),
        "wind_curtailment_instructions": len(wind_downs),
        "estimated_wind_curtailment_mwh": mw_hours(wind_downs),
        "estimated_all_curtailment_mwh": mw_hours(turn_downs),
        "top_curtailed_wind_bmus": [{"bmu": b, "mw_reduction": round(v, 0)} for b, v in top_wind],
    }


def wind_forecast():
    date, start, end = date_window(1)
    items = fetch("WINDFOR", {"from": start, "to": end})
    if isinstance(items, dict):
        return {"error": items["_error"]}

    vals = [i["generation"] for i in items if i.get("generation") is not None]
    if not vals:
        return {"date": date, "error": "no wind forecast data"}

    return {
        "date": date,
        "wind_forecast_mw": {
            "min": round(min(vals), 0),
            "max": round(max(vals), 0),
            "avg": round(sum(vals) / len(vals), 0),
        },
        "data_points": len(vals),
    }


def generation_mix():
    date, start, end = date_window(0)  # today's latest published data
    items = fetch("FUELHH", {"from": start, "to": end})
    if isinstance(items, dict):
        return {"error": items["_error"]}

    # Group by fuel type, take average generation
    by_fuel = {}
    for i in items:
        fuel = i.get("fuelType", "UNKNOWN")
        gen = i.get("generation", 0) or 0
        by_fuel.setdefault(fuel, []).append(gen)

    summary = {
        fuel: {"avg_mw": round(sum(vals) / len(vals), 0), "periods": len(vals)}
        for fuel, vals in by_fuel.items()
    }

    total_avg = sum(v["avg_mw"] for v in summary.values())
    for fuel in summary:
        pct = (summary[fuel]["avg_mw"] / total_avg * 100) if total_avg else 0
        summary[fuel]["share_pct"] = round(pct, 1)

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "note": "today's published half-hourly data",
        "by_fuel": summary,
        "total_avg_mw": round(total_avg, 0),
    }


def demand_forecast():
    # Today's transmission system demand forecast (ESO published)
    date, start, end = date_window(0)
    items = fetch("TSDF", {"from": start, "to": end})
    if isinstance(items, dict):
        return {"error": items["_error"]}

    # Filter for GB boundary (most useful for national view)
    gb = [i for i in items if i.get("boundary") == "N"]
    if not gb:
        gb = items  # fallback: use all

    vals = [i["demand"] for i in gb if i.get("demand") is not None]
    if not vals:
        return {"date": date, "error": "no TSDF demand values"}

    # Also fetch national demand forecast (NDFD) for day-ahead view
    ndfd = fetch("NDFD", {"from": start, "to": end})
    ndfd_vals = []
    if not isinstance(ndfd, dict) and ndfd:
        ndfd_vals = [i["demand"] for i in ndfd if i.get("demand") is not None]

    result = {
        "date": date,
        "tsdf_mw": {
            "min": round(min(vals), 0),
            "max": round(max(vals), 0),
            "avg": round(sum(vals) / len(vals), 0),
        },
        "periods": len(vals),
    }
    if ndfd_vals:
        result["ndfd_day_ahead_mw"] = {
            "min": round(min(ndfd_vals), 0),
            "max": round(max(ndfd_vals), 0),
        }

    return result


def system_margin():
    date, start, end = date_window(0)
    items = fetch("MELNGC", {"from": start, "to": end})
    if isinstance(items, dict):
        return {"error": items["_error"]}

    vals = [i["margin"] for i in items if i.get("margin") is not None]
    if not vals:
        return {"date": date, "error": "no margin data"}

    tight_periods = [v for v in vals if v < 500]
    return {
        "date": date,
        "margin_mw": {
            "min": round(min(vals), 0),
            "max": round(max(vals), 0),
            "avg": round(sum(vals) / len(vals), 0),
        },
        "tight_margin_periods_below_500mw": len(tight_periods),
        "periods_total": len(vals),
    }


def market_index_prices():
    date, start, end = date_window(1)
    items = fetch("MID", {"from": start, "to": end})
    if isinstance(items, dict):
        return {"error": items["_error"]}

    prices = [i["price"] for i in items if i.get("price") is not None]
    if not prices:
        return {"date": date, "error": "no MID prices"}

    # Find periods with negative prices (oversupply signal)
    negative = [p for p in prices if p < 0]

    return {
        "date": date,
        "market_index_price_gbp_mwh": {
            "min": round(min(prices), 2),
            "max": round(max(prices), 2),
            "avg": round(sum(prices) / len(prices), 2),
        },
        "negative_price_periods": len(negative),
        "total_periods": len(prices),
        "data_providers": list({i.get("dataProvider") for i in items if i.get("dataProvider")}),
    }


def main():
    print("Fetching Axle Flex Intel data from Elexon BMRS...", file=sys.stderr)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "curtailment": curtailment_analysis(),
        "wind_forecast": wind_forecast(),
        "generation_mix": generation_mix(),
        "demand_forecast": demand_forecast(),
        "system_margin": system_margin(),
        "market_prices": market_index_prices(),
    }

    print(json.dumps(output, indent=2))
    print("\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
