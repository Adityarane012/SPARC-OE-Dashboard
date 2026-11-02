# -*- coding: utf-8 -*-
"""
SPARC OE Insights - Phase 2 moderation.

Joins data/moderation.csv onto the cleaned reviews and emits data/oe_public.json:
the publishable dataset, and the ONLY data file the page is allowed to consume.

Three things are enforced here rather than trusted:
  1. coverage  - every review carrying a tip has a moderation decision, and no
                 decision references a review that does not exist
  2. content   - no profanity, no faculty name, no identifying institution in
                 anything that reaches oe_public.json (hard fail)
  3. shape     - 'REMOVED' rows publish nothing; every other row publishes text

Fields deliberately absent from the output: tip_raw, why_not, workload_raw,
respondent_id, submitted_at, oe_raw. why_not is where both of the slurs in this
dataset actually live, so it is never published - see audit notes.
"""

import csv
import io
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

from patterns import load_banned

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# Hard fail if any of these reach the published file. The list is real: faculty
# names, a product promo and the profanity present in the export. It lives in
# data/banned_patterns.txt, git-ignored, because checking that a professor's
# name never ships means holding the name, and a public file listing faculty
# surnames under "banned" is the harm this pass exists to prevent.
BANNED = load_banned(DATA)

# Not failures - printed for a human to eyeball. Gendered titles and pronouns are
# how a de-named tip usually still points at one identifiable person.
WARN = [r"\bma'?a?m\b", r"\bsir\b", r"\bshe\b", r"\bher\b", r"\bhe\b", r"\bhim\b", r"\bhis\b"]

MAX_TIP = 300  # anything longer was meant to be trimmed in moderation.csv


def load_csv(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    reviews = load_csv(os.path.join(DATA, "reviews.csv"))
    decisions = load_csv(os.path.join(DATA, "moderation.csv"))
    with io.open(os.path.join(DATA, "oe_stats.json"), encoding="utf-8") as fh:
        stats = json.load(fh, object_pairs_hook=OrderedDict)

    by_id = {d["review_id"]: d for d in decisions}
    with_tip = {r["review_id"] for r in reviews if r["tip_raw"].strip()}
    errors = []

    # ---------------------------------------------------------------- coverage
    assert len(by_id) == len(decisions), "duplicate review_id in moderation.csv"
    missing = sorted(with_tip - set(by_id))
    if missing:
        errors.append("reviews with a tip but no moderation decision: %s" % missing)
    orphan = sorted(set(by_id) - with_tip)
    if orphan:
        errors.append("moderation decisions for reviews with no tip: %s" % orphan)

    # ---------------------------------------------------------------- shape + content
    warnings = []
    for rid, d in sorted(by_id.items()):
        pub = d["tip_public"].strip()
        act = d["action"].strip()
        if act == "REMOVED":
            if pub:
                errors.append("%s is REMOVED but publishes text" % rid)
            continue
        if not pub:
            errors.append("%s has action %r but publishes nothing" % (rid, act))
            continue
        if len(pub) > MAX_TIP:
            errors.append("%s tip is %d chars, over the %d limit" % (rid, len(pub), MAX_TIP))
        for pat in BANNED:
            if re.search(pat, pub, re.I):
                errors.append("%s tip matches banned pattern %r" % (rid, pat))
        hits = [p for p in WARN if re.search(p, pub, re.I)]
        if hits:
            warnings.append((rid, hits, pub))

    if errors:
        print("MODERATION FAILED")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    # ---------------------------------------------------------------- publish
    tips_by_oe = defaultdict(list)
    # Each tip keeps the verdict of the student who wrote it. A card headed
    # "Mixed reviews" that quotes the one person who liked the course reads as a
    # recommendation, so the card layer needs to know who said what.
    dissent_by_oe = defaultdict(list)
    oe_of = {r["review_id"]: r["oe_key"] for r in reviews}
    again_of = {r["review_id"]: (r["would_take_again"] or "").strip() for r in reviews}
    for rid, d in by_id.items():
        pub = d["tip_public"].strip()
        if d["action"].strip() != "REMOVED" and pub:
            tips_by_oe[oe_of[rid]].append(pub)
            if again_of.get(rid) != "Yes":
                dissent_by_oe[oe_of[rid]].append(pub)
    for k in tips_by_oe:
        # longest first: the most informative tip leads, and the page can take [0]
        tips_by_oe[k].sort(key=lambda t: (-len(t), t))
    for k in dissent_by_oe:
        dissent_by_oe[k].sort(key=lambda t: (-len(t), t))

    out_oes = []
    for s in stats["oes"]:
        tips = tips_by_oe.get(s["oe_key"], [])
        # the table/card tip: most informative one that still reads at a glance
        short = [t for t in tips if len(t) <= 160]
        display = (short[0] if short else (tips[-1] if tips else None))
        o = OrderedDict()
        for k in ("oe_key", "name", "short", "basket", "dept", "n", "n_ica", "band_counts",
                  "pct_41_plus", "pct_above_45", "n_again", "yes", "maybe", "no", "pct_yes",
                  "subject_type", "needs_confirm", "confirm_note", "card_eligible"):
            o[k] = s[k]
        o["n_tips_public"] = len(tips)
        dis = [t for t in dissent_by_oe.get(s["oe_key"], []) if len(t) <= 160]
        o["dissent_tip"] = (dis[0] if dis else None)
        o["display_tip"] = display
        o["tips"] = tips
        out_oes.append(o)

    meta = OrderedDict(stats["meta"])
    meta["tips_total"] = sum(len(v) for v in tips_by_oe.values())
    meta["tips_removed"] = sum(1 for d in decisions if d["action"].strip() == "REMOVED")
    meta["moderation_note"] = (
        "Every tip shown has been through a moderation pass: no faculty named, no profanity, "
        "course-level advice only. The free-text 'why not' answers are not published at all."
    )
    out = OrderedDict([("meta", meta), ("oes", out_oes)])
    with io.open(os.path.join(DATA, "oe_public.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=2, ensure_ascii=False))

    # ------------------------------------------------- side-by-side for team sign-off
    # Contains the raw text, so it is git-ignored. This is the sheet the team reads to
    # approve or overrule each decision (PROJECT.md open decision 1).
    raw_of = {r["review_id"]: r["tip_raw"] for r in reviews}
    L = ["# Moderation review sheet\n",
         "Generated by `build/moderate.py`. **Internal - contains the unmoderated text.**\n",
         "One row per tip. Approve or overrule each decision, then edit `data/moderation.csv`",
         "and re-run the pipeline. `action` key: `keep` as written, `copyedit` spelling/clarity",
         "only, `denamed` a faculty reference removed or recast, `trim` shortened, `REMOVED`",
         "not published at all.\n",
         "The free-text *why not* answers are not published in any form - both slurs in this",
         "dataset live in that field.\n"]
    order = {"REMOVED": 0, "denamed": 1, "trim": 2, "copyedit": 3, "keep": 4}
    for rid, d in sorted(by_id.items(), key=lambda kv: (order.get(kv[1]["action"].strip(), 9), kv[0])):
        L.append("---\n")
        L.append("**%s** · %s · `%s`\n" % (d["oe_name"], rid, d["action"].strip()))
        L.append("- As submitted: %s" % (raw_of.get(rid, "").replace("\n", " ") or "_(none)_"))
        L.append("- Published: %s" % (d["tip_public"].strip() or "**nothing - removed**"))
        if d["note"].strip():
            L.append("- Why: %s" % d["note"].strip())
        L.append("")
    with io.open(os.path.join(DATA, "moderation_review.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    # ---------------------------------------------------------------- report
    print("OK  %d decisions / %d published / %d removed"
          % (len(decisions), meta["tips_total"], meta["tips_removed"]))
    print("    banned-pattern scan: clean (%d patterns checked)" % len(BANNED))
    no_tip = [o["name"] for o in out_oes if o["card_eligible"] and not o["display_tip"]]
    if no_tip:
        print("    card-eligible OEs with no publishable tip: %s" % ", ".join(no_tip))
    if warnings:
        print("    %d tips keep a gendered title or pronoun - review:" % len(warnings))
        for rid, hits, pub in warnings:
            print("      %-14s %-22s %s" % (rid, ",".join(h.strip("\\b") for h in hits), pub[:70]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
