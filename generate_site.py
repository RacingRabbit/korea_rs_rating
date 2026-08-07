import html as html_lib
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

stocks_df = pd.read_csv("docs/rs_ratingsKR.csv")
stocks_df = stocks_df[
    [
        "ticker",
        "description",
        "rs_rating",
        "eps_rating",
    ]
].rename(columns={
    "ticker": "Ticker",
    "description": "Company",
    "rs_rating": "RS Rating",
    "eps_rating": "EPS Rating",
}).reset_index(drop=True)  # csv is already sorted by RS rating, descending

# Industry file is produced by the same rs_rating.py run (--industry-csv
# docs/rs_industry_KR.csv). Handled as optional so this script still builds
# the page if you haven't wired that flag up yet.
try:
    industry_df = pd.read_csv("docs/rs_industry_KR.csv")
    industry_df = industry_df.sort_values("group_rs_rating", ascending=False).reset_index(drop=True)
except FileNotFoundError:
    industry_df = None
    print("Note: docs/rs_industry_KR.csv not found -- skipping industry section. "
          "Run rs_rating.py with --industry-csv docs/rs_industry_KR.csv to include it.")


# ---------------------------------------------------------------------------
# Build markup fragments
# ---------------------------------------------------------------------------

def build_entry(rank, ticker, company, rs, eps):
    top_class = "top" if rs >= 90 else ""
    eps_is_missing = pd.isna(eps)
    eps_display = "\u2013" if eps_is_missing else f"{int(eps)}"
    eps_attr = "" if eps_is_missing else str(int(eps))
    eps_hot = "hot" if (not eps_is_missing and eps >= 90) else ""
    ticker_esc = html_lib.escape(str(ticker))
    company_esc = html_lib.escape(str(company))
    return f"""<div class="entry {top_class}" data-rs="{int(rs)}" data-eps="{eps_attr}">
  <span class="rank">{rank}</span>
  <span class="ticker">{ticker_esc}</span>
  <span class="name" title="{company_esc}">{company_esc}</span>
  <span class="leader"></span>
  <span class="rs">{rs}</span>
  <span class="eps {eps_hot}">{eps_display}</span>
</div>"""


def build_industry_entry(rank, industry, rs, n_stocks, leader_pct):
    top_class = "top" if rs >= 90 else ""
    industry_esc = html_lib.escape(str(industry))
    tooltip = html_lib.escape(f"{int(n_stocks)} stocks \u00b7 {leader_pct:.0f}% rated RS 80+")
    return f"""<div class="entry {top_class}">
  <span class="rank">{rank}</span>
  <span class="name name-wide" title="{tooltip}">{industry_esc}</span>
  <span class="leader"></span>
  <span class="rs">{int(rs)}</span>
</div>"""


entries_html = "\n".join(
    build_entry(i + 1, row["Ticker"], row["Company"], row["RS Rating"], row["EPS Rating"])
    for i, row in stocks_df.iterrows()
)

industry_section_html = ""
industry_count = 0
if industry_df is not None:
    industry_count = len(industry_df)
    industry_entries_html = "\n".join(
        build_industry_entry(
            i + 1, row["group"], row["group_rs_rating"], row["n_stocks"], row["leader_pct"]
        )
        for i, row in industry_df.iterrows()
    )
    industry_section_html = f"""
  <div class="section-label">
    <span>Industry Group Strength</span>
    <span class="legend">RS</span>
  </div>
  <div class="listing">
{industry_entries_html}
  </div>
"""

updated = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%B %d, %Y  ·  %H:%M")
count = len(stocks_df)


# ---------------------------------------------------------------------------
# Client-side sort (plain string, not an f-string, so JS braces need no escaping)
# ---------------------------------------------------------------------------

sort_script = """
<script>
(function () {
  var container = document.getElementById('stock-listing');
  if (!container) return;
  // Fixed snapshot of the original (RS-descending) order. Every sort reads
  // from this, never from a previous sort's result -- otherwise ties (very
  // common, since RS only spans 1-99 across thousands of stocks) drift a
  // little further from their original relative order on each click.
  var originalOrder = Array.prototype.slice.call(container.children);
  var state = { column: 'rs', dir: 'desc' };

  function applySort(column) {
    if (state.column === column) {
      state.dir = state.dir === 'desc' ? 'asc' : 'desc';
    } else {
      state.column = column;
      state.dir = 'desc';
    }

    var sorted = originalOrder.slice().sort(function (a, b) {
      var av = a.dataset[column];
      var bv = b.dataset[column];
      var aMissing = av === '';
      var bMissing = bv === '';
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;   // blanks always sink to the bottom
      if (bMissing) return -1;
      var diff = parseFloat(av) - parseFloat(bv);
      return state.dir === 'desc' ? -diff : diff;
    });

    sorted.forEach(function (entry, i) {
      entry.querySelector('.rank').textContent = i + 1;
      container.appendChild(entry);
    });

    ['rs', 'eps'].forEach(function (col) {
      var toggle = document.getElementById('sort-' + col);
      var isActive = col === column;
      toggle.classList.toggle('active', isActive);
      toggle.querySelector('.arrow').textContent = isActive
        ? (state.dir === 'desc' ? ' \u25bc' : ' \u25b2')
        : '';
    });
  }

  document.getElementById('sort-rs').addEventListener('click', function () { applySort('rs'); });
  document.getElementById('sort-eps').addEventListener('click', function () { applySort('eps'); });
})();
</script>
"""


# ---------------------------------------------------------------------------
# Assemble page
# ---------------------------------------------------------------------------

html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relative Strength Report — Korean Equities</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@800;900&family=Atkinson+Hyperlegible+Next:wght@400;700&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    color-scheme: light dark;
    --paper: #f7f6f2;
    --ink: #141414;
    --ink-soft: #55554f;
    --rule: #141414;
    --red: #8a1f11;
    --dots: #999;
    --divider: #ccc7b8;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --paper: #3a3733;
      --ink: #ece7dc;
      --ink-soft: #a8a196;
      --rule: #ece7dc;
      --red: #e2624f;
      --dots: #8a8478;
      --divider: #57534a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: 'Atkinson Hyperlegible Next', Arial, sans-serif;
  }}
  .wrap {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 28px 32px 60px;
  }}
  .utility-bar {{
    display: flex;
    justify-content: space-between;
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ink-soft);
    padding-bottom: 10px;
    border-bottom: 1px solid var(--rule);
  }}
  .masthead {{
    text-align: center;
    padding: 22px 0 14px;
  }}
  .masthead h1 {{
    font-family: 'Playfair Display', serif;
    font-weight: 900;
    font-size: 52px;
    letter-spacing: 0.01em;
    margin: 0;
    text-transform: uppercase;
  }}
  .masthead .subhead {{
    font-style: italic;
    font-size: 15px;
    color: var(--ink-soft);
    margin-top: 6px;
  }}
  .dateline {{
    display: flex;
    justify-content: space-between;
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--ink-soft);
    padding: 12px 0 8px;
  }}
  .rule-double {{
    border-top: 3px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    height: 4px;
    margin-bottom: 6px;
  }}
  .section-label {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 26px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--rule);
  }}
  .section-label .legend {{
    font-weight: 500;
    letter-spacing: 0.04em;
  }}
  .sort-toggle {{
    cursor: pointer;
    user-select: none;
  }}
  .sort-toggle:hover {{
    text-decoration: underline;
  }}
  .sort-toggle.active {{
    color: var(--ink);
    font-weight: 700;
  }}
  .sort-toggle .arrow {{
    font-size: 9px;
  }}

  /* Shared row style -- used identically by the individual-stock listing
     and the industry-group listing, so both sections read as one system. */
  .listing {{
    column-count: 3;
    column-gap: 24px;
    column-rule: 1px solid var(--rule);
  }}
  .entry {{
    display: flex;
    align-items: baseline;
    break-inside: avoid;
    padding: 4px 0;
    font-size: 15px;
    line-height: 1.6;
  }}
  .entry .rank {{
    color: var(--ink-soft);
    font-size: 12px;
    width: 34px;
    flex: none;
    font-variant-numeric: tabular-nums;
    text-align: right;
    padding-right: 6px;
  }}
  .entry .ticker {{
    font-weight: 700;
    width: 64px;
    flex: none;
    font-variant-numeric: tabular-nums;
  }}
  .entry .name {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 150px;
  }}
  .entry .name.name-wide {{
    max-width: 230px;
  }}
  .entry .leader {{
    flex: 1;
    border-bottom: 1px dotted var(--dots);
    margin: 0 6px;
    transform: translateY(-3px);
  }}
  .entry .rs {{
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    width: 28px;
    text-align: right;
    flex: none;
  }}
  .entry .eps {{
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    width: 28px;
    text-align: right;
    flex: none;
    margin-left: 8px;
    padding-left: 8px;
    border-left: 1px solid var(--divider);
    color: var(--ink-soft);
  }}
  .entry .eps.hot {{
    color: var(--red);
  }}
  .entry.top .rs, .entry.top .ticker {{
    color: var(--red);
  }}

  footer {{
    margin-top: 30px;
    padding-top: 12px;
    border-top: 1px solid var(--rule);
    font-family: 'Inter', sans-serif;
    font-size: 10.5px;
    color: var(--ink-soft);
    letter-spacing: 0.02em;
  }}
  @media (max-width: 900px) {{
    .listing {{ column-count: 2; }}
    .masthead h1 {{ font-size: 36px; }}
  }}
  @media (max-width: 560px) {{
    .listing {{ column-count: 1; }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <div class="utility-bar">
    <span>KOSPI · KOSDAQ Edition</span>
    <span>{industry_count} Industry Groups</span>
    <span>{count} Names Listed</span>
  </div>

  <div class="masthead">
    <h1>Relative Strength Report</h1>
    <div class="subhead">A Daily Ranking of Korean Equities and Industry Groups by Price and Earnings Momentum</div>
  </div>

  <div class="dateline">
    <span>Seoul, Republic of Korea</span>
    <span>Updated {updated} KST</span>
    <span>RS / EPS Rating · Scale 1&ndash;99</span>
  </div>

  <div class="rule-double"></div>
{industry_section_html}
  <div class="section-label">
    <span>Individual Stock Ratings</span>
    <span class="legend">
      <span id="sort-rs" class="sort-toggle active">RS<span class="arrow"> &#9660;</span></span>
      &nbsp;&nbsp;&nbsp;
      <span id="sort-eps" class="sort-toggle">EPS<span class="arrow"></span></span>
    </span>
  </div>
  <div class="listing" id="stock-listing">
{entries_html}
  </div>

  <footer>
    Independent, open-source approximation of the IBD Relative Strength and EPS Rating methodologies.
    Not affiliated with, endorsed by, or connected to Investor's Business Daily or TradingView.
    Ratings in red denote a score &ge; 90. EPS shown as &ndash; where earnings data is incomplete.
    Click RS or EPS above the listing to sort.
  </footer>

</div>
{sort_script}
</body>
</html>
"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Wrote docs/index.html with {count} stocks and {industry_count} industry groups.")