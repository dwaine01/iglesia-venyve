from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).parent
OUT = ROOT / "boards"
OUT.mkdir(exist_ok=True)
LOGO = Image.open("/app/frontend/public/assets/membership/church-logo.png").convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())
PHOTO = Image.open(ROOT / "member-photo.jpg").convert("RGB")
QR = Image.open(ROOT / "verification-qr.png").convert("RGB")

NAVY = "#0B1D3A"
BLUE = "#00A3C7"
GREEN = "#57C62F"
INK = "#101A2B"
MUTED = "#5B6878"
GOLD = "#B89A5A"
WARM = "#FBFAF5"
WHITE = "#FFFFFF"


def font(path, size, weight="Regular"):
    item = ImageFont.truetype(str(ROOT / "fonts" / path), size)
    try:
        item.set_variation_by_name(weight)
    except Exception:
        pass
    return item


def sans(size, weight="Regular"):
    return font("PlusJakartaSans.ttf", size, weight)


def serif(size, weight="Regular"):
    return font("CormorantGaramond.ttf", size, weight)


def brand(size, weight="Regular"):
    return font("Outfit.ttf", size, weight)


def contain(image, size):
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return layer


def cover(image, size, focus_y=.35):
    ratio = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, min(resized.height - size[1], round((resized.height - size[1]) * focus_y)))
    return resized.crop((left, top, left + size[0], top + size[1]))


def paste_rgba(base, image, xy):
    base.paste(image, xy, image if image.mode == "RGBA" else None)


def tracking_text(draw, xy, text, item_font, fill, tracking=2):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=item_font, fill=fill)
        x += draw.textlength(char, font=item_font) + tracking


def wrapped(draw, xy, text, item_font, fill, max_width, spacing=8, align="left"):
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=item_font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    draw.multiline_text(xy, "\n".join(lines), font=item_font, fill=fill, spacing=spacing, align=align)
    return lines


def shadowed(board, piece, xy, radius=22, offset=(0, 12), alpha=45):
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 0))
    mask = Image.new("L", piece.size, 255)
    shadow.paste((6, 18, 35, alpha), (xy[0] + offset[0], xy[1] + offset[1]), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius))
    board.alpha_composite(shadow)
    board.alpha_composite(piece, xy)


def logo_block(canvas, xy, size, dark=False):
    logo = contain(LOGO, size)
    paste_rgba(canvas, logo, xy)
    draw = ImageDraw.Draw(canvas)
    x = xy[0] + size[0] + 14
    draw.text((x, xy[1] + 8), "CASA DE ORACIÓN", font=sans(12, "SemiBold"), fill="#CAD5E2" if dark else MUTED)
    draw.text((x, xy[1] + 25), "VEN Y VE", font=sans(25, "ExtraBold"), fill=WHITE if dark else NAVY)


def concept_a_front():
    card = Image.new("RGBA", (856, 540), WHITE)
    d = ImageDraw.Draw(card)
    d.polygon([(555, 0), (856, 0), (856, 540), (675, 540)], fill=NAVY)
    d.polygon([(646, 0), (665, 0), (784, 540), (765, 540)], fill=GREEN)
    logo_block(card, (48, 35), (83, 62))
    tracking_text(d, (50, 150), "CARNET OFICIAL DE MIEMBRO", sans(12, "Bold"), BLUE, 1)
    wrapped(d, (50, 188), "María Fernanda Rodríguez", sans(42, "ExtraBold"), INK, 455, 3)
    d.ellipse((52, 314, 64, 326), fill=GREEN)
    d.text((75, 304), "MIEMBRO ACTIVO", font=sans(17, "Bold"), fill="#117A43")
    d.line((50, 382, 498, 382), fill="#D6DDE5", width=2)
    d.text((50, 405), "NÚMERO OFICIAL", font=sans(10, "Bold"), fill=MUTED)
    d.text((50, 428), "VV-0284", font=sans(24, "ExtraBold"), fill=NAVY)
    d.text((260, 405), "MIEMBRO DESDE", font=sans(10, "Bold"), fill=MUTED)
    d.text((260, 431), "05-18-2014", font=sans(18, "Bold"), fill=INK)
    photo = cover(PHOTO, (210, 310), .22)
    d.rounded_rectangle((596, 104, 816, 424), radius=10, fill=WHITE)
    card.paste(photo, (601, 109))
    d.text((605, 449), "CREDENCIAL INSTITUCIONAL", font=sans(9, "SemiBold"), fill="#B7C7D8")
    return card


def concept_a_back():
    card = Image.new("RGBA", (856, 540), NAVY)
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, 12, 540), fill=GREEN)
    logo_block(card, (50, 42), (84, 62), dark=True)
    tracking_text(d, (52, 150), "VERIFICACIÓN DE MEMBRESÍA", sans(12, "Bold"), "#8DDFC0", 1)
    d.text((52, 190), "VV-0284", font=sans(45, "ExtraBold"), fill=WHITE)
    d.text((52, 252), "María Fernanda Rodríguez", font=sans(21, "SemiBold"), fill="#DCE7F2")
    d.line((52, 298, 490, 298), fill="#30435D", width=2)
    wrapped(d, (52, 324), "Escanee el código para validar la autenticidad y vigencia de esta membresía.", sans(14, "Regular"), "#B8C7D7", 410, 7)
    qr = QR.resize((238, 238), Image.Resampling.NEAREST)
    d.rounded_rectangle((568, 82, 818, 332), radius=10, fill=WHITE)
    card.paste(qr, (574, 88))
    d.text((599, 355), "VERIFICACIÓN DIGITAL", font=sans(12, "Bold"), fill=WHITE)
    d.text((52, 475), "CASA DE ORACIÓN VEN Y VE", font=sans(11, "Bold"), fill="#8FA3B7")
    return card


def concept_a_certificate():
    cert = Image.new("RGBA", (1100, 850), WARM)
    d = ImageDraw.Draw(cert)
    d.rectangle((30, 30, 1070, 820), outline=NAVY, width=3)
    d.rectangle((30, 30, 360, 35), fill=GREEN)
    logo_block(cert, (72, 70), (110, 82))
    tracking_text(d, (72, 197), "RECONOCIMIENTO INSTITUCIONAL", sans(12, "Bold"), "#16784B", 2)
    d.text((72, 232), "CERTIFICADO", font=sans(56, "ExtraBold"), fill=NAVY)
    d.text((72, 292), "DE MEMBRESÍA", font=sans(56, "ExtraBold"), fill=NAVY)
    d.line((72, 371, 1028, 371), fill="#CAD3DD", width=2)
    d.text((72, 411), "Se certifica que", font=sans(18, "Medium"), fill=MUTED)
    d.text((72, 452), "María Fernanda Rodríguez", font=sans(48, "ExtraBold"), fill="#0F6D83")
    wrapped(d, (72, 526), "es miembro activo de Casa de Oración Ven y Ve, reconocido dentro de nuestra comunidad de fe y servicio.", sans(16, "Regular"), INK, 850, 7)
    d.line((72, 655, 425, 655), fill=NAVY, width=2)
    d.text((72, 670), "[PLACEHOLDER FIRMA PASTORA]", font=sans(13, "SemiBold"), fill=INK)
    d.text((72, 698), "PASTORA PRINCIPAL", font=sans(10, "Bold"), fill=MUTED)
    d.text((492, 648), "NÚMERO OFICIAL", font=sans(9, "Bold"), fill=MUTED)
    d.text((492, 671), "VV-0284", font=sans(19, "ExtraBold"), fill=NAVY)
    d.text((492, 716), "MIEMBRO DESDE", font=sans(9, "Bold"), fill=MUTED)
    d.text((492, 739), "05-18-2014", font=sans(16, "Bold"), fill=INK)
    qr = QR.resize((128, 128), Image.Resampling.NEAREST)
    cert.paste(qr, (854, 630))
    d.text((840, 772), "VERIFICACIÓN DE MEMBRESÍA", font=sans(9, "Bold"), fill=NAVY)
    return cert


def concept_b_front():
    card = Image.new("RGBA", (856, 540), NAVY)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((22, 22, 834, 518), radius=20, fill=WARM, outline=GOLD, width=2)
    d.rectangle((24, 24, 832, 88), fill=NAVY)
    logo = contain(LOGO, (76, 58))
    paste_rgba(card, logo, (390, 26))
    d.text((296, 98), "CASA DE ORACIÓN VEN Y VE", font=serif(21, "SemiBold"), fill=NAVY)
    d.line((330, 132, 526, 132), fill=GREEN, width=3)
    photo = cover(PHOTO, (206, 286), .22)
    d.rectangle((76, 166, 294, 464), outline=NAVY, width=3)
    card.paste(photo, (82, 172))
    d.text((344, 180), "MIEMBRO ACTIVO", font=sans(13, "Bold"), fill="#15784A")
    wrapped(d, (344, 217), "María Fernanda Rodríguez", serif(45, "Bold"), NAVY, 440, 2)
    d.line((344, 334, 780, 334), fill=GOLD, width=2)
    d.text((344, 362), "NÚMERO OFICIAL", font=sans(10, "Bold"), fill=MUTED)
    d.text((344, 386), "VV-0284", font=serif(28, "Bold"), fill=INK)
    d.text((584, 362), "MIEMBRO DESDE", font=sans(10, "Bold"), fill=MUTED)
    d.text((584, 392), "05-18-2014", font=sans(16, "SemiBold"), fill=INK)
    d.text((344, 449), "CARNET OFICIAL DE MIEMBRO", font=sans(10, "SemiBold"), fill=MUTED)
    return card


def concept_b_back():
    card = Image.new("RGBA", (856, 540), NAVY)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((18, 18, 838, 522), radius=20, outline=GOLD, width=2)
    d.rounded_rectangle((28, 28, 828, 512), radius=16, outline="#607089", width=1)
    logo = contain(LOGO, (94, 72))
    paste_rgba(card, logo, (381, 44))
    tracking_text(d, (285, 124), "CASA DE ORACIÓN VEN Y VE", sans(11, "Bold"), "#D4DEE8", 2)
    qr = QR.resize((230, 230), Image.Resampling.NEAREST)
    d.rectangle((313, 170, 543, 400), fill=WHITE)
    card.paste(qr, (313, 170))
    d.text((310, 421), "VERIFICACIÓN DE MEMBRESÍA", font=sans(12, "Bold"), fill=WHITE)
    d.text((376, 455), "VV-0284", font=serif(28, "Bold"), fill="#E6D2A3")
    d.rectangle((426, 484, 430, 493), fill=GREEN)
    return card


def concept_b_certificate():
    cert = Image.new("RGBA", (1100, 850), WARM)
    d = ImageDraw.Draw(cert)
    d.rectangle((26, 26, 1074, 824), outline=NAVY, width=3)
    d.rectangle((39, 39, 1061, 811), outline=GOLD, width=2)
    d.rectangle((49, 49, 1051, 801), outline="#D9D2C4", width=1)
    logo = contain(LOGO, (126, 94))
    paste_rgba(cert, logo, (487, 62))
    tracking_text(d, (382, 164), "CASA DE ORACIÓN VEN Y VE", sans(12, "Bold"), NAVY, 2)
    d.text((326, 215), "CERTIFICADO DE MEMBRESÍA", font=serif(48, "Bold"), fill=NAVY)
    d.line((390, 282, 710, 282), fill=GOLD, width=2)
    d.rectangle((546, 277, 554, 287), fill=GREEN)
    d.text((474, 318), "Se certifica que", font=serif(24, "Regular"), fill=MUTED)
    d.text((265, 367), "María Fernanda Rodríguez", font=serif(59, "Bold"), fill="#143F66")
    wrapped(d, (257, 455), "es miembro activo de esta congregación y forma parte de nuestra comunidad de fe, comunión y servicio.", serif(20, "Regular"), INK, 590, 8, "center")
    d.text((463, 560), "VV-0284", font=serif(27, "Bold"), fill=NAVY)
    d.text((428, 594), "MIEMBRO DESDE  ·  05-18-2014", font=sans(10, "Bold"), fill=MUTED)
    d.line((115, 696, 405, 696), fill=GOLD, width=2)
    d.text((122, 710), "[PLACEHOLDER FIRMA PASTORA]", font=sans(12, "SemiBold"), fill=INK)
    d.text((193, 738), "PASTORA PRINCIPAL", font=sans(9, "Bold"), fill=MUTED)
    qr = QR.resize((114, 114), Image.Resampling.NEAREST)
    cert.paste(qr, (866, 652))
    d.text((844, 773), "VERIFICACIÓN DE MEMBRESÍA", font=sans(8, "Bold"), fill=NAVY)
    return cert


def concept_c_front():
    card = Image.new("RGBA", (856, 540), "#F7FAFC")
    d = ImageDraw.Draw(card)
    d.ellipse((-190, -265, 760, 610), outline=BLUE, width=26)
    d.ellipse((-165, -240, 735, 585), outline=GREEN, width=10)
    d.polygon([(0, 398), (856, 330), (856, 540), (0, 540)], fill=NAVY)
    logo = contain(LOGO, (118, 88))
    paste_rgba(card, logo, (690, 30))
    photo = cover(PHOTO, (226, 304), .22)
    d.rounded_rectangle((54, 78, 292, 394), radius=112, fill=WHITE)
    mask = Image.new("L", (226, 304), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 225, 303), radius=108, fill=255)
    card.paste(photo, (60, 84), mask)
    tracking_text(d, (350, 108), "VEN Y VE · MEMBRESÍA", brand(12, "Bold"), "#0B7591", 2)
    wrapped(d, (350, 154), "María Fernanda Rodríguez", brand(42, "ExtraBold"), INK, 430, 2)
    d.ellipse((352, 298, 364, 310), fill=GREEN)
    d.text((375, 288), "MIEMBRO ACTIVO", font=brand(17, "Bold"), fill="#147A46")
    d.text((350, 325), "VV-0284", font=brand(27, "ExtraBold"), fill=NAVY)
    d.text((522, 334), "MIEMBRO DESDE  05-18-2014", font=brand(11, "SemiBold"), fill=MUTED)
    d.text((54, 461), "CARNET OFICIAL DE MIEMBRO", font=brand(12, "SemiBold"), fill=WHITE)
    return card


def concept_c_back():
    card = Image.new("RGBA", (856, 540), NAVY)
    d = ImageDraw.Draw(card)
    d.ellipse((-290, -120, 600, 660), outline="#0A9DC1", width=24)
    d.ellipse((-250, -84, 555, 625), outline=GREEN, width=9)
    logo = contain(LOGO, (112, 82))
    paste_rgba(card, logo, (50, 42))
    d.text((51, 154), "VERIFICACIÓN", font=brand(31, "ExtraBold"), fill=WHITE)
    d.text((51, 190), "DE MEMBRESÍA", font=brand(31, "ExtraBold"), fill=WHITE)
    d.text((53, 255), "VV-0284", font=brand(24, "Bold"), fill="#7DE0B3")
    wrapped(d, (52, 307), "Escanee para validar autenticidad y vigencia.", brand(14, "Regular"), "#C6D5E3", 330, 7)
    qr = QR.resize((246, 246), Image.Resampling.NEAREST)
    d.rounded_rectangle((562, 118, 820, 376), radius=28, fill=WHITE)
    card.paste(qr, (568, 124))
    d.line((562, 411, 820, 411), fill="#33465E", width=2)
    d.text((603, 430), "CASA DE ORACIÓN VEN Y VE", font=brand(10, "SemiBold"), fill="#AFC2D3")
    return card


def concept_c_certificate():
    cert = Image.new("RGBA", (1100, 850), "#F7FAFC")
    d = ImageDraw.Draw(cert)
    d.rectangle((0, 0, 46, 850), fill=NAVY)
    d.ellipse((565, -430, 1290, 285), outline=BLUE, width=18)
    d.ellipse((592, -402, 1260, 255), outline=GREEN, width=8)
    d.ellipse((-320, 636, 370, 1240), outline="#D6E8ED", width=16)
    d.line((78, 50, 78, 800), fill="#C8D4DC", width=2)
    logo = contain(LOGO, (126, 94))
    paste_rgba(cert, logo, (108, 74))
    tracking_text(d, (265, 92), "CASA DE ORACIÓN VEN Y VE", brand(13, "Bold"), NAVY, 2)
    tracking_text(d, (265, 126), "RECONOCIMIENTO OFICIAL", brand(10, "SemiBold"), "#0A839D", 2)
    d.text((108, 228), "CERTIFICADO", font=brand(60, "ExtraBold"), fill=NAVY)
    d.text((108, 289), "DE MEMBRESÍA", font=brand(60, "ExtraBold"), fill=NAVY)
    d.rectangle((108, 376, 220, 382), fill=GREEN)
    d.text((108, 414), "Se certifica que", font=brand(17, "Regular"), fill=MUTED)
    d.text((108, 460), "María Fernanda Rodríguez", font=brand(48, "ExtraBold"), fill="#0B7892")
    wrapped(d, (108, 532), "es miembro activo de Casa de Oración Ven y Ve y forma parte de nuestra comunidad de fe y servicio.", brand(16, "Regular"), INK, 780, 8)
    d.line((108, 680, 400, 680), fill=NAVY, width=2)
    d.text((108, 698), "[PLACEHOLDER FIRMA PASTORA]", font=brand(12, "SemiBold"), fill=INK)
    d.text((108, 728), "PASTORA PRINCIPAL", font=brand(9, "Bold"), fill=MUTED)
    d.text((485, 677), "VV-0284", font=brand(22, "ExtraBold"), fill=NAVY)
    d.text((485, 712), "MIEMBRO DESDE  ·  05-18-2014", font=brand(10, "SemiBold"), fill=MUTED)
    qr = QR.resize((116, 116), Image.Resampling.NEAREST)
    cert.paste(qr, (880, 650))
    d.text((852, 778), "VERIFICACIÓN DE MEMBRESÍA", font=brand(8, "Bold"), fill=NAVY)
    return cert


CONCEPTS = {
    "A": {
        "title": "INSTITUCIONAL CONTEMPORÁNEO",
        "subtitle": "Precisión ejecutiva · autoridad visual · claridad",
        "bg": "#E9EEF3",
        "front": concept_a_front,
        "back": concept_a_back,
        "cert": concept_a_certificate,
        "font": "PLUS JAKARTA SANS",
        "logic": [
            "Retícula asimétrica ejecutiva con una proporción 65/35.",
            "El bloque azul concentra identidad sin competir con los datos.",
            "Fotografía y nombre dominan la lectura; el verde solo acredita.",
            "El certificado traduce el mismo rigor a una composición editorial.",
        ],
        "palette": [WHITE, NAVY, GREEN, BLUE],
    },
    "B": {
        "title": "CLÁSICO CONTEMPORÁNEO",
        "subtitle": "Solemnidad moderna · equilibrio · permanencia",
        "bg": "#EEEAE2",
        "front": concept_b_front,
        "back": concept_b_back,
        "cert": concept_b_certificate,
        "font": "CORMORANT GARAMOND + PLUS JAKARTA SANS",
        "logic": [
            "Simetría medida y filetes finos evocan documentos de autoridad.",
            "La serif aporta permanencia; la sans ordena la información.",
            "El dorado funciona únicamente como acento de jerarquía.",
            "El certificado prioriza una presencia digna para ser enmarcada.",
        ],
        "palette": [WARM, NAVY, GOLD, GREEN],
    },
    "C": {
        "title": "VEN Y VE CONTEMPORÁNEO",
        "subtitle": "Geometría propia · reconocimiento · energía controlada",
        "bg": "#E7EFF1",
        "front": concept_c_front,
        "back": concept_c_back,
        "cert": concept_c_certificate,
        "font": "OUTFIT",
        "logic": [
            "Los óvalos reales del logo se convierten en una retícula de marca.",
            "Azul y verde generan reconocimiento sin añadir símbolos nuevos.",
            "La composición es dinámica, pero mantiene disciplina institucional.",
            "El certificado conserva el ADN Ven y Ve con sobriedad contemporánea.",
        ],
        "palette": ["#F7FAFC", NAVY, BLUE, GREEN],
    },
}


def board_for(key, concept):
    board = Image.new("RGBA", (1800, 1540), concept["bg"])
    d = ImageDraw.Draw(board)
    d.text((80, 54), f"CONCEPTO {key}", font=sans(16, "Bold"), fill=GREEN)
    d.text((80, 86), concept["title"], font=sans(39, "ExtraBold"), fill=NAVY)
    d.text((80, 140), concept["subtitle"], font=sans(17, "Medium"), fill=MUTED)
    d.text((80, 205), "CARNET — FRENTE", font=sans(13, "Bold"), fill=NAVY)
    d.text((960, 205), "CARNET — REVERSO", font=sans(13, "Bold"), fill=NAVY)
    front = concept["front"]().resize((760, 479), Image.Resampling.LANCZOS)
    back = concept["back"]().resize((760, 479), Image.Resampling.LANCZOS)
    shadowed(board, front, (80, 240))
    shadowed(board, back, (960, 240))
    d.text((80, 780), "CERTIFICADO — US LETTER LANDSCAPE", font=sans(13, "Bold"), fill=NAVY)
    cert = concept["cert"]().resize((870, 672), Image.Resampling.LANCZOS)
    shadowed(board, cert, (80, 815), radius=18, offset=(0, 8), alpha=38)
    d.text((1040, 815), "LÓGICA DE DISEÑO", font=sans(13, "Bold"), fill=NAVY)
    y = 858
    for line in concept["logic"]:
        d.ellipse((1042, y + 7, 1050, y + 15), fill=GREEN)
        wrapped(d, (1070, y), line, sans(16, "Regular"), INK, 620, 6)
        y += 58
    d.text((1040, 1112), "SISTEMA TIPOGRÁFICO", font=sans(11, "Bold"), fill=MUTED)
    d.text((1040, 1140), concept["font"], font=sans(17, "SemiBold"), fill=NAVY)
    d.text((1040, 1205), "PALETA INSTITUCIONAL", font=sans(11, "Bold"), fill=MUTED)
    x = 1040
    for color in concept["palette"]:
        d.rounded_rectangle((x, 1242, x + 92, 1300), radius=10, fill=color, outline="#C7CFD7", width=1)
        x += 112
    d.text((1040, 1333), "Mismos datos · Mismas proporciones · Comparación directa", font=sans(13, "Medium"), fill=MUTED)
    return board


for key, concept in CONCEPTS.items():
    board = board_for(key, concept)
    board.convert("RGB").save(OUT / f"concept-{key.lower()}.jpg", quality=94, subsampling=0)
    concept["front"]().convert("RGB").save(OUT / f"concept-{key.lower()}-card-front.png")
    concept["back"]().convert("RGB").save(OUT / f"concept-{key.lower()}-card-back.png")
    concept["cert"]().convert("RGB").save(OUT / f"concept-{key.lower()}-certificate.png")
    print(OUT / f"concept-{key.lower()}.jpg")