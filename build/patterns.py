# -*- coding: utf-8 -*-
"""
Loader for the banned-pattern list.

The list itself lives in data/banned_patterns.txt, which is git-ignored, because
it has to name the people it is checking for: the only way to prove a
professor's name never reaches the page is to hold the name. A public repo
carrying faculty surnames under the heading "banned" would do exactly the harm
the moderation pass exists to prevent.

Both the moderation step and the ship gate read it through here, so there is one
list and no chance of the two drifting apart. A missing file is a hard error
rather than an empty list: a scanner that silently checks nothing would report
a clean page and mean nothing by it.
"""

import io
import os
import sys

FILENAME = "banned_patterns.txt"
EXAMPLE = "banned_patterns.example.txt"


def load_banned(data_dir):
    path = os.path.join(data_dir, FILENAME)
    if not os.path.exists(path):
        sys.exit(
            "FAIL %s is missing.\n"
            "      It is git-ignored because it names real people. Copy\n"
            "      data/%s to data/%s and fill in the\n"
            "      real names and words, then re-run. Refusing to scan with an\n"
            "      empty list: it would pass and prove nothing."
            % (path, EXAMPLE, FILENAME)
        )

    patterns = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    if not patterns:
        sys.exit("FAIL %s has no patterns in it - every line is blank or a comment."
                 % path)
    return patterns
