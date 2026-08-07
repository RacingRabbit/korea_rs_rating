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
        "description_en",
        "description_ko",
        "rs_rating",
        "eps_rating",
    ]
].rename(columns={
    "ticker": "Ticker",
    "description_en": "Company EN",
    "description_ko": "Company KO",
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

def build_entry(rank, ticker, name_en, name_ko, rs, eps):
    top_class = "top" if rs >= 90 else ""
    eps_is_missing = pd.isna(eps)
    eps_display = "\u2013" if eps_is_missing else f"{int(eps)}"
    eps_attr = "" if eps_is_missing else str(int(eps))
    eps_hot = "hot" if (not eps_is_missing and eps >= 90) else ""
    ticker_esc = html_lib.escape(str(ticker))
    name_en_esc = html_lib.escape(str(name_en)) if pd.notna(name_en) else ticker_esc
    name_ko_esc = html_lib.escape(str(name_ko)) if pd.notna(name_ko) else ticker_esc
    return f"""<div class="entry {top_class}" data-rs="{int(rs)}" data-eps="{eps_attr}" data-name-en="{name_en_esc}" data-name-ko="{name_ko_esc}">
  <span class="rank">{rank}</span>
  <span class="ticker">{ticker_esc}</span>
  <span class="name" title="{name_ko_esc}">{name_ko_esc}</span>
  <span class="leader"></span>
  <span class="rs">{rs}</span>
  <span class="eps {eps_hot}">{eps_display}</span>
</div>"""


def build_industry_entry(rank, name_en, name_ko, rs, n_stocks, leader_pct):
    top_class = "top" if rs >= 90 else ""
    name_en_esc = html_lib.escape(str(name_en))
    name_ko_esc = html_lib.escape(str(name_ko))
    tooltip_en = html_lib.escape(f"{int(n_stocks)} stocks \u00b7 {leader_pct:.0f}% rated RS 80+")
    tooltip_ko = html_lib.escape(f"{int(n_stocks)}\uac1c \uc885\ubaa9 \u00b7 RS 80\uc810 \uc774\uc0c1 {leader_pct:.0f}%")
    return f"""<div class="entry {top_class}" data-name-en="{name_en_esc}" data-name-ko="{name_ko_esc}" data-tooltip-en="{tooltip_en}" data-tooltip-ko="{tooltip_ko}">
  <span class="rank">{rank}</span>
  <span class="name name-wide" title="{tooltip_ko}">{name_ko_esc}</span>
  <span class="leader"></span>
  <span class="rs">{int(rs)}</span>
</div>"""


entries_html = "\n".join(
    build_entry(i + 1, row["Ticker"], row["Company EN"], row["Company KO"], row["RS Rating"], row["EPS Rating"])
    for i, row in stocks_df.iterrows()
)

industry_section_html = ""
industry_count = 0
if industry_df is not None:
    industry_count = len(industry_df)
    industry_entries_html = "\n".join(
        build_industry_entry(
            i + 1, row["industry_en"], row["industry_ko"], row["group_rs_rating"], row["n_stocks"], row["leader_pct"]
        )
        for i, row in industry_df.iterrows()
    )
    industry_section_html = f"""
  <div class="section-label">
    <span><span class="lang-ko">업종별 강도</span><span class="lang-en">Industry Group Strength</span></span>
    <span class="legend">RS</span>
  </div>
  <div class="listing">
{industry_entries_html}
  </div>
"""

now = datetime.now(ZoneInfo("Asia/Seoul"))
updated_ko = now.strftime("%Y년 %m월 %d일  ·  %H:%M")
updated_en = now.strftime("%B %d, %Y  ·  %H:%M")
count = len(stocks_df)


# ---------------------------------------------------------------------------
# Client-side script (plain string, not an f-string, so JS braces need no
# escaping): handles both the RS/EPS sort and the EN/KO language toggle.
# ---------------------------------------------------------------------------

page_script = """
<script>
(function () {
  // ---- Sort ----
  var container = document.getElementById('stock-listing');
  var originalOrder = container ? Array.prototype.slice.call(container.children) : [];
  var sortState = { column: 'rs', dir: 'desc' };

  function applySort(column) {
    if (!container) return;
    if (sortState.column === column) {
      sortState.dir = sortState.dir === 'desc' ? 'asc' : 'desc';
    } else {
      sortState.column = column;
      sortState.dir = 'desc';
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
      return sortState.dir === 'desc' ? -diff : diff;
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
        ? (sortState.dir === 'desc' ? ' \u25bc' : ' \u25b2')
        : '';
    });
  }

  var sortRsBtn = document.getElementById('sort-rs');
  var sortEpsBtn = document.getElementById('sort-eps');
  if (sortRsBtn) sortRsBtn.addEventListener('click', function () { applySort('rs'); });
  if (sortEpsBtn) sortEpsBtn.addEventListener('click', function () { applySort('eps'); });

  // ---- Language toggle ----
  var TITLES = {
    ko: '\uc0c1\ub300\uac15\ub3c4 \ub9ac\ud3ec\ud2b8 \u2014 \ud55c\uad6d \uc8fc\uc2dd',
    en: 'Relative Strength Report \u2014 Korean Equities'
  };

  function setLanguage(lang) {
    document.documentElement.lang = lang;
    document.documentElement.classList.toggle('lang-mode-en', lang === 'en');
    document.title = TITLES[lang];

    var koBtn = document.getElementById('lang-ko-btn');
    var enBtn = document.getElementById('lang-en-btn');
    if (koBtn) koBtn.classList.toggle('active', lang === 'ko');
    if (enBtn) enBtn.classList.toggle('active', lang === 'en');

    document.querySelectorAll('[data-name-en]').forEach(function (el) {
      var nameEl = el.querySelector('.name');
      if (!nameEl) return;
      var text = lang === 'en' ? el.dataset.nameEn : el.dataset.nameKo;
      nameEl.textContent = text;
      var tooltip = lang === 'en'
        ? (el.dataset.tooltipEn || text)
        : (el.dataset.tooltipKo || text);
      nameEl.title = tooltip;
    });

    try { localStorage.setItem('rs-report-lang', lang); } catch (e) {}
  }

  var savedLang = 'ko';
  try { savedLang = localStorage.getItem('rs-report-lang') || 'ko'; } catch (e) {}
  setLanguage(savedLang);

  var langKoBtn = document.getElementById('lang-ko-btn');
  var langEnBtn = document.getElementById('lang-en-btn');
  if (langKoBtn) langKoBtn.addEventListener('click', function () { setLanguage('ko'); });
  if (langEnBtn) langEnBtn.addEventListener('click', function () { setLanguage('en'); });
})();
</script>
"""


# ---------------------------------------------------------------------------
# Assemble page
# ---------------------------------------------------------------------------

html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>상대강도 리포트 — 한국 주식</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900&family=Noto+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
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
    font-family: 'Noto Sans KR', sans-serif;
  }}
  .wrap {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 28px 32px 60px;
  }}

  /* Language toggle: Korean shows by default; the script adds .lang-mode-en
     to <html> (a distinct class from .lang-en on individual spans below --
     reusing the same name here would also match <html>, hiding the whole
     page) to flip both content sets. */
  .lang-en {{ display: none; }}
  html.lang-mode-en .lang-en {{ display: inline; }}
  html.lang-mode-en .lang-ko {{ display: none; }}

  .utility-bar {{
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: var(--ink-soft);
    padding-bottom: 10px;
    border-bottom: 1px solid var(--rule);
  }}
  .masthead {{
    text-align: center;
    padding: 22px 0 14px;
  }}
  .masthead h1 {{
    font-family: 'Noto Serif KR', serif;
    font-weight: 900;
    font-size: 46px;
    letter-spacing: 0.01em;
    margin: 0;
  }}
  .masthead .subhead {{
    font-size: 15px;
    color: var(--ink-soft);
    margin-top: 6px;
  }}
  .dateline {{
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.02em;
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
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: var(--ink-soft);
    margin: 26px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--rule);
  }}
  .section-label .legend {{
    font-weight: 500;
    letter-spacing: 0.02em;
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
    font-size: 10.5px;
    color: var(--ink-soft);
    letter-spacing: 0.01em;
  }}
  @media (max-width: 900px) {{
    .listing {{ column-count: 2; }}
    .masthead h1 {{ font-size: 32px; }}
  }}
  @media (max-width: 560px) {{
    .listing {{ column-count: 1; }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <div class="utility-bar">
    <span><span class="lang-ko">코스피 및 코스닥</span><span class="lang-en">KOSPI and KOSDAQ Stocks</span></span>
    <span><span class="lang-ko">{industry_count}개 업종</span><span class="lang-en">{industry_count} Industry Groups</span></span>
    <span><span class="lang-ko">{count}개 종목 수록</span><span class="lang-en">{count} Stocks Listed</span></span>
    <span class="lang-switch">
      <span id="lang-ko-btn" class="sort-toggle active">한국어</span>
      &nbsp;·&nbsp;
      <span id="lang-en-btn" class="sort-toggle">EN</span>
    </span>
  </div>

  <div class="masthead">
    <h1><span class="lang-ko">Daily Morning Brew Korea</span><span class="lang-en">Daily Morning Brew Korea</span></h1>
    <div class="subhead">
      <span class="lang-ko">매일 아침, 갓 내린 랭킹</span>
      <span class="lang-en">Freshly Brewed Rankings Every Morning</span>
    </div>
  </div>

  <div class="dateline">
    <span><span class="lang-ko">{updated_ko} 업데이트 (KST)</span><span class="lang-en">Updated {updated_en} KST</span></span>
    <span><span class="lang-ko">RS / EPS 등급 · 1&ndash;99점</span><span class="lang-en">RS / EPS Rating · Scale 1&ndash;99</span></span>
  </div>

  <div class="rule-double"></div>
{industry_section_html}
  <div class="section-label">
    <span><span class="lang-ko">개별 종목 등급</span><span class="lang-en">Individual Stock Ratings</span></span>
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
    <span class="lang-ko">
      IBD(Investor's Business Daily)의 상대강도(RS) 및 EPS 등급 산정 방식을 독자적으로 오픈소스 방식으로 근사한 것입니다.
      Investor's Business Daily 또는 TradingView와 제휴하거나 그들의 보증을 받지 않았으며 아무런 관련이 없습니다.
      빨간색 등급은 90점 이상을 의미합니다. 실적 데이터가 불완전한 경우 EPS는 &ndash;로 표시됩니다.
      목록 위쪽의 RS 또는 EPS를 클릭하면 정렬할 수 있습니다.
    </span>
    <span class="lang-en">
      Independent, open-source approximation of the IBD Relative Strength and EPS Rating methodologies.
      Not affiliated with, endorsed by, or connected to Investor's Business Daily or TradingView.
      Ratings in red denote a score &ge; 90. EPS shown as &ndash; where earnings data is incomplete.
      Click RS or EPS above the listing to sort.
    </span>
  </footer>

</div>
{page_script}
</body>
</html>
"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Wrote docs/index.html with {count} stocks and {industry_count} industry groups.")