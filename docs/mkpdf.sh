#!/bin/sh
# make the PDFs of the documents in this directory: pandoc to HTML, then a
# headless Chrome or Chromium prints it. Usage: sh docs/mkpdf.sh
cd "$(dirname "$0")" || exit 1
CHROME=${CHROME:-}
for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
	"/Applications/Chromium.app/Contents/MacOS/Chromium" chromium chromium-browser google-chrome chrome; do
	[ -n "$CHROME" ] && break
	if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then CHROME=$c; fi
done
[ -z "$CHROME" ] && { echo "no Chrome or Chromium found; set CHROME" >&2; exit 1; }
for md in *.md; do
	base=${md%.md}
	title=$(head -1 "$md" | sed 's/^# *//')
	pandoc -f gfm "$md" -s --metadata pagetitle="$title" -c pdf.css --resource-path=. |
		sed 's/href="\([A-Za-z]*\)\.md/href="\1.pdf/g' >"$base.html" &&
	"$CHROME" --headless --no-sandbox --disable-gpu --no-pdf-header-footer --print-to-pdf="$base.pdf" "file://$PWD/$base.html" 2>/dev/null &&
	echo "$base.pdf"
	rm -f "$base.html"
done
