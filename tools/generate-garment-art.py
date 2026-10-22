#!/usr/bin/env python3
"""Generate deterministic, original garment illustrations from the game catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import struct
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src/game/laundry_levels.cpp"
ATLAS_SIZE = 512
CELL = 128
CELLS_PER_ATLAS = 16
SCALE = 2
ART_DIR = ROOT / "artwork/garments"
RUNTIME_DIR = ROOT / "assets/garments"

RECORD = re.compile(
    r'\{"(g\d+_\d+)",\s*"((?:\\.|[^"\\])*)",\s*'
    r'"((?:\\.|[^"\\])*)",\s*"((?:\\.|[^"\\])*)",\s*\n\s*'
    r'Fabric::(\w+),\s*TextileColor::(\w+),\s*GarmentShape::(\w+),\s*'
    r'Stain::(\w+),\s*BleachAllowance::(\w+),\s*\n\s*'
    r'(\d+),\s*(\d+),\s*(\d+),\s*(true|false),\s*(true|false),\s*'
    r'(true|false),\s*(true|false),\s*(true|false),\s*(true|false)\}'
)


@dataclass(frozen=True)
class Garment:
    ident: str
    name: str
    reason: str
    composition: str
    fabric: str
    color: str
    shape: str
    stain: str
    bleach: str
    weight: int
    temperature: int
    spin: int
    valid: bool
    washable: bool
    mesh: bool
    eco: bool
    lightly_used: bool
    baby_sensitive: bool


def decode(value: str) -> str:
    return json.loads('"' + value + '"')


def plain(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(c))


def read_catalog() -> list[Garment]:
    source = SOURCE.read_text(encoding="utf-8")
    result: list[Garment] = []
    for match in RECORD.finditer(source):
        group = match.groups()
        result.append(Garment(
            decode(group[0]), decode(group[1]), decode(group[2]), decode(group[3]),
            group[4], group[5], group[6], group[7], group[8],
            int(group[9]), int(group[10]), int(group[11]),
            *(value == "true" for value in group[12:18]),
        ))
    ids = [item.ident for item in result]
    if len(result) != 92 or len(ids) != len(set(ids)):
        raise SystemExit(f"Catálogo de prendas inesperado: {len(result)} registros únicos (se esperan 92).")
    expected_levels = {f"g{level}_" for level in range(1, 21)}
    if {prefix for prefix in expected_levels if any(i.startswith(prefix) for i in ids)} != expected_levels:
        raise SystemExit("El catálogo no contiene registros para los veinte niveles.")
    expected_shapes = {
        "tee": "top", "blouse": "top", "shirt": "shirt", "polo": "polo",
        "hoodie": "hoodie", "sweatshirt": "top", "trousers": "trousers",
        "sport_trousers": "trousers", "workwear": "top",
        "jeans": "jeans", "shorts": "shorts", "skirt": "skirt", "dress": "dress",
        "nightdress": "dress", "knitwear": "knitwear", "coat": "coat",
        "blazer": "blazer", "linen": "linen", "towel": "towel", "robe": "robe",
        "scarf": "scarf", "hat": "hat", "belt": "belt", "lingerie": "lingerie",
        "bra": "bra", "socks": "socks", "hosiery": "hosiery", "bib": "bib",
        "handkerchief": "handkerchief", "romper": "romper", "pajamas": "pajamas",
        "tracksuit": "tracksuit",
    }
    mismatches = [(item.ident, item.shape, expected_shapes[garment_type(item)])
                  for item in result if item.shape != expected_shapes[garment_type(item)]]
    if mismatches:
        raise SystemExit("Formas del catálogo incoherentes: " + ", ".join(
            f"{ident} ({actual} debe ser {expected})" for ident, actual, expected in mismatches))
    return result


def garment_type(item: Garment) -> str:
    name = plain(item.name)
    rules = (
        (("cinturon",), "belt"), (("babero",), "bib"),
        (("panuelo",), "handkerchief"), (("bufanda",), "scarf"),
        (("gorro",), "hat"), (("sosten", "sujetador"), "bra"),
        (("calcetin", "calcetines"), "socks"),
        (("medias", "pantimedias"), "hosiery"),
        (("albornoz", "bata de bano"), "robe"),
        (("mantel", "manteleria", "sabana", "funda de cojin", "funda de almohada",
          "funda almohada", "mantita", "manta"), "linen"),
        (("toalla", "trapo", "pano de limpieza"), "towel"),
        (("lenceria",), "lingerie"),
        (("ropa de trabajo",), "workwear"),
        (("pantalon corto", "shorts"), "shorts"),
        (("vaquero",), "jeans"),
        (("pantalon deportivo",), "sport_trousers"),
        (("mallas", "pantalon", "leggings"), "trousers"),
        (("pelele", "pijama"), "romper" if "pelele" in name else "pajamas"),
        (("camison",), "nightdress"), (("vestido",), "dress"),
        (("falda",), "skirt"),
        (("americana",), "blazer"), (("anorak", "chaqueta", "abrigo"), "coat"),
        (("sudadera con capucha", "con capucha", "hoodie"), "hoodie"),
        (("chandal",), "tracksuit"), (("sudadera",), "sweatshirt"),
        (("polo",), "polo"), (("camisa",), "shirt"), (("blusa",), "blouse"),
        (("jersey", "lana"), "knitwear"),
        (("camiseta",), "tee"),
    )
    for needles, kind in rules:
        if any(needle in name for needle in needles):
            return kind
    return {
        "top": "tee", "shirt": "shirt", "polo": "polo", "hoodie": "hoodie",
        "trousers": "trousers", "jeans": "jeans", "shorts": "shorts",
        "skirt": "skirt", "dress": "dress", "knitwear": "knitwear",
        "coat": "coat", "blazer": "blazer", "linen": "linen", "towel": "towel",
        "robe": "robe", "scarf": "scarf", "hat": "hat", "belt": "belt",
        "lingerie": "lingerie", "bra": "bra", "socks": "socks", "hosiery": "hosiery",
        "bib": "bib", "handkerchief": "handkerchief", "romper": "romper",
        "pajamas": "pajamas", "tracksuit": "tracksuit",
    }.get(item.shape, "tee")


def palette_for(item: Garment) -> tuple[int, int, int]:
    name = plain(item.name)
    if "blanc" in name:
        base = (231, 229, 219)
    elif "negro" in name or "negra" in name or "oscuro" in name:
        base = (39, 47, 58)
    elif "marino" in name:
        base = (42, 61, 84)
    elif "celeste" in name:
        base = (118, 168, 194)
    elif "azul" in name:
        base = (57, 101, 151)
    elif "rojo" in name or "roja" in name:
        base = (163, 55, 51)
    elif "amarillo" in name:
        base = (205, 171, 53)
    elif "verde" in name:
        base = (78, 112, 72)
    elif "naranja" in name:
        base = (197, 111, 47)
    elif "rosa" in name:
        base = (202, 137, 157)
    elif "beige" in name or "arena" in name:
        base = (185, 161, 122)
    elif "cuero" in name or "piel" in name:
        base = (111, 76, 53)
    elif item.color == "white":
        base = (224, 222, 211)
    elif item.color == "dark":
        base = (43, 55, 69)
    else:
        choices = ((164, 59, 56), (54, 105, 153), (78, 116, 79),
                   (194, 138, 54), (177, 99, 67), (135, 91, 137))
        base = choices[int(hashlib.sha256(item.ident.encode()).hexdigest()[:4], 16) % len(choices)]
    return base


def polygon(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], fill: int = 255) -> None:
    draw.polygon(points, fill=fill)


def render_mask(item: Garment, kind: str, size: int = 256) -> Image.Image:
    scale = size / 256
    def p(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
        return [(round(x * scale), round(y * scale)) for x, y in points]
    def box(values: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        return tuple(round(v * scale) for v in values)  # type: ignore[return-value]
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    if kind in {"tee", "blouse", "shirt", "workwear", "polo", "hoodie", "sweatshirt",
                "knitwear", "coat", "blazer", "robe"}:
        if kind in {"hoodie", "sweatshirt", "knitwear", "coat", "blazer", "robe", "workwear"}:
            polygon(d, p([(82, 39), (105, 27), (128, 42), (151, 27), (174, 39), (215, 54),
                          (237, 166), (204, 176), (181, 104), (181, 225), (75, 225),
                          (75, 104), (52, 176), (19, 166), (41, 54)]))
        elif kind in {"shirt", "blouse"}:
            polygon(d, p([(83, 36), (104, 26), (152, 26), (173, 36), (212, 59),
                          (231, 133), (204, 145), (183, 105), (180, 224), (76, 224),
                          (73, 105), (52, 145), (25, 133), (44, 59)]))
        elif kind == "polo":
            polygon(d, p([(83, 36), (104, 26), (152, 26), (173, 36), (211, 62),
                          (194, 112), (180, 101), (180, 224), (76, 224), (76, 101),
                          (62, 112), (45, 62)]))
        else:
            polygon(d, p([(81, 39), (105, 28), (151, 28), (175, 39), (218, 67),
                          (196, 113), (181, 102), (181, 223), (75, 223), (75, 102),
                          (60, 113), (38, 67)]))
        if kind == "hoodie":
            d.ellipse(box((99, 18, 157, 84)), fill=255)
            d.rectangle(box((104, 39, 152, 78)), fill=0)
    elif kind in {"trousers", "sport_trousers", "jeans", "shorts"}:
        if kind == "shorts":
            polygon(d, p([(76, 37), (180, 37), (185, 107), (174, 163), (133, 155),
                          (128, 100), (122, 155), (81, 163), (71, 107)]))
        else:
            polygon(d, p([(76, 31), (180, 31), (176, 101), (160, 226), (128, 224),
                          (126, 107), (121, 224), (88, 226), (72, 101)]))
    elif kind == "tracksuit":
        polygon(d, p([(39, 44), (59, 34), (80, 45), (101, 34), (120, 44),
                      (135, 57), (143, 123), (124, 129), (113, 91), (113, 140),
                      (46, 140), (46, 91), (35, 129), (16, 123), (25, 57)]))
        polygon(d, p([(145, 42), (216, 42), (212, 101), (197, 222), (169, 222),
                      (165, 109), (161, 222), (134, 222), (145, 101)]))
    elif kind == "skirt":
        polygon(d, p([(92, 37), (164, 37), (190, 72), (219, 221), (37, 221), (66, 72)]))
    elif kind == "nightdress":
        polygon(d, p([(95, 29), (107, 32), (111, 82), (145, 82), (149, 32), (161, 29),
                      (171, 93), (202, 222), (54, 222), (85, 93)]))
    elif kind == "dress":
        polygon(d, p([(96, 28), (115, 36), (141, 36), (160, 28), (166, 89),
                      (184, 103), (214, 224), (42, 224), (72, 103), (90, 89)]))
    elif kind == "linen":
        d.rounded_rectangle(box((45, 39, 211, 218)), radius=round(14 * scale), fill=255)
        polygon(d, p([(46, 69), (112, 81), (209, 55), (209, 89), (117, 115), (46, 102)]))
    elif kind == "towel":
        d.rounded_rectangle(box((65, 28, 191, 228)), radius=round(17 * scale), fill=255)
    elif kind == "scarf":
        polygon(d, p([(88, 32), (151, 36), (176, 62), (137, 100), (183, 142),
                      (161, 182), (109, 216), (68, 199), (116, 163), (74, 123),
                      (98, 89), (66, 62)]))
    elif kind == "hat":
        d.ellipse(box((70, 43, 186, 193)), fill=255)
        d.rounded_rectangle(box((62, 142, 194, 190)), radius=round(18 * scale), fill=255)
        d.ellipse(box((112, 20, 144, 52)), fill=255)
    elif kind == "belt":
        polygon(d, p([(39, 117), (194, 117), (216, 136), (194, 155), (39, 155)]))
        d.rounded_rectangle(box((148, 101, 202, 171)), radius=round(8 * scale), fill=255)
        d.rectangle(box((158, 111, 192, 161)), fill=0)
    elif kind == "bra":
        d.rounded_rectangle(box((44, 102, 212, 172)), radius=round(18 * scale), fill=255)
        d.ellipse(box((59, 74, 132, 146)), fill=255)
        d.ellipse(box((124, 74, 197, 146)), fill=255)
    elif kind == "hosiery":
        polygon(d, p([(76, 38), (125, 38), (126, 147), (112, 193), (81, 207),
                      (62, 194), (82, 167)]))
        polygon(d, p([(139, 38), (188, 38), (174, 167), (194, 194), (175, 207),
                      (144, 193), (130, 147)]))
    elif kind == "socks":
        polygon(d, p([(68, 43), (119, 43), (116, 126), (108, 145), (83, 154),
                      (55, 148), (57, 132), (74, 123)]))
        polygon(d, p([(137, 43), (188, 43), (182, 123), (199, 132), (201, 148),
                      (173, 154), (148, 145), (140, 126)]))
    elif kind == "lingerie":
        if "braga" in plain(item.name) or "panty" in plain(item.name):
            polygon(d, p([(59, 62), (197, 62), (184, 193), (147, 218), (128, 157),
                          (109, 218), (72, 193)]))
        else:
            polygon(d, p([(58, 109), (198, 109), (188, 175), (68, 175)]))
            d.ellipse(box((63, 64, 127, 133)), fill=255)
            d.ellipse(box((129, 64, 193, 133)), fill=255)
    elif kind == "bib":
        d.ellipse(box((92, 24, 164, 95)), fill=255)
        polygon(d, p([(89, 79), (167, 79), (194, 111), (181, 218), (75, 218), (62, 111)]))
    elif kind == "handkerchief":
        polygon(d, p([(62, 52), (190, 35), (218, 179), (78, 217)]))
        polygon(d, p([(62, 52), (139, 119), (78, 217)]))
    elif kind == "romper":
        polygon(d, p([(87, 34), (111, 28), (145, 28), (169, 34), (196, 77),
                      (180, 116), (173, 174), (163, 220), (135, 220), (128, 153),
                      (121, 220), (93, 220), (83, 174), (76, 116), (60, 77)]))
    elif kind == "pajamas":
        polygon(d, p([(40, 50), (59, 40), (78, 53), (100, 60), (113, 121),
                      (93, 128), (78, 84), (78, 145), (117, 145), (115, 223),
                      (91, 223), (83, 171), (76, 223), (54, 223), (57, 119),
                      (50, 84), (35, 128), (15, 121), (27, 60)]))
        polygon(d, p([(139, 54), (207, 54), (200, 103), (183, 217), (150, 217),
                      (152, 111), (146, 217), (118, 217), (127, 103)]))
    else:
        d.rounded_rectangle(box((66, 49, 190, 211)), radius=round(16 * scale), fill=255)
    return mask


def lighten(rgb: tuple[int, int, int], amount: int) -> tuple[int, int, int, int]:
    return tuple(max(0, min(255, c + amount)) for c in rgb) + (255,)  # type: ignore[return-value]


def render_garment(item: Garment) -> Image.Image:
    size = 256
    kind = garment_type(item)
    mask = render_mask(item, kind, size)
    seed = int(hashlib.sha256(item.ident.encode("ascii")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    base = palette_for(item)
    # Cloth uses broad directional lighting plus restrained deterministic weave noise.
    pixels = bytearray(size * size * 3)
    for y in range(size):
        for x in range(size):
            center_light = max(0.0, 1.0 - abs(x - 116) / 150.0) * 0.10
            vertical_light = 0.77 + 0.22 * (1.0 - y / (size * 1.25))
            noise = rng.randrange(-12, 13) / 255.0
            fold = 0.065 * math.sin((x + seed % 23) * 0.072 + y * 0.018)
            fold += 0.045 * math.sin(y * 0.091 - x * 0.027 + seed % 17)
            weave = 0.0
            if item.fabric == "cotton":
                weave = 0.012 * math.sin(x * 1.7 + seed % 9) * math.sin(y * 1.5)
            elif item.fabric == "denim":
                weave = -0.035 if (x + 2 * y + seed) % 7 == 0 else 0.008
            elif item.fabric == "wool":
                weave = 0.022 * math.sin((x + y + seed % 11) * 0.72)
            elif item.fabric == "silk":
                highlight = math.exp(-((x - (112 + seed % 13)) / 18.0) ** 2)
                weave = 0.11 * highlight * (0.55 + 0.45 * math.sin(y * 0.035 + seed % 7))
            elif item.fabric == "leather":
                highlight = math.exp(-((x - 102) / 15.0) ** 2)
                weave = 0.075 * highlight - 0.018 * math.sin(y * 0.14 + seed % 5)
            elif item.fabric in {"synthetic", "sport", "down"}:
                weave = 0.018 * math.sin((x - y + seed % 17) * 0.42)
            shade = max(0.58, min(1.22, vertical_light + center_light + fold + noise + weave))
            i = (y * size + x) * 3
            pixels[i] = min(255, int(base[0] * shade))
            pixels[i + 1] = min(255, int(base[1] * shade))
            pixels[i + 2] = min(255, int(base[2] * shade))
    fabric = Image.frombytes("RGB", (size, size), bytes(pixels)).convert("RGBA")
    if "transparente" in plain(item.name):
        fabric.putalpha(mask.point(lambda alpha: round(alpha * 0.74)))
    else:
        fabric.putalpha(mask)

    shadow_alpha = mask.filter(ImageFilter.GaussianBlur(8)).point(lambda a: round(a * 0.34))
    shadow = Image.new("RGBA", (size, size), (22, 33, 42, 0))
    shadow.putalpha(shadow_alpha)
    shadow = ImageChops.offset(shadow, 2, 5)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.alpha_composite(shadow)
    result.alpha_composite(fabric)

    detail = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(detail)
    hi = lighten(base, 42)
    low = lighten(base, -54)
    seam = lighten(base, -30)
    def line(points: list[tuple[int, int]], fill: tuple[int, int, int, int], width: int = 2) -> None:
        d.line(points, fill=fill, width=width, joint="curve")
    def poly_detail(points: list[tuple[int, int]], fill: tuple[int, int, int, int]) -> None:
        d.polygon(points, fill=fill)

    if kind in {"tee", "blouse", "shirt", "workwear", "polo", "hoodie", "sweatshirt",
                "knitwear", "coat", "blazer", "robe"}:
        line([(83, 50), (106, 40), (128, 55), (150, 40), (173, 50)], low, 2)
        line([(75, 104), (78, 218)], seam, 2); line([(181, 104), (178, 218)], hi, 2)
        line([(81, 216), (176, 216)], hi, 3)
        if kind in {"hoodie", "sweatshirt", "knitwear", "coat", "blazer", "robe", "workwear"}:
            line([(43, 61), (52, 113), (28, 162)], seam, 2)
            line([(213, 61), (204, 113), (228, 162)], hi, 2)
            line([(22, 158), (51, 166)], low, 3); line([(205, 166), (234, 158)], hi, 3)
        else:
            line([(54, 67), (72, 106)], seam, 2); line([(202, 67), (184, 106)], hi, 2)
        if kind in {"shirt", "blouse", "workwear"}:
            poly_detail([(107, 42), (128, 57), (117, 81), (99, 61)], hi)
            poly_detail([(149, 42), (128, 57), (139, 81), (157, 61)], seam)
            line([(128, 58), (128, 214)], low, 2)
            for yy in (91, 119, 147, 175):
                d.ellipse((125, yy, 131, yy + 6), fill=(224, 220, 203, 220))
            d.rectangle((147, 115, 164, 150), outline=hi, width=2)
            if kind == "workwear":
                line([(100, 120), (116, 120), (116, 151), (100, 151), (100, 120)], seam, 2)
        elif kind == "polo":
            poly_detail([(106, 40), (128, 59), (115, 78), (100, 57)], hi)
            poly_detail([(150, 40), (128, 59), (141, 78), (157, 57)], seam)
            line([(128, 59), (128, 104)], low, 2)
            for yy in (75, 88): d.ellipse((125, yy, 130, yy + 5), fill=(230, 228, 214, 220))
        elif kind == "hoodie":
            d.arc((98, 17, 158, 91), 200, 340, fill=hi, width=4)
            line([(101, 155), (105, 145), (151, 145), (155, 155), (151, 181), (105, 181), (101, 155)], seam, 3)
            line([(113, 75), (112, 113)], hi, 2); line([(143, 75), (144, 113)], hi, 2)
            line([(32, 129), (57, 137)], seam, 3); line([(200, 137), (224, 129)], hi, 3)
        elif kind == "sweatshirt":
            d.arc((106, 24, 150, 59), 0, 180, fill=hi, width=4)
            line([(29, 132), (53, 138)], seam, 3); line([(203, 138), (227, 132)], hi, 3)
            line([(78, 217), (178, 217)], seam, 3)
        elif kind == "robe":
            line([(104, 47), (128, 72), (153, 47)], hi, 3)
            line([(94, 128), (162, 128)], seam, 3)
            d.rounded_rectangle((106, 122, 150, 132), radius=4, outline=hi, width=2)
        else:
            # Fine wrinkles catch light without imposing a printed graphic.
            for i in range(3):
                x = 91 + i * 29 + seed % 7
                line([(x, 113), (x - 7, 144), (x + 3, 171)], (255, 255, 255, 38), 3)
    if kind == "tracksuit":
        line([(41, 49), (79, 61), (117, 48)], low, 2)
        line([(79, 61), (79, 133)], hi, 2)
        line([(28, 59), (37, 91), (24, 119)], seam, 2)
        line([(126, 59), (137, 91), (131, 119)], hi, 2)
        line([(48, 138), (111, 138)], hi, 3)
        line([(22, 117), (37, 123)], low, 2); line([(124, 123), (140, 117)], hi, 2)
        line([(151, 55), (161, 210)], hi, 3)
        line([(204, 55), (186, 210)], seam, 2)
        line([(144, 218), (163, 218)], hi, 3)
        line([(171, 218), (197, 218)], hi, 3)
    if kind in {"trousers", "sport_trousers", "jeans", "shorts"}:
        line([(78, 39), (128, 54), (178, 39)], low, 2)
        line([(128, 53), (125, 101)], seam, 2)
        line([(80, 104), (93, 219)], hi, 2); line([(176, 104), (161, 219)], hi, 2)
        line([(91, 219), (119, 219)], hi, 3); line([(135, 219), (162, 219)], hi, 3)
        d.polygon([(84, 64), (110, 69), (106, 93), (82, 87)], outline=hi)
        d.polygon([(145, 69), (171, 64), (174, 87), (150, 93)], outline=hi)
        d.ellipse((124, 45, 132, 53), fill=(214, 200, 158, 230))
        if kind == "jeans":
            line([(92, 105), (102, 135), (110, 105)], hi, 2)
            line([(164, 105), (154, 135), (146, 105)], hi, 2)
            for yy in range(52, 215, 7):
                line([(119, yy), (119, yy + 2)], (215, 200, 165, 155), 1)
        if kind == "shorts":
            line([(75, 155), (122, 160)], hi, 2); line([(133, 160), (181, 155)], hi, 2)
        if kind == "sport_trousers":
            line([(77, 85), (96, 207)], (236, 240, 242, 180), 4)
            line([(179, 85), (159, 207)], (236, 240, 242, 180), 4)
    if kind in {"skirt", "dress", "nightdress"}:
        line([(93, 39), (163, 39)], hi, 3)
        line([(81, 81), (54, 215)], (255, 255, 255, 70), 3)
        line([(175, 81), (202, 215)], low, 2)
        for xx in (91, 111, 145, 165): line([(xx, 97), (xx + (xx - 128)//10, 205)], (255, 255, 255, 42), 3)
        if kind == "dress":
            line([(109, 39), (128, 60), (147, 39)], hi, 2)
            line([(89, 103), (167, 103)], seam, 2)
        if kind == "nightdress":
            line([(98, 32), (93, 70)], hi, 3); line([(158, 32), (163, 70)], hi, 3)
            line([(104, 75), (151, 75)], (255, 255, 255, 58), 2)
    if kind == "knitwear":
        d.arc((108, 29, 148, 63), 0, 180, fill=hi, width=4)
        line([(83, 214), (173, 214)], seam, 3)
        for x in range(82, 174, 8):
            line([(x, 211), (x, 218)], hi, 1)
        for y in (123, 133, 143):
            line([(28, y), (53, y + 5)], seam, 2)
            line([(202, y + 5), (228, y)], hi, 2)
    if kind in {"coat", "blazer"}:
        poly_detail([(106, 39), (128, 57), (117, 87), (98, 61)], hi)
        poly_detail([(150, 39), (128, 57), (139, 87), (158, 61)], seam)
        line([(128, 59), (128, 218)], low, 3)
        for yy in (100, 136, 172, 204):
            d.ellipse((123, yy, 132, yy + 9), fill=(218, 206, 175, 235))
        if item.fabric == "down":
            for yy in (83, 115, 149, 184):
                line([(80, yy), (176, yy)], (235, 240, 244, 90), 2)
            for xx in (93, 160): line([(xx, 54), (xx - 4, 210)], seam, 2)
        if "americana" in plain(item.name):
            d.polygon([(91, 89), (116, 99), (110, 135), (86, 127)], outline=hi)
            d.polygon([(140, 99), (165, 89), (170, 127), (146, 135)], outline=hi)
    if kind == "robe":
        poly_detail([(104, 42), (128, 65), (116, 101), (88, 60)], hi)
        poly_detail([(152, 42), (128, 65), (141, 101), (169, 60)], seam)
        line([(127, 65), (123, 213)], low, 3); line([(134, 65), (140, 213)], hi, 2)
        line([(91, 135), (166, 135)], seam, 4)
        d.rounded_rectangle((108, 127, 150, 143), radius=5, outline=hi, width=2)
    if kind in {"linen", "towel"}:
        line([(54, 77), (112, 91), (202, 66)], hi, 3)
        line([(55, 197), (195, 197)], seam, 2)
        for x in range(73, 190, 10):
            line([(x, 203), (x + 3, 210)], (255, 255, 255, 48), 1)
        if kind == "towel":
            for yy in range(82, 190, 12):
                for xx in range(78, 180, 12):
                    d.ellipse((xx, yy, xx + 3, yy + 3), fill=(255, 255, 255, 48))
        if "mantel" in plain(item.name):
            for x in range(55, 205, 8):
                d.ellipse((x, 218, x + 4, 222), fill=hi)
    if kind == "scarf":
        line([(89, 46), (122, 83), (99, 119), (151, 161), (125, 199)], hi, 4)
        for x in (78, 88, 98, 108): line([(x, 194), (x - 6, 222)], seam, 2)
    if kind == "hat":
        d.arc((75, 40, 181, 177), 180, 360, fill=hi, width=4)
        line([(66, 158), (190, 158)], seam, 4)
        for x in range(86, 180, 10): line([(x, 112), (x + 3, 145)], (255, 255, 255, 50), 2)
    if kind == "belt":
        d.rounded_rectangle((150, 109, 200, 164), radius=7, outline=(207, 180, 120, 255), width=5)
        for x in (82, 99, 116, 133): d.ellipse((x, 133, x + 6, 139), fill=(39, 30, 24, 210))
        line([(43, 119), (150, 119)], hi, 2); line([(43, 153), (150, 153)], low, 2)
    if kind in {"bra", "lingerie", "hosiery", "socks"}:
        if kind == "bra" or "sosten" in plain(item.name):
            d.arc((69, 73, 129, 137), 180, 360, fill=hi, width=3)
            d.arc((127, 73, 187, 137), 180, 360, fill=hi, width=3)
            line([(79, 107), (66, 46)], seam, 3); line([(177, 107), (190, 46)], seam, 3)
            line([(84, 159), (172, 159)], hi, 2)
        elif kind == "hosiery":
            line([(84, 44), (119, 156), (81, 196)], hi, 3)
            line([(146, 44), (170, 158), (188, 196)], seam, 3)
            line([(79, 49), (119, 49)], hi, 4); line([(141, 49), (185, 49)], hi, 4)
        elif kind == "socks":
            line([(69, 57), (117, 57)], hi, 4); line([(138, 57), (187, 57)], hi, 4)
            for x in (77, 86, 95, 104, 146, 155, 164, 173):
                line([(x, 61), (x + 1, 83)], (255, 255, 255, 46), 2)
            d.arc((57, 130, 112, 158), 190, 350, fill=hi, width=3)
            d.arc((143, 130, 198, 158), 190, 350, fill=hi, width=3)
        else:
            d.arc((70, 73, 128, 140), 180, 350, fill=hi, width=3)
            d.arc((128, 73, 186, 140), 190, 360, fill=hi, width=3)
            line([(74, 178), (182, 178)], seam, 2)
    if kind == "bib":
        d.ellipse((93, 27, 163, 97), outline=hi, width=4)
        d.ellipse((101, 33, 155, 89), outline=seam, width=2)
        d.rounded_rectangle((104, 128, 152, 178), radius=9, outline=hi, width=3)
    if kind == "handkerchief":
        line([(70, 62), (140, 118), (82, 207)], hi, 3)
        d.arc((156, 61, 199, 103), 10, 170, fill=(229, 211, 157, 220), width=3)
    if kind == "romper":
        line([(100, 43), (128, 57), (155, 43)], hi, 3)
        line([(128, 58), (128, 148)], seam, 2)
        for yy in (83, 108, 133): d.ellipse((125, yy, 131, yy + 6), fill=(228, 218, 193, 220))
        d.arc((89, 164, 128, 222), 190, 350, fill=hi, width=3)
        d.arc((128, 164, 167, 222), 190, 350, fill=hi, width=3)
    if kind == "pajamas":
        line([(50, 52), (73, 66), (87, 102)], hi, 3)
        line([(146, 59), (177, 59), (172, 91)], seam, 2)

    # Texture marks remain clipped to the actual garment silhouette.
    if item.fabric == "wool":
        for y in range(83, 207, 8):
            for x in range(83 + (y // 8 % 2) * 4, 174, 9):
                d.arc((x, y, x + 7, y + 5), 0, 180, fill=(255, 255, 255, 33), width=1)
    if item.fabric == "denim":
        for y in range(84, 212, 8):
            d.line((91, y, 95, y + 4), fill=(255, 255, 255, 24), width=1)
    if "encaje" in plain(item.composition) or item.fabric == "delicate":
        for y in range(78, 211, 13):
            for x in range(72 + ((y // 13) % 2) * 7, 190, 14):
                d.ellipse((x, y, x + 7, y + 7), outline=(255, 255, 255, 86), width=1)
                d.ellipse((x + 2, y + 2, x + 5, y + 5), fill=(35, 40, 47, 36))
    detail.putalpha(ImageChops.multiply(detail.getchannel("A"), mask))
    result.alpha_composite(detail)

    normalized = plain(item.name)
    if "rayas" in normalized:
        stripe = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stripe)
        for yy in (83, 111, 139, 167, 195):
            sd.line((73, yy, 183, yy), fill=(57, 100, 150, 178), width=8)
        stripe.putalpha(ImageChops.multiply(stripe.getchannel("A"), mask))
        result.alpha_composite(stripe)

    if item.stain != "none":
        stain_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stain_layer)
        stain_color = {
            "oil": (90, 72, 44, 150), "blood": (125, 38, 40, 175),
            "mud": (108, 77, 49, 180), "wine": (112, 38, 66, 175),
        }.get(item.stain, (100, 70, 50, 160))
        sx = 92 + seed % 73
        sy = 91 + (seed >> 4) % 75
        sd.ellipse((sx - 16, sy - 12, sx + 17, sy + 13), fill=stain_color)
        stain_layer = stain_layer.filter(ImageFilter.GaussianBlur(2))
        stain_layer.putalpha(ImageChops.multiply(stain_layer.getchannel("A"), mask))
        result.alpha_composite(stain_layer)

    return result.resize((CELL, CELL), Image.Resampling.LANCZOS)


def generated_files(items: list[Garment]) -> dict[Path, bytes]:
    atlases: list[Image.Image] = []
    sprites: list[Image.Image] = []
    mapping: list[tuple[Garment, int, int, int]] = []
    manifest_items: list[dict] = []
    for index, item in enumerate(items):
        atlas_index, slot = divmod(index, CELLS_PER_ATLAS)
        if slot == 0:
            atlases.append(Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0)))
        x, y = (slot % 4) * CELL, (slot // 4) * CELL
        sprite = render_garment(item)
        sprites.append(sprite)
        atlases[atlas_index].alpha_composite(sprite, (x, y))
        mapping.append((item, atlas_index, x, y))
        manifest_items.append({
            "id": item.ident, "name": item.name, "reason": item.reason,
            "type": garment_type(item), "fabric": item.fabric,
            "composition": item.composition, "color": item.color,
            "shape": item.shape, "weightGrams": item.weight,
            "care": {"machineWashable": item.washable,
                     "maxTemperatureC": item.temperature, "maxSpinRpm": item.spin,
                     "bleach": item.bleach, "mesh": item.mesh},
            "atlas": atlas_index, "x": x, "y": y, "width": CELL, "height": CELL,
        })

    outputs: dict[Path, bytes] = {}
    atlas_names: list[str] = []
    for index, atlas in enumerate(atlases):
        stem = f"garment-atlas-{index + 1:02d}"
        png_name = stem + ".png"
        raw_name = stem + ".rgba"
        atlas_names.append(png_name)
        png_path = ART_DIR / png_name
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        outputs[png_path] = png_bytes(atlas)
        outputs[RUNTIME_DIR / raw_name] = struct.pack("<II", ATLAS_SIZE, ATLAS_SIZE) + atlas.tobytes()

    preview = render_contact_sheet(items, sprites)
    outputs[ART_DIR / "catalog-preview.png"] = png_bytes(preview)
    outputs[ART_DIR / "manifest.json"] = (json.dumps({
        "schema": "taller-colada-garment-art-v1",
        "generator": "tools/generate-garment-art.py",
        "spriteSize": CELL,
        "atlasSize": ATLAS_SIZE,
        "atlasFiles": atlas_names,
        "items": manifest_items,
    }, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    outputs[ROOT / "src/game/garment_sprites.hpp"] = render_header(mapping).encode("utf-8")
    return outputs


def png_bytes(image: Image.Image) -> bytes:
    from io import BytesIO
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_contact_sheet(items: list[Garment], sprites: list[Image.Image]) -> Image.Image:
    from PIL import ImageFont
    columns, cell_w, cell_h = 8, 190, 170
    rows = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (236, 241, 244))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 12)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 10)
    except OSError:
        font = small = ImageFont.load_default()
    for index, item in enumerate(items):
        col, row = index % columns, index // columns
        left, top = col * cell_w, row * cell_h
        draw.rounded_rectangle((left + 6, top + 6, left + cell_w - 6, top + cell_h - 6),
                               radius=10, fill=(255, 255, 255), outline=(208, 219, 225), width=1)
        art = sprites[index].resize((112, 112), Image.Resampling.LANCZOS)
        sheet.paste(art, (left + (cell_w - 112) // 2, top + 8), art)
        draw.text((left + 12, top + 124), item.ident, font=small, fill=(37, 94, 117))
        label = item.name
        if len(label) > 27:
            label = label[:25] + "…"
        draw.text((left + 12, top + 141), label, font=font, fill=(28, 46, 58))
    return sheet


def render_header(mapping: list[tuple[Garment, int, int, int]]) -> str:
    lines = [
        "// Generated by tools/generate-garment-art.py; do not edit by hand.",
        "#pragma once", "", "#include <array>", "#include <cstddef>", "#include <cstdint>", "#include <string_view>", "",
        "namespace hui::game", "{",
        "struct GarmentSprite { std::string_view id; std::uint8_t atlas; std::uint16_t x; std::uint16_t y; };",
        "inline constexpr std::size_t kGarmentAtlasCount = 6;",
        f"inline constexpr std::array<GarmentSprite, {len(mapping)}> kGarmentSprites = {{{{",
    ]
    for item, atlas, x, y in mapping:
        lines.append(f'    {{"{item.ident}", {atlas}, {x}, {y}}},')
    lines += [
        "}};", "",
        "inline const GarmentSprite *find_garment_sprite(std::string_view id)", "{",
        "    for (const GarmentSprite &sprite : kGarmentSprites)",
        "        if (sprite.id == id)",
        "            return &sprite;",
        "    return nullptr;", "}", "", "} // namespace hui::game", "",
    ]
    return "\n".join(lines)


def apply(outputs: dict[Path, bytes], check: bool) -> None:
    stale: list[Path] = []
    for path, expected in outputs.items():
        if not path.is_file() or path.read_bytes() != expected:
            stale.append(path)
    if check:
        if stale:
            raise SystemExit("Ilustraciones de prendas desactualizadas: " + ", ".join(
                str(path.relative_to(ROOT)) for path in stale))
        print(f"Arte de prendas sincronizado: 92 ilustraciones, {len(list((ART_DIR).glob('garment-atlas-*.png')))} atlas.")
        return
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(content)
        temp.replace(path)
    print(f"Generadas 92 ilustraciones textiles en {len([p for p in outputs if p.suffix == '.png']) - 1} atlas; catálogo, sprites C++ y recursos RGBA sincronizados.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verifica recursos ya generados sin modificarlos")
    args = parser.parse_args()
    apply(generated_files(read_catalog()), args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
