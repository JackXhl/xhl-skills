"""Compose a WeChat Search promo card from a real mini-program code.

The QR image is pasted, never redrawn. The search keyword must be passed in.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MARK_PATH = Path(__file__).resolve().parents[1] / "assets" / "search-mark.png"

SCALE = 2
BG = (247, 247, 247, 255)
GREEN = (7, 193, 96, 255)
INK = (60, 60, 60, 255)
WHITE = (255, 255, 255, 255)
CARD_H = 377 * SCALE
RIGHT_MARGIN = 58 * SCALE
MAX_KEYWORD = 12


def find_font(explicit: str | None) -> str:
    if explicit:
        if not os.path.isfile(explicit):
            raise FileNotFoundError(f"font not found: {explicit}")
        return explicit
    env = os.environ.get("WECHAT_SEARCH_FONT", "").strip()
    if env:
        if not os.path.isfile(env):
            raise FileNotFoundError(f"WECHAT_SEARCH_FONT not found: {env}")
        return env
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = [
        os.path.join(windir, "Fonts", "msyhbd.ttc"),
        os.path.join(windir, "Fonts", "msyh.ttc"),
        os.path.join(windir, "Fonts", "simhei.ttf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "no CJK font found. Pass --font, or set WECHAT_SEARCH_FONT to a .otf/.ttc/.ttf file."
    )


def load_mark() -> Image.Image:
    if not MARK_PATH.is_file():
        raise FileNotFoundError(f"search mark missing: {MARK_PATH}")
    with Image.open(MARK_PATH) as im:
        return im.convert("RGBA")


def _near_white(pixel: tuple) -> bool:
    r, g, b = pixel[:3]
    return r > 220 and g > 220 and b > 220


def _outside_circle_is_blank(src: Image.Image) -> bool:
    """Corner wedges of a circular mini-program code are blank. A square code has modules there.

    Ignore the thin ring just outside the circle so antialiased rays are not treated as a square code.
    """
    w, h = src.size
    cx, cy = (w - 1) / 2, (h - 1) / 2
    radius = min(cx, cy)
    step = max(1, min(w, h) // 48)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if math.hypot(x - cx, y - cy) <= radius * 1.08:
                continue
            pixel = src.getpixel((x, y))
            if len(pixel) > 3 and pixel[3] < 20:
                continue
            if not _near_white(pixel):
                return False
    return True


def prepare_qr(path: str, size: int) -> Image.Image:
    with Image.open(path) as im:
        src = im.convert("RGBA")
    src = src.resize((size, size), Image.Resampling.LANCZOS)
    if not _outside_circle_is_blank(src):
        return src
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    src.putalpha(mask)
    return src


def safe_filename(keyword: str) -> str:
    banned = '\\/:*?"<>|\n\r\t'
    cleaned = "".join(ch for ch in keyword.strip() if ch not in banned)
    return cleaned or "search"


def render(qr_path: str, keyword: str, font_path: str) -> Image.Image:
    title_font = ImageFont.truetype(font_path, 80 * SCALE)
    btn_font = ImageFont.truetype(font_path, 58 * SCALE)

    logo_h = 108 * SCALE
    mark = load_mark()
    logo = mark.resize(
        (max(1, int(logo_h * mark.width / mark.height)), logo_h),
        Image.Resampling.LANCZOS,
    )
    lx = 423 * SCALE
    ly = int(110.5 * SCALE - logo.height / 2)

    title = "微信搜一搜"
    title_x = lx + logo.width + 29 * SCALE
    tb = title_font.getbbox(title)
    title_right = title_x + (tb[2] - tb[0])

    kb = btn_font.getbbox(keyword)
    kw = kb[2] - kb[0]
    btn_h = 115 * SCALE
    icon_r = 22 * SCALE
    stroke = 7 * SCALE
    pad_l = 34 * SCALE
    gap = 20 * SCALE
    pad_r = 40 * SCALE
    icon_span = int(icon_r * 2 + 18 * SCALE)
    btn_x = lx
    btn_w = pad_l + icon_span + gap + kw + pad_r
    btn_y = 205 * SCALE

    content_right = max(title_right, btn_x + btn_w)
    width = max(1024 * SCALE, int(math.ceil(content_right + RIGHT_MARGIN)))

    canvas = Image.new("RGBA", (width, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([0, 0, width - 1, CARD_H - 1], radius=20 * SCALE, fill=BG)

    qr = prepare_qr(qr_path, 317 * SCALE)
    canvas.paste(qr, (30 * SCALE, 30 * SCALE), qr)
    canvas.paste(logo, (lx, ly), logo)

    draw.text((title_x, ly + logo.height / 2), title, font=title_font, fill=INK, anchor="lm")
    draw.rounded_rectangle(
        [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
        radius=btn_h // 2,
        fill=GREEN,
    )

    icon_cx = btn_x + pad_l + icon_r + 2 * SCALE
    icon_cy = btn_y + btn_h / 2 - 2 * SCALE
    draw.ellipse(
        [icon_cx - icon_r, icon_cy - icon_r, icon_cx + icon_r, icon_cy + icon_r],
        outline=WHITE,
        width=stroke,
    )
    ang = math.radians(48)
    x1 = icon_cx + math.cos(ang) * (icon_r * 0.72)
    y1 = icon_cy + math.sin(ang) * (icon_r * 0.72)
    x2 = icon_cx + math.cos(ang) * (icon_r + 16 * SCALE)
    y2 = icon_cy + math.sin(ang) * (icon_r + 16 * SCALE)
    draw.line([(x1, y1), (x2, y2)], fill=WHITE, width=stroke)
    cap = stroke / 2
    draw.ellipse([x2 - cap, y2 - cap, x2 + cap, y2 + cap], fill=WHITE)

    text_x = btn_x + pad_l + icon_span + gap
    draw.text((text_x, btn_y + btn_h / 2 + SCALE), keyword, font=btn_font, fill=WHITE, anchor="lm")
    return canvas


def default_out(qr_path: str, keyword: str) -> str:
    folder = os.path.dirname(os.path.abspath(qr_path)) or os.getcwd()
    return os.path.join(folder, f"微信搜一搜-{safe_filename(keyword)}.png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a WeChat Search promo card.")
    parser.add_argument("--qr", required=True, help="Mini-program code image. Pixels are pasted, not redrawn.")
    parser.add_argument("--keyword", required=True, help="Search chip text. Do not guess this.")
    parser.add_argument("--out", help="Output PNG. Defaults to beside the QR image.")
    parser.add_argument("--font", help="CJK font file. Defaults to a system bold face.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    parser.add_argument(
        "--allow-long",
        action="store_true",
        help=f"Allow a keyword longer than {MAX_KEYWORD} characters.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    keyword = args.keyword.strip()
    if not keyword:
        print("keyword is empty. Ask for the search words; do not invent them.", file=sys.stderr)
        return 2
    if any(ch in keyword for ch in "\n\r\t"):
        print("keyword must be one line.", file=sys.stderr)
        return 2
    if len(keyword) > MAX_KEYWORD and not args.allow_long:
        print(
            f"keyword is {len(keyword)} characters (limit {MAX_KEYWORD}). "
            "Confirm with the user, then pass --allow-long.",
            file=sys.stderr,
        )
        return 2
    if not os.path.isfile(args.qr):
        print(f"qr not found: {args.qr}", file=sys.stderr)
        return 2
    out = args.out or default_out(args.qr, keyword)
    if os.path.exists(out) and not args.force:
        print(f"output exists: {out}. Confirm overwrite, then pass --force.", file=sys.stderr)
        return 3
    try:
        font_path = find_font(args.font)
        image = render(args.qr, keyword, font_path)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"could not read image: {exc}", file=sys.stderr)
        return 2
    parent = os.path.dirname(os.path.abspath(out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    image.save(out)
    print(f"wrote {out} {image.size[0]}x{image.size[1]} font={font_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
