# CA Inter — Copy Evaluation

First-pass evaluator, multiple subjects. Copies arrive unmarked. Mark each handwritten
sheet against the ICAI model answer, under that subject's rules.

**`/mark` marks one copy end to end** — the procedure is in `.gemini/skills/mark/`.
**`/new-subject` onboards a subject from its SOP** — `.gemini/skills/new-subject/`.
This file is the rules, and outranks both.

## Files

Multiple series run at once. Each holds its own paper and key.

```
CC_Law/
  GEMINI.md   marks.csv   .gemini/marker.py   .gemini/skills/mark/
  <series>/
    *_Question.pdf   Model_Answer*.pdf
    scheme.md                    ← built ONCE per series
    <student>/
      <scan>.pdf                 ← original, never touched
      spec.json                  ← this copy's awards + coordinates + remarks
      evaluation.md
      <student>_evaluated.pdf    ← generated
```

Portal filenames are not tidy — identify by pattern, not exact name:

| What | How to find it |
|---|---|
| Series | any folder at repo root |
| Question paper | PDF at series root with `Question` in the name |
| Model answer | PDF at series root with `Model_Answer` in the name |
| Student | each subfolder of a series — the folder name is the student |
| Answer sheet | the PDF in the student's folder not ending `_evaluated` |

Never rename the student's files. **Always mark against the model answer in that
student's own series folder** — never carry a paper or answer key across series.

Question paper or model answer missing → stop and say so. Never mark from memory of the law.

## The marking scheme — build once per series

`<series>/scheme.md` is the model answer's step marking written out: every question, every
step, what it is worth, the MCQ key, caps, Alternate Answers.

**First copy in a series** → build it, then mark against it.
**Every later copy** → read it. Never re-derive from the model answer.

Build it by reading, never by regex — step marks wrap across lines (`(1\n Mark)`) and caps
like `(1 Mark for each point max 5 marks)` match no `(n Marks)` pattern. Check when built:
every question's steps sum to its marks in the question paper. If a copy shows the scheme
is wrong, fix the scheme and say which earlier copies are hit.

## Reading the PDFs

`pdftoppm` is **not installed** — the Read tool cannot open PDFs.

- **Question paper, model answer** — `pdftotext -layout <file> <out>.txt`
- **Answer sheets** — image scans, no text layer:
  `python .gemini/marker.py --render "<series>/<student>"` → `_pages/pNN.jpg` (scratch)

## Completeness check — before marking anything

Read every page first, then list every question the paper expects against the sheet.

- Answers appear **out of order** — students jump around. Never conclude a question is
  unattempted until all pages are read.
- **An answer that ends mid-sentence on the last page means pages are missing.** Do not
  mark the copy. Flag `REVIEW` and report it.
- A compulsory sub-question missing while later ones are answered → suspect missing
  pages. Flag, do not award 0.
- Award 0 for "not attempted" **only** when the sheet is confirmed complete.

A scanning gap must never cost a student marks.

## Authority order

1. Question paper — its marks distribution is absolute
2. Model answer + its step marking — decides *what* an answer must contain
3. The series' **subject rules file** — *how* to award for that subject
4. Shared rules in this file
5. The subject's SOP txt, named in its rules file — how to judge only

## Subjects

Each subject's rules file holds how to award: MCQ policy, descriptive awarding,
optionals, deduct/warn policy, syllabus scope. **Never mark a copy without reading the
series' rules file.**

| Series name contains | Rules file |
|---|---|
| `Law` | `.gemini/rules/law.md` |
| `Account` | `.gemini/rules/advanced_accounts.md` |

A series matching no row, or a rules file that does not exist yet → **stop and ask**;
never guess a subject's rules. A new subject's rules file is built from its SOP file the
first time — never from memory of ICAI practice — and anything in an SOP that contradicts
this file is flagged to the evaluator, not silently obeyed.

## Output

- `evaluation.md` — marks per question with the reasoning, which optionals were counted,
  warnings tied to their question, anything flagged `REVIEW`, feedback, rating
- `<student>_evaluated.pdf` — annotated copy for the portal. Never overwrite the original.
- `marks.csv` at root — **written by `marker.py`**, keyed on (series, student). Never hand-
  edit it; fix `spec.json` and re-run.

The evaluator enters the marks in the portal themselves — never assume that is done.

## Annotating the copy

Red ink, **simple plain language** — short lines, no analysis prose. **The copy carries
marks; prose goes on the remarks page** — scans are usually too dense to put a comment
beside its answer without covering the handwriting. On the sheets:

- Tick or cross beside every MCQ, with its marks
- **A step mark in the margin on the line where each step is earned** — `✓1`, `✓½`, `✓2`.
  Left margin if there is one, right if not — spiral notebooks often have no left margin.
  Overwriting the student's own margin numbers is fine.
- `Q1(b) = 3 / 5` beside where each descriptive answer ends
- Spot marks only: underline a wrong section, cross a wrong conclusion. No prose.
- Totals box on page 1 in free space — every question including the unattempted ones, and
  which optionals were counted

Then two generated pages, same size as the sheets:

- **REMARKS** — every question with its mark and the reason: what was earned, what was not
  and what was needed, any warning. The only place a mark is explained, so the engine
  refuses to build if a question has no remark.
- **FEEDBACK** — total, rating **out of 5** per criterion with a one-line comment (no
  bars or graphics), what they did well, habits to fix, where the marks went, SME line

`marker.py` is the engine — never edit it per student. `spec.json` holds this copy's awards,
coordinates and remarks; copy an existing one for shape, but **redo every coordinate from
the pages** — a step mark on the wrong line is worse than none. The engine refuses a copy
that is not self-consistent, and **nudges any step mark or question mark that would land on
the student's ink** (outer margins don't count — overwriting margin numbering is fine). No
clear spot near the target → it fails; move that stamp in `spec.json`.

**Render the finished PDF and read it back.** Placement is guesswork until seen.

Page geometry varies wildly by portal — one scan is `4000x3000` with `/Rotate 90`, the next
is A4 `595x841`. `marker.py` normalises every page to a 3000px-wide space, so one set of
coordinates and fonts works for all, and keeps the original's physical page size. Marks are
burned in — to change one, fix `spec.json` and re-run.

## Self-check before submitting

- Every question evaluated and remarked, none skipped
- Consistent with `scheme.md` and with earlier copies in the batch

## Never

- Mark a copy whose pages may be missing, or award for content not on the sheet
- Invent or "correct" a section number
- Adjust marks for leniency or harshness
- Guess where flagging is possible
