from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).parent
OUT = ROOT / "grid_system"
OUT.mkdir(exist_ok=True)
LOGO = Image.open("/app/frontend/public/assets/membership/church-logo.png").convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())
PHOTO = Image.open(ROOT / "member-photo.jpg").convert("RGB")
QR = Image.open(ROOT / "verification-qr.png").convert("RGB")

NAVY = "#0A1D3B"
GREEN = "#58C92F"
TEAL = "#07869D"
INK = "#111827"
MUTED = "#5C6878"
PAPER = "#FBFCFC"
WHITE = "#FFFFFF"
RULE = "#D6DFE5"
GRID_CYAN = "#00BCD4"
GRID_BLUE = "#2563EB"
GRID_MAGENTA = (232, 67, 147, 34)
GRID_AMBER = (245, 158, 11, 40)
GRID_ROW = (100, 116, 139, 52)

CR_SCALE = 10
CR_W = 856
CR_H = 540
CR_SAFE = 30
CR_COL = 52.58
CR_GUTTER = 15
CR_ROW = 20

LT_SCALE = 4
LT_W = 1118
LT_H = 864
LT_FRAME = 25.4
LT_SAFE = 50.8
LT_COL = 70
LT_GUTTER = 16
LT_ROW = 25.4


def sans(size, weight="Regular"):
    item = ImageFont.truetype(str(ROOT / "fonts" / "PlusJakartaSans.ttf"), size)
    item.set_variation_by_name(weight)
    return item


def serif(size, weight="Regular"):
    item = ImageFont.truetype(str(ROOT / "fonts" / "CormorantGaramond.ttf"), size)
    item.set_variation_by_name(weight)
    return item


def tracking_text(draw, xy, text, item_font, fill, tracking=1):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=item_font, fill=fill)
        x += draw.textlength(char, font=item_font) + tracking


def wrap_lines(draw, text, item_font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=item_font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def contain(image, size):
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return layer


def cover(image, size, focus_y=.25):
    ratio = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, min(resized.height - size[1], round((resized.height - size[1]) * focus_y)))
    return resized.crop((left, top, left + size[0], top + size[1]))


def cr_col_start(number):
    return CR_SAFE + (number - 1) * (CR_COL + CR_GUTTER)


def cr_col_end(number):
    return cr_col_start(number) + CR_COL


def cr_row_start(number):
    return CR_SAFE + (number - 1) * CR_ROW


def cr_row_end(number):
    return CR_SAFE + number * CR_ROW


def lt_col_start(number):
    return LT_SAFE + (number - 1) * (LT_COL + LT_GUTTER)


def lt_col_end(number):
    return lt_col_start(number) + LT_COL


def lt_row_start(number):
    return LT_SAFE + (number - 1) * LT_ROW


def lt_row_end(number):
    return LT_SAFE + number * LT_ROW


def cr_front_final():
    card = Image.new("RGBA", (CR_W, CR_H), PAPER)
    draw = ImageDraw.Draw(card)
    photo_box = (round(cr_col_start(1)), round(cr_row_start(4)), round(cr_col_end(5)), round(cr_row_end(21)))
    identity_x = round(cr_col_start(6))
    identity_right = round(cr_col_end(12))

    photo = cover(PHOTO, (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]))
    card.paste(photo, (photo_box[0], photo_box[1]))
    draw.rectangle(photo_box, outline=NAVY, width=3)
    draw.rectangle((round(cr_col_end(5) + 4), photo_box[1], round(cr_col_end(5) + 9), photo_box[3]), fill=GREEN)

    logo = contain(LOGO, (72, 55))
    card.alpha_composite(logo, (identity_x, round(cr_row_start(4))))
    tracking_text(draw, (identity_x + 84, round(cr_row_start(4)) + 4), "PRIMERA IGLESIA DEL NAZARENO", sans(15, "Bold"), NAVY, .45)
    draw.text((identity_x + 84, round(cr_row_start(4)) + 27), "VEN Y VE", font=sans(25, "ExtraBold"), fill=NAVY)

    draw.text((identity_x, round(cr_row_start(8))), "María Fernanda Rodríguez", font=serif(42, "Bold"), fill=INK)
    draw.ellipse((identity_x, round(cr_row_start(12)) + 7, identity_x + 14, round(cr_row_start(12)) + 21), fill=GREEN)
    draw.text((identity_x + 26, round(cr_row_start(12))), "MIEMBRO ACTIVO", font=sans(24, "Bold"), fill="#137945")

    data_top = round(cr_row_start(15))
    draw.line((identity_x, data_top, identity_right, data_top), fill=RULE, width=2)
    draw.text((identity_x, data_top + 22), "NÚMERO OFICIAL", font=sans(14, "Bold"), fill=MUTED)
    draw.text((identity_x, data_top + 48), "VV-0284", font=sans(29, "ExtraBold"), fill=NAVY)
    second_x = round(cr_col_start(10))
    draw.text((second_x, data_top + 22), "MIEMBRO DESDE", font=sans(14, "Bold"), fill=MUTED)
    draw.text((second_x, data_top + 51), "05-18-2014", font=sans(23, "Bold"), fill=INK)
    draw.line((identity_x, round(cr_row_end(22)), identity_right, round(cr_row_end(22))), fill=NAVY, width=2)
    return card


def cr_back_final():
    card = Image.new("RGBA", (CR_W, CR_H), WHITE)
    draw = ImageDraw.Draw(card)
    info_left = round(cr_col_start(1))
    info_right = round(cr_col_end(7))
    verify_left = round(cr_col_start(8))
    verify_right = round(cr_col_end(12))
    divider_x = round((cr_col_end(7) + cr_col_start(8)) / 2)

    logo = contain(LOGO, (70, 53))
    card.alpha_composite(logo, (info_left, round(cr_row_start(2))))
    tracking_text(draw, (info_left + 82, round(cr_row_start(2)) + 2), "PRIMERA IGLESIA DEL NAZARENO", sans(13, "Bold"), NAVY, .35)
    draw.text((info_left + 82, round(cr_row_start(2)) + 25), "VEN Y VE", font=sans(23, "ExtraBold"), fill=NAVY)
    draw.line((info_left, round(cr_row_end(4)), info_right, round(cr_row_end(4))), fill=RULE, width=2)

    message_y = round(cr_row_start(6))
    message = "Al portador de este carnet se le reconoce como miembro activo de la Primera Iglesia del Nazareno ‘Ven y Ve’, con acceso a las actividades, servicios y beneficios de la congregación."
    message_font = sans(16, "Medium")
    lines = wrap_lines(draw, message, message_font, info_right - info_left - 8)
    for index, line in enumerate(lines):
        draw.text((info_left, message_y + index * 23), line, font=message_font, fill=INK)
    draw.text((info_left, round(cr_row_start(12))), "614-508-0303", font=sans(23, "Bold"), fill=TEAL)
    draw.text((info_left, round(cr_row_start(13)) + 4), "INFORMACIÓN INSTITUCIONAL", font=sans(12, "Bold"), fill=MUTED)

    signature_y = round(cr_row_start(17))
    draw.line((info_left, signature_y, info_right - 28, signature_y), fill=NAVY, width=2)
    draw.text((info_left + 34, signature_y + 12), "[FIRMA DINÁMICA DE PASTORA]", font=sans(14, "SemiBold"), fill=INK)
    draw.text((info_left + 132, signature_y + 38), "PASTORA PRINCIPAL", font=sans(11, "Bold"), fill=MUTED)

    draw.line((divider_x, round(cr_row_start(4)), divider_x, round(cr_row_end(22))), fill=NAVY, width=2)
    draw.rectangle((divider_x - 2, round(cr_row_start(6)), divider_x + 3, round(cr_row_end(17))), fill=GREEN)
    draw.text((verify_left, round(cr_row_start(2))), "VERIFICACIÓN", font=sans(14, "Bold"), fill=TEAL)
    draw.text((verify_left, round(cr_row_start(3)) + 2), "VV-0284", font=sans(24, "ExtraBold"), fill=NAVY)

    qr_size = 220
    qr_x = round((verify_left + verify_right - qr_size) / 2)
    qr_y = round(cr_row_start(6))
    qr = QR.resize((qr_size, qr_size), Image.Resampling.NEAREST)
    draw.rectangle((qr_x - 8, qr_y - 8, qr_x + qr_size + 8, qr_y + qr_size + 8), fill=WHITE, outline=RULE, width=2)
    card.paste(qr, (qr_x, qr_y))
    draw.text((verify_left, round(cr_row_start(19))), "ESCANEE PARA VALIDAR", font=sans(12, "Bold"), fill=NAVY)
    draw.text((verify_left, round(cr_row_start(20)) + 4), "Documento personal e intransferible", font=sans(11, "Medium"), fill=MUTED)
    return card


def certificate_final():
    cert = Image.new("RGBA", (LT_W, LT_H), PAPER)
    draw = ImageDraw.Draw(cert)
    draw.rectangle((round(LT_FRAME), round(LT_FRAME), LT_W - round(LT_FRAME), LT_H - round(LT_FRAME)), outline=NAVY, width=3)
    draw.rectangle((round(LT_SAFE), round(LT_SAFE), LT_W - round(LT_SAFE), LT_H - round(LT_SAFE)), outline="#9EB8C0", width=1)

    header_left = round(lt_col_start(3))
    header_right = round(lt_col_end(10))
    logo = contain(LOGO, (92, 70))
    cert.alpha_composite(logo, (header_left, round(lt_row_start(1)) + 6))
    tracking_text(draw, (header_left + 112, round(lt_row_start(1)) + 9), "PRIMERA IGLESIA DEL NAZARENO", sans(14, "Bold"), NAVY, .4)
    draw.text((header_left + 112, round(lt_row_start(2)) + 4), "VEN Y VE", font=sans(25, "ExtraBold"), fill=NAVY)
    draw.text((header_right - 165, round(lt_row_start(2)) + 5), "DOCUMENTO OFICIAL", font=sans(10, "Bold"), fill=TEAL)

    title = "CERTIFICADO DE MEMBRESÍA"
    title_font = serif(45, "Bold")
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((LT_W - (title_box[2] - title_box[0])) / 2, round(lt_row_start(4))), title, font=title_font, fill=NAVY)
    accent_left = round(lt_col_start(6))
    accent_right = round(lt_col_end(7))
    draw.rectangle((accent_left, round(lt_row_start(6)) - 6, accent_right, round(lt_row_start(6)) - 2), fill=GREEN)

    preamble = "Se certifica que"
    preamble_font = serif(21, "Regular")
    preamble_box = draw.textbbox((0, 0), preamble, font=preamble_font)
    draw.text(((LT_W - (preamble_box[2] - preamble_box[0])) / 2, round(lt_row_start(9))), preamble, font=preamble_font, fill=MUTED)

    member = "María Fernanda Rodríguez"
    member_font = serif(54, "Bold")
    member_box = draw.textbbox((0, 0), member, font=member_font)
    draw.text(((LT_W - (member_box[2] - member_box[0])) / 2, round(lt_row_start(11))), member, font=member_font, fill=TEAL)
    draw.line((round(lt_col_start(3)), round(lt_row_start(15)), round(lt_col_end(10)), round(lt_row_start(15))), fill=RULE, width=2)

    statement_1 = "ha sido reconocido(a) como miembro activo de esta congregación,"
    statement_2 = "afirmando su comunión, fe y servicio como parte del cuerpo de Cristo."
    statement_font = sans(14, "Regular")
    for index, statement in enumerate((statement_1, statement_2)):
        box = draw.textbbox((0, 0), statement, font=statement_font)
        draw.text(((LT_W - (box[2] - box[0])) / 2, round(lt_row_start(16 + index))), statement, font=statement_font, fill=INK)

    signature_left = round(lt_col_start(2))
    signature_right = round(lt_col_end(5))
    signature_y = round(lt_row_start(26))
    draw.line((signature_left, signature_y, signature_right, signature_y), fill=NAVY, width=2)
    draw.text((signature_left + 28, signature_y + 10), "[FIRMA DINÁMICA DE PASTORA]", font=sans(12, "SemiBold"), fill=INK)
    draw.text((signature_left + 92, signature_y + 31), "PASTORA PRINCIPAL", font=sans(9, "Bold"), fill=MUTED)

    data_left = round(lt_col_start(6))
    draw.text((data_left, round(lt_row_start(23))), "NÚMERO OFICIAL", font=sans(9, "Bold"), fill=MUTED)
    draw.text((data_left, round(lt_row_start(24))), "VV-0284", font=sans(18, "ExtraBold"), fill=NAVY)
    draw.text((data_left + 135, round(lt_row_start(23))), "MIEMBRO DESDE", font=sans(9, "Bold"), fill=MUTED)
    draw.text((data_left + 135, round(lt_row_start(24))), "05-18-2014", font=sans(15, "Bold"), fill=INK)
    draw.text((data_left, round(lt_row_start(26))), "FECHA DE EMISIÓN", font=sans(9, "Bold"), fill=MUTED)
    draw.text((data_left, round(lt_row_start(27))), "09-22-2026", font=sans(15, "Bold"), fill=INK)

    qr_size = 126
    qr_x = round(lt_col_start(10))
    qr_y = round(lt_row_start(23))
    cert.paste(QR.resize((qr_size, qr_size), Image.Resampling.NEAREST), (qr_x, qr_y))
    draw.text((qr_x - 4, qr_y + qr_size + 8), "VERIFICACIÓN DE MEMBRESÍA", font=sans(8, "Bold"), fill=NAVY)

    footer_y = round(lt_row_start(29))
    draw.line((round(lt_col_start(1)), footer_y, round(lt_col_end(12)), footer_y), fill=RULE, width=1)
    draw.text((round(lt_col_start(1)), footer_y + 10), "REGISTRO · VV-0284 · EMISIÓN 09-22-2026", font=sans(8, "SemiBold"), fill=MUTED)
    draw.text((round(lt_col_start(10)), footer_y + 10), "PRIMERA IGLESIA DEL NAZARENO VEN Y VE", font=sans(8, "SemiBold"), fill=MUTED)
    return cert


def overlay_cr_grid(base, view):
    result = base.copy().convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for col in range(1, 13):
        x1, x2 = round(cr_col_start(col)), round(cr_col_end(col))
        draw.rectangle((x1, CR_SAFE, x2, CR_H - CR_SAFE), fill=GRID_MAGENTA)
        draw.text((x1 + 4, CR_SAFE + 2), str(col), font=sans(11, "Bold"), fill="#A00057")
        if col < 12:
            draw.rectangle((x2, CR_SAFE, round(cr_col_start(col + 1)), CR_H - CR_SAFE), fill=GRID_AMBER)
    for row in range(25):
        y = round(CR_SAFE + row * CR_ROW)
        draw.line((CR_SAFE, y, CR_W - CR_SAFE, y), fill=GRID_ROW, width=1)
        if row < 24:
            draw.text((CR_SAFE + 3, y + 2), str(row + 1), font=sans(9, "SemiBold"), fill="#566476")
    draw.rectangle((CR_SAFE, CR_SAFE, CR_W - CR_SAFE, CR_H - CR_SAFE), outline=GRID_CYAN, width=3)
    if view == "front":
        split = round(cr_col_start(6) - CR_GUTTER / 2)
        draw.line((split, CR_SAFE, split, CR_H - CR_SAFE), fill=GRID_BLUE, width=3)
        draw.rectangle((round(cr_col_start(1)), round(cr_row_start(4)), round(cr_col_end(5)), round(cr_row_end(21))), outline="#E11D48", width=3)
        draw.rectangle((round(cr_col_start(6)), round(cr_row_start(4)), round(cr_col_end(12)), round(cr_row_end(22))), outline=GRID_BLUE, width=3)
    else:
        split = round((cr_col_end(7) + cr_col_start(8)) / 2)
        draw.line((split, CR_SAFE, split, CR_H - CR_SAFE), fill=GRID_BLUE, width=3)
        draw.rectangle((round(cr_col_start(1)), round(cr_row_start(4)), round(cr_col_end(7)), round(cr_row_end(22))), outline="#E11D48", width=3)
        draw.rectangle((round(cr_col_start(8)), round(cr_row_start(4)), round(cr_col_end(12)), round(cr_row_end(22))), outline=GRID_BLUE, width=3)
    return Image.alpha_composite(result, overlay)


def overlay_letter_grid(base):
    result = base.copy().convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for col in range(1, 13):
        x1, x2 = round(lt_col_start(col)), round(lt_col_end(col))
        draw.rectangle((x1, round(LT_SAFE), x2, LT_H - round(LT_SAFE)), fill=GRID_MAGENTA)
        draw.text((x1 + 5, round(LT_SAFE) + 3), str(col), font=sans(11, "Bold"), fill="#A00057")
        if col < 12:
            draw.rectangle((x2, round(LT_SAFE), round(lt_col_start(col + 1)), LT_H - round(LT_SAFE)), fill=GRID_AMBER)
    for row in range(31):
        y = round(LT_SAFE + row * LT_ROW)
        draw.line((round(LT_SAFE), y, LT_W - round(LT_SAFE), y), fill=GRID_ROW, width=1)
        if row < 30:
            draw.text((round(LT_SAFE) + 4, y + 2), str(row + 1), font=sans(9, "SemiBold"), fill="#566476")
    draw.rectangle((round(LT_FRAME), round(LT_FRAME), LT_W - round(LT_FRAME), LT_H - round(LT_FRAME)), outline="#0F172A", width=3)
    draw.rectangle((round(LT_SAFE), round(LT_SAFE), LT_W - round(LT_SAFE), LT_H - round(LT_SAFE)), outline=GRID_CYAN, width=3)
    axis_x = LT_W // 2
    draw.line((axis_x, round(LT_SAFE), axis_x, LT_H - round(LT_SAFE)), fill=GRID_BLUE, width=3)
    for row in (7, 22, 29):
        y = round(lt_row_start(row))
        draw.line((round(LT_SAFE), y, LT_W - round(LT_SAFE), y), fill=GRID_BLUE, width=3)
    return Image.alpha_composite(result, overlay)


def construction_sheet(document, title, spec, legend, letter=False):
    pad_x = 80
    top = 145 if letter else 125
    sheet = Image.new("RGBA", (document.width + pad_x * 2, document.height + top + 55), "#F0F4F6")
    draw = ImageDraw.Draw(sheet)
    draw.text((pad_x, 28), title, font=sans(21 if letter else 18, "ExtraBold"), fill=NAVY)
    draw.text((pad_x, 60), spec, font=sans(12 if letter else 11, "SemiBold"), fill=MUTED)
    x = pad_x
    for color, text in legend:
        draw.rectangle((x, 92, x + 16, 108), fill=color)
        draw.text((x + 24, 89), text, font=sans(11, "Bold"), fill=INK)
        x += 24 + draw.textlength(text, font=sans(11, "Bold")) + 32
    sheet.alpha_composite(document, (pad_x, top))
    draw.text((pad_x, top + document.height + 18), "El documento interior conserva exactamente sus dimensiones y proporción física.", font=sans(11, "Medium"), fill=MUTED)
    return sheet


front_final = cr_front_final()
back_final = cr_back_final()
certificate_clean = certificate_final()
front_grid_document = overlay_cr_grid(front_final, "front")
back_grid_document = overlay_cr_grid(back_final, "back")
certificate_grid_document = overlay_letter_grid(certificate_clean)
front_grid = construction_sheet(
    front_grid_document,
    "CARNET FRENTE — CONSTRUCTION / GRID",
    "CR80 85.60 × 53.98 mm · Safe 3 mm · 12 columnas · gutter 1.5 mm · 24 filas × 2 mm",
    [(GRID_CYAN, "Safe area"), ("#E11D48", "Foto C1–5 / R4–21"), (GRID_BLUE, "Identidad C6–12 / R4–22")],
)
back_grid = construction_sheet(
    back_grid_document,
    "CARNET REVERSO — CONSTRUCTION / GRID",
    "CR80 85.60 × 53.98 mm · División 60/40 · eje en gutter C7/C8 · ritmo 2 mm",
    [(GRID_CYAN, "Safe area"), ("#E11D48", "Información C1–7"), (GRID_BLUE, "Verificación C8–12")],
)
certificate_grid = construction_sheet(
    certificate_grid_document,
    "CERTIFICADO — CONSTRUCTION / GRID",
    "Letter 279.4 × 215.9 mm · Marco 6.35 mm · Safe 12.7 mm · 12 columnas · 30 filas × 6.35 mm",
    [(GRID_CYAN, "Safe area"), (GRID_BLUE, "Eje central"), ("#E11D48", "Zonas 6 / 15 / 7 / 2 filas")],
    letter=True,
)

files = {
    "01-carnet-frente-grid.png": front_grid,
    "02-carnet-frente-final.png": front_final,
    "03-carnet-reverso-grid.png": back_grid,
    "04-carnet-reverso-final.png": back_final,
    "05-certificado-grid.png": certificate_grid,
    "06-certificado-final.png": certificate_clean,
}
for name, image in files.items():
    image.convert("RGB").save(OUT / name, quality=96)

BOARD_W, BOARD_H = 2400, 3100
board = Image.new("RGBA", (BOARD_W, BOARD_H), "#E9EFF2")
draw = ImageDraw.Draw(board)
draw.text((95, 60), "SISTEMA DE CONSTRUCCIÓN INSTITUCIONAL", font=sans(22, "Bold"), fill=GREEN)
draw.text((95, 100), "RETÍCULA → PROPORCIÓN → ALINEACIÓN → JERARQUÍA", font=serif(47, "Bold"), fill=NAVY)
draw.text((95, 163), "CR80 + US Letter Landscape · Dirección de arte, no implementación", font=sans(18, "Medium"), fill=MUTED)
draw.text((95, 225), "CARNET FRENTE — CONSTRUCTION / GRID", font=sans(14, "Bold"), fill=NAVY)
draw.text((1260, 225), "CARNET FRENTE — FINAL", font=sans(14, "Bold"), fill=NAVY)
board.alpha_composite(front_grid_document.resize((1080, 681), Image.Resampling.LANCZOS), (95, 260))
board.alpha_composite(front_final.resize((1080, 681), Image.Resampling.LANCZOS), (1260, 260))
draw.text((95, 1010), "CARNET REVERSO — CONSTRUCTION / GRID", font=sans(14, "Bold"), fill=NAVY)
draw.text((1260, 1010), "CARNET REVERSO — FINAL", font=sans(14, "Bold"), fill=NAVY)
board.alpha_composite(back_grid_document.resize((1080, 681), Image.Resampling.LANCZOS), (95, 1045))
board.alpha_composite(back_final.resize((1080, 681), Image.Resampling.LANCZOS), (1260, 1045))
draw.text((95, 1800), "CERTIFICADO — CONSTRUCTION / GRID", font=sans(14, "Bold"), fill=NAVY)
draw.text((1260, 1800), "CERTIFICADO — FINAL", font=sans(14, "Bold"), fill=NAVY)
board.alpha_composite(certificate_grid_document.resize((1080, 835), Image.Resampling.LANCZOS), (95, 1835))
board.alpha_composite(certificate_clean.resize((1080, 835), Image.Resampling.LANCZOS), (1260, 1835))

draw.text((95, 2740), "PARÁMETROS FÍSICOS", font=sans(14, "Bold"), fill=NAVY)
params = [
    "CR80 · 85.60 × 53.98 mm · Safe 3 mm · 12 columnas · gutter 1.5 mm · filas 24 × 2 mm",
    "LETTER · 279.4 × 215.9 mm · Marco 6.35 mm · Safe 12.7 mm · 12 columnas · gutter 4 mm · filas 30 × 6.35 mm",
    "TIPOGRAFÍA · Cormorant Garamond + Plus Jakarta Sans · sin tercera familia",
    "COLOR · Navy dominante · verde funcional · off-white · neutral slate",
]
for index, text in enumerate(params):
    draw.text((95, 2780 + index * 48), text, font=sans(16, "Medium"), fill=INK)

board.convert("RGB").save(OUT / "00-sistema-completo.jpg", quality=94, subsampling=0)
geometry = {
    "cr80": {
        "physical_mm": [85.60, 53.98],
        "canvas_px": [CR_W, CR_H],
        "safe_mm": 3,
        "inner_width_mm": 79.60,
        "grid_width_mm": round(12 * 5.258 + 11 * 1.5, 3),
        "vertical_rhythm_mm": 24 * 2,
        "front_photo": {"columns": [1, 5], "rows": [4, 21]},
        "front_identity": {"columns": [6, 12], "rows": [4, 22]},
        "back_information": {"columns": [1, 7], "rows": [4, 22]},
        "back_verification": {"columns": [8, 12], "rows": [4, 22]},
    },
    "letter_landscape": {
        "physical_mm": [279.4, 215.9],
        "canvas_px": [LT_W, LT_H],
        "frame_mm": 6.35,
        "safe_mm": 12.7,
        "inner_width_mm": 254,
        "grid_width_mm": 12 * 17.5 + 11 * 4,
        "vertical_rhythm_mm": 30 * 6.35,
        "zones_rows": [6, 15, 7, 2],
    },
    "fonts": ["Plus Jakarta Sans", "Cormorant Garamond"],
}
(OUT / "geometry-report.json").write_text(json.dumps(geometry, indent=2), encoding="utf-8")
print(OUT)