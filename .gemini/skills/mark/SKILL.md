---
name: mark
description: Mark one CA Inter answer copy of any subject (Corporate and Other Laws, Advanced Accounts, ...) end to end — render the scan, read every page, award against the subject's rules and the series marking scheme, annotate the PDF, write evaluation.md and the marks.csv row. Use when the user types /mark, names a student to mark or evaluate, or asks for the next copy to be checked.
---

# Mark one copy

`GEMINI.md` holds the marking rules and **wins over anything here**. This file is only the
order of operations. One copy per invocation — never batch.

## 0. Pick the copy

`/mark <student>` → that student. `/mark` alone → the first student subfolder in any series
with no `<student>_evaluated.pdf`. Say which copy you picked, and stop if there are none.

## 1. Subject rules, then the series marking scheme

Match the series folder name against the **Subjects table in `GEMINI.md`** and read that
subject's rules file before awarding anything. No matching row, or the rules file missing
→ stop and ask; never guess a subject's rules.

`<series>/scheme.md` present → **read it**. Never re-derive the steps from the model answer;
that is what makes copy #1 and copy #40 the same standard.

Missing (new series) → build it first: `pdftotext -layout` the question paper and the model
answer, then write out every question, every step, what each is worth, the MCQ key, caps and
Alternate Answers. Its header names the subject and the rules file it was built under. Read the model answer to do this — **never regex**, step marks wrap
across lines and caps like `(1 Mark for each point max 5 marks)` match no pattern. Check
before continuing: each question's steps sum to its marks in the question paper.

## 2. Render and read every page

```
python .gemini/marker.py --render "<series>/<student>"
```

Writes `<student>/_pages/pNN.jpg` (scratch — delete when done). **Read all of them before
judging anything.** Students jump around; an answer you think is missing is often three
pages later.

## 3. Completeness check — before marking anything

- Answer ending **mid-sentence on the last page** → pages are missing
- A compulsory sub-question missing while later ones are answered → suspect missing pages

Either → flag `REVIEW`, stop, tell the user, ask them to check the portal's page count.
Never award 0 for "not attempted" until the sheet is confirmed complete. A scanning gap
must never cost a student marks.

## 4. Award

Step by step against `scheme.md`. Award only what is on the sheet. Wrong section but sound
reasoning → award the step, warn on the citation. Never deduct.

## 5. Find coordinates

From the rendered pages. Crop the full-resolution render to settle a doubtful section
number or option letter — do not squint at the downscaled page.

## 6. Write `spec.json`

Copy an existing one for shape. **Every coordinate in it is that student's — redo them all
from this student's pages.** A step mark on the wrong line is worse than no step mark.

The copy carries **marks only** — step marks, the per-question mark, and spot marks
(underline a wrong section, cross a wrong conclusion). All reasoning goes in `remarks`,
which becomes its own page. Do not fight a dense page to squeeze a comment in.

`remarks` needs an entry per question **and** for `MCQ` — the engine refuses to build
otherwise, because an unexplained mark is the thing this guards against. Each says what was
earned, what was not and what was needed.

Set `"review": true` if anything is flagged — it drives the `marks.csv` column.

## 7. Build

```
python .gemini/marker.py "<series>/<student>"
```

Refuses to stamp a copy whose marks are not self-consistent. The engine nudges any step
mark or question mark that would land on the student's ink to the nearest clear spot and
prints each nudge — read them; a big nudge means your coordinate was off. If it fails with
"no ink-free spot", pick a different place in `spec.json` rather than forcing it.
`PermissionError` → the PDF is open in a viewer.

## 8. Verify — render the output and read it back

**Not optional.** The ink guard keeps stamps off handwriting, but only your eye catches a
mark that sits beside the *wrong* answer, or a nudge that moved it a line away from its
step. Check every nudged stamp especially. Fix, rebuild, look again.

## 9. Write `evaluation.md`

Per-question marks with the reasoning, which optionals were counted, warnings tied to their
question, anything flagged, feedback and rating. `marker.py` already wrote the `marks.csv`
row — do not write it by hand.

## 10. Report

Lead with the total. Per-question table. Anything flagged `REVIEW`, and what you need from
the user to clear it. Name any call you were unsure of — the user calibrates against their
own judgement, and a borderline award they never hear about is a rule that never gets fixed.
