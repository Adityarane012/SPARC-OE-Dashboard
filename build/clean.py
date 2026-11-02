# -*- coding: utf-8 -*-
"""
SPARC OE Insights - Phase 1 clean pipeline.

Raw form export  ->  deduped, name-normalised, one-row-per-review data.

Deterministic and re-runnable: fix the map or the ledger, re-run, everything downstream
re-flows. Nothing here is hand-patched.

Outputs (all under data/):
  reviews.csv     one row per review
  oe_stats.json   per-OE aggregates, consumed by the page
  name_map.csv    every raw spelling -> canonical, with confidence
  audit.md        every drop, merge and rename, with its reason
"""

import csv
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "Docs", "Response Sheet.csv")
OUT = os.path.join(ROOT, "data")

# ---------------------------------------------------------------- dedupe ledger
# Three respondents submitted twice. Resolutions approved 1 Nov 2026.
DROP_SUBMISSIONS = {
    # 7RAZ7JA: keep 1st (yXbQEEg). Only delta is EPM workload 2 vs 4 - a field we never publish.
    "yXbQEAd": "duplicate of yXbQEEg (7RAZ7JA); kept 1st submission per approved ledger",
    # 81B8GPl: keep 1st (RWQOgz9) - it carries AR/VR *and* FIMIS with tips; the 2nd has AR/VR only.
    "GeVMy4z": "duplicate of RWQOgz9 (81B8GPl); kept 1st, which holds 2 reviews instead of 1",
    # rj4L8Jv: keep 2nd (4aY5jLY) for its richer tips, but take OE names from the 1st.
    "zEAlK61": "duplicate of 4aY5jLY (rj4L8Jv); kept 2nd for richer tips, names lifted from this row",
}

# rj4L8Jv merge: the kept submission (4aY5jLY) spells its OEs "bdms"/"ltls". Use the same
# respondent's own spelled-out names from the dropped row so canonicalisation rests on their
# words, not our acronym guess. Keyed by SUBMISSION id.
NAME_OVERRIDES = {
    ("4aY5jLY", 1): ("Basic Decision Making with Spreadsheets", "name taken from zEAlK61 (same respondent, 4 min earlier)"),
    ("4aY5jLY", 2): ("Leading Through Lifeskills", "name taken from zEAlK61 (same respondent, 4 min earlier)"),
}

# ---------------------------------------------------------------- the official basket
# data/basket_map.csv is the registrar's OE-I / OE-II list, transcribed from the sheet the
# club was given. It is the authority for which basket a course sits in and for its official
# spelling. Every canonical name below must match one of its rows exactly - the assertion in
# main() fails the build otherwise, so a typo here cannot quietly produce an unplaced course.
def load_baskets(data_dir):
    import csv as _csv
    with io.open(os.path.join(data_dir, "basket_map.csv"), encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))
    assert rows, "basket_map.csv is empty"
    by_name = {}
    for r in rows:
        assert r["basket"] in ("OE-I", "OE-II"), "bad basket %r" % r["basket"]
        assert r["official_name"] not in by_name, "duplicate official name %r" % r["official_name"]
        by_name[r["official_name"]] = (r["basket"], r["dept"], r["note"])
    return by_name


# ---------------------------------------------------------------- canonical OEs
# needs_confirm=True  -> cannot carry a headline card or an expanded name in public (PROJECT.md 9.2)
CANON = OrderedDict([
    ("financial_derivatives", dict(name="Financial Derivatives", short="FD", needs_confirm=False, note="")),
    ("forensic_science", dict(name="Introduction to Forensic Science", short="Forensic", needs_confirm=False, note="")),
    ("gis", dict(name="Introduction to GIS", short="GIS", needs_confirm=False, note="")),
    ("5g", dict(name="5G for Everyone", short="5G", needs_confirm=False, note="")),
    ("bdms", dict(name="Basic Decision Making with Spreadsheets", short="BDMS", needs_confirm=False,
                  note="BSDM/BDMS/bdms folded in; long form present in data confirms expansion.")),
    ("drone_tech", dict(name="Drone Technology", short="Drone", needs_confirm=False, note="")),
    ("epm", dict(name="Elements of Project Management", short="EPM", needs_confirm=False,
                 note="Long form present in data confirms expansion.")),
    ("game_design", dict(name="Game Design", short="Game Des.", needs_confirm=False, note="")),
    ("arvr", dict(name="Introduction to Virtual Reality and Augmented Reality", short="AR/VR", needs_confirm=False,
                  note="ARVR/ArVr/IVRAR/IVARVR folded in; expanded to the official OE-I name.")),
    ("disaster_mgmt", dict(name="Disaster Management", short="Disaster", needs_confirm=False, note="")),
    ("fimis", dict(name="Financial Institutions, Markets, Instruments and Services", short="FIMIS", needs_confirm=False,
                   note="Expanded from the official OE-II basket; the long form is exactly what FIMIS spells.")),
    ("ltls", dict(name="Leading Through Life Skills", short="LTLS", needs_confirm=False,
                  note="LTLS/ltls folded in; long form present in data.")),
    ("life_skills", dict(name="Life Skills", short="Life Sk.", needs_confirm=False,
                         note="RESOLVED: the official basket lists 'Life Skills' (OE-II, BSH) and 'Leading Through Life Skills' (OE-II, TM) as two separate courses. They are never merged, so LTLS stays at N=3 and stays out of the cards.")),
    ("3d_printing", dict(name="3D Printing", short="3D Print", needs_confirm=False, note="'3d' folded in.")),
    ("advertising_pr", dict(name="Advertising and Public Relations", short="Adv/PR", needs_confirm=False, note="")),
    ("cem", dict(name="Creativity and Ethics in Marketing", short="CEM", needs_confirm=False,
                 note="Confirmed against the official OE-II basket.")),
    ("evt", dict(name="Electric Vehicle Technology", short="EVT", needs_confirm=False,
                 note="Long form present in data confirms expansion.")),
    ("climate_change", dict(name="Fundamentals of Climate Change", short="Climate", needs_confirm=False, note="")),
    ("interior_design", dict(name="Interior Design", short="Interior", needs_confirm=False, note="")),
    ("research_methodology", dict(name="Research Methodology", short="Res. Meth.", needs_confirm=False,
                                  note="Spelled out by respondents; kept distinct from the bare 'RES' entries.")),
    ("renewable_energy", dict(name="Renewable Energy Sources", short="Renewable", needs_confirm=False,
                              note="Confirmed from the official OE-I basket. The bare 'RES' entries fold in here: one RES tip says 'Mechanical faculty ke close raho' and Renewable Energy Sources is the Mechanical OE-I course, while Research Methodology is Civil. Confirmed by the team 2 Nov 2026.")),
    ("scada", dict(name="Supervisory Control and Data Acquisition", short="SCADA", needs_confirm=False,
                   note="Long form present in data confirms expansion.")),
    ("mgmt_movies", dict(name="Management Through Movies", short="Mgmt/Movies", needs_confirm=False, note="")),
    ("modelling_simulation", dict(name="Modelling and Simulation", short="Mod/Sim", needs_confirm=False,
                                  note="The bare 'ML' entry folds in here. No Machine Learning course exists in either basket; confirmed by the team 2 Nov 2026.")),
    ("smart_cities", dict(name="Smart Cities", short="Smart Cit.", needs_confirm=False, note="")),
    ("waste_mgmt", dict(name="Waste Management", short="Waste", needs_confirm=False, note="")),
    ("em", dict(name="Environment Management", short="Env. Mgmt", needs_confirm=False,
                note="'EM' resolved to the OE-II BSH course; confirmed by the team 2 Nov 2026.")),
    ("pm", dict(name="Production Management", short="Prod. Mgmt", needs_confirm=False,
                note="'PM' resolved to the OE-II Mechanical course, NOT Elements of Project Management (which respondents spelled out separately); confirmed by the team 2 Nov 2026.")),
])

# normalised raw spelling -> canonical key. 'high' = exact/trivial case or spacing variant,
# 'medium' = acronym or abbreviation resolved from a long form present elsewhere in the data.
NAME_MAP = {
    "financial derivatives": ("financial_derivatives", "high"),
    "fd": ("financial_derivatives", "medium"),
    "introduction to forensic science": ("forensic_science", "high"),
    "introduction to forensic": ("forensic_science", "high"),
    "gis": ("gis", "high"),
    "intro to gis": ("gis", "high"),
    "introduction to gis": ("gis", "high"),
    "res": ("renewable_energy", "medium"),   # team-confirmed 2 Nov 2026
    "5g for everyone": ("5g", "high"),
    "basic decision making with spreadsheet": ("bdms", "high"),
    "basic decision making with spreadsheets": ("bdms", "high"),
    "bdms": ("bdms", "medium"),
    "bsdm": ("bdms", "medium"),
    "drone technology": ("drone_tech", "high"),
    "drone tech": ("drone_tech", "high"),
    "epm": ("epm", "medium"),
    "elements of project management": ("epm", "high"),
    "game design": ("game_design", "high"),
    "arvr": ("arvr", "medium"),
    "ivarvr": ("arvr", "medium"),
    "ivrar": ("arvr", "medium"),
    "disaster management": ("disaster_mgmt", "high"),
    "fimis": ("fimis", "high"),
    "ltls": ("ltls", "medium"),
    "leading through lifeskills": ("ltls", "high"),
    "life skills": ("life_skills", "high"),
    "3d": ("3d_printing", "medium"),
    "3d printing": ("3d_printing", "high"),
    "advertising and pr": ("advertising_pr", "high"),
    "cem": ("cem", "high"),
    "creativity and ethics in marketting": ("cem", "medium"),
    "electric vehicle technology": ("evt", "high"),
    "evt": ("evt", "medium"),
    "fundamentals of climate change": ("climate_change", "high"),
    "interior design": ("interior_design", "high"),
    "research methodology": ("research_methodology", "high"),
    "renewable energy resources": ("renewable_energy", "high"),
    "scada": ("scada", "medium"),
    "supervisory control and data acquisition": ("scada", "high"),
    "management thru movies": ("mgmt_movies", "high"),
    "ml": ("modelling_simulation", "medium"),   # team-confirmed 2 Nov 2026
    "modelling and simulation": ("modelling_simulation", "high"),
    "smart cities": ("smart_cities", "high"),
    "waste management": ("waste_mgmt", "high"),
    "em": ("em", "high"),
    "pm": ("pm", "high"),
}

# ICA bands. Midpoints are a modelling choice, used ONLY as a secondary sort key -
# the published metric is pct_41_plus, which counts real answers and invents nothing.
BANDS = ["Below 35", "35-40", "41-45", "Above 45"]
BAND_MIDPOINT = {"Below 35": 32.5, "35-40": 37.5, "41-45": 43.0, "Above 45": 47.0}
BAND_IS_41_PLUS = {"Below 35": False, "35-40": False, "41-45": True, "Above 45": True}


def norm_name(s):
    s = s.strip().lower()
    s = s.replace("’", "'")
    s = re.sub(r"[\s ]+", " ", s)
    return s.strip(" .,-")


def norm_band(s):
    """Normalise the ICA band, tolerating en-dash / em-dash / hyphen and stray spacing."""
    s = s.strip()
    if not s:
        return ""
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    for b in BANDS:
        if s.lower() == b.lower():
            return b
    raise ValueError("unrecognised ICA band: %r" % s)


BASKETS = load_baskets(OUT)

# Every canonical name must be a course the registrar actually offers. This is the check that
# makes the basket split trustworthy: an invented, misspelt or stale name fails the build here
# rather than appearing on the page under the wrong heading or under no heading at all.
_unplaced = [m["name"] for m in CANON.values() if m["name"] not in BASKETS]
assert not _unplaced, ("these canonical names are not in data/basket_map.csv, so they have no "
                       "basket: %s" % _unplaced)


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    with io.open(RAW, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    audit_drops, audit_renames = [], []
    seen_raw = Counter()
    unmapped = set()
    reviews = []

    for r in rows:
        sub = r["Submission ID"].strip()
        resp = r["Respondent ID"].strip()
        if sub in DROP_SUBMISSIONS:
            audit_drops.append((sub, resp, DROP_SUBMISSIONS[sub]))
            continue

        for slot in (1, 2):
            suf = "" if slot == 1 else " (2)"
            raw = r["Which OE %d did you take?" % slot].strip()
            override_note = ""
            if (sub, slot) in NAME_OVERRIDES:
                replacement, override_note = NAME_OVERRIDES[(sub, slot)]
                if raw:
                    audit_renames.append((sub, resp, raw, replacement, override_note))
                    raw = replacement
            if not raw:
                continue

            seen_raw[raw] += 1
            key = norm_name(raw)
            if key not in NAME_MAP:
                unmapped.add(raw)
                continue
            canon_key, _conf = NAME_MAP[key]

            workload = r["Workload (assignments, projects, submissions)" + suf].strip()
            reviews.append(OrderedDict([
                ("review_id", "%s-%d" % (sub, slot)),
                ("respondent_id", resp),
                ("submitted_at", r["Submitted at"].strip()),
                ("oe_key", canon_key),
                ("oe_name", CANON[canon_key]["name"]),
                ("oe_raw", raw),
                ("ica_band", norm_band(r["What expected ICA are you thinking" + suf])),
                # kept for the record, deliberately NOT published: respondents read the
                # 1-5 scale inconsistently (PROJECT.md trap 2)
                ("workload_raw", int(workload) if workload.isdigit() else ""),
                ("would_take_again", r["Would you take this OE again?" + suf].strip()),
                ("why_not", r["Why not?" + suf].strip()),
                ("subject_type", r["What type of subject was it?" + suf].strip()),
                ("tip_raw", r["One tip for peers taking this OE" + suf].strip()),
                ("name_note", override_note),
            ]))

    if unmapped:
        sys.exit("FAIL unmapped OE spellings (add them to NAME_MAP): %s" % sorted(unmapped))

    # ------------------------------------------------------------- aggregate
    by_oe = defaultdict(list)
    for rv in reviews:
        by_oe[rv["oe_key"]].append(rv)

    stats = []
    for key, rs in by_oe.items():
        meta = CANON[key]
        n = len(rs)
        bands = Counter(rv["ica_band"] for rv in rs if rv["ica_band"])
        n_ica = sum(bands.values())
        n_41 = sum(c for b, c in bands.items() if BAND_IS_41_PLUS[b])
        again = Counter(rv["would_take_again"] for rv in rs if rv["would_take_again"])
        n_again = sum(again.values())
        mids = [BAND_MIDPOINT[rv["ica_band"]] for rv in rs if rv["ica_band"]]
        subj = Counter(rv["subject_type"] for rv in rs if rv["subject_type"])
        tips = [rv["tip_raw"] for rv in rs if rv["tip_raw"]]

        stats.append(OrderedDict([
            ("oe_key", key),
            ("name", meta["name"]),
            ("short", meta["short"]),
            ("n", n),
            ("n_ica", n_ica),
            ("band_counts", OrderedDict((b, bands.get(b, 0)) for b in BANDS)),
            ("pct_41_plus", round(100.0 * n_41 / n_ica, 1) if n_ica else None),
            # pct_41_plus saturates (most OEs are seen as scoring), so the top band is what
            # actually separates them - it decides the "easiest to score" superlative.
            ("pct_above_45", round(100.0 * bands.get("Above 45", 0) / n_ica, 1) if n_ica else None),
            ("avg_ica_midpoint", round(sum(mids) / len(mids), 2) if mids else None),
            ("n_again", n_again),
            ("yes", again.get("Yes", 0)),
            ("maybe", again.get("Maybe", 0)),
            ("no", again.get("No", 0)),
            ("pct_yes", round(100.0 * again.get("Yes", 0) / n_again, 1) if n_again else None),
            ("subject_type", OrderedDict(sorted(subj.items()))),
            ("n_tips", len(tips)),
            ("basket", BASKETS[meta["name"]][0]),
            ("dept", BASKETS[meta["name"]][1]),
            ("needs_confirm", meta["needs_confirm"]),
            ("confirm_note", meta["note"]),
            ("card_eligible", n >= 4 and not meta["needs_confirm"]),
        ]))

    stats.sort(key=lambda s: (-s["n"], -(s["pct_yes"] or 0), s["name"]))

    # ------------------------------------------------------------- assertions
    assert sum(s["n"] for s in stats) == len(reviews), "per-OE N does not sum to review count"
    assert all(s["basket"] in ("OE-I", "OE-II") for s in stats), "an OE has no basket"
    assert (sum(s["n"] for s in stats if s["basket"] == "OE-I")
            + sum(s["n"] for s in stats if s["basket"] == "OE-II")) == len(reviews),         "reviews split across baskets does not sum to the review count"
    assert len(reviews) == 79, "expected 79 reviews after dedupe, got %d" % len(reviews)
    assert len({rv["respondent_id"] for rv in reviews}) == 48, "expected 48 respondents"
    assert len({rv["review_id"] for rv in reviews}) == len(reviews), "duplicate review_id"
    assert set(DROP_SUBMISSIONS) == {"yXbQEAd", "GeVMy4z", "zEAlK61"}, "dedupe ledger drifted"
    # the rj4L8Jv merge must actually fire - it silently no-ops if the key shape is wrong
    assert len(audit_renames) == len(NAME_OVERRIDES), \
        "NAME_OVERRIDES did not all apply: %d of %d fired" % (len(audit_renames), len(NAME_OVERRIDES))
    for s in stats:
        assert s["n_again"] == s["yes"] + s["maybe"] + s["no"], "would-take-again counts inconsistent for %s" % s["name"]
        assert sum(s["band_counts"].values()) == s["n_ica"], "band counts inconsistent for %s" % s["name"]
    unused = [k for k in CANON if k not in by_oe]
    assert not unused, "declared canonical OEs with no reviews: %s" % unused

    # ------------------------------------------------------------- write
    with io.open(os.path.join(OUT, "reviews.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(reviews[0].keys()))
        w.writeheader()
        w.writerows(reviews)

    n_resp = len({rv["respondent_id"] for rv in reviews})
    meta = OrderedDict([
        ("generated_from", "Docs/Response Sheet.csv"),
        ("submissions_raw", len(rows)),
        ("submissions_dropped", len(audit_drops)),
        ("reviews", len(reviews)),
        ("respondents", n_resp),
        ("distinct_oes", len(stats)),
        ("card_eligible_oes", sum(1 for s in stats if s["card_eligible"])),
        ("oes_oe1", sum(1 for s in stats if s["basket"] == "OE-I")),
        ("oes_oe2", sum(1 for s in stats if s["basket"] == "OE-II")),
        ("reviews_oe1", sum(s["n"] for s in stats if s["basket"] == "OE-I")),
        ("reviews_oe2", sum(s["n"] for s in stats if s["basket"] == "OE-II")),
        ("basket_source", "data/basket_map.csv - the registrar's OE-I/OE-II list"),
        ("needs_confirm_oes", [s["name"] for s in stats if s["needs_confirm"]]),
        ("caveat_line", "%d reviews from %d students, collected in October 2026. Some courses got only one or two, so the review count sits beside every number. Tips are students' own words, tidied for clarity." % (len(reviews), n_resp)),
        ("band_midpoints_note", "avg_ica_midpoint is a sort key only; the published scorability metric is pct_41_plus, a direct count."),
    ])
    with io.open(os.path.join(OUT, "oe_stats.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(OrderedDict([("meta", meta), ("oes", stats)]), indent=2, ensure_ascii=False))

    with io.open(os.path.join(OUT, "name_map.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["raw_spelling", "occurrences", "canonical", "confidence", "needs_confirm", "note"])
        for raw in sorted(seen_raw, key=lambda x: (norm_name(x), x)):
            ck, conf = NAME_MAP[norm_name(raw)]
            w.writerow([raw, seen_raw[raw], CANON[ck]["name"], conf,
                        "YES" if CANON[ck]["needs_confirm"] else "no", CANON[ck]["note"]])

    L = []
    A = L.append
    A("# Phase 1 audit - clean pipeline\n")
    A("Generated by `build/clean.py` from `Docs/Response Sheet.csv`. Re-run to regenerate.\n")
    A("## Totals\n")
    A("| | |")
    A("|---|---|")
    A("| Raw submissions | %d |" % len(rows))
    A("| Submissions dropped as duplicates | %d |" % len(audit_drops))
    A("| Reviews (one row per OE reviewed) | **%d** |" % len(reviews))
    A("| Distinct respondents | **%d** |" % n_resp)
    A("| Distinct OEs after normalisation | %d |" % len(stats))
    A("| OEs eligible for a headline card (N>=4, name confirmed) | %d |" % sum(1 for s in stats if s["card_eligible"]))
    A("")
    A("Raw export carried 84 reviews from 51 submissions. PROJECT.md section 5 recorded one")
    A("near-duplicate; there were three. Deduping costs 5 reviews, so the public caveat line")
    A("reads **%d reviews from %d students**, not 84 from 51.\n" % (len(reviews), n_resp))
    A("## Submissions dropped\n")
    A("| Submission | Respondent | Reason |")
    A("|---|---|---|")
    for sub, resp, why in audit_drops:
        A("| `%s` | `%s` | %s |" % (sub, resp, why))
    A("")
    A("## Names lifted across a merge\n")
    if audit_renames:
        A("| Submission | Respondent | As submitted | Used instead | Why |")
        A("|---|---|---|---|---|")
        for sub, resp, old, new, why in audit_renames:
            A("| `%s` | `%s` | %s | %s | %s |" % (sub, resp, old, new, why))
    else:
        A("_None._")
    A("")
    A("## Names needing team confirmation\n")
    A("These are held out of headline cards and shown unexpanded in the table until confirmed.\n")
    A("| OE | N | Why it is unresolved |")
    A("|---|---|---|")
    for s in stats:
        if s["needs_confirm"]:
            A("| %s | %d | %s |" % (s["name"], s["n"], s["confirm_note"]))
    A("")
    A("## Per-OE summary\n")
    A("| OE | N | Expecting 41+ | Would take again | Y/M/N | Tips | Card eligible |")
    A("|---|---|---|---|---|---|---|")
    for s in stats:
        A("| %s%s | %d | %s | %s | %d/%d/%d | %d | %s |" % (
            s["name"], " (!)" if s["needs_confirm"] else "", s["n"],
            ("%.0f%%" % s["pct_41_plus"]) if s["pct_41_plus"] is not None else "--",
            ("%.0f%%" % s["pct_yes"]) if s["pct_yes"] is not None else "--",
            s["yes"], s["maybe"], s["no"], s["n_tips"], "yes" if s["card_eligible"] else "no"))
    A("")
    A("## Fields deliberately not published\n")
    A("- `workload_raw` (1-5): respondents read the scale inconsistently - some treated 5 as")
    A("  \"heavy\", others as \"great\". Kept in `reviews.csv` for the record, never shown.")
    A("- `why_not`, `tip_raw`: free text, pending the Phase 2 moderation pass.")
    A("- `respondent_id`, `submitted_at`: internal only.")
    with io.open(os.path.join(OUT, "audit.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print("OK  %d reviews / %d respondents / %d OEs / %d card-eligible"
          % (len(reviews), n_resp, len(stats), sum(1 for s in stats if s["card_eligible"])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
