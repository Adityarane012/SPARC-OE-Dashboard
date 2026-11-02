# OE Insights

Peer reviews of 28 Open Electives, from 79 reviews by 48 students, built by
[SPARC](https://tally.so/r/peeeQZ) so juniors have something better than hearsay
to pick from. One page, one file, no tracking.

**Live:** deployed on Vercel.

## What is here

`index.html` is the whole site: a single self-contained file with the data
inlined, no CDN and no network requests at runtime. `cards/` holds the 1080x1350
images for Instagram, rendered from the same data the page uses, so a card and
the page cannot disagree.

Everything in `build/` is the pipeline that produced them.

| step | what it does |
|---|---|
| `clean.py` | raw export to deduped reviews, one row per review, with assertions |
| `moderate.py` | applies the moderation decisions, scans for anything that must not ship |
| `cards.py` | picks the verdict cards by rule rather than by hand |
| `build_page.py` | inlines the data and the branding into `index.html` |
| `make_cards.py` | lays out the share cards for screenshotting |
| `verify.py` | nine checks the build has to pass before it can be published |

Run them in that order. Each one is deterministic, so correcting the data and
re-running re-flows everything downstream instead of needing hand patches.

## What is deliberately not here

The raw export, the per-review file, the moderation sheet and the audit trail
are git-ignored. They carry free text and per-respondent submission ids.

`data/banned_patterns.txt` is git-ignored too. It is the list `verify.py` scans
the built page against, and it names the faculty it is checking for, because
holding the name is the only way to prove the name never ships. A public file
listing staff surnames under the heading "banned" would cause exactly the harm
the moderation pass exists to prevent. Copy `data/banned_patterns.example.txt`
over it to run the pipeline yourself.

Without those files the pipeline will not run, and `verify.py` refuses rather
than scanning against an empty list and reporting a clean page it never checked.

## How the numbers work

Four or more reviews before a course can carry a verdict. Below that the numbers
are shown but no winner is called. Cards state counts rather than percentages,
because "100%" on four people reads like a measured rate. Grade bands are never
averaged: that would invent a number nobody gave us.

Tips are students' own words, edited for clarity. Nothing naming a member of
staff is published, and complaints about a person rather than a course were left
out.
