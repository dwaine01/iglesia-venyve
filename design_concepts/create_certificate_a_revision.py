from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).parent
OUT = ROOT / "boards"
OUT.mkdir(exist_ok=True)
LOGO = Image.open("/app/frontend/public/assets/membership/church-logo.png").convert("RGBA")
LOGO = LOGO.crop(LOGO.getbbox())
QR = Image.open(ROOT / "verification-qr.png").convert("RGB")

NAVY = "#0B1D3A"
GREEN = "#57C62F"
TEAL = "#079DBC"
INK = "#101A2B"
MUTED = "#5B6878"
PAPER = "#FBFAF5"
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


def certificate():
    page = Image.new("RGBA", (1320, 1020), PAPER)
    draw = ImageDraw.Draw(page)
    control_x = 870

    draw.rectangle((control_x, 0, 1320, 1020), fill=NAVY)
    draw.rectangle((control_x, 0, control_x + 9, 1020), fill=GREEN)
    draw.rectangle((24, 24, 1296, 996), outline=NAVY, width=3)
    draw.rectangle((24, 24, 390, 31), fill=GREEN)

    logo = contain(LOGO, (175, 132))
    page.alpha_composite(logo, (70, 55))
    draw.text((268, 82), "PRIMERA IGLESIA DEL NAZARENO", font=font(19, "Bold"), fill=NAVY)
    draw.text((268, 119), "VEN Y VE", font=font(34, "ExtraBold"), fill=NAVY)
    draw.line((268, 166, 786, 166), fill="#C8D2DC", width=2)

    draw.text((70, 235), "RECONOCIMIENTO INSTITUCIONAL", font=font(14, "Bold"), fill="#157A49")
    draw.text((70, 284), "CERTIFICADO", font=font(66, "ExtraBold"), fill=NAVY)
    draw.text((70, 354), "DE MEMBRESÍA", font=font(66, "ExtraBold"), fill=NAVY)
    draw.line((70, 445, 790, 445), fill="#CBD4DC", width=2)

    draw.text((70, 492), "Se certifica que", font=font(19, "Medium"), fill=MUTED)
    draw.text((70, 539), "María Fernanda Rodríguez", font=font(47, "ExtraBold"), fill=TEAL)
    draw.text(
        (70, 612),
        "es miembro activo de la Primera Iglesia del Nazareno Ven y Ve, reconocido(a)",
        font=font(15, "Regular"),
        fill=INK,
    )
    draw.text((70, 640), "dentro de nuestra comunidad de fe, comunión y servicio.", font=font(15, "Regular"), fill=INK)

    draw.line((70, 835, 520, 835), fill=NAVY, width=2)
    draw.text((122, 850), "[PLACEHOLDER FIRMA PASTORA]", font=font(14, "SemiBold"), fill=INK)
    draw.text((224, 883), "PASTORA PRINCIPAL", font=font(10, "Bold"), fill=MUTED)

    draw.text((930, 70), "CERTIFICACIÓN", font=font(13, "Bold"), fill="#9FE3C4")
    draw.text((930, 98), "OFICIAL", font=font(29, "ExtraBold"), fill=WHITE)
    draw.line((930, 153, 1245, 153), fill="#425571", width=2)

    labels = [
        ("NÚMERO OFICIAL", "VV-0284"),
        ("MIEMBRO DESDE", "05-18-2014"),
        ("FECHA DE EMISIÓN", "09-22-2026"),
    ]
    y = 208
    for label, value in labels:
        draw.text((930, y), label, font=font(11, "Bold"), fill="#9BACBF")
        draw.text((930, y + 28), value, font=font(21, "Bold"), fill=WHITE)
        y += 92

    qr = QR.resize((235, 235), Image.Resampling.NEAREST)
    draw.rounded_rectangle((930, 520, 1177, 767), radius=8, fill=WHITE)
    page.paste(qr, (936, 526))
    draw.text((930, 790), "VERIFICACIÓN DE MEMBRESÍA", font=font(10, "Bold"), fill=WHITE)
    draw.text((930, 817), "Escanee para validar autenticidad", font=font(11, "Regular"), fill="#BECADA")
    draw.text((930, 930), "PRIMERA IGLESIA DEL NAZARENO", font=font(9, "Bold"), fill="#91A3B8")
    draw.text((930, 952), "VEN Y VE", font=font(13, "Bold"), fill=WHITE)
    return page


def presentation_board(document):
    board = Image.new("RGBA", (1600, 1200), "#E8EDF1")
    draw = ImageDraw.Draw(board)
    draw.text((90, 58), "CONCEPTO A · CERTIFICADO REVISADO", font=font(18, "Bold"), fill="#157A49")
    draw.text((90, 94), "INSTITUCIONAL CONTEMPORÁNEO", font=font(42, "ExtraBold"), fill=NAVY)
    draw.text((90, 151), "Logo ampliado · nombre institucional completo · retícula 65/35", font=font(18, "Medium"), fill=MUTED)

    preview = document.resize((1320, 1020), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", board.size, (0, 0, 0, 0))
    shadow.paste((7, 21, 38, 42), (150, 234), Image.new("L", preview.size, 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    board.alpha_composite(shadow)
    board.alpha_composite(preview, (140, 210))
    return board


document = certificate()
document.convert("RGB").save(OUT / "concept-a-certificate-revision.png")
presentation_board(document).convert("RGB").save(OUT / "concept-a-certificate-revision-board.jpg", quality=95, subsampling=0)
print(OUT / "concept-a-certificate-revision-board.jpg")