import pandas as pd
from datetime import datetime

df = pd.read_csv("docs/rs_ratingsKR.csv")

html_table = df.to_html(
    index=False,
    classes="table",
    border=0,
    float_format=lambda x: f"{x:.2f}"
)

html = f"""
<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8">

<title>Korean RS Ratings</title>

<style>

body {{
    font-family: Arial, sans-serif;
    max-width: 1400px;
    margin: 30px auto;
    padding: 20px;
}}

h1 {{
    margin-bottom: 0;
}}

p {{
    color: #666;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 14px;
}}

th {{
    position: sticky;
    top: 0;
    background: #efefef;
}}

th, td {{
    border: 1px solid #ddd;
    padding: 6px 10px;
    text-align: right;
}}

th:first-child,
td:first-child {{
    text-align: left;
}}

tr:nth-child(even) {{
    background: #fafafa;
}}

</style>

</head>

<body>

<h1>Korean Relative Strength Ratings</h1>

<p>
Updated:
{datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
</p>

{html_table}

</body>
</html>
"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)