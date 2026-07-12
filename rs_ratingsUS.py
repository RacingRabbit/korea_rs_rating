"""
IBD-Style RS (Relative Strength) Rating Calculator
====================================================
Independent, open-source approximation of the IBD RS Rating methodology.
Not affiliated with, endorsed by, or connected to Investor's Business Daily
or TradingView in any way.

Universe: US common stocks on NASDAQ, NYSE, and AMEX (NYSE Arca/NYSE American)
Formula:  RS_raw = 0.4*Perf3M + 0.2*Perf6M + 0.2*Perf9M + 0.2*Perf12M
          (Perf9M is linearly interpolated between Perf6M and Perf12M,
           since TradingView's screener does not expose a native 9M field)
Output:   RS Rating = percentile rank of RS_raw, scaled 1-99 (IBD convention)

Requires: pip install tradingview-screener pandas --break-system-packages
"""

import argparse
import json
from datetime import datetime, timezone

import pandas as pd
from tradingview_screener import Query, col


def fetch_universe() -> pd.DataFrame:
    """Pull the full US common-stock universe with performance fields."""
    query = (
        Query()
        .select(
            "name",
            "description",
            "exchange",
            "close",
            "volume",
            "market_cap_basic",
            "Perf.3M",
            "Perf.6M",
            "Perf.Y",
        )
        .where(
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("type") == "stock",
            col("typespecs").has("common"),
        )
        .set_markets("america")
        .limit(10000)
    )

    n_rows, df = query.get_scanner_data()
    print(f"Fetched {n_rows} rows from TradingView scanner (returned {len(df)}).")
    return df


def clean_universe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows missing the performance fields needed for the RS calc."""
    required = ["Perf.3M", "Perf.6M", "Perf.Y"]
    before = len(df)
    df = df.dropna(subset=required).copy()
    print(f"Dropped {before - len(df)} rows with missing performance data "
          f"({len(df)} remain).")
    return df


def compute_rs_rating(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the weighted RS score and convert it to a 1-99 percentile rank."""
    df["Perf.9M_interp"] = (df["Perf.6M"] + df["Perf.Y"]) / 2

    df["rs_raw"] = (
        0.4 * df["Perf.3M"]
        + 0.2 * df["Perf.6M"]
        + 0.2 * df["Perf.9M_interp"]
        + 0.2 * df["Perf.Y"]
    )

    # Percentile rank -> scale to IBD's 1-99 convention
    pct_rank = df["rs_raw"].rank(pct=True, method="average")
    df["rs_rating"] = (pct_rank * 98 + 1).round().astype(int)

    df = df.sort_values("rs_rating", ascending=False).reset_index(drop=True)
    return df


def save_outputs(df: pd.DataFrame, csv_path: str, json_path: str) -> None:
    out_cols = [
        "name", "description", "exchange", "close", "volume",
        "market_cap_basic", "Perf.3M", "Perf.6M", "Perf.9M_interp", "Perf.Y",
        "rs_raw", "rs_rating",
    ]
    out = df[out_cols].rename(columns={
        "name": "ticker",
        "market_cap_basic": "market_cap",
        "Perf.3M": "perf_3m",
        "Perf.6M": "perf_6m",
        "Perf.9M_interp": "perf_9m_interp",
        "Perf.Y": "perf_12m",
    })

    out.to_csv(csv_path, index=False)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "universe_size": len(out),
        "methodology": (
            "RS_raw = 0.4*P3M + 0.2*P6M + 0.2*P9M(interp) + 0.2*P12M; "
            "RS Rating = percentile rank scaled 1-99. "
            "Independent approximation, not IBD's proprietary formula."
        ),
        "stocks": out.to_dict(orient="records"),
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved {len(out)} rows to {csv_path} and {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Compute IBD-style RS Ratings.")
    parser.add_argument("--csv", default="rs_ratingsUS.csv", help="CSV output path")
    parser.add_argument("--json", default="rs_ratingsUS.json", help="JSON output path")
    parser.add_argument("--top", type=int, default=20,
                         help="Number of top-rated stocks to print to console")
    args = parser.parse_args()

    df = fetch_universe()
    df = clean_universe(df)
    df = compute_rs_rating(df)
    save_outputs(df, args.csv, args.json)

    print(f"\nTop {args.top} stocks by RS Rating:")
    print(
        df[["name", "close", "rs_rating", "Perf.3M", "Perf.Y"]]
        .head(args.top)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()