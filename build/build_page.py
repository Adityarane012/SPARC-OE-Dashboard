# -*- coding: utf-8 -*-
"""
SPARC OE Insights - Phase 5: build index.html.

Inlines the published data and the branding config into the template and writes
one self-contained file. No framework, no build step for the reader, no CDN, no
network requests at all - it opens from a file:// path or any static host.

The page is only ever fed data/oe_public.json and data/cards.json. The internal
files (reviews.csv, oe_stats.json) are not read here, so unmoderated text cannot
reach the page even by mistake.
"""

import base64
import io
import json
import os
import re
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "index.html")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    with io.open(os.path.join(DATA, "oe_public.json"), encoding="utf-8") as fh:
        pub = json.load(fh, object_pairs_hook=OrderedDict)
    with io.open(os.path.join(DATA, "cards.json"), encoding="utf-8") as fh:
        cards = json.load(fh, object_pairs_hook=OrderedDict)
    with io.open(os.path.join(BUILD, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    with io.open(os.path.join(BUILD, "page.template.html"), encoding="utf-8") as fh:
        tpl = fh.read()

    # only the fields the page actually renders - anything else stays server-side
    keep = ("name", "basket", "dept", "format", "n", "pct_41_plus", "pct_yes", "band_counts", "yes",
            "maybe", "no", "needs_confirm", "display_tip")
    payload = OrderedDict([
        ("meta", OrderedDict([
            ("reviews", pub["meta"]["reviews"]),
            ("respondents", pub["meta"]["respondents"]),
            ("distinct_oes", pub["meta"]["distinct_oes"]),
            ("oes_oe1", pub["meta"]["oes_oe1"]),
            ("oes_oe2", pub["meta"]["oes_oe2"]),
        ])),
        ("cards", [OrderedDict([(k, c[k]) for k in
                                ("basket", "label", "oe", "stat_value", "stat_label", "sub", "n", "tip")])
                   for c in cards["cards"]]),
        ("oes", [OrderedDict([(k, o[k]) for k in keep]) for o in pub["oes"]]),
    ])
    # A key renamed upstream silently renders an empty element rather than failing,
    # so every field the page prints must arrive non-empty. tip is the one field
    # allowed to be absent - some courses genuinely have no tip.
    for c in payload["cards"]:
        for k, v in c.items():
            if k != "tip" and (v is None or v == ""):
                sys.exit("FAIL card %r has an empty %r - did a key get renamed upstream?"
                         % (c.get("oe"), k))
    for o in payload["oes"]:
        for k in ("name", "n"):
            if o[k] is None or o[k] == "":
                sys.exit("FAIL course record missing %r: %r" % (k, o))

    # </script> inside JSON would close the tag early
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    url = cfg["cta_url"].strip()
    if not url:
        print("    WARNING: config.json has no cta_url - the Join button points nowhere.")
        url = "#join"

    # The logo is inlined as a data URI rather than linked. The page's whole
    # promise is that it is one file with no network requests - a <img src="assets/..">
    # would quietly break that the moment someone hosts index.html on its own.
    if cfg["logo_path"].strip():
        logo = os.path.join(ROOT, cfg["logo_path"].replace("/", os.sep))
        if not os.path.exists(logo):
            sys.exit("FAIL config.json logo_path points at a file that does not exist: %s" % logo)
        mime = {".png": "image/png", ".svg": "image/svg+xml",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp"}.get(os.path.splitext(logo)[1].lower())
        if mime is None:
            sys.exit("FAIL unsupported logo format: %s" % cfg["logo_path"])
        with open(logo, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        wordmark = '<img src="data:%s;base64,%s" alt="%s"><b class="vh">%s</b>' % (
            mime, b64, esc(cfg["wordmark_text"]), esc(cfg["wordmark_text"]))
        print("    logo inlined: %s (%.1f KB as base64)" % (cfg["logo_path"], len(b64) / 1024.0))
    else:
        wordmark = "<b>%s</b>" % esc(cfg["wordmark_text"])

    meta_desc = ("Peer reviews of %d Open Electives from %d students, collected by SPARC. "
                 "Review counts shown on every course." %
                 (pub["meta"]["distinct_oes"], pub["meta"]["respondents"]))

    html = tpl
    for token, value in (
        ("__DATA__", blob),
        ("__CTA_URL__", esc(url)),
        ("__CTA_LABEL__", esc(cfg["cta_label"])),
        ("__WORDMARK__", wordmark),
        ("__META_DESC__", esc(meta_desc)),
    ):
        html = html.replace(token, value)

    for name, token in (("accent_bar", "--bar:#1c5cab;"), ("brand_ink", "--brand-ink:var(--ink);"),
                        ("cta_bg", "--brand-cta-bg:var(--ink);"), ("cta_ink", "--brand-cta-ink:#ffffff;")):
        var = token.split(":")[0]
        html = html.replace(token, "%s:%s;" % (var, cfg[name]))

    left = re.findall(r"__[A-Z_]+__", html)
    if left:
        sys.exit("FAIL unreplaced template tokens: %s" % sorted(set(left)))

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)

    print("OK  index.html  %.1f KB  (%d courses, %d cards, no external requests)"
          % (len(html.encode("utf-8")) / 1024.0, len(payload["oes"]), len(payload["cards"])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
