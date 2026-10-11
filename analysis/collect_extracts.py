"""Sort Dropbox text extracts (saved fetch results, JSON with a `text`
field) into legacy/ and v2/ folders named by store number."""
import json
import re
import sys
from pathlib import Path

STORE_RE = re.compile(r"^\tStore (\d+)\b", re.M)


def classify(text):
    """'v2' or 'legacy' by sheet layout, plus the store number."""
    # legacy period sheets carry a "Sales Ideal" block; v2 has the hour grids
    if "Sales Ideal" in text and "Manager Sales Forecast" in text:
        kind = "legacy"
    elif "Earned Staff per Hour" in text:
        kind = "v2"
    else:
        return None, None
    m = STORE_RE.search(text)
    if not m:
        # legacy sheets open with the store in the period title row
        m = re.search(r"Store (\d+) ", text)
    return kind, m.group(1) if m else None


if __name__ == "__main__":
    out = Path(sys.argv[1])
    for k in ("legacy", "v2"):
        (out / k).mkdir(parents=True, exist_ok=True)
    found = {"legacy": set(), "v2": set()}
    for p in sys.argv[2:]:
        try:
            doc = json.loads(Path(p).read_text())
        except (ValueError, OSError):
            continue
        text = doc.get("text", "")
        kind, store = classify(text)
        title = doc.get("title", "")
        m = re.match(r"Store (\d+) ", title)
        if m:
            store = m.group(1)
        if kind and store:
            (out / kind / f"{store}.txt").write_text(text)
            found[kind].add(store)
    for k, v in found.items():
        print(k, len(v), " ".join(sorted(v, key=int)))
