# generate_html.py
# Run with: python generate_html.py
# Creates report.html and opens it in your default browser.

import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path

students = [
    {"name": "Asha", "course": "Python", "score": 92},
    {"name": "Ravi", "course": "SQL", "score": 78},
    {"name": "Meena", "course": "Python", "score": 85},
    {"name": "Karthik", "course": "Data Science", "score": 66},
]


def grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "D"


def build_rows(rows):
    html_rows = []
    for s in rows:
        g = grade(s["score"])
        html_rows.append(
            f"<tr>"
            f"<td>{escape(s['name'])}</td>"
            f"<td>{escape(s['course'])}</td>"
            f"<td>{s['score']}</td>"
            f"<td class='grade {g}'>{g}</td>"
            f"</tr>"
        )
    return "\n".join(html_rows)


def build_page(rows):
    avg = sum(s["score"] for s in rows) / len(rows)
    top = max(rows, key=lambda s: s["score"])
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Student Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 40px; color: #222; }}
    .card {{ max-width: 700px; margin: auto; background: #fff; padding: 30px;
             border-radius: 12px; box-shadow: 0 4px 14px rgba(0,0,0,.08); }}
    h1 {{ margin-top: 0; }}
    .stats {{ display: flex; gap: 16px; margin: 20px 0; }}
    .stat {{ flex: 1; background: #eef3ff; padding: 14px; border-radius: 8px; text-align: center; }}
    .stat b {{ display: block; font-size: 22px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e3e3e3; }}
    th {{ background: #333; color: #fff; }}
    tr:hover {{ background: #fafafa; }}
    .grade {{ font-weight: bold; }}
    .A {{ color: #1a8f3c; }} .B {{ color: #2b6cb0; }}
    .C {{ color: #d98200; }} .D {{ color: #c0392b; }}
    footer {{ margin-top: 20px; font-size: 12px; color: #888; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Student Report</h1>
    <div class="stats">
      <div class="stat">Students<b>{len(rows)}</b></div>
      <div class="stat">Average score<b>{avg:.1f}</b></div>
      <div class="stat">Top scorer<b>{escape(top['name'])}</b></div>
    </div>
    <table>
      <tr><th>Name</th><th>Course</th><th>Score</th><th>Grade</th></tr>
      {build_rows(rows)}
    </table>
    <footer>Generated on {now} with Python</footer>
  </div>
</body>
</html>"""


def main():
    output = Path("report.html")
    output.write_text(build_page(students), encoding="utf-8")
    print(f"Created {output.resolve()}")
    webbrowser.open(output.resolve().as_uri())


if __name__ == "__main__":
    main()