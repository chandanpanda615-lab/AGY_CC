---
name: new-subject
description: Onboard a new CA Inter subject from its evaluator SOP — read the SOP, write .gemini/rules/<subject>.md, register the subject in GEMINI.md's Subjects table so /mark can route its copies. Use when the user drops a new subject's SOP, types /new-subject, or names a subject (Audit, Taxation, ...) whose rules file does not exist yet.
---

# Onboard one subject

One subject per invocation. `GEMINI.md` outranks this file. The SOP is the source —
**never write rules from memory of ICAI practice**; no SOP, no rules file.

## 1. Find the SOP

`/new-subject <file>` → that file. Otherwise: the newest `.md`/`.txt` under `.gemini/`
that is not already referenced by a rules file, or ask the user where they put it.
Announce which file you picked. No SOP found → stop and ask for it.

## 2. Read the whole SOP

All of it, before writing anything. Note especially: what earns marks, what it says
about deductions, formats it names, anything it escalates ("consult the head examiner").

## 3. Write `.gemini/rules/<subject>.md`

Model it on `.gemini/rules/law.md` — same section order so every subject reads the same
way: header naming the SOP file → Syllabus/scope → MCQs → Descriptive (or numerical)
answers → Optional questions → Deduct-vs-warn policy → REVIEW triggers.

- Every rule cites its SOP section, so a disputed award can be traced to the source.
- Where the SOP is silent (often MCQs and optionals), carry the evaluator's established
  policy from an existing rules file and mark the section **"carried — confirm"** so the
  user knows it was not in their SOP.

## 4. Contradictions with the shared rules

An SOP that says "deduct" where `GEMINI.md` says never deduct, or the reverse → do not
silently obey either. Apply the evaluator's established policy (the Law precedent:
"penalise X" becomes "the step is not earned + a warning naming X"), and **flag the
contradiction in your report** so the user can overrule it before the first copy.

## 5. Register the subject

Add its row to the **Subjects table in `GEMINI.md`**: a keyword that will appear in the
series folder names → the rules file. The keyword must not collide with an existing row
(`Law`, `Account`, ...). Tell the user to keep that keyword in every series folder name.

## 6. Report

The rules in brief, every "carried — confirm" section, every contradiction and how it
was resolved, and the next step: drop the series folder (question paper + model answer
+ student folders) and `/mark <student>`.
