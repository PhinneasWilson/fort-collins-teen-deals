#!/usr/bin/env python3
"""fort-collins-teen-deals: build a static HTML deals board from a CSV.

Student discounts, free events and gigs near Rocky Mountain High School in Fort Collins, Colorado.
Every row must have a source link. Rows without a valid http(s) source are rejected, so the board
only ever shows listings someone has actually checked. The script invents nothing: deals.csv ships
with a header row only.

    python deals_board.py check deals.csv              # validate the CSV and list problems
    python deals_board.py build deals.csv -o index.html
    python deals_board.py build deals.csv --today 2026-11-01   # pretend today is this date
    python deals_board.py --test

CSV columns (header row required):
    name, category, details, location, source_url, date_checked, ends
  category     one of: student discount, free event, gig
  source_url   REQUIRED, must start with http:// or https://
  date_checked REQUIRED, YYYY-MM-DD, the day someone confirmed the listing at the source
  ends         optional YYYY-MM-DD, the board hides the row after this date

Standard library only.
"""
import argparse
import csv
import html
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from urllib.parse import urlparse

CATEGORIES = ["student discount", "free event", "gig"]
COLUMNS = ["name", "category", "details", "location", "source_url", "date_checked", "ends"]
STALE_DAYS = 60
TITLE = "Fort Collins teen deals board"


class Row:
    def __init__(self, data):
        self.name = data["name"]
        self.category = data["category"]
        self.details = data["details"]
        self.location = data["location"]
        self.source_url = data["source_url"]
        self.date_checked = data["date_checked"]
        self.ends = data["ends"]


def parse_date(text):
    return datetime.strptime(text.strip(), "%Y-%m-%d").date()


def valid_url(text):
    p = urlparse(text.strip())
    return p.scheme in ("http", "https") and bool(p.netloc) and "." in p.netloc


def read_rows(path):
    """Return (rows, problems). A problem is a string like 'line 4: missing source_url'."""
    rows, problems = [], []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = [c.strip().lower() for c in (reader.fieldnames or [])]
        missing = [c for c in ("name", "category", "source_url", "date_checked") if c not in header]
        if missing:
            return [], [f"header is missing required column(s): {', '.join(missing)}"]
        for n, raw in enumerate(reader, start=2):
            rec = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            if not any(rec.values()):
                continue
            rec = {c: rec.get(c, "") for c in COLUMNS}
            rec["category"] = rec["category"].lower()
            error = validate_row(rec)
            if error:
                problems.append(f"line {n}: {error}")
            else:
                rows.append(Row(rec))
    return rows, problems


def validate_row(rec):
    if not rec["name"]:
        return "missing name"
    if rec["category"] not in CATEGORIES:
        return f"category must be one of: {', '.join(CATEGORIES)}"
    if not rec["source_url"]:
        return "missing source_url (every listing needs a source link)"
    if not valid_url(rec["source_url"]):
        return f"source_url is not a valid http(s) link: {rec['source_url']!r}"
    try:
        parse_date(rec["date_checked"])
    except ValueError:
        return "date_checked must be YYYY-MM-DD"
    if rec["ends"]:
        try:
            parse_date(rec["ends"])
        except ValueError:
            return "ends must be YYYY-MM-DD or empty"
    return None


def is_live(row, today):
    return not row.ends or parse_date(row.ends) >= today


def is_stale(row, today):
    return (today - parse_date(row.date_checked)).days > STALE_DAYS


def render_card(row, today):
    e = html.escape
    stale = ' <span class="stale">check the source, last confirmed over 60 days ago</span>' if is_stale(row, today) else ""
    ends = f"<div>Ends {e(row.ends)}</div>" if row.ends else ""
    where = f"<div>{e(row.location)}</div>" if row.location else ""
    details = f"<p>{e(row.details)}</p>" if row.details else ""
    link = f'<a href="{e(row.source_url, quote=True)}" rel="noopener nofollow" target="_blank">Source</a>'
    return (
        f'<article class="card" data-cat="{e(row.category, quote=True)}"><h3>{e(row.name)}</h3>{details}{where}{ends}'
        f'<div class="meta">{link}, confirmed {e(row.date_checked)}{stale}</div></article>'
    )


STYLE = """body{font-family:system-ui,sans-serif;max-width:46em;margin:1.5em auto;padding:0 1em;color:#222}
h1{margin-bottom:.2em}.card{border:1px solid #ddd;border-radius:8px;padding:.7em 1em;margin:.6em 0}
.card h3{margin:.1em 0}.meta{font-size:.85em;color:#555;margin-top:.4em}.stale{color:#a05a00}
nav button{margin:0 .3em .5em 0;padding:.3em .8em;border:1px solid #888;border-radius:99px;background:#fff;cursor:pointer}
nav button.on{background:#222;color:#fff}.empty{color:#666}"""

SCRIPT = """document.querySelectorAll('nav button').forEach(function(b){b.onclick=function(){
document.querySelectorAll('nav button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
var c=b.dataset.cat;document.querySelectorAll('.card').forEach(function(card){
card.style.display=(c==='all'||card.dataset.cat===c)?'':'none'})}});"""


def build_page(rows, today):
    live = [r for r in rows if is_live(r, today)]
    live.sort(key=lambda r: (CATEGORIES.index(r.category), r.name.lower()))
    buttons = '<button class="on" data-cat="all">All</button>' + "".join(
        f'<button data-cat="{c}">{c.title()}</button>' for c in CATEGORIES
    )
    if live:
        body = "\n".join(render_card(r, today) for r in live)
    else:
        body = '<p class="empty">No confirmed listings yet. Check back soon.</p>'
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{TITLE}</title><style>{STYLE}</style></head><body>\n"
        f"<h1>{TITLE}</h1>\n<p>Student discounts, free events and gigs near Rocky Mountain High School. "
        f"Every listing links to its source. Page built {today.isoformat()}.</p>\n<nav>{buttons}</nav>\n"
        f"{body}\n<script>{SCRIPT}</script>\n</body></html>\n"
    )


def build(csv_path, out_path, today=None, strict=False):
    today = today or date.today()
    rows, problems = read_rows(csv_path)
    if problems and strict:
        return None, problems
    page = build_page(rows, today)
    folder = os.path.dirname(os.path.abspath(out_path))
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(page)
    os.replace(tmp, out_path)
    return sum(1 for r in rows if is_live(r, today)), problems


def main(argv=None):
    p = argparse.ArgumentParser(description="Build a static deals board from a CSV.")
    p.add_argument("--test", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("check")
    c.add_argument("csv")
    b = sub.add_parser("build")
    b.add_argument("csv")
    b.add_argument("-o", "--output", default="index.html")
    b.add_argument("--today", help="YYYY-MM-DD, default is today")
    b.add_argument("--strict", action="store_true", help="refuse to build if any row is invalid")
    args = p.parse_args(argv)
    if args.test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoardTests))
        return 0 if result.wasSuccessful() else 1
    if args.cmd not in ("check", "build"):
        p.print_help()
        return 2
    try:
        if args.cmd == "check":
            rows, problems = read_rows(args.csv)
            print(f"{len(rows)} valid rows, {len(problems)} problems")
            for line in problems:
                print("  " + line)
            return 1 if problems else 0
        today = parse_date(args.today) if args.today else None
        shown, problems = build(args.csv, args.output, today, args.strict)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    for line in problems:
        print("skipped " + line, file=sys.stderr)
    if shown is None:
        print("not built: fix the rows above or drop --strict", file=sys.stderr)
        return 1
    print(f"wrote {args.output} with {shown} listings ({len(problems)} rows skipped)")
    return 0


class BoardTests(unittest.TestCase):
    HEADER = ",".join(COLUMNS) + "\n"

    def write(self, tmp, text):
        path = os.path.join(tmp, "d.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_header_only_builds_empty_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "i.html")
            shown, problems = build(self.write(tmp, self.HEADER), out, date(2026, 10, 21))
            self.assertEqual((shown, problems), (0, []))
            self.assertIn("No confirmed listings yet", open(out, encoding="utf-8").read())

    def test_rows_without_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.HEADER + (
                "Alpha,gig,d,l,,2026-10-01,\n"
                "Beta,gig,d,l,not-a-link,2026-10-01,\n"
                "Gamma,gig,d,l,https://example.org/g,2026-10-01,\n"
            )
            rows, problems = read_rows(self.write(tmp, text))
            self.assertEqual([r.name for r in rows], ["Gamma"])
            self.assertEqual(len(problems), 2)
            self.assertIn("missing source_url", problems[0])

    def test_bad_category_and_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.HEADER + (
                "A,coupon,d,l,https://a.org/x,2026-10-01,\n"
                "B,gig,d,l,https://a.org/x,10/01/2026,\n"
                "C,gig,d,l,https://a.org/x,2026-10-01,soon\n"
            )
            rows, problems = read_rows(self.write(tmp, text))
            self.assertEqual((len(rows), len(problems)), (0, 3))

    def test_missing_required_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, problems = read_rows(self.write(tmp, "name,category\nA,gig\n"))
            self.assertEqual(rows, [])
            self.assertIn("source_url", problems[0])

    def test_expired_hidden_stale_flagged_and_html_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self.HEADER + (
                'Old event,free event,d,l,https://a.org/1,2026-09-01,2026-10-01\n'
                'Fresh <b>gig</b>,gig,"Pays ""well""",Old Town,https://a.org/2?a=1&b=2,2026-10-15,\n'
                'Stale deal,student discount,d,l,https://a.org/3,2026-06-01,\n'
            )
            out = os.path.join(tmp, "i.html")
            shown, _ = build(self.write(tmp, text), out, date(2026, 10, 21))
            page = open(out, encoding="utf-8").read()
            self.assertEqual(shown, 2)
            self.assertNotIn("Old event", page)
            self.assertIn("Fresh &lt;b&gt;gig&lt;/b&gt;", page)
            self.assertNotIn("<b>gig</b>", page)
            self.assertIn("a=1&amp;b=2", page)
            self.assertEqual(page.count("last confirmed over 60 days ago"), 1)
            self.assertLess(page.index("Stale deal"), page.index("Fresh"))  # categories sorted: discount before gig

    def test_strict_mode_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, self.HEADER + "A,gig,d,l,,2026-10-01,\n")
            out = os.path.join(tmp, "i.html")
            self.assertEqual(main(["build", path, "-o", out, "--strict"]), 1)
            self.assertFalse(os.path.exists(out))
            self.assertEqual(main(["check", path]), 1)
            self.assertEqual(main(["build", path, "-o", out]), 0)
            self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    sys.exit(main())
