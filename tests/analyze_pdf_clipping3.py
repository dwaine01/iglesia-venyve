"""Analyze PDF for glyph clipping in the certificate name+statement zones."""
import numpy as np
import pypdfium2 as pdfium
from pathlib import Path

OUT = Path("/app/test_reports/pdf_bug_verification3")
SCALE = 4.0
PAGE_H_PT = 612.0  # certificate height (portrait pt; PDF is landscape 11x8.5, so height=8.5in=612pt)
PAGE_W_PT = 792.0


def render(pdf_path, page_idx=0):
    d = pdfium.PdfDocument(str(pdf_path))
    pg = d.get_page(page_idx)
    img = pg.render(scale=SCALE).to_pil().convert("L")
    pg.close(); d.close()
    return np.array(img)


def y_pt_to_px(y_in):
    return int(y_in * 72 * SCALE)  # inches * 72pt/in * scale = pixels


def analyze_box(arr, y0_in, height_in, label, margin_in=0.08):
    """Report on the darkest rows within [y0-margin, y0+height+margin]."""
    y_top = y_pt_to_px(y0_in)
    y_bot = y_pt_to_px(y0_in + height_in)
    y_scan_top = max(0, y_pt_to_px(y0_in - margin_in))
    y_scan_bot = min(arr.shape[0], y_pt_to_px(y0_in + height_in + margin_in))
    # threshold: text pixels darker than 128
    band = arr[y_scan_top:y_scan_bot, :]
    row_darkness = (band < 128).sum(axis=1)  # count of dark pixels per row
    dark_rows = np.where(row_darkness > 30)[0]  # only rows with meaningful text
    if not len(dark_rows):
        print(f"[{label}] NO text pixels found in scan band")
        return
    first_dark = dark_rows[0] + y_scan_top
    last_dark = dark_rows[-1] + y_scan_top
    top_margin_px = first_dark - y_top
    bot_margin_px = y_bot - last_dark
    top_margin_in = top_margin_px / (72 * SCALE)
    bot_margin_in = bot_margin_px / (72 * SCALE)
    print(f"[{label}] box y_px=[{y_top},{y_bot}] text_px=[{first_dark},{last_dark}] top_margin={top_margin_px}px ({top_margin_in:.3f}in) bot_margin={bot_margin_px}px ({bot_margin_in:.3f}in)")
    # Clipping check: if text pixel touches the CSS box edge (within 1px) it's likely clipped
    if first_dark <= y_top + 1:
        print(f"[{label}] WARNING: text touches TOP of box (possible clipping)")
    if last_dark >= y_bot - 1:
        print(f"[{label}] WARNING: text touches BOTTOM of box (possible clipping)")


def save_crop(arr, y0_in, height_in, out_name, margin_in=0.15):
    from PIL import Image
    y0 = max(0, y_pt_to_px(y0_in - margin_in))
    y1 = min(arr.shape[0], y_pt_to_px(y0_in + height_in + margin_in))
    Image.fromarray(arr[y0:y1, :]).save(OUT / out_name)


# Long name case (wrapsName=True): name top=3.34in height=1.06in
print("=== cert_long.pdf ===")
long_arr = render(OUT / "cert_long.pdf")
print("image shape:", long_arr.shape)
analyze_box(long_arr, 3.34, 1.06, "name-long")
analyze_box(long_arr, 4.48, 0.85, "stmt-long")
save_crop(long_arr, 3.34, 1.06, "cert_long_name_crop.png")
save_crop(long_arr, 4.48, 0.85, "cert_long_stmt_crop.png")

# Short name case: top=3.325in height=.81in
print("\n=== cert_short.pdf ===")
short_arr = render(OUT / "cert_short.pdf")
analyze_box(short_arr, 3.30, 1.00, "name-short")
analyze_box(short_arr, 4.48, 0.85, "stmt-short")
save_crop(short_arr, 3.30, 1.00, "cert_short_name_crop.png")
save_crop(short_arr, 4.48, 0.85, "cert_short_stmt_crop.png")
