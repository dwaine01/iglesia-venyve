from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).parent
OUT = ROOT / "boards"
OUT.mkdir(exist_ok=True)
LOGO = Image.open("/app/frontend/public/assets/membership/church-logo.png").convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())
PHOTO = Image.open(ROOT / "member-photo.jpg").convert("RGB")
QR = Image.open(ROOT / "verification-qr.png").convert("RGB")

NAVY = "#0A1C3B"
CYAN = "#08A4C4"
GREEN = "#58C92F"
TEAL = "#07879E"
INK = "#111827"
MUTED = "#5A6776"
PAPER = "#FBFDFE"
WHITE = "#FFFFFF"


def font(size, weight="Regular"):
    item = ImageFont.truetype(str(ROOT / "fonts" / "Outfit.ttf"), size)
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


def circular_arcs(draw, bounds, start=90, end=270, widths=(10, 5), gap=15):
    for index, (width, color) in enumerate(zip(widths, (CYAN, GREEN))):
        inset = index * gap
        box = (bounds[0] + inset, bounds[1] + inset, bounds[2] - inset, bounds[3] - inset)
        draw.arc(box, start=start, end=end, fill=color, width=width)
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        rx, ry = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
        radius = width * .32
        for angle in (start, end):
            x = cx + rx * cos(radians(angle))
            y = cy + ry * sin(radians(angle))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def card_front():
    card = Image.new("RGBA", (856, 540), PAPER)
    draw = ImageDraw.Draw(card)
    draw.polygon([(0, 414), (856, 360), (856, 540), (0, 540)], fill=NAVY)
    circular_arcs(draw, (650, -40, 930, 240), start=90, end=270, widths=(10, 5), gap=15)

    portrait = cover(PHOTO, (220, 310))
    mask = Image.new("L", portrait.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 219, 309), radius=108, fill=255)
    card.paste(portrait, (58, 85), mask)

    draw.text((330, 116), "PRIMERA IGLESIA DEL NAZARENO", font=font(11, "Bold"), fill=TEAL)
    draw.text((330, 141), "VEN Y VE · MEMBRESÍA", font=font(13, "Bold"), fill=NAVY)
    draw.text((330, 190), "María Fernanda", font=font(39, "ExtraBold"), fill=INK)
    draw.text((330, 233), "Rodríguez", font=font(39, "ExtraBold"), fill=INK)
    draw.ellipse((333, 307, 346, 320), fill=GREEN)
    draw.text((358, 297), "MIEMBRO ACTIVO", font=font(17, "Bold"), fill="#137A45")
    draw.text((330, 344), "VV-0284", font=font(26, "ExtraBold"), fill=NAVY)
    draw.text((478, 356), "MIEMBRO DESDE · 05-18-2014", font=font(10, "SemiBold"), fill=MUTED)

    logo = contain(LOGO, (126, 96))
    card.alpha_composite(logo, (722, 21))
    draw.text((58, 470), "CARNET OFICIAL DE MIEMBRO", font=font(11, "SemiBold"), fill=WHITE)
    return card


def card_back():
    card = Image.new("RGBA", (856, 540), WHITE)
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((7, 7, 849, 533), radius=18, outline="#C9D7E1", width=2)
    circular_arcs(draw, (535, 80, 755, 460), start=90, end=270, widths=(10, 5), gap=15)

    logo = contain(LOGO, (112, 84))
    card.alpha_composite(logo, (38, 25))
    draw.text((162, 42), "PRIMERA IGLESIA DEL NAZARENO", font=font(11, "Bold"), fill=NAVY)
    draw.text((162, 69), "VEN Y VE", font=font(22, "ExtraBold"), fill=NAVY)
    draw.line((38, 125, 818, 125), fill="#D8E1E7", width=2)

    draw.text((38, 151), "VERIFICACIÓN DE MEMBRESÍA", font=font(11, "Bold"), fill=TEAL)
    draw.text((38, 184), "VV-0284", font=font(26, "ExtraBold"), fill=NAVY)
    draw.text((38, 229), "Al portador de este carnet se le reconoce como miembro", font=font(14, "Medium"), fill=INK)
    draw.text((38, 254), "activo de la Primera Iglesia del Nazareno ‘Ven y Ve’,", font=font(14, "Medium"), fill=INK)
    draw.text((38, 279), "con acceso a las actividades, servicios y beneficios", font=font(14, "Medium"), fill=INK)
    draw.text((38, 304), "correspondientes de la congregación.", font=font(14, "Medium"), fill=INK)
    draw.text((38, 344), "Para más información: 614-508-0303", font=font(15, "Bold"), fill=TEAL)
    draw.line((38, 409, 420, 409), fill=NAVY, width=2)
    draw.text((86, 422), "[FIRMA DINÁMICA DE PASTORA]", font=font(12, "SemiBold"), fill=INK)
    draw.text((160, 451), "PASTORA PRINCIPAL", font=font(9, "Bold"), fill=MUTED)

    qr = QR.resize((168, 168), Image.Resampling.NEAREST)
    draw.rounded_rectangle((660, 170, 840, 350), radius=12, fill=WHITE, outline="#C9D7E1", width=2)
    card.paste(qr, (666, 176))
    draw.text((681, 365), "ESCANEE PARA VALIDAR", font=font(9, "Bold"), fill=NAVY)
    draw.text((654, 470), "Documento personal e intransferible", font=font(9, "Medium"), fill=MUTED)
    return card


def certificate():
    cert = Image.new("RGBA", (1100, 850), PAPER)
    draw = ImageDraw.Draw(cert)
    draw.rectangle((26, 26, 1074, 824), outline=NAVY, width=3)
    draw.rectangle((38, 38, 1062, 812), outline="#8EBAC3", width=1)
    circular_arcs(draw, (760, 40, 1060, 340), start=90, end=270, widths=(11, 5), gap=16)

    logo = contain(LOGO, (130, 98))
    cert.alpha_composite(logo, (95, 68))
    draw.text((250, 84), "PRIMERA IGLESIA DEL NAZARENO", font=font(13, "Bold"), fill=NAVY)
    draw.text((250, 116), "VEN Y VE", font=font(23, "ExtraBold"), fill=NAVY)
    draw.text((250, 151), "RECONOCIMIENTO OFICIAL", font=font(10, "Bold"), fill=TEAL)

    draw.text((100, 260), "CERTIFICADO", font=font(53, "ExtraBold"), fill=NAVY)
    draw.text((100, 316), "DE MEMBRESÍA", font=font(53, "ExtraBold"), fill=NAVY)
    draw.rectangle((100, 389, 205, 395), fill=GREEN)
    draw.text((100, 427), "Se certifica que", font=font(17, "Medium"), fill=MUTED)
    draw.text((100, 474), "María Fernanda Rodríguez", font=font(46, "ExtraBold"), fill=TEAL)
    draw.text((100, 540), "es miembro activo de la Primera Iglesia del Nazareno Ven y Ve y forma parte", font=font(14, "Regular"), fill=INK)
    draw.text((100, 567), "de nuestra comunidad de fe, comunión y servicio.", font=font(14, "Regular"), fill=INK)

    draw.line((100, 690, 388, 690), fill=NAVY, width=2)
    draw.text((121, 705), "[FIRMA DINÁMICA DE PASTORA]", font=font(11, "SemiBold"), fill=INK)
    draw.text((207, 734), "PASTORA PRINCIPAL", font=font(9, "Bold"), fill=MUTED)
    draw.text((454, 674), "NÚMERO OFICIAL", font=font(9, "Bold"), fill=MUTED)
    draw.text((454, 700), "VV-0284", font=font(18, "ExtraBold"), fill=NAVY)
    draw.text((607, 674), "MIEMBRO DESDE", font=font(9, "Bold"), fill=MUTED)
    draw.text((607, 702), "05-18-2014", font=font(15, "Bold"), fill=INK)
    draw.text((760, 674), "FECHA DE EMISIÓN", font=font(9, "Bold"), fill=MUTED)
    draw.text((760, 702), "09-22-2026", font=font(15, "Bold"), fill=INK)

    qr = QR.resize((120, 120), Image.Resampling.NEAREST)
    cert.paste(qr, (890, 650))
    draw.text((868, 780), "VERIFICACIÓN DE MEMBRESÍA", font=font(8, "Bold"), fill=NAVY)
    return cert


def shadowed(board, piece, xy):
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 0))
    shadow.paste((8, 22, 40, 38), (xy[0], xy[1] + 10), Image.new("L", piece.size, 255))
    board.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    board.alpha_composite(piece, xy)


board = Image.new("RGBA", (1800, 1540), "#E8F0F2")
draw = ImageDraw.Draw(board)
draw.text((80, 50), "COMPOSICIÓN LITERAL DE LA REFERENCIA ELEGIDA", font=font(16, "Bold"), fill="#117A43")
draw.text((80, 83), "PRIMERA IGLESIA DEL NAZARENO VEN Y VE", font=font(37, "ExtraBold"), fill=NAVY)
draw.text((80, 135), "Misma retícula visual · correcciones únicamente funcionales", font=font(17, "Medium"), fill=MUTED)
draw.text((80, 196), "CARNET — FRENTE", font=font(13, "Bold"), fill=NAVY)
draw.text((960, 196), "CARNET — REVERSO CLARO", font=font(13, "Bold"), fill=NAVY)
shadowed(board, card_front().resize((760, 479), Image.Resampling.LANCZOS), (80, 232))
shadowed(board, card_back().resize((760, 479), Image.Resampling.LANCZOS), (960, 232))
draw.text((80, 766), "CERTIFICADO — US LETTER LANDSCAPE", font=font(13, "Bold"), fill=NAVY)
shadowed(board, certificate().resize((870, 672), Image.Resampling.LANCZOS), (80, 803))
draw.text((1035, 803), "CAMBIOS SOLICITADOS", font=font(13, "Bold"), fill=NAVY)
notes = [
    "Composición izquierda del certificado conservada literalmente.",
    "Reverso claro con la misma división texto / arco / QR.",
    "Arcos circulares completos dentro de zonas exclusivas.",
    "Nombre institucional, mensaje, teléfono y firma dinámica.",
]
y = 848
for note in notes:
    draw.ellipse((1038, y + 7, 1047, y + 16), fill=GREEN)
    draw.text((1067, y), note, font=font(15, "Regular"), fill=INK)
    y += 62

board.convert("RGB").save(OUT / "literal-reference-board.jpg", quality=95, subsampling=0)
card_front().convert("RGB").save(OUT / "literal-card-front.png")
card_back().convert("RGB").save(OUT / "literal-card-back.png")
certificate().convert("RGB").save(OUT / "literal-certificate.png")
print(OUT / "literal-reference-board.jpg")