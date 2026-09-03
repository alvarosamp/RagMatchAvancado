from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


REFERENCE = Path(r"C:\Users\vish8\Downloads\papel_timbrado.docx")
OUTPUT = Path(r"C:\Users\vish8\OneDrive\Documentos\RagMatchAvan-ado\backend\app\templates\documents")
DPI = 150


def load_images() -> tuple[Image.Image, Image.Image]:
    with ZipFile(REFERENCE) as package:
        header = Image.open(BytesIO(package.read("word/media/image1.png"))).convert("RGB")
        footer = Image.open(BytesIO(package.read("word/media/image2.png"))).convert("RGB")
    return header, footer


def build(name: str, width_inches: float, height_inches: float) -> None:
    page_width = round(width_inches * DPI)
    page_height = round(height_inches * DPI)
    graphic_width = round(6.9 * DPI)
    header, footer = load_images()
    header_height = round(graphic_width * header.height / header.width)
    footer_height = round(graphic_width * footer.height / footer.width)
    header = header.resize((graphic_width, header_height), Image.Resampling.LANCZOS)
    footer = footer.resize((graphic_width, footer_height), Image.Resampling.LANCZOS)

    page = Image.new("RGB", (page_width, page_height), "white")
    left = (page_width - graphic_width) // 2
    page.paste(header, (left, 0))
    page.paste(footer, (left, page_height - footer_height))
    page.save(OUTPUT / name, format="PNG", optimize=True, dpi=(DPI, DPI))


build("papel_timbrado_fundo_a4.png", 8.27, 11.69)
build("papel_timbrado_fundo_carta.png", 8.5, 11.0)
