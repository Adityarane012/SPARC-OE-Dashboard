# -*- coding: utf-8 -*-
"""
SPARC OE Insights - Phase 7: the ship gate.

Runs against the built index.html, not against the data that produced it, so a
stale build, a hand-edited number or a renamed key is caught rather than assumed
away. Exit code is non-zero if anything fails; the publish checklist in
DELIVERABLES.md section C maps onto these checks one for one.

  1  reconciliation   per-OE N sums to the review count
  2  N gate           no card names an OE under N=4 or with an unconfirmed name
  3  moderation       zero banned strings in the shipped HTML
  4  leakage          no internal field reaches the page payload
  5  data drift       every figure inlined in the page matches oe_public.json
  6  contrast         every text/background pair clears WCAG AA
  7  self-contained   no third-party sub-resource fetched at load
  8  CTA              the Join link actually points somewhere

What this does NOT check is layout: whether anything overlaps or overflows needs
a real browser. Render the page and look at it as well.
"""

import io
import json
import os
import re
import sys
from collections import OrderedDict

from patterns import load_banned

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(ROOT, "index.html")

BANNED = load_banned(DATA)
INTERNAL = ["tip_raw", "why_not", "respondent_id", "workload_raw", "submitted_at", "oe_raw"]

results = []


def check(name, ok, detail=""):
    results.append((bool(ok), name, detail))


# ---------------------------------------------------------------- load
def srgb(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexstr):
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main():
    if not os.path.exists(PAGE):
        sys.exit("FAIL index.html does not exist - run build/build_page.py first")

    html = io.open(PAGE, encoding="utf-8").read()
    with io.open(os.path.join(DATA, "oe_public.json"), encoding="utf-8") as fh:
        pub = json.load(fh, object_pairs_hook=OrderedDict)
    with io.open(os.path.join(DATA, "cards.json"), encoding="utf-8") as fh:
        cards = json.load(fh, object_pairs_hook=OrderedDict)
    with io.open(os.path.join(BUILD, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)

    m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("FAIL could not find the inlined payload in index.html")
    payload = json.loads(m.group(1).replace("<\\/", "</"))

    by_name = {o["name"]: o for o in pub["oes"]}

    # 1 ------------------------------------------------------- reconciliation
    total = sum(o["n"] for o in pub["oes"])
    check("reconciliation", total == pub["meta"]["reviews"],
          "per-OE N sums to %d, dataset says %d" % (total, pub["meta"]["reviews"]))

    # 2 ------------------------------------------------------- the N>=4 gate
    bad = []
    for c in cards["cards"]:
        o = by_name.get(c["oe"])
        if o is None:
            bad.append("%s names an unknown course %r" % (c["slot"], c["oe"]))
        else:
            if o["n"] < 4:
                bad.append("%s: %s has N=%d" % (c["slot"], c["oe"], o["n"]))
            if o["needs_confirm"]:
                bad.append("%s: %s has an unconfirmed name" % (c["slot"], c["oe"]))
    # and nothing unconfirmed may be printed with an invented long name
    for o in pub["oes"]:
        if o["needs_confirm"] and len(o["name"]) > 12:
            bad.append("%s is unconfirmed but printed with an expanded name" % o["name"])
    check("N>=4 gate on every card", not bad, "; ".join(bad))

    # 3 ------------------------------------------------------- moderation
    hits = [p for p in BANNED if re.search(p, html, re.I)]
    check("no profanity or faculty name in the shipped HTML", not hits,
          "matched: %s" % hits)

    # 4 ------------------------------------------------------- leakage
    leaked = [f for f in INTERNAL if '"%s"' % f in m.group(1)]
    check("no internal field in the page payload", not leaked, "found: %s" % leaked)

    # 5 ------------------------------------------------------- data drift
    drift = []
    if len(payload["oes"]) != len(pub["oes"]):
        drift.append("page has %d courses, dataset has %d" % (len(payload["oes"]), len(pub["oes"])))
    for po in payload["oes"]:
        src = by_name.get(po["name"])
        if src is None:
            drift.append("page shows unknown course %r" % po["name"])
            continue
        for k in ("n", "pct_41_plus", "pct_yes", "yes", "maybe", "no", "needs_confirm", "display_tip"):
            if po.get(k) != src.get(k):
                drift.append("%s.%s page=%r data=%r" % (po["name"], k, po.get(k), src.get(k)))
    for pc, sc in zip(payload["cards"], cards["cards"]):
        for k in ("label", "oe", "stat_value", "stat_label", "sub", "n", "tip"):
            if pc.get(k) != sc.get(k):
                drift.append("card %s.%s page=%r data=%r" % (sc["slot"], k, pc.get(k), sc.get(k)))
    check("every figure on the page matches the dataset", not drift, "; ".join(drift[:6]))

    # 6 ------------------------------------------------------- contrast
    tok = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;", html))
    pairs = [
        ("body text", tok["--ink"], tok["--paper"]),
        ("body text on card", tok["--ink"], tok["--surface"]),
        ("secondary text", tok["--ink-2"], tok["--paper"]),
        ("secondary text on card", tok["--ink-2"], tok["--surface"]),
        ("muted text", tok["--ink-3"], tok["--paper"]),
        ("muted text on card", tok["--ink-3"], tok["--surface"]),
        ("CTA label", cfg["cta_ink"], cfg["cta_bg"]),
    ]
    failed = ["%s %.2f:1" % (n, contrast(f, b)) for n, f, b in pairs if contrast(f, b) < 4.5]
    check("text contrast >= 4.5:1 (WCAG AA)", not failed, "; ".join(failed))

    bar = contrast(cfg["accent_bar"], tok["--surface"])
    check("data bar >= 3:1 against the surface", bar >= 3.0, "%.2f:1" % bar)

    # 7 ------------------------------------------------------- self-contained
    # Only sub-resources count: a src=, or an href on <link>/<script>/<iframe>, is something
    # the browser fetches on load. An <a href> is a link a reader chooses to follow - the join
    # CTA is one, by design - and counting it here would make the check unpassable.
    ext = re.findall(r'\ssrc="(https?://[^"]+)"', html)
    ext += re.findall(r'<(?:link|script|iframe)[^>]*\shref="(https?://[^"]+)"', html, re.I)
    ext += re.findall(r"url\(\s*['\"]?(https?://[^)'\"]+)", html, re.I)
    ext += re.findall(r"@import\s+['\"](https?://[^'\"]+)", html, re.I)
    check("no third-party sub-resource at runtime", not ext, "found: %s" % ext[:4])

    # 8 ------------------------------------------------------- the CTA
    url = cfg["cta_url"].strip()
    check("join CTA points somewhere", bool(url) and url != "#",
          "config.json cta_url is empty - the Join button is a dead link")

    # ---------------------------------------------------------------- report
    width = max(len(n) for _, n, _ in results)
    failures = 0
    for ok, name, detail in results:
        if ok:
            print("  PASS  %-*s" % (width, name))
        else:
            failures += 1
            print("  FAIL  %-*s  %s" % (width, name, detail))

    print()
    if failures:
        print("%d of %d checks failed - not ready to publish." % (failures, len(results)))
        sys.exit(1)
    print("all %d checks pass." % len(results))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
