# -*- coding: utf-8 -*-
"""
SPARC OE Insights - Phase 3: pick the verdict cards.

Derived by rule from data/oe_public.json rather than hand-picked, so the choices
can be re-checked and re-derive themselves if the data is corrected.

Two deliberate choices about how the numbers are phrased:

  Cards say "7 of 7 would take it again", not "100%". At N=4 a percentage
  overclaims - "100%" reads like a measured rate when it is four people. The
  count is the same fact told honestly, which is the whole point of the N>=4
  gate. The table keeps percentages, because it shows N in its own column.

  "Easiest to score" is decided on the share expecting the top band (Above 45),
  not on the share expecting 41+. The latter saturates: 21 of 30 OEs sit at
  100%, so it cannot separate them.

Cards are picked WITHIN a basket, not across both. A student takes one OE-I and
one OE-II, so "crowd favourite" is only a useful answer if it names something
they can actually choose between. A global ranking would put two OE-I winners in
front of someone deciding their OE-II.

OE-II supports fewer cards than OE-I simply because fewer of its courses clear
N>=4 - 2 against 7. The rule emits what each basket can honestly carry rather
than padding OE-II out to a matching four.

The gate: a card may only name an OE with N>=4 whose name is confirmed. An OE
that clears N>=4 but has an ambiguous name is emitted as a blocked card, ready
to switch on once the team confirms it.
"""

import io
import json
import os
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def count_phrase(k, n, what):
    return ("%d of %d %s" % (k, n, what)).strip()


def figure(k, n):
    """The stat is split in two: a short figure that stays on one line at any
    card width, and a qualifier set smaller beneath it. A single run of text
    like '7 of 7 would take it again' wraps mid-phrase on a narrow card, which
    is exactly where these get read - in a screenshot."""
    return "%d of %d" % (k, n)


def main():
    with io.open(os.path.join(DATA, "oe_public.json"), encoding="utf-8") as fh:
        pub = json.load(fh, object_pairs_hook=OrderedDict)

    oes = pub["oes"]
    eligible = [o for o in oes if o["card_eligible"]]

    # Each slot carries a GUARD as well as a ranking. Picking the maximum is not the same
    # as the claim being true: in OE-II the best remaining "easiest to score" candidate had
    # nobody at all expecting the top band, and the card would have read "0 of 4 expect 45+
    # marks" under the heading "Easiest to score". A superlative no course in the basket
    # actually earns is not emitted - the basket simply carries fewer cards.
    SLOTS = [
        ("crowd_favourite", "Most liked",
         lambda pool: sorted(pool, key=lambda o: (-o["pct_yes"], -o["n"]))[:1],
         lambda o: o["pct_yes"] >= 60.0,
         "Highest would-take-again share in this basket among OEs with enough reviews."),
        ("easiest_to_score", "Best marks",
         lambda pool: sorted(pool, key=lambda o: (-o["pct_above_45"], -o["pct_41_plus"], -o["n"]))[:1],
         lambda o: o["pct_above_45"] >= 50.0,
         "Largest share of reviewers expecting the top ICA band (Above 45) in this basket."),
        ("hidden_gem", "Worth a look",
         lambda pool: sorted([o for o in pool if o["n"] <= 4],
                             key=lambda o: (-o["pct_yes"], -o["n_tips_public"], o["name"]))[:1],
         lambda o: o["pct_yes"] >= 60.0,
         "Well liked but among the least-reviewed OEs in this basket that still clear the gate."),
        ("most_mixed", "Mixed reviews",
         lambda pool: sorted(pool, key=lambda o: (o["pct_yes"], o["pct_above_45"], o["name"]))[:1],
         lambda o: o["pct_yes"] <= 60.0,
         "Lowest would-take-again share in this basket among OEs with enough reviews."),
    ]

    picks = []   # (basket, slot, label, oe, why)
    skipped = []
    for basket in ("OE-I", "OE-II"):
        used = set()
        for slot, label, chooser, guard, why in SLOTS:
            pool = [o for o in eligible
                    if o["basket"] == basket and o["oe_key"] not in used]
            hit = chooser(pool)
            if not hit:
                skipped.append((basket, slot, "no candidate left in this basket"))
                continue
            o = hit[0]
            if not guard(o):
                skipped.append((basket, slot,
                                "best candidate %s does not support the claim" % o["name"]))
                continue
            used.add(o["oe_key"])
            picks.append((basket, slot, label, o, why))

    def n41(o):
        return int(round(o["pct_41_plus"] * o["n_ica"] / 100.0))

    def tip_for(slot, o):
        """A "mixed reviews" card quoting the one student who would take the course
        again reads as a recommendation under a negative heading. Prefer a tip from
        someone who did not answer Yes; fall back to the usual one if nobody who
        dissented left a tip."""
        if slot == "most_mixed" and o.get("dissent_tip"):
            return o["dissent_tip"]
        return o["display_tip"]

    def card(basket, slot, label, o, stat_value, stat_label, sub, why):
        return OrderedDict([
            ("basket", basket),
            ("slot", slot),
            ("label", label),
            ("oe", o["name"]),
            ("stat_value", stat_value),
            ("stat_label", stat_label),
            ("stat", "%s %s" % (stat_value, stat_label)),
            ("sub", sub),
            ("n", o["n"]),
            ("tip", tip_for(slot, o)),
            ("why", why),
        ])

    SHAPE = {
        "crowd_favourite": lambda o: (figure(o["yes"], o["n_again"]), "would take it again",
                                      count_phrase(n41(o), o["n_ica"], "expect 41+ out of 50")),
        "easiest_to_score": lambda o: (figure(o["band_counts"]["Above 45"], o["n_ica"]), "expect 45+ out of 50",
                                       count_phrase(o["yes"], o["n_again"], "would take it again")),
        "hidden_gem": lambda o: (figure(o["yes"], o["n_again"]), "would take it again",
                                 count_phrase(n41(o), o["n_ica"], "expect 41+ out of 50")),
        "most_mixed": lambda o: (figure(o["yes"], o["n_again"]), "would take it again",
                                 count_phrase(n41(o), o["n_ica"], "expect 41+ out of 50")),
    }
    cards = []
    for basket, slot, label, o, why in picks:
        stat_value, stat_label, sub = SHAPE[slot](o)
        cards.append(card(basket, slot, label, o, stat_value, stat_label, sub, why))

    # OEs that clear N>=4 but cannot be named yet
    blocked = [
        OrderedDict([
            ("oe", o["name"]),
            ("n", o["n"]),
            ("would_be", "People were split - %s would take it again"
                         % count_phrase(o["yes"], o["n_again"], "").strip()),
            ("blocked_on", o["confirm_note"]),
        ])
        for o in oes if o["n"] >= 4 and o["needs_confirm"]
    ]

    # ---------------------------------------------------------------- gate
    errors = []
    by_key = {o["name"]: o for o in oes}
    for c in cards:
        o = by_key[c["oe"]]
        if o["n"] < 4:
            errors.append("%s names %s with N=%d (gate is N>=4)" % (c["slot"], c["oe"], o["n"]))
        if o["needs_confirm"]:
            errors.append("%s names %s, whose name is unconfirmed" % (c["slot"], c["oe"]))
        if c["n"] != o["n"]:
            errors.append("%s prints N=%s but the data says %s" % (c["slot"], c["n"], o["n"]))
    if len({c["oe"] for c in cards}) != len(cards):
        errors.append("the same OE appears on more than one card")
    for c in cards:
        if by_key[c["oe"]]["basket"] != c["basket"]:
            errors.append("%s is filed under %s but the course sits in %s"
                          % (c["oe"], c["basket"], by_key[c["oe"]]["basket"]))
    if not any(c["basket"] == "OE-I" for c in cards) or not any(c["basket"] == "OE-II" for c in cards):
        errors.append("a basket ended up with no cards at all")
    if errors:
        print("CARD GATE FAILED")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    out = OrderedDict([
        ("meta", OrderedDict([
            ("gate", "N>=4 reviews and a confirmed course name"),
            ("eligible_oes", len(eligible)),
            ("eligible_oe1", sum(1 for o in eligible if o["basket"] == "OE-I")),
            ("eligible_oe2", sum(1 for o in eligible if o["basket"] == "OE-II")),
            ("selection_note", "Cards are picked within a basket, not across both: a student "
                               "chooses one OE-I and one OE-II, so a cross-basket ranking would "
                               "answer a question nobody is asking."),
            ("phrasing_note", "Cards state counts, not percentages: at N=4 a percentage overclaims."),
            ("caveat_line", pub["meta"]["caveat_line"]),
        ])),
        ("cards", cards),
        ("slots_not_filled", [OrderedDict([("basket", b), ("slot", sl), ("reason", r)])
                              for b, sl, r in skipped]),
        ("blocked", blocked),
    ])
    with io.open(os.path.join(DATA, "cards.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=2, ensure_ascii=False))

    print("OK  %d cards from %d eligible OEs, %d blocked" % (len(cards), len(eligible), len(blocked)))
    for c in cards:
        print("  %-6s %-16s %-56s %-28s N=%d  %s"
              % (c["basket"], c["slot"], c["oe"], c["stat"], c["n"], "tip" if c["tip"] else "NO TIP"))
    for b in blocked:
        print("  %-16s %-42s blocked: name unconfirmed" % ("(blocked)", b["oe"]))
    for b, sl, r in skipped:
        print("  %-6s %-16s not emitted - %s" % (b, sl, r))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
