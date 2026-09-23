from pathlib import Path
from math import cos, radians, sin

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).parent
OUT = ROOT / "boards"
OUT.mkdir(exist_ok=True)
LOGO = Image.open("/app/frontend/public/assets/membership/church-logo.png").convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())
PHOTO = Image.open(ROOT / "member-photo.jpg").convert("RGB")
QR = Image.open(ROOT / "verification-qr.png").convert("RGB")

NAVY = "#0B1D3A"
CYAN = "#08A4C4"
GREEN = "#57C62F"
INK = "#111827"
MUTED = "#586778"
LINE = "#DCE4E9"
PAPER = "#FDFDFB"
WHITE = "#FFFFFF"


def font(size, weight="Regular"):
    item = ImageFont.truetype(str(ROOT / "fonts" / "PlusJakartaSans.ttf"), size)
    item.set_variation_by_name(weight)
    return item


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


def brand_arcs(draw, bounds, widths=(13, 7), colors=(CYAN, GREEN), start=0, end=360, rounded=True):
    for offset, (width, color) in enumerate(zip(widths, colors)):
        inset = offset * 18
        box = (bounds[0] + inset, bounds[1] + inset, bounds[2] - inset, bounds[3] - inset)
        draw.arc(box, start=start, end=end, fill=color, width=width)
        if rounded and end - start < 360:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            rx, ry = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
            radius = width * .36
            for angle in (start, end):
                x = cx + rx * cos(radians(angle))
                y = cy + ry * sin(radians(angle))
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def front():
    card = Image.new("RGBA", (856, 540), "#FAFCFD")
    draw = ImageDraw.Draw(card)
    brand_arcs(draw, (730, 70, 970, 330), widths=(12, 6), start=90, end=270)
    draw.polygon([(0, 414), (856, 360), (856, 540), (0, 540)], fill=NAVY)
    logo = contain(LOGO, (118, 90))
    card.alpha_composite(logo, (45, 24))
    draw.text((174, 38), "PRIMERA IGLESIA DEL NAZARENO", font=font(11, "Bold"), fill=NAVY)
    draw.text((174, 66), "VEN Y VE", font=font(24, "ExtraBold"), fill=NAVY)

    portrait = cover(PHOTO, (210, 270))
    mask = Image.new("L", portrait.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, portrait.width - 1, portrait.height - 1), radius=110, fill=255)
    card.paste(portrait, (52, 135), mask)

    draw.text((318, 133), "CARNET OFICIAL DE MIEMBRO", font=font(11, "Bold"), fill="#0B758C")
    draw.text((318, 177), "María Fernanda", font=font(39, "ExtraBold"), fill=INK)
    draw.text((318, 220), "Rodríguez", font=font(39, "ExtraBold"), fill=INK)
    draw.ellipse((321, 295, 334, 308), fill=GREEN)
    draw.text((347, 286), "MIEMBRO ACTIVO", font=font(17, "Bold"), fill="#137944")
    draw.text((318, 335), "VV-0284", font=font(26, "ExtraBold"), fill=NAVY)
    draw.text((466, 347), "MIEMBRO DESDE  ·  05-18-2014", font=font(10, "Bold"), fill=MUTED)
    draw.text((52, 470), "CARNET OFICIAL DE MIEMBRO", font=font(11, "SemiBold"), fill=WHITE)
    return card


def back():
    card = Image.new("RGBA", (856, 540), WHITE)
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((6, 6, 850, 534), radius=18, outline="#CFDAE2", width=2)
    brand_arcs(draw, (750, 340, 1010, 520), widths=(11, 5), start=140, end=220)
    logo = contain(LOGO, (126, 96))
    card.alpha_composite(logo, (38, 25))
    draw.text((174, 44), "PRIMERA IGLESIA DEL NAZARENO", font=font(11, "Bold"), fill=NAVY)
    draw.text((174, 70), "VEN Y VE", font=font(23, "ExtraBold"), fill=NAVY)
    draw.line((38, 128, 818, 128), fill=LINE, width=2)

    draw.text((38, 153), "VERIFICACIÓN DE MEMBRESÍA", font=font(11, "Bold"), fill="#0B7C92")
    draw.text((38, 184), "VV-0284", font=font(25, "ExtraBold"), fill=NAVY)
    draw.text((38, 225), "Al portador de este carnet se le reconoce como miembro", font=font(15, "Medium"), fill=INK)
    draw.text((38, 251), "activo de la Primera Iglesia del Nazareno ‘Ven y Ve’,", font=font(15, "Medium"), fill=INK)
    draw.text((38, 277), "con acceso a las actividades, servicios y beneficios", font=font(15, "Medium"), fill=INK)
    draw.text((38, 303), "correspondientes de la congregación.", font=font(15, "Medium"), fill=INK)
    draw.text((38, 343), "Para más información: 614-508-0303", font=font(15, "Bold"), fill="#087D98")

    qr = QR.resize((174, 174), Image.Resampling.NEAREST)
    draw.rounded_rectangle((608, 150, 794, 336), radius=12, fill=WHITE, outline="#CCD8E0", width=2)
    card.paste(qr, (614, 156))
    draw.text((618, 350), "ESCANEE PARA VALIDAR", font=font(9, "Bold"), fill=NAVY)

    draw.line((38, 411, 378, 411), fill=NAVY, width=2)
    draw.text((69, 424), "[FIRMA DINÁMICA DE PASTORA]", font=font(12, "SemiBold"), fill=INK)
    draw.text((136, 453), "PASTORA PRINCIPAL", font=font(9, "Bold"), fill=MUTED)
    draw.text((585, 443), "Documento personal e intransferible", font=font(9, "Medium"), fill=MUTED)
    return card


def certificate():
    cert = Image.new("RGBA", (1100, 850), PAPER)
    draw = ImageDraw.Draw(cert)
    draw.rectangle((25, 25, 1075, 825), outline=NAVY, width=3)
    draw.rectangle((37, 37, 1063, 813), outline="#92BFC4", width=1)
    brand_arcs(draw, (900, 55, 1060, 215), widths=(10, 5), start=90, end=270)

    logo = contain(LOGO, (146, 110))
    cert.alpha_composite(logo, (477, 55))
    draw.text((350, 166), "PRIMERA IGLESIA DEL NAZARENO VEN Y VE", font=font(15, "ExtraBold"), fill=NAVY)
    draw.text((452, 203), "RECONOCIMIENTO OFICIAL", font=font(10, "Bold"), fill="#0D879D")

    draw.text((279, 257), "CERTIFICADO DE MEMBRESÍA", font=font(45, "ExtraBold"), fill=NAVY)
    draw.line((375, 324, 725, 324), fill="#B9C7D2", width=2)
    draw.rectangle((535, 321, 565, 327), fill=GREEN)
    draw.text((462, 358), "Se certifica que", font=font(17, "Medium"), fill=MUTED)
    draw.text((258, 410), "María Fernanda Rodríguez", font=font(48, "ExtraBold"), fill="#087E98")
    draw.text((225, 478), "es miembro activo de la Primera Iglesia del Nazareno Ven y Ve, reconocido(a)", font=font(14, "Regular"), fill=INK)
    draw.text((307, 506), "dentro de nuestra comunidad de fe, comunión y servicio.", font=font(14, "Regular"), fill=INK)

    draw.line((110, 665, 385, 665), fill=NAVY, width=2)
    draw.text((125, 681), "[FIRMA DINÁMICA DE PASTORA]", font=font(11, "SemiBold"), fill=INK)
    draw.text((205, 709), "PASTORA PRINCIPAL", font=font(9, "Bold"), fill=MUTED)

    draw.text((452, 648), "NÚMERO OFICIAL", font=font(9, "Bold"), fill=MUTED)
    draw.text((452, 673), "VV-0284", font=font(18, "ExtraBold"), fill=NAVY)
    draw.text((603, 648), "MIEMBRO DESDE", font=font(9, "Bold"), fill=MUTED)
    draw.text((603, 676), "05-18-2014", font=font(15, "Bold"), fill=INK)
    draw.text((755, 648), "FECHA DE EMISIÓN", font=font(9, "Bold"), fill=MUTED)
    draw.text((755, 676), "09-22-2026", font=font(15, "Bold"), fill=INK)

    qr = QR.resize((120, 120), Image.Resampling.NEAREST)
    cert.paste(qr, (887, 620))
    draw.text((867, 751), "VERIFICACIÓN DE MEMBRESÍA", font=font(8, "Bold"), fill=NAVY)
    return cert


def shadowed(board, piece, xy):
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 0))
    shadow.paste((8, 22, 40, 38), (xy[0], xy[1] + 10), Image.new("L", piece.size, 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    board.alpha_composite(shadow)
    board.alpha_composite(piece, xy)


board = Image.new("RGBA", (1800, 1540), "#E8F0F2")
draw = ImageDraw.Draw(board)
draw.text((80, 50), "PROPUESTA CORREGIDA · FUENTE VISUAL ELEGIDA", font=font(16, "Bold"), fill="#117A43")
draw.text((80, 83), "PRIMERA IGLESIA DEL NAZARENO VEN Y VE", font=font(37, "ExtraBold"), fill=NAVY)
draw.text((80, 135), "Arcos institucionales · reverso de bajo consumo · certificado ceremonial", font=font(17, "Medium"), fill=MUTED)
draw.text((80, 196), "CARNET — FRENTE", font=font(13, "Bold"), fill=NAVY)
draw.text((960, 196), "CARNET — REVERSO CLARO", font=font(13, "Bold"), fill=NAVY)
front_preview = front().resize((760, 479), Image.Resampling.LANCZOS)
back_preview = back().resize((760, 479), Image.Resampling.LANCZOS)
shadowed(board, front_preview, (80, 232))
shadowed(board, back_preview, (960, 232))
draw.text((80, 766), "CERTIFICADO — US LETTER LANDSCAPE", font=font(13, "Bold"), fill=NAVY)
cert_preview = certificate().resize((870, 672), Image.Resampling.LANCZOS)
shadowed(board, cert_preview, (80, 803))
draw.text((1035, 803), "DECISIONES CORREGIDAS", font=font(13, "Bold"), fill=NAVY)
notes = [
    "La imagen adjunta es ahora la fuente visual de verdad.",
    "Reverso blanco para reducir drásticamente el consumo de tinta.",
    "Mensaje, teléfono y firma dinámica integrados sin saturar.",
    "Certificado simétrico, ceremonial y reconocible como documento oficial.",
    "Arcos azul/verde sustituyen bloques oscuros y decoración genérica.",
]
y = 848
for note in notes:
    draw.ellipse((1038, y + 7, 1047, y + 16), fill=GREEN)
    draw.text((1067, y), note, font=font(15, "Regular"), fill=INK)
    y += 62

board.convert("RGB").save(OUT / "corrected-institutional-board.jpg", quality=95, subsampling=0)
front().convert("RGB").save(OUT / "corrected-card-front.png")
back().convert("RGB").save(OUT / "corrected-card-back-low-ink.png")
certificate().convert("RGB").save(OUT / "corrected-certificate-institutional.png")
print(OUT / "corrected-institutional-board.jpg")