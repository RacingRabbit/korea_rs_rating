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

Also computes an Industry Group RS Rating: constituent rs_raw scores are
aggregated per industry (TradingView's 131-category 'industry' field, the
closest match to IBD's ~197 industry groups), then re-ranked with the same
1-99 percentile convention. Pass group_col='sector' instead for the coarser
21-category view.

Also computes an EPS Rating: an independent approximation of IBD's earnings
growth rating, on the same 1-99 percentile scale. IBD's real formula leans
heavily on the most recent 1-2 quarters plus a 3-5 year growth trend, but
TradingView doesn't expose a multi-year EPS CAGR field, so quarterly YoY,
TTM YoY, and FY YoY growth stand in as the closest available horizons.

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
            "sector",
            "industry",
            "close",
            "volume",
            "market_cap_basic",
            "Perf.3M",
            "Perf.6M",
            "Perf.Y",
            "earnings_per_share_diluted_yoy_growth_fq",
            "earnings_per_share_diluted_yoy_growth_ttm",
            "earnings_per_share_diluted_yoy_growth_fy",
        )
        .where(
            col("type") == "stock",
            col("typespecs").has("common"),
        )
        .set_markets("korea")
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

    missing_industry = df["industry"].isna().sum()
    if missing_industry:
        print(f"Note: {missing_industry} stocks have no industry classification "
              f"and will be excluded from the industry group RS calc.")
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


def compute_eps_rating(df: pd.DataFrame) -> pd.DataFrame:
    """
    Independent approximation of IBD's EPS Rating: ranks stocks by earnings
    growth on the same 1-99 percentile scale used for RS Rating.

    Weighted toward the most recent quarter (matching IBD's stated emphasis
    on recent earnings), blended with TTM and FY YoY growth as proxies for
    the longer-term trend IBD normally captures with a 3-5 year CAGR.

    Stocks missing any of the three growth fields (e.g. no reported earnings
    yet) are left with a null eps_rating rather than dropped from the sheet,
    so the RS-only stocks in the output aren't silently lost.
    """
    growth_cols = [
        "earnings_per_share_diluted_yoy_growth_fq",
        "earnings_per_share_diluted_yoy_growth_ttm",
        "earnings_per_share_diluted_yoy_growth_fy",
    ]
    eps_df = df.dropna(subset=growth_cols).copy()
    print(f"EPS rating: {len(df) - len(eps_df)} of {len(df)} stocks lack "
          f"complete EPS growth data and will show a blank eps_rating.")

    eps_df["eps_raw"] = (
        0.5 * eps_df["earnings_per_share_diluted_yoy_growth_fq"]
        + 0.3 * eps_df["earnings_per_share_diluted_yoy_growth_ttm"]
        + 0.2 * eps_df["earnings_per_share_diluted_yoy_growth_fy"]
    )

    pct_rank = eps_df["eps_raw"].rank(pct=True, method="average")
    eps_df["eps_rating"] = (pct_rank * 98 + 1).round().astype(int)

    df = df.merge(eps_df[["name", "eps_raw", "eps_rating"]], on="name", how="left")
    return df


def compute_group_rs(
    df: pd.DataFrame,
    group_col: str,
    min_group_size: int = 5,
    weight_col: str | None = None,
) -> pd.DataFrame:
    """
    Aggregate stock-level rs_raw into an IBD-style group Relative Strength Rating.

    group_col:      'industry' (131 TradingView industries -- the closest match
                     to IBD's ~197 industry groups) or 'sector' (21 broad sectors).
    min_group_size:  groups with fewer constituents than this are dropped --
                     a 2-stock "industry" isn't a meaningful group signal.
    weight_col:      None -> equal-weighted average across constituents.
                     'market_cap_basic' -> cap-weighted average, closer to how
                     IBD's own group indexes are built, but lets one or two
                     giants dominate the group's reading.
    """
    work = df.dropna(subset=[group_col]).copy()

    if weight_col:
        def _weighted(g: pd.DataFrame) -> pd.Series:
            w = g[weight_col].clip(lower=0)
            avg = (g["rs_raw"] * w).sum() / w.sum() if w.sum() > 0 else g["rs_raw"].mean()
            return pd.Series({
                "avg_rs_raw": avg,
                "n_stocks": len(g),
                "leaders_80plus": int((g["rs_rating"] >= 80).sum()),
            })
        grouped = work.groupby(group_col).apply(_weighted, include_groups=False)
    else:
        grouped = work.groupby(group_col).agg(
            avg_rs_raw=("rs_raw", "mean"),
            n_stocks=("rs_raw", "size"),
            leaders_80plus=("rs_rating", lambda s: int((s >= 80).sum())),
        )

    grouped = grouped.reset_index()

    before = len(grouped)
    grouped = grouped[grouped["n_stocks"] >= min_group_size].copy()
    print(f"[{group_col}] dropped {before - len(grouped)} groups with fewer "
          f"than {min_group_size} constituents ({len(grouped)} remain).")

    pct_rank = grouped["avg_rs_raw"].rank(pct=True, method="average")
    grouped["group_rs_rating"] = (pct_rank * 98 + 1).round().astype(int)
    grouped["leader_pct"] = (grouped["leaders_80plus"] / grouped["n_stocks"] * 100).round(1)

    grouped = grouped.rename(columns={group_col: "group"})
    grouped = grouped.sort_values("group_rs_rating", ascending=False).reset_index(drop=True)
    return grouped


def save_outputs(df: pd.DataFrame, csv_path: str, json_path: str) -> None:
    out_cols = [
        "name", "description", "exchange", "sector", "industry", "close", "volume",
        "market_cap_basic", "Perf.3M", "Perf.6M", "Perf.9M_interp", "Perf.Y",
        "rs_raw", "rs_rating", "eps_raw", "eps_rating",
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
            "EPS_raw = 0.5*QoQ-quarter YoY growth + 0.3*TTM YoY growth + 0.2*FY YoY growth; "
            "EPS Rating = percentile rank scaled 1-99 (null where earnings data is incomplete). "
            "Independent approximation, not IBD's proprietary formula."
        ),
        "stocks": out.to_dict(orient="records"),
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved {len(out)} rows to {csv_path} and {json_path}")


def save_group_outputs(grouped: pd.DataFrame, group_type: str, csv_path: str, json_path: str) -> None:
    grouped.to_csv(csv_path, index=False)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "group_type": group_type,
        "group_count": len(grouped),
        "methodology": (
            "Group RS Rating = percentile rank (1-99) of each group's "
            "constituent-average rs_raw score, using the same conversion as "
            "individual stock RS. Independent approximation, not IBD's method."
        ),
        "groups": grouped.to_dict(orient="records"),
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved {len(grouped)} {group_type} groups to {csv_path} and {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Compute IBD-style RS Ratings.")
    parser.add_argument("--csv", default="rs_ratingsKR.csv", help="Stock-level CSV output path")
    parser.add_argument("--json", default="rs_ratingsKR.json", help="Stock-level JSON output path")
    parser.add_argument("--industry-csv", default="rs_industry_KR.csv", help="Industry-group CSV output path")
    parser.add_argument("--industry-json", default="rs_industry_KR.json", help="Industry-group JSON output path")
    parser.add_argument("--min-group-size", type=int, default=5,
                         help="Minimum stocks required for an industry to get a group rating")
    parser.add_argument("--cap-weighted", action="store_true",
                         help="Weight group RS by market cap instead of equal-weighting constituents")
    parser.add_argument("--top", type=int, default=20,
                         help="Number of top-rated stocks/industries to print to console")
    args = parser.parse_args()

    df = fetch_universe()
    df = clean_universe(df)
    df = compute_rs_rating(df)
    df = compute_eps_rating(df)
    save_outputs(df, args.csv, args.json)

    weight_col = "market_cap_basic" if args.cap_weighted else None
    industry_rs = compute_group_rs(
        df, "industry", min_group_size=args.min_group_size, weight_col=weight_col
    )
    save_group_outputs(industry_rs, "industry", args.industry_csv, args.industry_json)

    print(f"\nTop {args.top} stocks by RS Rating:")
    print(
        df[["name", "close", "rs_rating", "Perf.3M", "Perf.Y"]]
        .head(args.top)
        .to_string(index=False)
    )

    print(f"\nTop {args.top} industry groups by RS Rating:")
    print(
        industry_rs[["group", "group_rs_rating", "n_stocks", "leader_pct"]]
        .head(args.top)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()