"""Stamp evaluator marks onto a scanned answer sheet, and append a feedback page.

    python .gemini/marker.py "<series>/<student>"            # mark the copy
    python .gemini/marker.py --render "<series>/<student>"   # dump pages to read
    python .gemini/marker.py --grid "<series>/<student>"     # dump pages with coordinate grid overlay

Reads <student>/spec.json, writes <student>/<student>_evaluated.pdf and the copy's row
in marks.csv. The student's original scan is never touched.

Why render-then-draw rather than PDF annotation objects: some scans are landscape
4000x3000 with /Rotate 90, and annotations are placed in *unrotated* page space, so
text stamped that way comes out sideways. pypdfium2's renderer applies the rotation
itself, so what the eye sees on the rendered page is where the ink lands. The cost is
that marks are burned in - to change one, re-run from the original.

Portals hand back wildly different page geometry: one scan is 3000x4000pt, the next is
A4 at 595x841pt. Every page is therefore rendered to a constant WORK_W-wide image, so
one set of font sizes and one coordinate space work for every copy. Output is saved at
a matching resolution so the physical page size of the original is preserved.

The spec carries what changes per copy (awards, coordinates, comments). Everything
here is the same for every student.
"""
import csv
import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

RED = (200, 0, 0)
INK = (25, 25, 30)
GREY = (70, 70, 75)

# Every page is rendered to this width, whatever the source geometry. All coordinates in
# spec.json and all font sizes below live in this space. pdfium's get_size() already
# reports the *displayed* size, so /Rotate needs no special handling.
WORK_W = 3000

F_MARK = ImageFont.truetype('arialbd.ttf', 78)
F_NOTE = ImageFont.truetype('arial.ttf', 52)
F_STEP = ImageFont.truetype('arialbd.ttf', 62)
F_BOX = ImageFont.truetype('arialbd.ttf', 62)
F_BOXT = ImageFont.truetype('arialbd.ttf', 76)
FB_T = ImageFont.truetype('arialbd.ttf', 96)
FB_S = ImageFont.truetype('arial.ttf', 52)
FB_H = ImageFont.truetype('arialbd.ttf', 66)
FB_B = ImageFont.truetype('arial.ttf', 54)
FB_BB = ImageFont.truetype('arialbd.ttf', 54)
FB_R = ImageFont.truetype('arialbd.ttf', 56)
FB_RC = ImageFont.truetype('arial.ttf', 46)
F_REMARK_H = ImageFont.truetype('arialbd.ttf', 68)
F_REMARK_B = ImageFont.truetype('arial.ttf', 62)

LABEL = {0.5: '½', 1: '1', 1.5: '1½', 2: '2', 2.5: '2½', 3: '3'}


# --- primitives ---------------------------------------------------------------

def tick(d, x, y, s=1.0):
    d.line([(x, y + 34 * s), (x + 30 * s, y + 68 * s), (x + 86 * s, y - 30 * s)],
           fill=RED, width=max(1, int(11 * s)), joint='curve')


def cross(d, x, y, s=1.0):
    d.line([(x, y - 26 * s), (x + 74 * s, y + 62 * s)], fill=RED, width=max(1, int(11 * s)))
    d.line([(x + 74 * s, y - 26 * s), (x, y + 62 * s)], fill=RED, width=max(1, int(11 * s)))


def notes(d, x, y, lines, font=F_NOTE, lh=62):
    for i, ln in enumerate(lines):
        d.text((x, y + i * lh), ln, fill=RED, font=font)


def step_mark(d, x, y, marks):
    """Step mark in the left margin, on the line where the step is earned."""
    tick(d, x, y, 0.55)
    d.text((x + 74, y - 42), LABEL[marks], fill=RED, font=F_STEP)


# --- placement ----------------------------------------------------------------

def ink_mask(im):
    """Where the student's ink is. The outer margins never count: overwriting the
    student's own margin numbering is allowed, and scan edges are noisy."""
    g = np.asarray(im.convert('L'))
    m = g < 145
    m[:, :330] = False
    m[:, 2870:] = False
    return m


def place(mask, x, y, w, h, what):
    """Nearest ink-free spot for a w x h stamp near (x, y).

    A mark must never land on the student's handwriting. Requested spot clear ->
    keep it. Not clear -> search nearby (sideways cheap, vertical dear - a step mark
    that drifts a line down points at the wrong step). Nothing clear -> fail loudly;
    silent overlaps cost several rebuilds before this existed.
    """
    H, W = mask.shape

    def clear(px, py):
        if px < 0 or py < 0 or px + w > W or py + h > H:
            return False
        return not mask[py:py + h, px:px + w].any()

    # Widen dx and dy bounds to make coordinate placement more forgiving
    cands = sorted(((abs(dx) + 1.5 * abs(dy), x + dx, y + dy)
                    for dx in range(-442, 443, 34)
                    for dy in range(-272, 273, 34)), key=lambda c: c[0])
    for cost, px, py in cands:
        if clear(px, py):
            if (px, py) != (x, y):
                 print(f'  nudged {what}: ({x},{y}) -> ({px},{py})')
            mask[py:py + h, px:px + w] = True   # claim it, so stamps never stack
            return px, py
    raise AssertionError(f'{what}: no ink-free spot near ({x},{y}) - move it in spec.json')


# --- checks -------------------------------------------------------------------

def check(spec):
    """Make the independently-written parts of the copy prove each other.

    The margin step marks, the page-1 box and the printed total are all authored by
    hand. A copy that goes out with the margin disagreeing with the total is worse
    than a crash here.
    """
    mcq_got = sum(r['marks'] for r in spec['mcq']['rows'] if r['ok'])
    mcq_max = sum(r['marks'] for r in spec['mcq']['rows'])

    for q in spec['questions']:
        earned = sum(s['marks'] for s in spec['steps'] if s['q'] == q['q'])
        if q.get('attempted', True):
            assert earned == q['got'], \
                f"{q['q']}: step marks total {earned}, but {q['got']} is printed on the copy"
        else:
            assert q['got'] == 0 and earned == 0, f"{q['q']}: not attempted but carries marks"
        assert q['got'] <= q['max'], f"{q['q']}: {q['got']} exceeds its {q['max']} mark allocation"

    total = mcq_got + sum(q['got'] for q in spec['questions'])
    assert total == spec['total'], f"marks sum to {total}, but {spec['total']} is printed"
    assert mcq_got + sum(q['max'] for q in spec['questions']) >= spec['total']
    assert mcq_max + sum(q['max'] for q in spec['questions']) == spec['max'], \
        'question maxima do not add up to the paper total'

    if spec.get('rating'):
        for r in spec['rating']:
            assert 0 <= r['score'] <= 5, f"rating '{r['name']}' is {r['score']} - scale is out of 5"
        got = sum(r['score'] for r in spec['rating'])
        assert got == spec['rating_total'], \
            f"rating scores sum to {got}, but {spec['rating_total']} is printed"

    # The remarks page is the only place a mark is explained, so every question must
    # appear there - a silently unexplained mark is the failure this guards against.
    remarked = [r['q'] for r in spec['remarks']]
    expected = ['MCQ'] + [q['q'] for q in spec['questions']]
    missing = [q for q in expected if q not in remarked]
    assert not missing, f'no remark written for: {", ".join(missing)}'
    unknown = [q for q in remarked if q not in expected]
    assert not unknown, f'remark for a question that does not exist: {unknown}'
    return mcq_got, total


# --- remarks page -------------------------------------------------------------

def remarks_page(spec, size=(WORK_W, 4000)):
    """Question-wise reasoning, one page, ahead of the feedback page.

    Scans are often dense enough that a comment cannot be placed beside the answer it
    refers to without landing on the student's handwriting. So the copy carries only
    marks (ticks, step marks, the per-question mark) and the reasoning lives here,
    where it has room to be read.
    """
    fb = Image.new('RGB', size, (255, 255, 255))
    d = ImageDraw.Draw(fb)
    d.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=RED, width=6)

    got = {q['q']: (q['got'], q['max']) for q in spec['questions']}
    mcq_got = sum(r['marks'] for r in spec['mcq']['rows'] if r['ok'])
    mcq_max = sum(r['marks'] for r in spec['mcq']['rows'])
    got['MCQ'] = (mcq_got, mcq_max)

    y = 220
    d.text((220, y), 'REMARKS', fill=RED, font=FB_T); y += 128
    d.text((220, y), f"{spec['student']}  |  {spec['paper']}", fill=INK, font=FB_S); y += 78
    d.text((220, y), f"Total:  {spec['total']} / {spec['max']}", fill=RED, font=FB_H); y += 112
    d.line([(220, y), (2780, y)], fill=RED, width=5); y += 60

    for r in spec['remarks']:
        g, m = got[r['q']]
        head = f"{r['q']}   {r['title']}" if r.get('title') else r['q']
        d.text((260, y), head, fill=INK, font=FB_R)
        d.text((2420, y), f'{g} / {m}', fill=RED, font=FB_R)
        y += 72
        for ln in r['lines']:
            d.text((320, y), ln, fill=GREY, font=FB_RC)
            y += 56
        y += 26

    assert y < size[1] - 60, 'remarks page overflows - trim lines'
    return fb


# --- feedback page ------------------------------------------------------------

def feedback_page(spec, size=(WORK_W, 4000)):
    fb = Image.new('RGB', size, (255, 255, 255))
    d = ImageDraw.Draw(fb)
    d.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=RED, width=6)

    y = 220
    d.text((220, y), 'FEEDBACK', fill=RED, font=FB_T); y += 128
    d.text((220, y), f"{spec['student']}  |  {spec['paper']}", fill=INK, font=FB_S); y += 78
    d.text((220, y), f"Total:  {spec['total']} / {spec['max']}", fill=RED, font=FB_H); y += 112
    d.line([(220, y), (2780, y)], fill=RED, width=5); y += 60

    if spec.get('rating'):
        d.text((220, y), 'RATING', fill=RED, font=FB_H); y += 96
        for r in spec['rating']:
            d.text((260, y), r['name'], fill=INK, font=FB_R)
            d.text((1560, y), f"{r['score']} / 5", fill=RED, font=FB_R)
            y += 68
            d.text((300, y), r['note'], fill=GREY, font=FB_RC)
            y += 76
        y += 6
        d.text((260, y), 'Overall', fill=INK, font=FB_R)
        d.text((1560, y), f"{spec['rating_total']} / 25", fill=RED, font=FB_R)
        y += 96
        d.line([(220, y), (2780, y)], fill=RED, width=5); y += 56

    for blk in spec['feedback']:
        d.text((220, y), blk['head'], fill=RED, font=FB_H); y += 92
        for ln in blk['lines']:
            bold = ln.startswith('*')
            d.text((260, y), ln.lstrip('*'), fill=INK, font=FB_BB if bold else FB_B)
            y += 66
        y += blk.get('gap', 34)

    d.line([(220, y + 10), (2780, y + 10)], fill=RED, width=3)
    d.text((220, y + 46), spec['footer'], fill=INK, font=FB_B)
    assert y + 120 < size[1], 'feedback page overflows - trim lines or drop a block'
    return fb


# --- inputs / outputs ---------------------------------------------------------

CSV_COLS = ['series', 'student', 'total_marks', 'max_marks',
            'flagged_for_review', 'evaluated_on']


def source_scan(folder):
    src = [p for p in folder.glob('*.pdf') if not p.stem.endswith('_evaluated')]
    assert len(src) == 1, f'expected exactly one source scan in {folder}, found {len(src)}'
    return src[0]


def work_scale(doc):
    """Render scale that puts every page in the WORK_W-wide coordinate space."""
    return WORK_W / doc[0].get_size()[0]


def render_pages(folder, out_dir=None, draw_grid=False):
    """Dump the scan's pages as JPEGs to read, halved from the working space."""
    folder = Path(folder)
    out_dir = Path(out_dir) if out_dir else folder / ('_pages_grid' if draw_grid else '_pages')
    out_dir.mkdir(exist_ok=True)
    doc = pdfium.PdfDocument(str(source_scan(folder)))
    k = work_scale(doc)
    made = []
    for i in range(len(doc)):
        im = doc[i].render(scale=k).to_pil().convert('RGB')
        
        if draw_grid:
            d = ImageDraw.Draw(im)
            grid_font = ImageFont.load_default()
            try:
                grid_font = ImageFont.truetype('arial.ttf', 36)
            except:
                pass
            for x in range(200, WORK_W, 200):
                d.line([(x, 0), (x, im.height)], fill=(220, 220, 220), width=3)
                d.text((x + 5, 10), str(x), fill=(150, 0, 0), font=grid_font)
            for y in range(200, im.height, 200):
                d.line([(0, y), (WORK_W, y)], fill=(220, 220, 220), width=3)
                d.text((10, y + 5), str(y), fill=(150, 0, 0), font=grid_font)

        im.thumbnail((WORK_W // 2, WORK_W), Image.LANCZOS)   # half of working space
        p = out_dir / (f'p{i + 1:02d}_grid.jpg' if draw_grid else f'p{i + 1:02d}.jpg')
        im.save(p, 'JPEG', quality=88)
        made.append(p)
    print(f'{len(made)} pages -> {out_dir}  (x{k:.2f}; page coords = 2x these pixels; grid={draw_grid})')
    return made


def write_marks_row(spec, folder):
    """Upsert this copy's row in marks.csv.

    Keyed on (series, student) and rewritten in place, so re-running marker.py on the
    same copy corrects the row instead of appending a duplicate.
    """
    csv_path = Path(__file__).resolve().parent.parent / 'marks.csv'
    row = {
        'series': folder.resolve().parent.name,
        'student': spec['student'],
        'total_marks': spec['total'],
        'max_marks': spec['max'],
        'flagged_for_review': 'yes' if spec.get('review') else 'no',
        'evaluated_on': datetime.date.today().isoformat(),
    }

    rows = []
    if csv_path.exists():
        with csv_path.open(newline='', encoding='utf-8') as f:
            rows = [r for r in csv.DictReader(f) if any(v for v in r.values())]

    for i, r in enumerate(rows):
        if (r['series'], r['student']) == (row['series'], row['student']):
            rows[i] = row
            break
    else:
        rows.append(row)

    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(rows)
    return row


# --- git auto-push ------------------------------------------------------------

def git_auto_push(folder, student):
    import subprocess
    try:
        # Check if git is initialized
        res = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
        if res.returncode != 0:
            return  # Not a git repo, skip quietly
            
        csv_path = Path(__file__).resolve().parent.parent / 'marks.csv'
        
        # Stage the student folder and marks.csv
        subprocess.run(["git", "add", str(folder), str(csv_path)], check=True, capture_output=True)
        
        # Check if there are changes to commit (git diff-index --cached --quiet HEAD)
        diff_res = subprocess.run(["git", "diff-index", "--cached", "--quiet", "HEAD"])
        if diff_res.returncode != 0:
            commit_msg = f"Auto-eval: Stamped marks for {student}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)
            # Push changes to origin
            subprocess.run(["git", "push"], check=True, capture_output=True)
            print(f"  Auto-pushed evaluation for {student} to GitHub.")
        else:
            print(f"  No changes to push for {student}.")
            
    except Exception as e:
        print(f"  Warning: Git auto-push to GitHub failed: {e}")


# --- build --------------------------------------------------------------------

def build(folder):
    folder = Path(folder)
    spec = json.loads((folder / 'spec.json').read_text(encoding='utf-8'))

    src = source_scan(folder)
    out = folder / f"{spec['student']}_evaluated.pdf"

    mcq_got, total = check(spec)
    mcq_max = sum(r['marks'] for r in spec['mcq']['rows'])
    got = {q['q']: (q['got'], q['max']) for q in spec['questions']}
    got['MCQ'] = (mcq_got, mcq_max)

    has_inline_remarks = all('page' in r for r in spec.get('remarks', []) if r)

    doc = pdfium.PdfDocument(str(src))
    k = work_scale(doc)
    pages = []
    for i in range(len(doc)):
        im = doc[i].render(scale=k).to_pil().convert('RGB')   # rotation applied here
        
        # Auto-pad bottom of page for remarks
        page_remarks = [r for r in spec.get('remarks', []) if r.get('page') == i + 1]
        extra_h = 0
        if has_inline_remarks and page_remarks:
            extra_h = 100
            for r in page_remarks:
                extra_h += 76 + len(r['lines']) * 66 + 40
        
        orig_h = im.height
        if extra_h > 0:
            padded = Image.new('RGB', (im.width, im.height + extra_h), (255, 255, 255))
            padded.paste(im, (0, 0))
            im = padded

        mask = ink_mask(im)
        d = ImageDraw.Draw(im)

        for s in spec['steps']:
            if s['page'] == i + 1:
                # a step mark occupies (x-5, y-50) to (x+125, y+78): tick + label
                x, y = place(mask, s['x'] - 5, s['y'] - 50, 130, 128,
                             f"step {s['q']} p{i + 1}")
                step_mark(d, x + 5, y + 50, s['marks'])
        for m in spec.get('marks', []):
            if m['page'] == i + 1:
                bb = d.textbbox((0, 0), m['text'], font=F_MARK)
                x, y = place(mask, m['x'], m['y'], bb[2], bb[3],
                             f"mark '{m['text']}' p{i + 1}")
                d.text((x, y), m['text'], fill=RED, font=F_MARK)
        for u in spec.get('underlines', []):
            if u['page'] == i + 1:
                d.line([(u['x1'], u['y']), (u['x2'], u['y'])], fill=RED, width=7)
        for c in spec.get('crosses', []):
            if c['page'] == i + 1:
                cross(d, c['x'], c['y'])
        for n in spec.get('notes', []):
            if n['page'] == i + 1:
                notes(d, n['x'], n['y'], n['lines'],
                      font=ImageFont.truetype('arial.ttf', n.get('size', 52)),
                      lh=n.get('lh', 62))

        # Add inline remarks if enabled
        if has_inline_remarks and page_remarks:
            ry = orig_h + 50
            for r in page_remarks:
                rx = r.get('x', 100)
                head = f"{r['q']}   {r['title']}" if r.get('title') else r['q']
                g, m = got.get(r['q'], (None, None))
                if g is not None:
                    head = f"{head}   ({g} / {m})"
                d.text((rx, ry), head, fill=RED, font=F_REMARK_H)
                ry += 76
                for ln in r['lines']:
                    d.text((rx + 20, ry), ln, fill=RED, font=F_REMARK_B)
                    ry += 66
                ry += 40

        if i == 0:
            mc = spec['mcq']
            for r in mc['rows']:
                (tick if r['ok'] else cross)(d, mc['x_tick'], r['y'])
                d.text((mc['x_mark'], r['y'] - 40), str(r['marks'] if r['ok'] else 0),
                       fill=RED, font=F_MARK)
            b = spec['box']
            d.rectangle([b['x1'], b['y1'], b['x2'], b['y2']], outline=RED, width=7)
            d.text((b['x1'] + 60, b['y1'] + 50), f"TOTAL:  {spec['total']} / {spec['max']}",
                   fill=RED, font=F_BOXT)
            d.line([(b['x1'] + 60, b['y1'] + 170), (b['x2'] - 60, b['y1'] + 170)],
                   fill=RED, width=4)
            yy = b['y1'] + 220
            d.text((b['x1'] + 60, yy), f'MCQ (Part I)     {mcq_got} / '
                   f"{sum(r['marks'] for r in mc['rows'])}", fill=RED, font=F_BOX)
            yy += 88
            for q in spec['questions']:
                tail = '   not attempted' if not q.get('attempted', True) else ''
                d.text((b['x1'] + 60, yy), f"{q['q']}   {q['got']} / {q['max']}{tail}",
                       fill=RED, font=F_BOX)
                yy += 88
            d.line([(b['x1'] + 60, b['y2'] - 150), (b['x2'] - 60, b['y2'] - 150)],
                   fill=RED, width=4)
            d.text((b['x1'] + 60, b['y2'] - 120), f"Counted: {spec['counted']}",
                   fill=RED, font=F_BOX)

        pages.append(im)

    if not has_inline_remarks:
        pages.append(remarks_page(spec, pages[0].size))
    pages.append(feedback_page(spec, pages[0].size))
    # resolution keeps the output's physical page size equal to the original's: the render
    # is k x bigger than the page in points, so the DPI must be k x 72.
    pages[0].save(out, 'PDF', resolution=72 * k, save_all=True, append_images=pages[1:])
    row = write_marks_row(spec, folder)
    print(f"{spec['student']}: {spec['total']}/{spec['max']} -> {out.name} "
          f'({len(pages)} pages, {out.stat().st_size / 1e6:.2f} MB)')
    print(f"marks.csv: {row['series']} | {row['student']} | {row['total_marks']}/"
          f"{row['max_marks']} | review={row['flagged_for_review']} | {row['evaluated_on']}")
    
    # Auto-push the changes to GitHub
    git_auto_push(folder, spec['student'])

    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == '--render':
        render_pages(args[1], draw_grid=False)
    elif len(args) == 2 and args[0] == '--grid':
        render_pages(args[1], draw_grid=True)
    elif len(args) == 1 and not args[0].startswith('-'):
        build(args[0])
    else:
        sys.exit(__doc__)
