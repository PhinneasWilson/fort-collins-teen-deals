# fort-collins-teen-deals

A script that turns a CSV of student discounts, free events and gigs near Rocky Mountain High School (Fort Collins, Colorado) into one static HTML page you can host anywhere, for example GitHub Pages.

Every row must have a source link and the date someone confirmed it. Rows without a valid source link are rejected, so the board never shows an unchecked listing. `deals.csv` ships with the header row only. No listings are included, so nothing here is invented. Add rows after you have checked each one at its source.

One file, Python 3 standard library only.

## Use

```
python deals_board.py check deals.csv
python deals_board.py build deals.csv -o index.html
python deals_board.py build deals.csv -o index.html --strict   # refuse to build if any row is invalid
python deals_board.py --test
```

CSV columns: `name, category, details, location, source_url, date_checked, ends`

- category: student discount, free event or gig
- source_url: required, must start with http:// or https://
- date_checked: required, YYYY-MM-DD, the day you confirmed the listing at the source
- ends: optional YYYY-MM-DD. The board hides the row after that date

Rows last confirmed more than 60 days ago stay up with a note to check the source. The page has filter buttons by category and escapes all text.

## Tested

The built-in self-test (6 tests) passes. It covers an empty board, rejecting rows with a missing or invalid source link, bad categories and dates, a missing required column, hiding expired rows, the stale note, HTML escaping, and strict mode.

Not tested: the page in a real browser, and no real listings have been loaded yet.
