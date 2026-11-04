# -*- coding: utf-8 -*-
"""
SPARC OE Insights - Phase 6: the share cards.

Writes cards.html, a sheet of 1080x1350 nodes to be screenshotted one per file
into cards/. They are built from the same cards.json the dashboard uses, so a
card and the page can never disagree - there is no separate design file to
drift out of sync.

Five cards: an opener that carries the pitch, then the four verdicts. Every one
of them prints its review count and the SPARC footer, because a card travels
further than the page and has to stand up on its own.
"""

import base64
import io
import json
import os
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cards.html")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#30334a;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
     font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased;padding:40px;display:flex;flex-wrap:wrap;gap:40px}
.card{width:1080px;height:1350px;background:__PAPER__;color:__INK__;padding:96px 88px;display:flex;flex-direction:column;position:relative}
.label{font-size:34px;font-weight:600;letter-spacing:-.01em;color:__INK3__}
.label .bk{display:block;margin-bottom:10px;font-size:30px;font-weight:700;letter-spacing:.14em;color:__BAR__}
.oe{margin-top:28px;font-size:76px;font-weight:700;letter-spacing:-.035em;line-height:1.04}
.figure{margin-top:76px;font-size:230px;font-weight:700;letter-spacing:-.055em;line-height:.9;white-space:nowrap}
.qual{margin-top:18px;font-size:60px;font-weight:600;letter-spacing:-.025em;line-height:1.1}
.sub{margin-top:30px;font-size:36px;color:__INK2__}
.n{margin-top:10px;font-size:36px;color:__INK3__}
.tip{margin-top:52px;padding-top:40px;border-top:3px solid __RULE__;font-size:38px;line-height:1.45;color:__INK2__}
.tip.none{font-style:italic;color:__INK3__}
.foot{margin-top:auto;padding-top:56px;display:flex;align-items:flex-end;justify-content:space-between;gap:40px}
.foot .mark{font-size:44px;font-weight:700;letter-spacing:-.02em;color:__BRANDINK__}
.foot .mark img{display:block;height:92px;width:auto;margin-bottom:6px}
.foot .mark span{display:block;margin-top:10px;font-size:28px;font-weight:400;letter-spacing:0;color:__INK3__}
.foot .join{font-size:28px;line-height:1.4;color:__INK2__;max-width:540px}
.foot .join b{display:block;font-size:30px;color:__INK__}
.foot .join .u{display:block;margin-bottom:8px;font-size:30px;font-weight:700;
               letter-spacing:-.01em;color:__INK__;white-space:nowrap}

/* opener */
.card.opener .lede{margin-top:auto;font-size:88px;font-weight:700;letter-spacing:-.04em;line-height:1.05}
.card.opener .stats{margin-top:56px;display:flex;gap:72px}
.card.opener .stats div{font-size:34px;color:__INK2__}
.card.opener .stats b{display:block;font-size:92px;font-weight:700;letter-spacing:-.04em;color:__INK__;line-height:1}
.card.opener .caveat{margin-top:52px;padding-top:40px;border-top:3px solid __RULE__;font-size:32px;line-height:1.45;color:__INK3__}
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    with io.open(os.path.join(DATA, "cards.json"), encoding="utf-8") as fh:
        cards = json.load(fh, object_pairs_hook=OrderedDict)
    with io.open(os.path.join(DATA, "oe_public.json"), encoding="utf-8") as fh:
        pub = json.load(fh, object_pairs_hook=OrderedDict)
    with io.open(os.path.join(BUILD, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)

    css = CSS
    for token, value in (("__PAPER__", "#f2f3f7"), ("__INK__", "#171a2e"), ("__INK2__", "#4d5168"),
                         ("__INK3__", "#63677f"), ("__RULE__", "#b9bdd0"),
                         ("__BRANDINK__", cfg["brand_ink"]), ("__BAR__", cfg["accent_bar"])):
        css = css.replace(token, value)

    url = cfg["cta_url"].strip()
    pretty = url.split("://", 1)[-1].rstrip("/") if url else ""
    site = cfg.get("site_url", "").strip()
    site_pretty = site.split("://", 1)[-1].rstrip("/") if site else ""

    logo_path = cfg.get("logo_path", "").strip()
    if logo_path:
        full = os.path.join(ROOT, logo_path.replace("/", os.sep))
        if not os.path.exists(full):
            sys.exit("FAIL logo_path does not exist: %s" % full)
        mime = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".webp": "image/webp"}[os.path.splitext(full)[1].lower()]
        with open(full, "rb") as fh:
            mark = '<img src="data:%s;base64,%s" alt="%s">' % (
                mime, base64.b64encode(fh.read()).decode("ascii"), esc(cfg["wordmark_text"]))
    else:
        mark = esc(cfg["wordmark_text"])

    foot = (
        '<div class="foot">'
        '<div class="mark">%s<span>OE Insights</span></div>'
        '<div class="join"><b>All %d courses</b><span class="u">%s</span>'
        "Built by SPARC, the automation and research club. Join us: %s</div>"
        '</div>' % (mark, pub["meta"]["distinct_oes"],
                    esc(site_pretty) if site_pretty else "link in bio",
                    esc(pretty) if pretty else "link in bio")
    )

    out = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
           "<title>OE Insights - share cards</title><style>%s</style></head><body>" % css]

    meta = pub["meta"]
    out.append(
        '<article class="card opener" id="card-0">'
        '<div class="label"><span class="bk">SPARC</span>OE Insights</div>'
        '<div class="lede">%d students told us what their electives were actually like.</div>'
        '<div class="stats"><div><b>%d</b>reviews</div><div><b>%d</b>courses</div>'
        '<div><b>%d</b>students</div></div>'
        '<div class="caveat">Collected October 2026. Every course shows how many people reviewed it. '
        'Below four reviews we show the numbers, but we don\'t pick a winner.</div>'
        '%s</article>' % (meta["respondents"], meta["reviews"], meta["distinct_oes"],
                          meta["respondents"], foot))

    for i, c in enumerate(cards["cards"], start=1):
        tip = ('<div class="tip">%s</div>' % esc(c["tip"])) if c["tip"] \
            else '<div class="tip none">Nobody left a tip for this one.</div>'
        out.append(
            '<article class="card" id="card-%d">'
            '<div class="label"><span class="bk">%s</span>%s</div>'
            '<div class="oe">%s</div>'
            '<div class="figure">%s</div>'
            '<div class="qual">%s</div>'
            '<div class="sub">%s</div>'
            '<div class="n">from %d review%s</div>'
            '%s%s</article>'
            % (i, esc(c["basket"]), esc(c["label"]), esc(c["oe"]), esc(c["stat_value"]), esc(c["stat_label"]),
               esc(c["sub"]), c["n"], "" if c["n"] == 1 else "s", tip, foot))

    out.append("</body></html>")
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))

    names = ["card-0 opener"] + ["card-%d %s" % (i, c["slot"]) for i, c in enumerate(cards["cards"], 1)]
    print("OK  cards.html  %d cards at 1080x1350" % (len(cards["cards"]) + 1))
    for n in names:
        print("    #%s" % n)
    if not url:
        print("    WARNING: no cta_url - cards fall back to 'link in bio'")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
