# Social handoff

Everything needed to post OE Insights. Hand this file to whoever runs the account
and whoever cuts the reel.

- **Dashboard:** https://sparc-oe-dashboard.vercel.app
- **Join form:** https://tally.so/r/peeeQZ
- **Cards:** `cards/`, eight PNGs at 1080x1350 (Instagram portrait)

Every card already prints both links, so a card works on its own even if nobody
reads the caption.

---

## The carousel

Post all eight as one carousel, in filename order. The opener sets up the
numbers; each card after it answers one question.

| # | File | What it says |
|---|---|---|
| 1 | `00-opener.png` | 104 reviews, 30 courses, 63 students |
| 2 | `01-oe1-most-liked.png` | OE-I, Basic Decision Making, 5 of 6 would retake |
| 3 | `02-oe1-best-marks.png` | OE-I, 5G for Everyone, 3 of 4 expect 45+ |
| 4 | `03-oe1-worth-a-look.png` | OE-I, Intro to VR and AR, 3 of 4 would retake |
| 5 | `04-oe1-mixed-reviews.png` | OE-I, Renewable Energy Sources, 1 of 7 would retake |
| 6 | `05-oe2-most-liked.png` | OE-II, Financial Derivatives, 7 of 7 would retake |
| 7 | `06-oe2-best-marks.png` | OE-II, Leading Through Life Skills, 4 of 5 expect 45+ |
| 8 | `07-oe2-mixed-reviews.png` | OE-II, Elements of Project Management, 2 of 9 |

Card 5 is the one people will argue with. That is fine and it is the point: it is
seven real reviews, not an opinion. Do not drop it to keep the set positive.

**Caption draft**

> We asked 63 students what their Open Electives were actually like. 104 reviews,
> 30 courses, both baskets.
>
> No course gets called a winner on fewer than four reviews. Every number shows
> how many people it came from.
>
> Full table, all 30 courses: sparc-oe-dashboard.vercel.app

---

## The reel

**Concept:** a walkthrough of the live dashboard on a phone. No voiceover needed.
The thing worth filming is the bars drawing themselves as you scroll.

**Length:** 20 to 25 seconds.

### Shot list

| Time | Shot | On-screen text |
|---|---|---|
| 0:00-0:02 | Hero, held still. "Which OE should you take?" | Picking your OE blind? |
| 0:02-0:07 | Scroll into the OE-I picks. "5 of 6" lands big. | 63 students told us |
| 0:07-0:14 | Scroll through the course table. Bars draw as rows arrive. **Slow here.** | none, let it play |
| 0:14-0:18 | Tap "Show the other 9 courses". It expands. | Every course, not just the popular ones |
| 0:18-0:22 | Scroll to OE-II. "7 of 7, Financial Derivatives". | both baskets |
| 0:22-0:25 | End on the footer with the URL. Freeze. | sparc-oe-dashboard.vercel.app |

### Capture notes

These matter more than the edit:

1. **Hard-refresh the page before recording.** The bars animate once per page
   load. If the page has already been scrolled, they are sitting at full width
   and the best shot in the reel is gone.
2. **Check Reduce Motion is OFF** on the phone (iOS: Settings > Accessibility >
   Motion). The page honours it, so with it on the bars appear instantly and
   there is nothing to film.
3. **Scroll slowly through the table.** Each bar takes about three quarters of a
   second to fill and they are staggered down the rows. Scrolling fast skips the
   whole effect.
4. **One finger, steady, one take.** Trim it afterwards rather than stitching
   several takes.
5. **Do not tap Join SPARC during the walkthrough.** It leaves the site for the
   recruitment form and kills the flow. Save the link for the caption.
6. Record portrait, 1080x1920, 60fps if the phone offers it.

### Audio and edit

Trending audio with a clear beat. Cut on the beat at 0:07 (into the table) and
0:14 (the expand). Those are the two moments with visible change.

**Caption draft**

> Every Open Elective, with the numbers behind it. 104 reviews from 63 students.
>
> sparc-oe-dashboard.vercel.app

---

## Rules

Non-negotiable, and the reason the dashboard took as long as it did:

- **No professor is named anywhere.** Not on the page, not in a caption, not in a
  comment reply. Reviews that named staff were edited or dropped before publishing.
- **Do not film anything except the live site.** The repo and the working files
  contain raw responses and respondent IDs.
- **Do not round the numbers up in a caption.** "7 of 7" is seven people. Writing
  "100% of students" is the one thing that would make the whole project dishonest.
- If someone comments asking which professor teaches what, point them at the
  official OE list. Do not answer it from the data.
