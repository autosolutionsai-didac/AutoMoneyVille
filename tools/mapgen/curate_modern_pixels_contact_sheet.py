"""Contact-sheet rendering for the local licensed authoring cache."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tools.mapgen import curate_modern_pixels_v2 as curation


def write_contact_sheet(
    output: Path,
    root: Path,
    source_records: list[dict],
    prop_records: list[dict],
) -> None:
    font = ImageFont.load_default()
    cards = []
    for record in source_records:
        if record.get("source_scope") == "project":
            continue
        image = curation._open_png(
            curation._safe_source(root, record["relative_path"])
        )
        image.thumbnail((144, 96), Image.Resampling.NEAREST)
        cards.append((record["source_id"], image))
    props = {record["asset_key"]: record for record in prop_records}
    frames = json.loads((output / "props.json").read_text(encoding="utf-8"))[
        "frames"
    ]
    for key in sorted(props):
        with Image.open(output / "props.png") as atlas:
            frame = frames[key]["frame"]
            image = atlas.crop(
                (
                    frame["x"],
                    frame["y"],
                    frame["x"] + frame["w"],
                    frame["y"] + frame["h"],
                )
            )
        image.thumbnail((144, 96), Image.Resampling.NEAREST)
        cards.append((key.removeprefix("prop."), image))
    columns, card_width, card_height, header = 5, 176, 132, 42
    rows = math.ceil(len(cards) / columns)
    sheet = Image.new(
        "RGBA",
        (columns * card_width, header + rows * card_height),
        (31, 38, 35, 255),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (12, 12),
        "Claudeville v2 - licensed Modern Pixels (native 16px)",
        fill=(236, 226, 195, 255),
        font=font,
    )
    for index, (label, image) in enumerate(cards):
        x = (index % columns) * card_width
        y = header + (index // columns) * card_height
        draw.rectangle(
            (x + 4, y + 4, x + card_width - 5, y + card_height - 5),
            fill=(57, 66, 59, 255),
            outline=(144, 132, 102, 255),
        )
        px = x + (card_width - image.width) // 2
        py = y + 12 + (88 - image.height) // 2
        sheet.alpha_composite(image, (px, py))
        draw.text(
            (x + 8, y + 106),
            label[:27],
            fill=(238, 237, 223, 255),
            font=font,
        )
    curation._write_png(output / "contact_sheet.png", sheet)
