from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).parent
OUT = ROOT / "boards"
LOGO = Image.open("/app/frontend/public/assets/membership/church-logo.png").convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())
PHOTO = Image.open(ROOT / "member-photo.jpg").convert("RGB")
QR = Image.open(ROOT / "verification-qr.png").convert("RGB")
CERTIFICATE = Image.open(OUT / "concept-a-certificate-revision.png").convert("RGBA")

NAVY = "#0B1D3A"
GREEN = "#57C62F"
TEAL = "#079DBC"
INK = "#101A2B"
MUTED = "#5B6878"
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


def institutional_header(card, dark=False):
    draw = ImageDraw.Draw(card)
    logo = contain(LOGO, (118, 90))
    card.alpha_composite(logo, (42, 28))
    primary = WHITE if dark else NAVY
    secondary = "#B8C7D7" if dark else MUTED
    draw.text((175, 40), "PRIMERA IGLESIA DEL NAZARENO", font=font(12, "Bold"), fill=secondary)
    draw.text((175, 67), "VEN Y VE", font=font(27, "ExtraBold"), fill=primary)


def card_front():
    card = Image.new("RGBA", (856, 540), WHITE)
    draw = ImageDraw.Draw(card)
    draw.polygon([(555, 0), (856, 0), (856, 540), (675, 540)], fill=NAVY)
    draw.polygon([(646, 0), (665, 0), (784, 540), (765, 540)], fill=GREEN)
    institutional_header(card)
    draw.text((50, 150), "CARNET OFICIAL DE MIEMBRO", font=font(13, "Bold"), fill=TEAL)
    draw.text((50, 194), "María Fernanda", font=font(39, "ExtraBold"), fill=INK)
    draw.text((50, 237), "Rodríguez", font=font(39, "ExtraBold"), fill=INK)
    draw.ellipse((52, 310, 65, 323), fill=GREEN)
    draw.text((77, 301), "MIEMBRO ACTIVO", font=font(17, "Bold"), fill="#117A43")
    draw.line((50, 378, 495, 378), fill="#CCD5DE", width=2)
    draw.text((50, 403), "NÚMERO OFICIAL", font=font(10, "Bold"), fill=MUTED)
    draw.text((50, 428), "VV-0284", font=font(24, "ExtraBold"), fill=NAVY)
    draw.text((270, 403), "MIEMBRO DESDE", font=font(10, "Bold"), fill=MUTED)
    draw.text((270, 433), "05-18-2014", font=font(17, "Bold"), fill=INK)
    photo = cover(PHOTO, (210, 310))
    draw.rounded_rectangle((596, 104, 816, 424), radius=10, fill=WHITE)
    card.paste(photo, (601, 109))
    draw.text((603, 451), "CREDENCIAL INSTITUCIONAL", font=font(9, "SemiBold"), fill="#B7C7D8")
    return card


def card_back():
    card = Image.new("RGBA", (856, 540), NAVY)
    draw = ImageDraw.Draw(card)
    draw.rectangle((0, 0, 12, 540), fill=GREEN)
    institutional_header(card, dark=True)
    draw.text((52, 151), "VERIFICACIÓN DE MEMBRESÍA", font=font(12, "Bold"), fill="#8DDFC0")
    draw.text((52, 190), "VV-0284", font=font(45, "ExtraBold"), fill=WHITE)
    draw.text((52, 252), "María Fernanda Rodríguez", font=font(21, "SemiBold"), fill="#DCE7F2")
    draw.line((52, 298, 490, 298), fill="#30435D", width=2)
    draw.text((52, 327), "Escanee el código para validar autenticidad", font=font(13, "Regular"), fill="#B8C7D7")
    draw.text((52, 351), "y vigencia de esta membresía.", font=font(13, "Regular"), fill="#B8C7D7")
    qr = QR.resize((238, 238), Image.Resampling.NEAREST)
    draw.rounded_rectangle((568, 82, 818, 332), radius=10, fill=WHITE)
    card.paste(qr, (574, 88))
    draw.text((598, 355), "VERIFICACIÓN DIGITAL", font=font(12, "Bold"), fill=WHITE)
    draw.text((52, 476), "PRIMERA IGLESIA DEL NAZARENO VEN Y VE", font=font(10, "Bold"), fill="#8FA3B7")
    return card


def shadowed(board, piece, xy):
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 0))
    shadow.paste((6, 18, 35, 42), (xy[0], xy[1] + 10), Image.new("L", piece.size, 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    board.alpha_composite(shadow)
    board.alpha_composite(piece, xy)


board = Image.new("RGBA", (1800, 1540), "#E8EDF1")
draw = ImageDraw.Draw(board)
draw.text((80, 52), "CONCEPTO A · REVISIÓN INSTITUCIONAL", font=font(16, "Bold"), fill="#157A49")
draw.text((80, 84), "PRIMERA IGLESIA DEL NAZARENO VEN Y VE", font=font(38, "ExtraBold"), fill=NAVY)
draw.text((80, 137), "Logo ampliado · nombre completo · mismo sistema visual en las tres piezas", font=font(17, "Medium"), fill=MUTED)
draw.text((80, 202), "CARNET — FRENTE", font=font(13, "Bold"), fill=NAVY)
draw.text((960, 202), "CARNET — REVERSO", font=font(13, "Bold"), fill=NAVY)
front = card_front().resize((760, 479), Image.Resampling.LANCZOS)
back = card_back().resize((760, 479), Image.Resampling.LANCZOS)
shadowed(board, front, (80, 238))
shadowed(board, back, (960, 238))
draw.text((80, 775), "CERTIFICADO — US LETTER LANDSCAPE", font=font(13, "Bold"), fill=NAVY)
certificate = CERTIFICATE.resize((870, 672), Image.Resampling.LANCZOS)
shadowed(board, certificate, (80, 812))
draw.text((1040, 812), "CAMBIOS INSTITUCIONALES", font=font(13, "Bold"), fill=NAVY)
changes = [
    "Logo real ampliado en carnet y certificado.",
    "Nombre oficial completo en frente y reverso.",
    "Jerarquía tipográfica ejecutiva y consistente.",
    "Geometría A: recta, navy, blanca y verde mínimo.",
]
y = 855
for text in changes:
    draw.ellipse((1042, y + 6, 1050, y + 14), fill=GREEN)
    draw.text((1070, y), text, font=font(16, "Regular"), fill=INK)
    y += 58

board.convert("RGB").save(OUT / "concept-a-full-revision-board.jpg", quality=95, subsampling=0)
card_front().convert("RGB").save(OUT / "concept-a-revised-card-front.png")
card_back().convert("RGB").save(OUT / "concept-a-revised-card-back.png")
print(OUT / "concept-a-full-revision-board.jpg")