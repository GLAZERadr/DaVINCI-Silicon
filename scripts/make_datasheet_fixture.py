"""Draw the datasheet fixture used to test image/PDF spec input.

Writes spec/fixtures/sf16_datasheet.png (page 1) and sf16_datasheet.pdf
(page 1 + timing diagram). The wording deliberately differs from
spec/requirements.json so extraction has to read, not copy. This is a
fixture written for DaVINCI, not a vendor document.

usage: python scripts/make_datasheet_fixture.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "spec" / "fixtures"
W, H = 1700, 2200
INK, MUTED, RULE = (15, 23, 32), (100, 116, 139), (203, 213, 225)


def font(size, bold=False):
    for name in (["Arial Bold.ttf", "DejaVuSans-Bold.ttf"] if bold else ["Arial.ttf", "DejaVuSans.ttf"]):
        for d in ("/System/Library/Fonts/Supplemental", "/usr/share/fonts/truetype/dejavu"):
            try:
                return ImageFont.truetype(f"{d}/{name}", size)
            except OSError:
                pass
    return ImageFont.load_default(size)


def header(d, title, page):
    d.text((100, 80), "SF-16 Synchronous FIFO", font=font(54, True), fill=INK)
    d.text((100, 150), title, font=font(30), fill=MUTED)
    d.text((W - 100, 90), f"page {page}/2", font=font(26), fill=MUTED, anchor="ra")
    d.line((100, 205, W - 100, 205), fill=INK, width=3)
    d.text((100, H - 90), "Datasheet fixture written for DaVINCI testing. Not a vendor document.",
           font=font(22), fill=MUTED)


def table(d, x, y, cols, rows, widths, size=26):
    f, fb = font(size), font(size, True)
    row_h = size + 22
    for i, c in enumerate(cols):
        d.text((x + sum(widths[:i]) + 12, y + 10), c, font=fb, fill=INK)
    y += row_h
    d.line((x, y, x + sum(widths), y), fill=INK, width=2)
    for r in rows:
        lines = [str(cell).split("\n") for cell in r]
        h = row_h + (max(len(l) for l in lines) - 1) * (size + 8)
        for i, cell in enumerate(lines):
            for k, line in enumerate(cell):
                d.text((x + sum(widths[:i]) + 12, y + 10 + k * (size + 8)), line, font=f, fill=INK)
        y += h
        d.line((x, y, x + sum(widths), y), fill=RULE, width=1)
    return y


def page1():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    header(d, "Section 3 · Pins and functional operation", 1)
    d.text((100, 250), "3.1 Configuration", font=font(34, True), fill=INK)
    d.text((100, 305), "Data width 8 bits · 16 entries · almost-full level 14 · occupancy counter 5 bits",
           font=font(28), fill=INK)
    d.text((100, 380), "3.2 Pins", font=font(34, True), fill=INK)
    y = table(d, 100, 430, ["Pin", "Dir", "Description"], [
        ["clk", "in", "Clock. All state changes on the rising edge."],
        ["rst", "in", "Synchronous reset, active high."],
        ["wr_en", "in", "Push request."],
        ["din[7:0]", "in", "Push data."],
        ["rd_en", "in", "Pop request."],
        ["dout[7:0]", "out", "Pop data, registered (valid after the edge)."],
        ["full / empty", "out", "Occupancy is 16 / occupancy is 0."],
        ["almost_full", "out", "Occupancy at or above the almost-full level."],
        ["overflow", "out", "Push refused, high for one clock."],
        ["underflow", "out", "Pop refused, high for one clock."],
        ["count[4:0]", "out", "Words currently held."],
    ], [300, 110, 1090])
    d.text((100, y + 50), "3.3 Operation at each rising clock edge", font=font(34, True), fill=INK)
    table(d, 100, y + 100, ["Condition", "Result"], [
        ["rst = 1", "Storage emptied. count 0, empty 1, dout 00h,\noverflow 0, underflow 0."],
        ["push, not full", "din stored; count + 1."],
        ["push while full, no pop", "Push dropped. overflow pulses for one clock."],
        ["pop, not empty", "Oldest word appears on dout; count - 1."],
        ["pop while empty", "Ignored; dout keeps its old value.\nunderflow pulses for one clock."],
        ["push + pop while full", "Oldest word out, new word in; count stays 16.\nNo overflow."],
        ["push + pop while empty", "Word stored, pop ignored, underflow pulses."],
    ], [520, 980])
    return img


def page2():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    header(d, "Section 4 · Timing", 2)
    d.text((100, 250), "Figure 4.1  Push and pop in the same cycle while full", font=font(34, True), fill=INK)
    x0, step, n = 380, 150, 8
    names = ["clk", "wr_en", "rd_en", "din", "dout", "count", "full", "overflow"]
    # Inputs are sampled at the edge starting each slot; registered outputs
    # show their new value in the following slot.
    bus = {"din": ["--", "A0", "A1", "A2", "A3", "--", "--", "--"],
           "dout": ["?", "?", "30", "31", "32", "33", "34", "34"],
           "count": ["16", "16", "16", "16", "16", "16", "15", "15"]}
    lvl = {"wr_en": [0, 1, 1, 1, 1, 0, 0, 0], "rd_en": [0, 1, 1, 1, 1, 1, 0, 0],
           "full": [1, 1, 1, 1, 1, 1, 0, 0], "overflow": [0, 0, 0, 0, 0, 0, 0, 0]}
    y = 360
    f = font(28)
    for name in names:
        d.text((100, y + 12), name, font=font(28, True), fill=INK)
        hi, lo = y, y + 50
        if name == "clk":
            for i in range(n):
                x = x0 + i * step
                d.line([(x, lo), (x, hi), (x + step / 2, hi), (x + step / 2, lo), (x + step, lo)], fill=INK, width=3)
        elif name in bus:
            for i, v in enumerate(bus[name]):
                x = x0 + i * step
                d.line([(x + 10, hi), (x + step - 10, hi)], fill=INK, width=3)
                d.line([(x + 10, lo), (x + step - 10, lo)], fill=INK, width=3)
                d.line([(x, (hi + lo) / 2), (x + 10, hi)], fill=INK, width=3)
                d.line([(x, (hi + lo) / 2), (x + 10, lo)], fill=INK, width=3)
                d.text((x + step / 2, (hi + lo) / 2), v, font=f, fill=INK, anchor="mm")
        else:
            pts, prev = [], None
            for i, v in enumerate(lvl[name]):
                x, yy = x0 + i * step, (hi if v else lo)
                if prev is not None and prev != yy:
                    pts.append((x, prev))
                pts.append((x, yy))
                prev = yy
            pts.append((x0 + n * step, prev))
            d.line(pts, fill=INK, width=3)
        y += 110
    for i in range(n + 1):
        d.line((x0 + i * step, 340, x0 + i * step, y), fill=RULE, width=1)
    notes = [
        "Cycle 1-4: the FIFO holds 16 words; push and pop are both high.",
        "Each edge returns the oldest word on dout and stores din; count stays 16, full stays 1,",
        "overflow stays 0 because a pop frees the slot in the same cycle.",
        "Cycle 5: pop only, count falls to 15 and full drops.",
        "",
        "Ordering: words leave in the order they were pushed, including when the internal",
        "address wraps from entry 15 back to entry 0.",
        "almost_full is high whenever count is 14 or more.",
    ]
    for k, line in enumerate(notes):
        d.text((100, y + 60 + k * 44), line, font=font(28), fill=INK)
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    p1, p2 = page1(), page2()
    p1.save(OUT / "sf16_datasheet.png", optimize=True)
    p1.save(OUT / "sf16_datasheet.pdf", save_all=True, append_images=[p2], resolution=200)
    print("wrote", OUT / "sf16_datasheet.png", OUT / "sf16_datasheet.pdf")
